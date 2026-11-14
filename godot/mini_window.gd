# mini_window.gd — Main Controller for SON Liquid Glass Floating Mini Assistant
extends Control

const SonStateController = preload("res://son_state_controller.gd")
const SonWebSocketClient = preload("res://websocket_client.gd")
const NativeWindowBridgeGD = preload("res://native_window_bridge.gd")
const MiniWindowSettings = preload("res://mini_window_settings.gd")

# ── Window Size Configurations ─────────────────────────────────────────
const COMPACT_SIZE = Vector2i(280, 80)
const EXPANDED_SIZE = Vector2i(380, 530)

enum WindowMode { COMPACT, EXPANDED }
var current_mode: int = WindowMode.COMPACT

# Subsystems
var state_controller: SonStateController
var ws_client: SonWebSocketClient
var native_bridge: NativeWindowBridgeGD
var settings: MiniWindowSettings

# Drag state
var _is_dragging: bool = false
var _drag_start_mouse: Vector2i = Vector2i.ZERO
var _drag_start_window: Vector2i = Vector2i.ZERO

# Animation and visual properties
var _tween: Tween
var _current_window_size: Vector2 = Vector2(COMPACT_SIZE)
var _is_settings_open: bool = false
var _is_mic_active: bool = false
var _pending_approval_id: String = ""

# Telemetry data
var _cpu_percent: float = 0.0
var _gpu_percent: float = 0.0
var _vram_percent: float = 0.0
var _active_model: String = "llama3.2:latest"

# Node references
@onready var glass_panel: ColorRect = $GlassPanel
@onready var compact_container: MarginContainer = $CompactContainer
@onready var expanded_container: MarginContainer = $ExpandedContainer
@onready var settings_panel: PanelContainer = $SettingsPanel
@onready var orb_canvas: Control = $OrbCanvas

# Compact controls
@onready var compact_state_label: Label = $CompactContainer/HBox/InfoBox/StateLabel
@onready var compact_status_dot: ColorRect = $CompactContainer/HBox/InfoBox/TopRow/StatusDot
@onready var compact_transcript_label: Label = $CompactContainer/HBox/InfoBox/TranscriptLabel

# Expanded controls
@onready var exp_state_chip: Label = $ExpandedContainer/VBox/HeaderBar/StateChip
@onready var exp_cpu_label: Label = $ExpandedContainer/VBox/TelemetryBar/CpuChip/Label
@onready var exp_gpu_label: Label = $ExpandedContainer/VBox/TelemetryBar/GpuChip/Label
@onready var exp_vram_label: Label = $ExpandedContainer/VBox/TelemetryBar/VramChip/Label
@onready var exp_model_label: Label = $ExpandedContainer/VBox/TelemetryBar/ModelChip/Label
@onready var exp_transcript_box: RichTextLabel = $ExpandedContainer/VBox/ChatScroll/TranscriptText
@onready var exp_activity_banner: PanelContainer = $ExpandedContainer/VBox/ActivityBanner
@onready var exp_activity_label: Label = $ExpandedContainer/VBox/ActivityBanner/HBox/Label
@onready var exp_input_edit: LineEdit = $ExpandedContainer/VBox/InputBar/LineEdit
@onready var exp_mic_btn: Button = $ExpandedContainer/VBox/InputBar/MicButton
@onready var exp_pin_btn: Button = $ExpandedContainer/VBox/HeaderBar/PinButton

# Settings controls
@onready var style_option: OptionButton = $SettingsPanel/VBox/StyleOption
@onready var opacity_slider: HSlider = $SettingsPanel/VBox/OpacitySlider
@onready var anim_slider: HSlider = $SettingsPanel/VBox/AnimSlider
@onready var low_power_check: CheckBox = $SettingsPanel/VBox/LowPowerCheck
@onready var topmost_check: CheckBox = $SettingsPanel/VBox/TopmostCheck

