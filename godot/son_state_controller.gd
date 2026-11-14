# son_state_controller.gd — Visual State Controller for SON Floating Mini Assistant
class_name SonStateController
extends RefCounted

signal state_changed(old_state: int, new_state: int, state_name: String)
signal visual_updated(primary_color: Color, rim_color: Color, energy: float, waveform: PackedFloat32Array)

enum State {
    IDLE = 0,
    LISTENING = 1,
    THINKING = 2,
    SPEAKING = 3,
    EXECUTING = 4,
    VISION = 5,
    WARNING = 6,
    ERROR = 7
}

const STATE_NAMES = [
    "IDLE",
    "LISTENING",
    "THINKING",
    "SPEAKING",
    "EXECUTING",
    "VISION",
    "WARNING",
    "ERROR"
]

# Color profiles for each state
const STATE_COLORS = {
    State.IDLE: {
        "primary": Color("#00E5FF"),      # Cyan
        "rim": Color("#38BDF8"),          # Sky Blue
        "glow": Color(0.0, 0.898, 1.0, 0.35),
        "freq": 0.8,
        "base_energy": 0.85
    },
    State.LISTENING: {
        "primary": Color("#06B6D4"),      # Teal / Cyan
        "rim": Color("#22D3EE"),          # Bright Cyan
        "glow": Color(0.02, 0.71, 0.83, 0.65),
        "freq": 2.2,
        "base_energy": 1.3
    },
    State.THINKING: {
        "primary": Color("#A855F7"),      # Purple
        "rim": Color("#EC4899"),          # Pink / Magenta
        "glow": Color(0.66, 0.33, 0.97, 0.55),
        "freq": 3.0,
        "base_energy": 1.2
    },
    State.SPEAKING: {
        "primary": Color("#38BDF8"),      # Electric Blue
        "rim": Color("#00E5FF"),          # Neon Cyan
        "glow": Color(0.22, 0.74, 0.97, 0.60),
        "freq": 2.6,
        "base_energy": 1.4
    },
    State.EXECUTING: {
        "primary": Color("#F59E0B"),      # Amber Gold
        "rim": Color("#10B981"),          # Emerald Green
        "glow": Color(0.96, 0.62, 0.04, 0.60),
        "freq": 4.0,
        "base_energy": 1.35
    },
    State.VISION: {
        "primary": Color("#10B981"),      # Emerald Green
        "rim": Color("#34D399"),          # Bright Mint
        "glow": Color(0.06, 0.73, 0.51, 0.60),
        "freq": 1.8,
        "base_energy": 1.2
    },
    State.WARNING: {
        "primary": Color("#F97316"),      # Orange
        "rim": Color("#FBBF24"),          # Warm Amber
        "glow": Color(0.98, 0.45, 0.09, 0.70),
        "freq": 2.0,
        "base_energy": 1.5
    },
    State.ERROR: {
        "primary": Color("#EF4444"),      # Crimson Red
        "rim": Color("#F87171"),          # Light Red
        "glow": Color(0.94, 0.27, 0.27, 0.80),
        "freq": 5.0,
        "base_energy": 1.6
    }
}

var current_state: int = State.IDLE
var target_state: int = State.IDLE

# Interpolated visual parameters
var current_primary_color: Color = Color("#00E5FF")
var current_rim_color: Color = Color("#38BDF8")
var current_glow_color: Color = Color(0.0, 0.898, 1.0, 0.35)
var current_energy: float = 0.85
var current_freq: float = 0.8

# Audio reactive properties
var target_audio_amplitude: float = 0.0
var smoothed_audio_amplitude: float = 0.0

# Dynamic 16-bar waveform array for audio visualization
var waveform_bars: PackedFloat32Array = PackedFloat32Array()
var _phase: float = 0.0

func _init() -> void:
    waveform_bars.resize(16)
    for i in range(16):
        waveform_bars[i] = 0.1

func set_state(new_state: int, meta: Dictionary = {}) -> void:
    if new_state == current_state and target_state == new_state:
        return

    var old_state = current_state
    target_state = new_state
    current_state = new_state

    var s_name = get_state_name()
    state_changed.emit(old_state, new_state, s_name)

