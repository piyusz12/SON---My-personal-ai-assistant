# SON Desktop — Product Requirements Document (PRD)

## 1. Executive Summary & Vision

**SON Desktop** is a premier, locally hosted Windows AI assistant designed to unify conversational AI, real-time voice, long-term memory, computer vision, local PC automation, and hardware-accelerated model orchestration into a unified, secure Windows desktop application.

Built as a native Windows client paired with an enterprise-hardened Python AI engine, SON Desktop turns an HP OMEN 16 gaming workstation (Ryzen 7 7840HS, RTX 4060 8GB VRAM, 16GB RAM) into an autonomous personal command center without sacrificing host security or leaking private data to third-party clouds.

---

## 2. Target Workstation & Resource Constraints

| Hardware / Environment Element | Specification | Application Allocation & Constraints |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 Home (x64, Build 26300+) | Modern WinUI / WPF desktop presentation; Windows API integration |
| **Processor (CPU)** | AMD Ryzen 7 7840HS (8 Cores, 16 Threads) | Asynchronous task workers; Fast STT/TTS audio synthesis |
| **Graphics (GPU)** | NVIDIA GeForce RTX 4060 Laptop GPU (8GB VRAM) | CUDA 13.3 accelerated Ollama LLM inference; Vision models |
| **VRAM Ceiling** | 8,188 MiB | **Strict 6.0 GB budget** for LLMs (reserving 2GB for OS & display) |
| **System RAM** | 16 GB DDR5 | **Strict 3.5 GB budget** for Python backend, vector RAG, and UI |
| **Model Runtime** | Ollama v0.40.15 + llama-server | Local REST/WebSocket inference; streaming token generation |
| **Windows Desktop SDK** | .NET SDK 8.0.427 + WindowsDesktop.App 8.0.33 | High-performance C# WPF GUI client with MVVM architecture |

---

## 3. Comprehensive Module Requirements

### A. Home Dashboard
The central command deck providing an instant overview of assistant health and workstation vitals:
1. **Assistant State & Greeting**:
   - Dynamic conversational greeting based on time of day.
   - Status indicators: `Ready`, `Listening`, `Thinking`, `Executing Tool`, `Awaiting Approval`, `Offline`.
2. **Hardware Telemetry Monitor**:
   - Live CPU utilization gauge (%) and clock temperature.
   - System RAM gauge (used / available GB).
   - NVIDIA GPU compute utilization (%) via NVML / `nvidia-smi`.
   - VRAM usage bar (e.g. `4.2 GB / 8.0 GB used`) with warning thresholds when VRAM exceeds 85%.
3. **Engine Health & Ollama Status**:
   - Ollama service connection status (heartbeat indicator).
   - Currently active model name, context window size, and quantization level.
   - Python backend IPC link state and latency (ms).
4. **Action & Activity Feed**:
   - Pending security approval counter (with direct jump to approval prompt).
   - Count of active background automation routines.
   - Chronological log of recent operations (last 10 tool calls with status badges).
5. **Quick Action Tiles**:
   - "New Chat", "Voice Dictation", "Capture Screen", "System Status", "Run Routine".

### B. AI Chat
Production conversational workspace backed by the defensive PydanticAI agent:
1. **Streaming & Formatting**:
   - Smooth token-by-token character streaming without UI freezing.
   - Rich Markdown rendering (headers, tables, lists, KaTeX inline/display math).
   - Syntax-highlighted code blocks with language badges and a one-click "Copy Code" button.
2. **Session & History Management**:
   - Thread list sidebar with date categorizations (Today, Yesterday, Last 7 Days).
   - Full-text search across historical conversations.
   - Create new thread, rename thread, and permanent deletion.
3. **Execution Transparency**:
   - Live "Thinking" collapsible panel showing step-by-step reasoning tokens.
   - Tool execution progress pill: displays active tool name, elapsed execution time, and outcome.
   - Embedded interactive approval card when high-risk actions require authorization.
4. **Input Controls**:
   - Multi-line auto-expanding input box supporting `Enter` to send and `Shift+Enter` for newline.
   - "Stop Generation" button to cancel active inference turns immediately.
   - "Regenerate Response" action with variant branching.
   - Drag-and-drop file and image attachment handling.

### C. Voice Assistant
Hands-free audio interaction driven by local faster-whisper and neural TTS:
1. **Microphone Capture & Voice Activity**:
   - Push-to-talk hotkey support (configurable, e.g. `Right Alt` or `Ctrl+Space`).
   - Hands-free wake-word detection (optional, toggled by user).
   - Live animated soundwave / audio visualizer reflecting mic input levels.
2. **Audio Processing States**:
   - Discrete visible states: `Idle`, `Listening`, `Transcribing`, `Reasoning`, `Speaking`.
   - Ability to interrupt/stop speech synthesis instantly by pressing Esc or speaking.
3. **Audio Device Selection**:
   - Device dropdowns for Microphone Input and Audio Output Speaker devices.
   - Volume and mic sensitivity sliders with test feedback loops.