func _ready() -> void:
    # 1. Initialize subsystems
    settings = MiniWindowSettings.new()
    state_controller = SonStateController.new()
    ws_client = SonWebSocketClient.new()
    native_bridge = NativeWindowBridgeGD.new()

    # 2. Configure window native properties
    _setup_native_window()

    # 3. Connect signals
    _connect_subsystem_signals()

    # 4. Apply initial settings & layout
    _apply_settings_to_ui()
    _set_mode(WindowMode.COMPACT, false)
    _position_window_on_startup()

    # 5. Start WebSocket client
    ws_client.connect_to_server(settings.server_url, settings.auth_token)

    # 6. Ensure input focus & custom rendering hooks
    orb_canvas.draw.connect(_on_orb_draw)

func _setup_native_window() -> void:
    # Bind HWND and configure frameless, transparent, rounded glass
    native_bridge.bind_window(0)
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true)
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, settings.always_on_top)
    get_tree().root.transparent_bg = true

func _connect_subsystem_signals() -> void:
    # State controller signals
    state_controller.state_changed.connect(_on_son_state_changed)
    state_controller.visual_updated.connect(_on_son_visual_updated)

    # WebSocket telemetry & chat signals
    ws_client.connected.connect(_on_ws_connected)
    ws_client.disconnected.connect(_on_ws_disconnected)
    ws_client.event_received.connect(_on_ws_event_received)
    ws_client.transcript_updated.connect(_on_ws_transcript_updated)
    ws_client.assistant_replied.connect(_on_ws_assistant_replied)
    ws_client.telemetry_updated.connect(_on_ws_telemetry_updated)
    ws_client.approval_requested.connect(_on_ws_approval_requested)

    # UI Interactive signals
    exp_input_edit.text_submitted.connect(_on_chat_submitted)

func _process(delta: float) -> void:
    # Poll subsystems
    ws_client.poll(delta)
    state_controller.update(delta)

    # Update shader mouse tracking
    if glass_panel and glass_panel.material is ShaderMaterial:
        var local_mouse = get_local_mouse_position()
        var norm_mouse = Vector2(
            clamp(local_mouse.x / max(size.x, 1.0), 0.0, 1.0),
            clamp(local_mouse.y / max(size.y, 1.0), 0.0, 1.0)
        )
        (glass_panel.material as ShaderMaterial).set_shader_parameter("mouse_position", norm_mouse)

    # Redraw animated holographic orb
    orb_canvas.queue_redraw()

func _input(event: InputEvent) -> void:
    # ── Window Dragging ───────────────────────────────────────────────
    if event is InputEventMouseButton:
        if event.button_index == MOUSE_BUTTON_LEFT:
            if event.pressed:
                # Initiate drag if click was outside interactive inputs
                if not _is_interactive_control(get_viewport().gui_get_focus_owner()):
                    _is_dragging = true
                    _drag_start_mouse = DisplayServer.mouse_get_position()
                    _drag_start_window = DisplayServer.window_get_position()
            else:
                _is_dragging = false

    elif event is InputEventMouseMotion and _is_dragging:
        var current_mouse = DisplayServer.mouse_get_position()
        DisplayServer.window_set_position(_drag_start_window + (current_mouse - _drag_start_mouse))

    # ── Keyboard Shortcuts ────────────────────────────────────────────
    elif event is InputEventKey and event.pressed:
        if event.keycode == KEY_ESCAPE:
            if _is_settings_open:
                _toggle_settings(false)
            elif current_mode == WindowMode.EXPANDED:
                _set_mode(WindowMode.COMPACT)
            else:
                # Minimize / Hide
                DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_MINIMIZED)

        elif event.ctrl_pressed and event.keycode == KEY_E:
            _toggle_mode()

        elif event.ctrl_pressed and event.keycode == KEY_M:
            _toggle_mic()

func _is_interactive_control(node: Node) -> bool:
    return node is LineEdit or node is TextEdit or node is Button or node is Slider or node is OptionButton

# ── Window Mode Transitions (Compact <-> Expanded) ─────────────────────
func _toggle_mode() -> void:
    if current_mode == WindowMode.COMPACT:
        _set_mode(WindowMode.EXPANDED)
    else:
        _set_mode(WindowMode.COMPACT)