func set_state_by_name(state_name: String, meta: Dictionary = {}) -> void:
    var upper = state_name.to_upper().strip_edges()
    for idx in range(STATE_NAMES.size()):
        if STATE_NAMES[idx] == upper:
            set_state(idx, meta)
            return

    # Fallback mappings for event types
    match upper:
        "SON_READY":
            set_state(State.IDLE, meta)
        "TOOL_STARTED":
            set_state(State.EXECUTING, meta)
        "TOOL_COMPLETED":
            set_state(State.IDLE, meta)
        "TRANSCRIPTION":
            set_state(State.LISTENING, meta)
        "VISION_ACTIVE":
            set_state(State.VISION, meta)
        _:
            set_state(State.IDLE, meta)

func set_audio_amplitude(amplitude: float) -> void:
    target_audio_amplitude = clamp(amplitude, 0.0, 1.0)

func get_state_name() -> String:
    if current_state >= 0 and current_state < STATE_NAMES.size():
        return STATE_NAMES[current_state]
    return "UNKNOWN"

func get_primary_color() -> Color:
    return current_primary_color

func get_rim_color() -> Color:
    return current_rim_color

func get_glow_color() -> Color:
    return current_glow_color

func update(delta: float) -> void:
    _phase += delta * current_freq * TAU

    # 1. Smoothly interpolate colors and base energy
    var target_cfg = STATE_COLORS.get(current_state, STATE_COLORS[State.IDLE])
    var blend_speed = 7.0 * delta

    current_primary_color = current_primary_color.lerp(target_cfg["primary"], blend_speed)
    current_rim_color = current_rim_color.lerp(target_cfg["rim"], blend_speed)
    current_glow_color = current_glow_color.lerp(target_cfg["glow"], blend_speed)
    current_freq = lerp(current_freq, float(target_cfg["freq"]), blend_speed)

    # 2. Audio smoothing
    smoothed_audio_amplitude = lerp(smoothed_audio_amplitude, target_audio_amplitude, 15.0 * delta)

    # 3. Dynamic energy oscillation (breathing / pulsing)
    var pulse = sin(_phase) * 0.15 + 0.85
    var audio_boost = smoothed_audio_amplitude * 0.8
    current_energy = (target_cfg["base_energy"] * pulse) + audio_boost

    # 4. Synthesize 16-bar waveform visualization
    for i in range(16):
        var freq_factor = float(i + 1) * 0.4
        var bar_wave = sin(_phase * freq_factor + float(i) * 0.5) * 0.5 + 0.5
        var target_val = 0.08

        match current_state:
            State.LISTENING:
                target_val = 0.15 + (bar_wave * 0.5 * max(0.3, smoothed_audio_amplitude))
            State.SPEAKING:
                target_val = 0.2 + (bar_wave * 0.7 * max(0.4, smoothed_audio_amplitude))
            State.THINKING:
                target_val = 0.2 + (sin(_phase * 2.0 + float(i) * 0.8) * 0.35 + 0.35)
            State.EXECUTING:
                # Sequential spinning wave
                target_val = 0.2 + (sin(_phase * 3.0 - float(i) * 0.4) * 0.4 + 0.4)
            State.VISION:
                # Scanning line peak
                var scan_pos = fmod(_phase * 0.5, 16.0)
                var dist_to_scan = abs(float(i) - scan_pos)
                target_val = 0.15 + clamp(1.0 - (dist_to_scan * 0.3), 0.0, 0.8)
            State.WARNING, State.ERROR:
                target_val = 0.2 + (pulse * 0.6)
            _:
                # Idle gentle ambient wave
                target_val = 0.1 + (sin(_phase * 0.5 + float(i) * 0.2) * 0.08)

        waveform_bars[i] = lerp(waveform_bars[i], target_val, 12.0 * delta)

    visual_updated.emit(current_primary_color, current_rim_color, current_energy, waveform_bars)
