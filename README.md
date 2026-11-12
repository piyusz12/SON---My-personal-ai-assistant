<div align="center">

# 🤖 SON V3 — Personal AI Operating Companion & Desktop Assistant

### *Listen • See • Think • Speak • Remember • Control • Automate*

[![.NET 8](https://img.shields.io/badge/.NET-8.0%20WPF-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)](https://dotnet.microsoft.com/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%2F%2010-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com)
[![Hardware](https://img.shields.io/badge/Hardware-NVIDIA%20RTX%20%2B%20Ryzen-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://nvidia.com)
[![Local-First](https://img.shields.io/badge/Privacy-100%25%20Local--First-green?style=for-the-badge&logo=shield&logoColor=white)]()
[![Zero-Trust](https://img.shields.io/badge/Security-Zero--Trust%20Gateway-blue?style=for-the-badge&logo=lock&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](LICENSE)

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-desktop-application-shell-net-8-wpf">Desktop UI</a> •
  <a href="#-floating-mini-ai-companion-hud">Mini Companion</a> •
  <a href="#-core-architecture--ipc">Architecture & IPC</a> •
  <a href="#-10-specialized-workspaces">Workspaces</a> •
  <a href="#-vision--camera-subsystems">Vision</a> •
  <a href="#-3-layer-memory-system">Memory</a> •
  <a href="#-security--zero-trust-gateway">Security</a> •
  <a href="#-quick-start--installation">Quick Start</a>
</p>

---

</div>

## 🌟 Overview

**SON V3** is a production-grade, local-first **Personal AI Operating Companion** for Windows. It is designed to act not as a disconnected chatbot, but as an intelligent desktop operating layer capable of:

- **Natural Voice & Streaming AI Conversation** via local Ollama models (`llama3.2:latest`, `Qwen3:8b`, `deepseek-r1:8b`).
- **Hardware-Accelerated Screen Understanding & OCR** powered by native GDI capture and multi-modal models (`llama3.2-vision`).
- **Living Apple Liquid Glass Desktop Interface** (.NET 8 WPF) with dynamic aurora plasma visuals and cyber cyan/violet styling.
- **Floating Mini AI Companion HUD** that remains accessible on screen when minimized to assist your daily workflows.
- **Zero-Trust Security Gateway** with cryptographic action approvals, policy engine evaluation, and tamper-resistant audit logging.
- **High-Speed Named Pipe IPC** connecting the responsive C# desktop client with the Python orchestration engine.

---

## 🖥️ Desktop Application Shell (.NET 8 WPF)

The primary user interface is built on **.NET 8 WPF** adhering to Microsoft Fluent Design and Apple Liquid Glass aesthetics:

- **Ultra-Translucent Acrylic Glassmorphism**: High-contrast, glare-free glass cards calibrated to WCAG AAA contrast ratios (`#FFFFFF` text on `#0C1220FA` surfaces).
- **Living Aurora Plasma Visuals**: Hardware-accelerated background ambient orbs that gently drift and pause automatically when hidden to conserve CPU/GPU power.
- **macOS-Style Traffic Lights & Window Capsule**: Integrated minimize, maximize, close, and always-on-top pin controls.
- **Global Command Palette (`Ctrl + K`)**: Instant keyboard-driven fuzzy navigation across all workspaces and system actions.
- **Collapsible Adaptive Sidebar (`Ctrl + B`)**: Full label mode or collapsed icon navigation that never consumes unnecessary workspace area.

---

## 🛸 Floating Mini AI Companion HUD

Minimizing the main window—via top-right buttons, macOS traffic lights, taskbar, or `Ctrl + M`—automatically summons the **Floating Mini AI Companion HUD** at the bottom-right of your screen:

```text
┌─────────────────────────────────────────────────────────────┐
│ (◉) SON AI • Ready to assist                 [ — ] [ ↗ ]    │
├─────────────────────────────────────────────────────────────┤
│ [ Ask SON anything or snap screen...               🎙  ⚡ ] │
├─────────────────────────────────────────────────────────────┤
│ [ 🎙 Voice ]   [ 👁 Vision ]   [ ⚡ Fix ]   [ 📋 Brief ]     │
└─────────────────────────────────────────────────────────────┘
```

- **Expressive Living Animations**: 10-second rotating orbital reticle, breathing AI avatar shadow pulse, and 5-bar reactive equalizer bars.
- **One-Click Screen Snapping**: Native GDI display capture with handle leak protection and immediate multi-modal vision analysis.
- **Direct Workflow Assistance**: Instant explanation of code, debugging of visible errors, and summarization of open windows.
- **Smooth Window Transition**: Double-clicking anywhere on the pill or clicking `↗` restores the full desktop workspace.

---

## 🏗️ Core Architecture & IPC

```mermaid
flowchart TD
    subgraph Frontend["SON Desktop (.NET 8 WPF)"]
        MainWindow[MainWindow & 10 Workspaces]
        MiniCompanion[Floating Mini Companion HUD]
        ScreenCap[ScreenCaptureService (Native GDI)]
        NamedPipeClient[NamedPipeIpcClient]
        ProcManager[BackendProcessManager (Win32 Job Object)]
    end

    subgraph IPC["Named Pipe IPC (\\\\.\\pipe\\son_desktop_ipc)"]
        Frames[4-Byte Big-Endian Header + UTF-8 JSON]
    end

    subgraph Backend["Python AI Backend"]
        PipeServer[NamedPipeServer (Async Listener)]
        Dispatcher[ProtocolDispatcher]
        Orchestrator[SonOrchestrator & Intent Router]
        VisionEngine[ScreenVision (Llama 3.2 Vision)]
        Security[PolicyEngine & ApprovalManager]
        Audit[SecurityAuditLogger (JSONL)]
        MemorySys[Structured SQLite + ChromaDB Vector]
    end

    MainWindow --> NamedPipeClient
    MiniCompanion --> NamedPipeClient
    MainWindow --> ScreenCap
    MiniCompanion --> ScreenCap
    ProcManager -.->|Manages Lifecycle| PipeServer

    NamedPipeClient <-->|Framed JSON Packets| Frames
    Frames <-->|Framed JSON Packets| PipeServer
    PipeServer --> Dispatcher
    Dispatcher --> Orchestrator
    Dispatcher --> VisionEngine
    Dispatcher --> MemorySys
    Orchestrator --> Security
    Orchestrator --> Audit
```

### Key Engineering Standards
1. **Named Pipe IPC (`\\.\pipe\son_desktop_ipc`)**: Sub-millisecond local process communication using length-prefixed binary framing.
2. **Win32 Job Object Containment**: The child Python backend process is registered to a Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. The OS kernel guarantees the Python process will terminate immediately if the desktop frontend exits.
3. **Handle-Guarded Screen Capture**: `IScreenCaptureService` encapsulates GDI P/Invoke calls (`GetWindowDC`, `CreateCompatibleBitmap`, `BitBlt`) in strict `try ... finally` blocks to eliminate GDI handle leaks.

---

## 🗂️ 10 Specialized Workspaces

| Workspace | Shortcut | Core Functionality |
| :--- | :---: | :--- |
| **1. Home Dashboard** | `Ctrl + 1` | Live hardware utilization (CPU, RAM, GPU, VRAM, session uptime) and quick action hero. |
| **2. AI Chat Studio** | `Ctrl + 2` | Streaming conversation with PydanticAI defensive pipeline, tool call cards, and UI virtualization. |
| **3. Voice Interaction** | `Ctrl + 3` | Push-to-talk and continuous hands-free voice conversation with reactive equalizer reactor. |
| **4. Memory & Knowledge**| `Ctrl + 4` | Search, add, categorize, and delete persistent structured facts from SQLite memory. |
| **5. Vision Studio** | `Ctrl + 5` | Hardware screen capture, visual error diagnosis, OCR transcription, and multi-modal Q&A. |
| **6. Automation Center** | `Ctrl + 6` | Scheduled and on-demand system routines with execution history logs and zero-trust verification. |
| **7. Files Explorer** | `Ctrl + 7` | Native directory browser, instant syntax file preview, and AI document summarization. |
| **8. Coding Studio** | `Ctrl + 8` | Integrated multi-language code inspector with AI explain, refactor, bug audit, and terminal. |
| **9. Tasks Monitor** | `Ctrl + 9` | Multi-step autonomous agent goal decomposition with pre-flight checks and audit checkpoints. |
| **10. Security Gateway** | `Ctrl + 0` | Human-in-the-loop authorization inbox, cryptographic token approvals, and live audit stream. |

---

## 👁️ Vision & Camera Subsystems

SON V3 features dual-engine visual intelligence:

1. **Desktop Screen Vision (`vision/screen/` & `ScreenCaptureService.cs`)**:
   - Ultra-fast native screen capture with Lanczos / PNG downscaling to minimize VRAM usage.
   - Answers queries like *"Explain what's on my screen"*, *"Find errors in this code"*, and *"Transcribe this text"*.
   - Direct IPC endpoint (`handle_vision_analyze`) routes captured frames straight into multi-modal vision inference.

2. **Physical Camera Privacy Engine (`vision/camera/`)**:
   - **Hardware Killswitch**: Releasing the camera device completely halts frame polling and frees the USB device handle.
   - **Person Detection vs. Local Face ID**: Distinguishes between anonymous room count (<15ms via OpenCV HOG) and opt-in local biometric face matching (128-dimensional normalized embedding vectors stored in SQLite).

---

## 🧠 3-Layer Memory System

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        SON 3-LAYER MEMORY                              │
├───────────────────┬───────────────────────────┬────────────────────────┤
│  L1: RAM Memory   │  L2: Structured SQLite    │  L3: Semantic ChromaDB │
│  (<1ms Latency)   │  (<5ms Latency)           │  (<15ms Latency)       │
├───────────────────┼───────────────────────────┼────────────────────────┤
│ • Recent Turns    │ • Facts & Preferences     │ • Document Vectors     │
│ • Working Context │ • Enrolled Biometric Faces│ • Codebase Chunks      │
│ • Session State   │ • Episodic Vision Events  │ • Deep Chat History    │
└───────────────────┴───────────────────────────┴────────────────────────┘
```

---

## 🛡️ Security & Zero-Trust Gateway

SON V3 strictly avoids silent execution of privileged operations:

1. **Zero-Trust Policy Engine**: Tool executions are categorized into `SAFE`, `MEDIUM`, `SENSITIVE`, and `CRITICAL`.
2. **Cryptographic Approval Manager**: Sensitive actions (file deletion, system configuration, terminal commands) generate single-use authorization tokens requiring explicit user approval.
3. **Tamper-Resistant Audit Logger**: Every security event, approval resolution, and policy evaluation is recorded to append-only JSONL files (`logs/security_audit.jsonl`).
4. **Shell Injection Prevention**: ViewModels use structured `ArgumentList` parameters and 45-second execution timeouts instead of raw shell concatenation.
5. **System Path Guards**: Critical directories (`C:\Windows`, `C:\Program Files`, `C:\Users\Default`) are strictly protected from deletion.

---

## 🚀 Quick Start & Installation

### Prerequisites
- **Windows 11 / 10** (64-bit)
- **.NET 8 SDK / Desktop Runtime**
- **Python 3.11 – 3.13** (64-bit)
- **[Ollama](https://ollama.com)** with local models (`ollama pull llama3.2:latest`)

### 1. Clone & Set Up Python Backend
```bash
git clone https://github.com/piyusz12/SON---My-personal-ai-assistant.git
cd SON---My-personal-ai-assistant

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Launch SON Desktop (.NET 8 WPF)
Simply double-click **`SON.bat`** or run:
```bash
dotnet run --project "SON.Desktop\SON.Desktop.csproj" -c Release
```

### 3. Run Automated Tests
```bash
# Run .NET 8 WPF Desktop Unit Tests (13 tests)
dotnet test SON.sln -c Release

# Run Python Backend & Defensive Security Suite (260 tests)
python -m pytest tests/ -q
```

---

## 📂 Repository Structure

```text
SON/
│
├── SON.Desktop/            # .NET 8 WPF Desktop Application (Apple Glass Aesthetic)
│   ├── Views/              # 10 Workspace Views + MainWindow + MiniCompanionWindow
│   ├── ViewModels/         # MVVM CommunityToolkit ViewModels
│   ├── Services/           # Named Pipe IPC, ScreenCaptureService, Process Manager
│   ├── Models/             # Shared IPC Contracts & Data Transfer Objects
│   └── Converters/         # WPF Visual & Theme Converters
│
├── SON.Desktop.Tests/      # .NET 8 xUnit Desktop Test Suite (13 / 13 passing)
│
├── core/                   # Central Framework & Infrastructure
│   ├── orchestrator.py     # Master request orchestrator & Intent Router
│   ├── security/           # PolicyEngine, ApprovalManager, AuditLogger, Sandbox
│   ├── brain.py            # LLM reasoning engine & model router
│   ├── config.py           # Unified application settings & logging configuration
│   └── gpu_manager.py      # Real-time NVML hardware metrics supervisor
│
├── services/               # System Services
│   ├── ipc/                # Named Pipe Server & Protocol Dispatcher
│   └── sandbox/            # Containerized Execution Sandbox
│
├── vision/                 # Dual Vision Engine (Camera Biometrics + Desktop Screen)
├── memory/                 # 3-Layer Memory (RAM, SQLite, ChromaDB)
├── plugins/                # Extensible Tools (Windows, Files, VS Code, Browser)
├── data/                   # Default configuration, automations, and settings
├── logs/                   # Contained application lifecycle & security audit logs
├── tests/                  # 260 Unit, Regression, and Security Defensive Tests
├── SON.bat                 # One-click Windows launch script
└── SON.sln                 # Visual Studio Solution (.NET 8)
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

<div align="center">
  <sub>Built with ❤️ as a private, local-first personal AI assistant.</sub>
</div>