func _set_mode(target_mode: int, animated: bool = true) -> void:
    current_mode = target_mode
    var target_size = EXPANDED_SIZE if target_mode == WindowMode.EXPANDED else COMPACT_SIZE

    if _tween and _tween.is_valid():
        _tween.kill()

    if not animated:
        custom_minimum_size = target_size
        DisplayServer.window_set_size(target_size)
        compact_container.visible = (target_mode == WindowMode.COMPACT)
        expanded_container.visible = (target_mode == WindowMode.EXPANDED)
        _update_orb_layout()
        return

    _tween = create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)

    # Animate window geometry
    _tween.tween_method(
        func(s: Vector2):
            custom_minimum_size = s
            DisplayServer.window_set_size(Vector2i(int(s.x), int(s.y))),
        Vector2(DisplayServer.window_get_size()),
        Vector2(target_size),
        0.32
    )

    if target_mode == WindowMode.EXPANDED:
        compact_container.modulate.a = 0.0
        compact_container.visible = false
        expanded_container.visible = true
        expanded_container.modulate.a = 0.0
        _tween.tween_property(expanded_container, "modulate:a", 1.0, 0.25).set_delay(0.08)
    else:
        expanded_container.modulate.a = 0.0
        expanded_container.visible = false
        compact_container.visible = true
        compact_container.modulate.a = 0.0
        _tween.tween_property(compact_container, "modulate:a", 1.0, 0.25).set_delay(0.08)

    _update_orb_layout()

func _update_orb_layout() -> void:
    if current_mode == WindowMode.COMPACT:
        orb_canvas.position = Vector2(14, 14)
        orb_canvas.size = Vector2(52, 52)
    else:
        orb_canvas.position = Vector2(size.x * 0.5 - 40, 52)
        orb_canvas.size = Vector2(80, 80)

# ── Dynamic Orb & Waveform Drawing ─────────────────────────────────────
func _on_orb_draw() -> void:
    var center = orb_canvas.size * 0.5
    var radius = min(orb_canvas.size.x, orb_canvas.size.y) * 0.44

    var primary = state_controller.get_primary_color()
    var rim = state_controller.get_rim_color()
    var energy = state_controller.current_energy

    # 1. Outer ambient glow ring
    var glow_col = Color(primary.r, primary.g, primary.b, 0.15 * energy)
    orb_canvas.draw_circle(center, radius * 1.35, glow_col)

    # 2. Main holographic sphere gradient
    var sphere_col = Color(primary.r * 0.7, primary.g * 0.7, primary.b * 0.8, 0.85)
    orb_canvas.draw_circle(center, radius, sphere_col)

    # 3. Rotating cybernetic orbital ring
    var time_sec = Time.get_ticks_msec() / 1000.0
    var ring_pts = PackedVector2Array()
    var segments = 32
    for i in range(segments + 1):
        var ang = (float(i) / float(segments)) * TAU + (time_sec * 1.8)
        var rx = cos(ang) * (radius * 1.15)
        var ry = sin(ang) * (radius * 0.5) # Elliptical orbit
        ring_pts.append(center + Vector2(rx, ry))

    orb_canvas.draw_polyline(ring_pts, Color(rim.r, rim.g, rim.b, 0.7), 1.4, true)

    # 4. Central specular hot spot
    var spot_offset = Vector2(-radius * 0.28, -radius * 0.28)
    orb_canvas.draw_circle(center + spot_offset, radius * 0.32, Color(1.0, 1.0, 1.0, 0.55 * energy))

    # 5. Audio waveform ripples (if in Speaking or Listening mode)
    if current_mode == WindowMode.EXPANDED:
        var bars = state_controller.waveform_bars
        var bar_w = 4.0
        var spacing = 6.0
        var total_w = bars.size() * spacing
        var start_x = center.x - (total_w * 0.5)
        var base_y = orb_canvas.size.y + 12.0

        for b in range(bars.size()):
            var bar_h = bars[b] * 32.0 * energy
            var x = start_x + (b * spacing)
            var bar_col = rim.lerp(Color.WHITE, 0.3)
            orb_canvas.draw_line(
                Vector2(x, base_y - bar_h),
                Vector2(x, base_y + bar_h),
                bar_col,
                bar_w,
                true
            )

