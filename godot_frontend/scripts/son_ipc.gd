# son_ipc.gd — Autoload WebSocket Client for SON Python Backend (Godot 4)
extends Node

signal state_changed(state: String, label: String, intensity: float)
signal audio_waveform_received(amplitude: float, waveform: Array)
signal thought_pipeline_updated(stage: int, step_name: String, description: String)
signal telemetry_updated(cpu: float, gpu: float, vram_gb: float, vram_total: float, ram_gb: float, ram_total: float)
signal perception_updated(camera_active: bool, person_count: int, face_name: String, confidence: float)
signal subtitle_received(speaker: String, text: String)
signal sound_cue_triggered(cue_name: String)

var socket: WebSocketPeer = WebSocketPeer.new()
var ws_url: String = "ws://127.0.0.1:8765"
var is_connected: bool = false
var reconnect_timer: float = 0.0

func _ready() -> void:
	connect_to_backend()

func connect_to_backend() -> void:
	var err = socket.connect_to_url(ws_url)
	if err == OK:
		print("[SON IPC] Connecting to Python backend at ", ws_url)
	else:
		print("[SON IPC] Connection initiation failed: ", err)

func _process(delta: float) -> void:
	socket.poll()
	var state = socket.get_ready_state()

	if state == WebSocketPeer.STATE_OPEN:
		if not is_connected:
			is_connected = true
			print("[SON IPC] Successfully connected to SON Python Backend!")
			emit_signal("state_changed", "idle", "SYSTEM ONLINE", 1.0)

		while socket.get_available_packet_count() > 0:
			var packet = socket.get_packet()
			var text = packet.get_string_from_utf8()
			_handle_message(text)

	elif state == WebSocketPeer.STATE_CLOSED:
		if is_connected:
			is_connected = false
			print("[SON IPC] Disconnected from backend.")
			emit_signal("state_changed", "sleep", "BACKEND OFFLINE", 0.5)

		reconnect_timer += delta
		if reconnect_timer >= 2.0:
			reconnect_timer = 0.0
			connect_to_backend()

func _handle_message(raw_json: String) -> void:
	var json = JSON.new()
	var err = json.parse(raw_json)
	if err != OK:
		return

	var data_dict = json.get_data()
	if typeof(data_dict) != TYPE_DICTIONARY:
		return

	var event = data_dict.get("event", "")
	var data = data_dict.get("data", {})

	match event:
		"state_change":
			emit_signal(
				"state_changed",
				data.get("state", "idle"),
				data.get("label", ""),
				data.get("intensity", 1.0)
			)
		"audio_waveform":
			emit_signal(
				"audio_waveform_received",
				data.get("amplitude", 0.0),
				data.get("waveform", [])
			)
		"thought_pipeline":
			emit_signal(
				"thought_pipeline_updated",
				int(data.get("stage", 0)),
				data.get("step_name", ""),
				data.get("description", "")
			)
		"system_telemetry":
			emit_signal(
				"telemetry_updated",
				float(data.get("cpu", 0.0)),
				float(data.get("gpu", 0.0)),
				float(data.get("vram_gb", 0.0)),
				float(data.get("vram_total", 8.0)),
				float(data.get("ram_gb", 0.0)),
				float(data.get("ram_total", 16.0))
			)
		"perception_update":
			emit_signal(
				"perception_updated",
				bool(data.get("camera_active", true)),
				int(data.get("person_count", 0)),
				str(data.get("face_name", "None")),
				float(data.get("confidence", 0.0))
			)
		"subtitle":
			emit_signal(
				"subtitle_received",
				str(data.get("speaker", "SON")),
				str(data.get("text", ""))
			)
		"sound_cue":
			emit_signal("sound_cue_triggered", str(data.get("cue", "")))

# ── Outbound Commands to Python ──────────────────────────────

func send_user_prompt(prompt_text: String) -> void:
	_send_event("user_prompt", {"text": prompt_text})

func send_voice_trigger() -> void:
	_send_event("voice_trigger", {})

func send_toggle_camera() -> void:
	_send_event("toggle_camera", {})

func _send_event(event_name: String, data: Dictionary) -> void:
	if socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
		var payload = {
			"event": event_name,
			"data": data,
			"timestamp": Time.get_unix_time_from_system()
		}
		socket.send_text(JSON.stringify(payload))
