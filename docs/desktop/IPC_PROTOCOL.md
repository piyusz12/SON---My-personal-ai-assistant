# SON Desktop — Inter-Process Communication (IPC) Protocol Specification

## 1. Transport Layer Specification

SON Desktop uses native **Windows Named Pipes** for high-performance, low-latency, kernel-isolated local communication between the C# WPF frontend and the Python backend service.

| Parameter | Specification |
| :--- | :--- |
| **Pipe Name** | `\\.\pipe\son_desktop_ipc` |
| **Transmission Mode** | Byte Stream (`PIPE_TYPE_BYTE` / `PIPE_READMODE_BYTE`) |
| **Buffer Sizes** | 65,536 bytes (64 KB) input and output buffers |
| **Access Security (ACL)** | Restricted to current user security token (`GENERIC_READ \| GENERIC_WRITE`). Rejects remote network connections (`PIPE_REJECT_REMOTE_CLIENTS`). |
| **Framing Format** | Length-prefixed binary framing: `[4-Byte Big-Endian Int32 Length] + [UTF-8 JSON Payload]` |

---

## 2. Framing & Wire Format

Every message transmitted over the pipe begins with a 4-byte big-endian unsigned integer indicating the length of the following JSON string in bytes:

```
+-----------------------------------+---------------------------------------------------+
| Field                             | Type / Size                                       |
+-----------------------------------+---------------------------------------------------+
| Payload Length (N)                | 4 Bytes (Int32, Big-Endian)                       |
| Payload Body                      | N Bytes (UTF-8 encoded JSON text)                 |
+-----------------------------------+---------------------------------------------------+
```

### Base Message JSON Schema
```json
{
  "protocol_version": "1.0",
  "message_id": "msg_01J9X8B7C6D5E4F3A2B1",
  "request_id": "req_847192847",
  "message_type": "REQUEST | RESPONSE | STREAM_CHUNK | EVENT_PUSH",
  "action": "chat_send | approval_resolve | telemetry_stream | voice_stream",
  "timestamp": 1731198420.123,
  "payload": { ... },
  "error": null
}
```

---

## 3. Core Protocol Operations

### A. Handshake & Session Initialization
Initiated immediately upon pipe connection to establish authenticated identity and session binding.
```json
// Client -> Backend (HANDSHAKE_REQ)
{
  "message_type": "REQUEST",
  "action": "handshake",
  "payload": {
    "client_version": "3.0.0",
    "client_type": "wpf_desktop",
    "requested_user_id": "primary_user"
  }
}

// Backend -> Client (HANDSHAKE_RESP)
{
  "message_type": "RESPONSE",
  "action": "handshake",
  "payload": {
    "status": "AUTHENTICATED",
    "user_id": "primary_user",
    "session_id": "sess_89f41a87e2b3c4d5",
    "server_version": "3.0.0",
    "active_model": "llama3.2:latest",
    "features_enabled": ["pydantic_ai", "faster_whisper", "e2b_sandbox", "audit_logger"]
  }
}
```

### B. Chat Interaction & Token Streaming
Enables character-by-character streaming without UI blocking.
```json
// Client -> Backend (CHAT_SEND)
{
  "message_type": "REQUEST",
  "action": "chat_send",
  "request_id": "req_turn_01",
  "payload": {
    "prompt": "Show me the top 3 docker containers and delete the temp file.",
    "model": "llama3.2:latest",
    "conversation_id": "conv_4918"
  }
}

// Backend -> Client: Streaming Reasoning (THINKING_CHUNK)
{
  "message_type": "STREAM_CHUNK",
  "action": "chat_stream",
  "request_id": "req_turn_01",
  "payload": {
    "phase": "thinking",
    "delta": "Analyzing request. Identifying tools: docker_list_containers, delete_path."
  }
}

// Backend -> Client: Streaming Response (CONTENT_CHUNK)
{
  "message_type": "STREAM_CHUNK",
  "action": "chat_stream",
  "request_id": "req_turn_01",
  "payload": {
    "phase": "content",
    "delta": "Here are your running containers..."
  }
}

// Backend -> Client: Turn Complete (CHAT_COMPLETE)
{
  "message_type": "RESPONSE",
  "action": "chat_send",
  "request_id": "req_turn_01",
  "payload": {
    "status": "SUCCESS",
    "total_tokens": 142,
    "duration_ms": 842.1
  }
}
```

### C. Human-in-the-Loop Approval Protocol
Pushes authorization prompts for HIGH/CRITICAL actions and captures decisions.
```json
// Backend -> Client (APPROVAL_PROMPT_PUSH)
{
  "message_type": "EVENT_PUSH",
  "action": "approval_required",
  "payload": {
    "approval_id": "appr_77a98b1c",
    "tool_name": "delete_path",
    "risk_level": "HIGH",
    "arguments": { "path": "C:\\temp\\junk.txt" },
    "justification": "Permanent file deletion requested by user.",
    "expires_at": 1731198540.0,
    "ttl_seconds": 120
  }
}

// Client -> Backend (APPROVAL_RESOLVE)
{
  "message_type": "REQUEST",
  "action": "approval_resolve",
  "payload": {
    "approval_id": "appr_77a98b1c",
    "approved": true,
    "decision_by": "Dad"
  }
}

// Backend -> Client (APPROVAL_ACK)
{
  "message_type": "RESPONSE",
  "action": "approval_resolve",
  "payload": {
    "approval_id": "appr_77a98b1c",
    "status": "CONSUMED",
    "execution_status": "EXECUTING"
  }
}
```

### D. Live Hardware Telemetry Stream (1Hz Push)
```json
// Backend -> Client (TELEMETRY_PUSH)
{
  "message_type": "EVENT_PUSH",
  "action": "hardware_telemetry",
  "payload": {
    "cpu_percent": 34.2,
    "cpu_temp_c": 54,
    "ram_used_bytes": 9879048192,
    "ram_total_bytes": 17179869184,
    "gpu_percent": 18,
    "vram_used_bytes": 3650722816,
    "vram_total_bytes": 8589934592,
    "ollama_active": true
  }
}
```

---

## 4. Error Codes & Recovery Matrix

| Error Code | Meaning | Recovery Action |
| :--- | :--- | :--- |
| `ERR_PIPE_BROKEN` | Backend crashed or process killed | Desktop displays reconnecting banner; supervisor triggers restart (up to 3x). |
| `ERR_AUTH_REJECTED` | Unrecognized user ID or invalid session token | Client initiates full handshake re-authentication. |
| `ERR_SCHEMA_VIOLATION` | Malformed JSON or unparseable fields | Request rejected fail-closed; error logged to security audit trail. |
| `ERR_APPROVAL_EXPIRED` | User took longer than 120s to decide | Ticket invalidated; agent halts turn; user informed to retry. |
| `ERR_VRAM_OOM_WARNING` | VRAM usage exceeded 85% (>6.8 GB) | Desktop alerts user; backend rejects loading additional large models. |