# ── State Controller Events ────────────────────────────────────────────
func _on_son_state_changed(old_state: int, new_state: int, s_name: String) -> void:
    compact_state_label.text = s_name
    exp_state_chip.text = s_name

    var col = state_controller.get_primary_color()
    exp_state_chip.modulate = col
    compact_state_label.modulate = col

func _on_son_visual_updated(prim: Color, rim: Color, energy: float, waveform: PackedFloat32Array) -> void:
    if glass_panel and glass_panel.material is ShaderMaterial:
        var sm = glass_panel.material as ShaderMaterial
        sm.set_shader_parameter("state_glow_color", state_controller.get_glow_color())
        sm.set_shader_parameter("rim_color", rim)
        sm.set_shader_parameter("state_energy", energy)

# ── WebSocket Events ───────────────────────────────────────────────────
func _on_ws_connected() -> void:
    compact_status_dot.color = Color("#10B981") # Green
    compact_transcript_label.text = "Connected to SON Backend"
    _append_chat_message("system", "Connected to SON V3 Core Engine.")

func _on_ws_disconnected() -> void:
    compact_status_dot.color = Color("#EF4444") # Red
    compact_transcript_label.text = "Offline - Reconnecting..."
    _append_chat_message("system", "Disconnected from backend. Retrying in background...")

func _on_ws_event_received(ev_type: String, payload: Dictionary, ts: float) -> void:
    state_controller.set_state_by_name(ev_type, payload)

    match ev_type:
        "tool_started":
            var tool_name = str(payload.get("tool_name", "Executing tool..."))
            _show_activity_banner("Running: " + tool_name, true)

        "tool_completed":
            var tool_name = str(payload.get("tool_name", "Tool"))
            var success = bool(payload.get("success", true))
            _show_activity_banner(tool_name + (": Succeeded" if success else ": Failed"), false)

        "speaking":
            var text = str(payload.get("text", ""))
            if text:
                compact_transcript_label.text = text

        "listening":
            var energy = float(payload.get("audio_energy", 0.5))
            state_controller.set_audio_amplitude(energy)

func _on_ws_transcript_updated(text: String, is_final: bool) -> void:
    compact_transcript_label.text = text
    if is_final and text.strip_edges():
        _append_chat_message("user", text)

func _on_ws_assistant_replied(text: String, tool_results: Array) -> void:
    _append_chat_message("assistant", text)
    state_controller.set_state(SonStateController.State.IDLE)
    _show_activity_banner("", false)

func _on_ws_telemetry_updated(cpu: float, ram_pct: float, gpu: float, vram_pct: float, model: String) -> void:
    _cpu_percent = cpu
    _gpu_percent = gpu
    _vram_percent = vram_pct
    _active_model = model

    exp_cpu_label.text = "CPU: %d%%" % int(cpu)
    exp_gpu_label.text = "GPU: %d%%" % int(gpu)
    exp_vram_label.text = "VRAM: %d%%" % int(vram_pct)
    exp_model_label.text = model

func _on_ws_approval_requested(approval_data: Dictionary) -> void:
    _pending_approval_id = str(approval_data.get("request_id", ""))
    var tool = str(approval_data.get("tool_name", "Privileged Action"))
    var reason = str(approval_data.get("reason", "Confirmation required"))
    _show_activity_banner("Approval Required: " + tool + " (" + reason + ")", true)
    state_controller.set_state(SonStateController.State.WARNING)

# ── Chat & Interactive Inputs ──────────────────────────────────────────
func _on_chat_submitted(text: String) -> void:
    var prompt = text.strip_edges()
    if not prompt:
        return

    exp_input_edit.text = ""
    _append_chat_message("user", prompt)
    state_controller.set_state(SonStateController.State.THINKING)
    ws_client.send_chat(prompt)

func _append_chat_message(sender: String, message: String) -> void:
    var col_tag = "#00E5FF" if sender == "assistant" else ("#E2E8F0" if sender == "user" else "#94A3B8")
    var prefix = "[b]SON:[/b] " if sender == "assistant" else ("[b]You:[/b] " if sender == "user" else "[i]System:[/i] ")
    exp_transcript_box.append_text("[color=" + col_tag + "]" + prefix + message + "[/color]\n\n")