### D. Memory Center
Zero-leak persistent memory and Retrieval-Augmented Generation (RAG) management:
1. **Memory Browser**:
   - Filterable view of episodic and factual memories extracted from user interactions.
   - Category tags: `Preferences`, `Workspaces`, `Projects`, `Contacts`, `System Rules`.
   - Manual memory creation modal and individual memory entry deletion.
2. **RAG Knowledge Base**:
   - Indexed local document collections (PDFs, Markdown notes, codebases).
   - Vector index health status (embedding model: `nomic-embed-text:latest`).
   - Full privacy guarantee: credentials, API keys, and sensitive tokens are permanently filtered before vector indexing.

### E. Vision Center
Explicit opt-in visual perception and screen understanding:
1. **Privacy Safeguards**:
   - **Never secretly captures the screen**. Screen captures require explicit user triggers or modal confirmation.
   - Visual flashing indicator / notification pill whenever a screenshot is grabbed.
2. **Screen & Image Question Answering**:
   - Full-screen capture, active window capture, or interactive area marquee selection.
   - Thumbnail preview with zoom inspector before submitting to model.
   - Multimodal analysis via `llama3.2-vision:latest` or `qwen3-vl:8b`.
   - OCR text extraction tool with copy-to-clipboard functionality.

### F. PC Control Center
Controlled, allowlist-governed Windows desktop management:
1. **Application Launcher**:
   - Tile grid of verified applications (VS Code, Chrome, Terminal, Obsidian, Spotify).
   - One-click launch without shell execution.
2. **File Explorer (Sanctioned Roots Only)**:
   - Scoped file browser strictly confined to approved roots (Documents, Downloads, Desktop, Workspace).
   - Path canonicalization preventing access to Windows system directories or credential stores.
3. **Desktop Hardware Toggles**:
   - Master volume slider and screen brightness control.
   - Docker container quick-manager (start/stop/restart with approval gating).

### G. Automation Center
Scheduled and trigger-based routine orchestrator:
1. **Routine Management**:
   - List of configured routines (e.g. "Morning Briefing", "Workspace Prep", "Nightly Cleanup").
   - Routine builder: step-by-step sequential tool actions.
2. **Safety & Fail-Closed Halting**:
   - Any routine step requiring human approval halts execution and triggers a Desktop toast/modal.
   - Execution history with duration, exit status, and detailed error logs.
   - One-click immediate emergency abort for all active background routines.

### H. Model & Hardware Center
Intelligent Ollama and VRAM workload orchestration:
1. **Local Model Inventory**:
   - Live catalog of installed models (model tag, disk size, parameter count, quantization).
   - One-click model switching (e.g. swapping `llama3.2` for `qwen2.5-coder:7b`).
   - Download/pull progress bar for new models from the Ollama library.
2. **8GB VRAM Hardware Optimization**:
   - Hardware-aware recommendations: flags models requiring > 6GB VRAM as "Heavy / High Latency".
   - Automatic unloading of vision models when reverting to text-only mode to prevent CUDA OOM.
   - Configurable context length (2,048 to 16,384 tokens) with live VRAM usage estimates.

### I. Security Center
Real-time audit log, risk policy management, and approval hub:
1. **Pending Approval Inbox**:
   - Prominent badge showing unreviewed requests.
   - Detailed approval card: Tool name, target path/arguments, risk tier (`HIGH`/`CRITICAL`), reason, and single-use token expiration timer.
   - Approve / Deny buttons with approver identity recording.
2. **Security Audit Log**:
   - Live stream of all security events (`ACTION_EXECUTED`, `ACTION_DENIED`, `PROMPT_INJECTION_FLAGGED`, `FILE_SYSTEM_ROOT_BLOCKED`).
   - Secret redaction inspector verifying no tokens appear in cleartext.
   - Sandbox status monitoring (E2B connectivity, isolation guarantees).

### J. Settings
Comprehensive application customization:
1. **Themes & UI**: Dark theme (default), accent color selector, font scale.
2. **Backend & IPC**: Named Pipe address, heartbeat interval, process watchdog settings.
3. **Privacy**: Opt-in telemetry toggles, memory auto-pruning, prompt-injection sensitivity.
4. **Startup**: Launch on Windows startup (minimized to system tray).

---

## 4. Non-Functional Requirements (NFRs)

1. **Performance & Responsiveness**:
   - Desktop UI must maintain a consistent 60 FPS on the HP OMEN 16 display.
   - IPC round-trip latency between C# WPF frontend and Python backend must remain under **10 milliseconds**.
   - UI thread must never block during LLM token streaming, file I/O, or audio synthesis.
2. **Memory Footprint**:
   - C# WPF application memory consumption: **< 150 MB RAM**.
   - Python backend service: **< 400 MB RAM** idle (excluding active model VRAM).
3. **Zero-Trust Security**:
   - Zero direct execution from GUI to OS shells. Every action routes through the backend `PolicyEngine` and `ActionExecutor`.
   - IPC channel must be authenticated and restricted strictly to local machine access.
4. **Reliability & Watchdog**:
   - If the Python backend crashes or is terminated, the C# desktop app must detect the disconnection within 1.5 seconds, display an unobtrusive reconnecting banner, and offer a one-click backend restart.

