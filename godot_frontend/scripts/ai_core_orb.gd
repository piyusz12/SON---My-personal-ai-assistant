# ai_core_orb.gd — 3D/2D Holographic AI Core Orb (Godot 4)
extends Node2D

@export var base_radius: float = 120.0
@export var current_state: String = "idle"

# Colors for state morphing
var color_idle: Color = Color(0.0, 0.94, 1.0, 0.9)        # Cyan
var color_listening: Color = Color(0.0, 1.0, 0.67, 0.95)   # Aquamarine
var color_thinking: Color = Color(0.71, 0.27, 1.0, 0.95)   # Purple
var color_speaking: Color = Color(0.0, 0.9, 1.0, 1.0)      # High Energy Cyan
var color_executing: Color = Color(1.0, 0.67, 0.0, 0.95)   # Amber Gold
var color_searching: Color = Color(0.0, 0.75, 1.0, 0.95)   # Sky Blue
var color_vision: Color = Color(0.0, 1.0, 0.78, 0.95)      # Cyber Emerald
var color_warning: Color = Color(1.0, 0.7, 0.0, 1.0)       # Amber
var color_error: Color = Color(1.0, 0.16, 0.27, 1.0)       # Crimson

var target_color: Color = color_idle
var current_color: Color = color_idle

var ring1_rot: float = 0.0
var ring2_rot: float = 0.0
var ring3_rot: float = 0.0
var pulse_phase: float = 0.0
var audio_amp: float = 0.0
var target_audio_amp: float = 0.0
var ring_speed_mult: float = 1.0

var status_label_text: String = "SYSTEM ONLINE"
var wave_bars: Array = []

func _ready() -> void:
	# Connect to SonIPC singleton
	if SonIPC:
		SonIPC.state_changed.connect(_on_state_changed)
		SonIPC.audio_waveform_received.connect(_on_audio_waveform)

	for i in range(32):
		wave_bars.append(0.0)

func _process(delta: float) -> void:
	# Advance physics and rotation
	ring1_rot += delta * 0.8 * ring_speed_mult
	ring2_rot -= delta * 1.2 * ring_speed_mult
	ring3_rot += delta * 0.5 * ring_speed_mult
	pulse_phase += delta * 2.5

	# Smooth color and audio transitions
	current_color = current_color.lerp(target_color, delta * 4.0)
	audio_amp = lerp(audio_amp, target_audio_amp, delta * 8.0)

	# Shift waveform
	wave_bars.pop_front()
	wave_bars.append(audio_amp)

	queue_redraw()

func _on_state_changed(state: String, label: String, intensity: float) -> void:
	current_state = state
	status_label_text = label.to_upper() if label != "" else state.to_upper()

	match state:
		"idle":
			target_color = color_idle
			ring_speed_mult = 1.0
		"listening":
			target_color = color_listening
			ring_speed_mult = 2.0
		"thinking":
			target_color = color_thinking
			ring_speed_mult = 3.5
		"speaking":
			target_color = color_speaking
			ring_speed_mult = 1.8
		"executing":
			target_color = color_executing
			ring_speed_mult = 2.5
		"searching":
			target_color = color_searching
			ring_speed_mult = 3.0
		"vision":
			target_color = color_vision
			ring_speed_mult = 2.0
		"warning":
			target_color = color_warning
			ring_speed_mult = 2.5
		"error":
			target_color = color_error
			ring_speed_mult = 4.0
		"sleep":
			target_color = Color(0.0, 0.4, 0.6, 0.4)
			ring_speed_mult = 0.2

func _on_audio_waveform(amplitude: float, _waveform: Array) -> void:
	target_audio_amp = clamp(amplitude, 0.0, 1.0)

func _draw() -> void:
	var pulse = sin(pulse_phase) * 0.08 + (audio_amp * 0.25)
	var active_radius = base_radius * (1.0 + pulse)

	# 1. Outer Ambient Glow
	draw_circle(Vector2.ZERO, active_radius * 1.35, Color(current_color.r, current_color.g, current_color.b, 0.08))
	draw_circle(Vector2.ZERO, active_radius * 1.15, Color(current_color.r, current_color.g, current_color.b, 0.18))

	# 2. Concentric Gyroscopic Rings (Iron Man / Hologram HUD)
	_draw_gyro_ring(active_radius * 0.95, ring1_rot, 4, current_color, 2.0)
	_draw_dashed_ring(active_radius * 0.78, ring2_rot, 16, current_color * 0.8, 1.5)
	_draw_gyro_ring(active_radius * 0.62, ring3_rot, 2, current_color, 1.2)

	# 3. Audio Waveform Radial Bars
	var num_bars = wave_bars.size()
	for i in range(num_bars):
		var angle = (float(i) / num_bars) * TAU
		var bar_val = wave_bars[i]
		var r_inner = active_radius * 0.65
		var r_outer = r_inner + 4.0 + (bar_val * 32.0)

		var p1 = Vector2(cos(angle), sin(angle)) * r_inner
		var p2 = Vector2(cos(angle), sin(angle)) * r_outer
		var bar_col = Color(1.0, 1.0, 1.0, 0.8) if bar_val > 0.4 else current_color
		draw_line(p1, p2, bar_col, 2.0)

	# 4. Central Plasma Core Sphere
	draw_circle(Vector2.ZERO, active_radius * 0.48, Color(current_color.r, current_color.g, current_color.b, 0.5))
	draw_circle(Vector2.ZERO, active_radius * 0.32, Color(1.0, 1.0, 1.0, 0.85))

	# 5. Core Branding Reticle
	draw_arc(Vector2.ZERO, active_radius * 0.22, 0, TAU, 32, current_color, 1.5)

func _draw_gyro_ring(radius: float, rotation_angle: float, segments: int, col: Color, width: float) -> void:
	var seg_angle = TAU / segments
	var arc_len = seg_angle * 0.7
	for i in range(segments):
		var start_a = rotation_angle + i * seg_angle
		draw_arc(Vector2.ZERO, radius, start_a, start_a + arc_len, 24, col, width)

func _draw_dashed_ring(radius: float, rotation_angle: float, count: int, col: Color, width: float) -> void:
	for i in range(count):
		var a = rotation_angle + (float(i) / count) * TAU
		var p1 = Vector2(cos(a), sin(a)) * (radius - 3.0)
		var p2 = Vector2(cos(a), sin(a)) * (radius + 3.0)
		draw_line(p1, p2, col, width)