func _show_activity_banner(text: String, is_active: bool) -> void:
    exp_activity_banner.visible = is_active or text.length() > 0
    exp_activity_label.text = text

func _toggle_mic() -> void:
    _is_mic_active = not _is_mic_active
    exp_mic_btn.modulate = Color("#EF4444") if _is_mic_active else Color.WHITE
    if _is_mic_active:
        state_controller.set_state(SonStateController.State.LISTENING)
    else:
        state_controller.set_state(SonStateController.State.IDLE)

# ── Quick Action Triggers ──────────────────────────────────────────────
func _on_quick_scan_screen_pressed() -> void:
    state_controller.set_state(SonStateController.State.VISION)
    ws_client.request_vision_analysis("Scan screen and summarize current active work.")

func _on_quick_check_hardware_pressed() -> void:
    ws_client.request_telemetry()
    _append_chat_message("system", "Telemetry updated: CPU %d%%, GPU %d%%, VRAM %d%%." % [int(_cpu_percent), int(_gpu_percent), int(_vram_percent)])

func _on_quick_open_vscode_pressed() -> void:
    _on_chat_submitted("Open VS Code")

func _on_quick_leave_letter_pressed() -> void:
    _on_chat_submitted("Open Microsoft Office Word and write a 3-day leave letter.")

# ── Settings & Window Position ─────────────────────────────────────────
func _toggle_settings(show: bool) -> void:
    _is_settings_open = show
    settings_panel.visible = show

func _apply_settings_to_ui() -> void:
    if glass_panel and glass_panel.material is ShaderMaterial:
        var sm = glass_panel.material as ShaderMaterial
        sm.set_shader_parameter("low_power_mode", settings.low_power_mode)
        sm.set_shader_parameter("solid_mode", settings.visual_style == "solid")
        sm.set_shader_parameter("tint_color", Color(0.047, 0.078, 0.141, settings.transparency))

    native_bridge.set_always_on_top(settings.always_on_top)

func _position_window_on_startup() -> void:
    var screen_idx = DisplayServer.window_get_current_screen()
    var usable = DisplayServer.screen_get_usable_rect(screen_idx)

    var target_pos = Vector2i.ZERO
    match settings.startup_position:
        "bottom_right":
            target_pos = Vector2i(
                usable.position.x + usable.size.x - COMPACT_SIZE.x - 24,
                usable.position.y + usable.size.y - COMPACT_SIZE.y - 48
            )
        "top_right":
            target_pos = Vector2i(
                usable.position.x + usable.size.x - COMPACT_SIZE.x - 24,
                usable.position.y + 40
            )
        "center":
            target_pos = Vector2i(
                usable.position.x + (usable.size.x - COMPACT_SIZE.x) / 2,
                usable.position.y + (usable.size.y - COMPACT_SIZE.y) / 2
            )
        _:
            target_pos = settings.custom_pos

    DisplayServer.window_set_position(target_pos)

# ── Button Click Bindings ──────────────────────────────────────────────
func _on_expand_button_pressed() -> void:
    _set_mode(WindowMode.EXPANDED)

func _on_collapse_button_pressed() -> void:
    _set_mode(WindowMode.COMPACT)

func _on_close_button_pressed() -> void:
    _set_mode(WindowMode.COMPACT)

func _on_settings_button_pressed() -> void:
    _toggle_settings(not _is_settings_open)

func _on_pin_button_pressed() -> void:
    settings.always_on_top = not settings.always_on_top
    native_bridge.set_always_on_top(settings.always_on_top)
    exp_pin_btn.modulate = Color("#00E5FF") if settings.always_on_top else Color("#64748B")

func _on_approve_pressed() -> void:
    if _pending_approval_id:
        ws_client.send_approval(_pending_approval_id, true)
        _show_activity_banner("Action Approved", false)
        _pending_approval_id = ""

func _on_deny_pressed() -> void:
    if _pending_approval_id:
        ws_client.send_approval(_pending_approval_id, false)
        _show_activity_banner("Action Denied", false)
        _pending_approval_id = ""
