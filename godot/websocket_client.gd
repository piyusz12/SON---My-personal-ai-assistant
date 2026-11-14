# websocket_client.gd — Asynchronous Authenticated WebSocket Client for SON HUD
class_name SonWebSocketClient
extends RefCounted

signal connected
signal disconnected
signal connection_error(message: String)

# Telemetry and state signals
signal event_received(event_type: String, payload: Dictionary, timestamp: float)
signal response_received(action: String, payload: Dictionary, request_id: String)
signal transcript_updated(text: String, is_final: bool)
signal assistant_replied(text: String, tool_results: Array)
signal telemetry_updated(cpu: float, ram_pct: float, gpu: float, vram_pct: float, model: String)
signal approval_requested(approval_data: Dictionary)

var _ws: WebSocketPeer = WebSocketPeer.new()
var _server_url: String = "ws://127.0.0.1:8765"
var _auth_token: String = ""
var _is_connected: bool = false
var _session_id: String = ""

# Auto reconnect parameters
var auto_reconnect: bool = true
var _reconnect_delay: float = 1.0
var _reconnect_timer: float = 0.0
var _ping_timer: float = 0.0
const PING_INTERVAL: float = 15.0

func _init() -> void:
    _ws.inbound_buffer_size = 1048576 # 1MB buffer
    _ws.outbound_buffer_size = 1048576

func connect_to_server(url: String = "ws://127.0.0.1:8765", token: String = "") -> void:
    _server_url = url
    _auth_token = token
    _reconnect_timer = 0.0
    _reconnect_delay = 1.0

    print("[WebSocket] Initiating connection to ", _server_url)
    var err = _ws.connect_to_url(_server_url)
    if err != OK:
        connection_error.emit("Failed to initiate connection: " + str(err))

func disconnect_from_server() -> void:
    auto_reconnect = false
    if _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _ws.close(1000, "Normal closure")
    _is_connected = false

func is_connected_to_backend() -> bool:
    return _is_connected and _ws.get_ready_state() == WebSocketPeer.STATE_OPEN

func send_json(data: Dictionary) -> bool:
    if not is_connected_to_backend():
        return false

    var json_str = JSON.stringify(data)
    var err = _ws.send_text(json_str)
    return err == OK

func send_chat(prompt: String) -> bool:
    var req_id = "req_" + str(Time.get_ticks_msec())
    return send_json({
        "action": "chat_send",
        "request_id": req_id,
        "payload": {
            "prompt": prompt,
            "session_id": _session_id,
            "user_id": "usr_primary"
        }
    })

func send_approval(approval_id: String, approved: bool) -> bool:
    return send_json({
        "action": "approval_resolve",
        "payload": {
            "approval_id": approval_id,
            "approved": approved,
            "decision_by": "usr_primary"
        }
    })

func request_telemetry() -> bool:
    return send_json({
        "action": "hardware_telemetry",
        "payload": {}
    })

func request_vision_analysis(prompt: String = "Describe what is visible on this screen.") -> bool:
    return send_json({
        "action": "vision_analyze",
        "payload": {
            "prompt": prompt
        }
    })

func poll(delta: float) -> void:
    _ws.poll()
    var state = _ws.get_ready_state()

    match state:
        WebSocketPeer.STATE_OPEN:
            if not _is_connected:
                _is_connected = true
                _reconnect_delay = 1.0
                _send_handshake()
                connected.emit()

            # Heartbeat ping
            _ping_timer += delta
            if _ping_timer >= PING_INTERVAL:
                _ping_timer = 0.0
                send_json({"action": "ping", "payload": {}})

            # Read all available packets
            while _ws.get_available_packet_count() > 0:
                var packet = _ws.get_packet()
                var text = packet.get_string_from_utf8()
                _handle_raw_message(text)

        WebSocketPeer.STATE_CLOSED:
            if _is_connected:
                _is_connected = false
                disconnected.emit()

            if auto_reconnect:
                _reconnect_timer += delta
                if _reconnect_timer >= _reconnect_delay:
                    _reconnect_timer = 0.0
                    _reconnect_delay = min(_reconnect_delay * 1.5, 10.0) # Exponential backoff
                    _ws.connect_to_url(_server_url)

        WebSocketPeer.STATE_CONNECTING:
            pass

func _send_handshake() -> void:
    send_json({
        "action": "handshake",
        "payload": {
            "client_version": "3.0.0",
            "client_type": "godot_mini",
            "requested_user_id": "usr_primary",
            "auth_token": _auth_token
        }
    })

func _handle_raw_message(raw_json: String) -> void:
    var parsed = JSON.parse_string(raw_json)
    if typeof(parsed) != TYPE_DICTIONARY:
        return

    var msg_type = parsed.get("type", "")

    match msg_type:
        "welcome":
            print("[WebSocket] Connected to SON backend: ", parsed.get("client_id"))

        "event":
            _handle_telemetry_event(parsed)

        "response":
            _handle_action_response(parsed)

        _:
            # Direct response or untyped
            if parsed.has("action"):
                _handle_action_response(parsed)

func _handle_telemetry_event(data: Dictionary) -> void:
    var ev_type = str(data.get("event_type", "")).to_lower()
    var payload = data.get("payload", {})
    var ts = float(data.get("timestamp", Time.get_unix_time_from_system()))

    event_received.emit(ev_type, payload, ts)

    match ev_type:
        "transcription":
            var txt = str(payload.get("text", payload.get("transcription", "")))
            var is_final = bool(payload.get("is_final", true))
            transcript_updated.emit(txt, is_final)

        "approval_requested":
            approval_requested.emit(payload)

func _handle_action_response(data: Dictionary) -> void:
    var action = str(data.get("action", ""))
    var payload = data.get("payload", {})
    var req_id = str(data.get("request_id", ""))

    response_received.emit(action, payload, req_id)

    match action:
        "handshake":
            if payload.get("status") == "AUTHENTICATED":
                _session_id = str(payload.get("session_id", ""))
                # Immediately request initial telemetry
                request_telemetry()

        "chat_send":
            var resp_text = str(payload.get("response", ""))
            var tool_results = payload.get("tool_results", [])
            assistant_replied.emit(resp_text, tool_results)

        "hardware_telemetry":
            var cpu = float(payload.get("cpu_percent", 0.0))
            var ram_used = float(payload.get("ram_used_bytes", 0.0))
            var ram_total = max(1.0, float(payload.get("ram_total_bytes", 1.0)))
            var ram_pct = (ram_used / ram_total) * 100.0

            var gpu = float(payload.get("gpu_percent", 0.0))
            var vram_used = float(payload.get("vram_used_bytes", 0.0))
            var vram_total = max(1.0, float(payload.get("vram_total_bytes", 1.0)))
            var vram_pct = (vram_used / vram_total) * 100.0
            var model = str(payload.get("model_name", "llama3.2"))

            telemetry_updated.emit(cpu, ram_pct, gpu, vram_pct, model)
