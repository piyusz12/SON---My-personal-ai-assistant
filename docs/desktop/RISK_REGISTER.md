# SON Desktop — Risk Register & Mitigation Strategy

## 1. Risk Matrix Overview

| Risk ID | Risk Description | Probability | Impact | Severity | Primary Mitigation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | **VRAM Exhaustion (CUDA OOM)**: Loading multiple models or vision models alongside gaming/display exceeds the 8GB RTX 4060 VRAM limit. | **High** | **High** | **CRITICAL** | Enforce a strict **6.0 GB VRAM ceiling**; explicitly unload previous model weights before loading new models; fallback Faster-Whisper to CPU INT8 if VRAM > 85%. |
| **RSK-02** | **Indirect Prompt Injection**: External web/file text contains adversarial instructions attempting to hijack assistant behavior. | **High** | **High** | **HIGH** | XML isolation delimiters (`<untrusted_external_content>`); regex prompt injection heuristics; mandatory human approval for destructive operations. |
| **RSK-03** | **Named Pipe IPC Disconnect**: Backend terminates abruptly or encounters unhandled Python exception, breaking the pipe link. | **Medium** | **Medium** | **MEDIUM** | Process supervisor watchdog in C#; automatic reconnect loop with exponential backoff (max 3 retries); UI transitions gracefully to `Reconnecting`. |
| **RSK-04** | **Host Path Traversal & Escape**: Malicious prompt uses `..` or null bytes to escape workspace roots and touch system/credential files. | **Low** | **Critical** | **HIGH** | `StrictToolParams` with `extra="forbid"`; explicit `..` rejection in Pydantic schemas; `SecureFileService.validate_path` workspace boundary enforcement. |
| **RSK-05** | **UI Thread Starvation**: Heavy streaming token chunks or syntax highlighting calculations freeze the WPF UI thread. | **Medium** | **Medium** | **MEDIUM** | Length-prefixed byte reading runs on a dedicated background thread; UI updates marshalled via `Dispatcher.InvokeAsync` in 50ms batching windows. |
| **RSK-06** | **E2B Sandbox Outage**: Code execution requested when E2B cloud is unreachable or `E2B_API_KEY` is not configured. | **Medium** | **High** | **HIGH** | Permanent fail-closed security policy: return controlled error; host subprocess/shell execution fallback is strictly prohibited. |
| **RSK-07** | **Audio Feedback / Mic Echo**: Text-to-speech speaker output loops back into microphone input, triggering self-conversation. | **Medium** | **Low** | **LOW** | Hardware microphone auto-ducking/muting while TTS audio stream is actively playing; Push-to-Talk mode by default. |
| **RSK-08** | **Cross-Session Approval Replay**: Attacker intercepts an approved token ID to execute unauthorized actions in another session. | **Low** | **High** | **MEDIUM** | Cryptographic session and user ID binding; canonical SHA-256 argument hash matching; single-use atomic token consumption under thread lock. |
| **RSK-09** | **Windows SmartScreen Alert**: Unsigned executable triggers Windows Defender SmartScreen warning on new installations. | **High** | **Low** | **LOW** | Provide code-signing certificate instructions; install strictly into user-writable `%LocalAppData%\Programs` without requiring Admin UAC escalation. |
| **RSK-10** | **Process Zombie / Leakage**: Python backend or Ollama server left orphaned in background upon closing the desktop window. | **Medium** | **Medium** | **MEDIUM** | C# client sends explicit `SHUTDOWN_REQ` on `App.OnExit`; uses Windows Job Objects (`CreateJobObject`) to ensure child process tree is killed if parent terminates. |

---

## 2. Contingency & Incident Response Protocols

### A. VRAM Emergency Evacuation
If NVML telemetry detects VRAM exceeding 7.2 GB (90% capacity):
1. Immediately issue an unload request to Ollama: `curl http://127.0.0.1:11434/api/generate -d '{"model": "<active_model>", "keep_alive": 0}'`.
2. Free CUDA cached memory in Python: `torch.cuda.empty_cache()`.
3. Display visual amber toast on the desktop HUD alerting Dad of high GPU memory pressure.

### B. Security Breach / Injection Alarm
If `PROMPT_INJECTION_FLAGGED` is triggered:
1. Log structured security event with raw input preview and detected injection patterns to `audit.jsonl`.
2. Wrap content in strict XML warning tags before passing to model reasoning.
3. Automatically escalate any subsequent tool calls originating from this turn to `HIGH RISK`, requiring explicit interactive confirmation from Dad.

