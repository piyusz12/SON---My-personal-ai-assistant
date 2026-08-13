<div align="center">

# 🤖 SON V3 — Personal Computer & Vision Assistant

### *Listen • See • Think • Speak • Remember • Control • Automate*

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%2F%2010-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com)
[![Hardware](https://img.shields.io/badge/Hardware-NVIDIA%20RTX%20%2B%20Ryzen-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://nvidia.com)
[![Local-First](https://img.shields.io/badge/Privacy-100%25%20Local--First-green?style=for-the-badge&logo=shield&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](LICENSE)

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-son-version-roadmap">Roadmap</a> •
  <a href="#-core-architecture">Architecture</a> •
  <a href="#-camera--vision-subsystem">Camera & Vision</a> •
  <a href="#-3-layer-memory-system">3-Layer Memory</a> •
  <a href="#-benchmarks--performance">Benchmarks</a> •
  <a href="#-installation--setup">Getting Started</a> •
  <a href="#-commands--capabilities">Capabilities</a>
</p>

---

</div>

## 🌟 Overview

**SON V3** is a high-performance, local-first **Personal Computer and Vision Assistant** engineered to operate seamlessly on your hardware with low latency, zero cloud dependency, and total biometric privacy.

Unlike generic chatbot wrappers, SON acts as a deeply integrated computer co-pilot. It unifies high-speed **Intent Routing (<50ms execution)**, a **dedicated Camera & Vision Subsystem** (separating human presence detection from local, opt-in face recognition), **3-Layer Memory** (RAM, SQLite, and Vector DB), **streaming voice interaction**, and OS automation.

---

## 🗺️ SON Version Roadmap

```text
SON V1 ───► Local AI • Text Chat • Ollama • Basic Memory
              ↓
SON V2 ───► Voice AI • Wake Word ("Hey SON") • Whisper STT • Piper TTS
              ↓
🟢 SON V3 ──► PERSONAL COMPUTER & VISION ASSISTANT (Current Milestone)
            ├── Sub-50ms Intent Router & Bypass Architecture
            ├── Dedicated Camera Vision (Person Detection vs Local Opt-in Face ID)
            ├── Desktop Screen Vision & Visual Error Analysis (Llama 3.2 Vision)
            ├── 3-Layer Memory Hierarchy (RAM + SQLite + ChromaDB Vector RAG)
            ├── Resilient Ollama Engine with TTFT Profiling
            └── Security Sandboxing & Hardware Privacy Killswitches
              ↓
SON V4 ───► AI AGENT • Multi-Agent Orchestration • Autonomous Goal Planning
              ↓
SON V5 ───► PERSONAL AI OS • Multi-Device Awareness • Self-Healing Workflows
```

---

## 🏗️ Core Architecture

```text
                                 ┌─────────────────────────────────┐
                                 │       USER INPUT STREAM         │
                                 │   Voice / Keyboard / Camera     │
                                 └────────────────┬────────────────┘
                                                  │
                                                  ▼
                                 ┌─────────────────────────────────┐
                                 │          INTENT ROUTER          │
                                 └──────┬─────────┼─────────┬──────┘
                                        │         │         │
                   ┌────────────────────┘         │         └────────────────────┐
                   ▼                              ▼                              ▼
          ┌──────────────────┐          ┌───────────────────┐          ┌──────────────────┐
          │  COMMAND (<50ms) │          │    CHAT (Lite)    │          │  COMPLEX (RAG)   │
          │  Direct Execute  │          │ Fast Qwen3 / LLM  │          │ Memory + Codebase│
          └────────┬─────────┘          └─────────┬─────────┘          └────────┬─────────┘
                   │                              │                             │
                   ├──────────────────────────────┴─────────────────────────────┤
                   ▼                                                            ▼
    ┌─────────────────────────────┐                              ┌─────────────────────────────┐
    │     HARDWARE EXECUTION      │                              │      3-LAYER MEMORY         │
    │  Windows / Camera / Docker  │                              │  L1 RAM • L2 SQL • L3 Vector│
    └─────────────────────────────┘                              └─────────────────────────────┘
```

### 1. High-Speed Intent Router (`core/intent_router.py`)
Direct commands (such as *"Open Chrome"*, *"Take a screenshot"*, *"Is anyone in the room?"*, *"Volume 50"*) never touch an 8-billion parameter LLM. They are classified and executed in **<50ms** via pre-compiled regex pipelines, eliminating latency.

### 2. Resilient Brain & Multi-Model Routing (`core/brain.py` & `core/ollama_client.py`)
- **Resilient Ollama Client**: Automatic retries with exponential backoff, health status caching, and connection self-healing.
- **Dynamic Context**: Strips unnecessary memory/codebase context for conversational queries to minimize TTFT.
- **Model Router**:
  - **General Reasoning**: `qwen3:8b`
  - **Coding Tasks**: `qwen2.5-coder:7b`
  - **Visual Understanding**: `llama3.2-vision`

---

## 👁️ Camera & Vision Subsystem

The vision architecture is partitioned into two specialized engines: **Camera Vision** and **Screen Vision**.

```text
                                    VISION SUBSYSTEM
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
          CAMERA VISION (Physical)                      SCREEN VISION (Desktop)
                    │                                             │
      ┌─────────────┼─────────────┐                               ├── Capture (mss, 720p LANCZOS)
      ▼             ▼             ▼                               ├── Screen OCR (pytesseract)
 Motion Check    Person Det    Face Rec (Opt-In)                  └── Visual Bug/UI Diagnosis
 (Background)  (Room Count)   (Local SQLite DB)                       (Llama 3.2 Vision)
```

### 1. Physical Camera Privacy Controls (`vision/camera/capture.py`)
- **Hardware-Level Release**: Pausing the camera completely halts frame polling and releases the camera device handle.
- **Independent Privacy Toggles**: Toggle `Camera Active`, `Person Detection`, or `Face Recognition` independently.

### 2. Person Detection vs. Face Identification
- **Person Detection (`vision/camera/detection.py`)**: Checks motion deltas and counts people in the room using HOG/Cascade detectors.
  - *Query*: *"SON, is anyone in the room?"* ➔ *"Yes, I detect one person in the room."* (<20ms, zero cloud/LLM call).
- **Local Face Recognition (`vision/camera/recognition.py`)**:
  - **Opt-In Biometrics Only**: Matches against locally enrolled faces stored in SQLite (`enrolled_people` table). Zero public/cloud databases.
  - **Embedder**: Generates normalized 128-dimensional spatial gradient biometric templates with cosine distance verification.
  - *Enrollment Command*: `"Enroll person Piyush"` captures frames, computes embeddings, and stores the biometric template locally.

### 3. Event-Driven Vision Loop (`vision/camera/events.py`)
Runs at a lightweight **1 FPS** to monitor presence. Automatically logs episodic events (`person_entered`, `person_left`, `known_person_detected`) to SQLite memory without wasting GPU inference cycles.

### 4. Desktop Screen Vision (`vision/screen/`)
- Ultra-fast desktop screenshot capture with LANCZOS downscaling to 720p to preserve VRAM.
- Answers questions like *"What's on my screen?"*, *"Explain this bug traceback"*, or *"Analyze this UI"*.

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

The unified **`MemoryManager`** automatically routes queries:
- **COMMAND**: Bypasses memory search completely (<1ms).
- **CHAT**: Pulls L1 working turns + relevant L2 preferences (<5ms).
- **COMPLEX**: Executes full RAG (L1 + L2 + L3 ChromaDB cosine search).

---

## 🛡️ Security & Sandbox Hardening

SON V3 enforces strict security policies across all tool and command executions:

1. **Command Injection Mitigation**: `run_terminal_command` strictly blocks command chaining, subshells, and redirection operators (`&`, `;`, `|`, `` ` ``, `$`, `\n`, `\r`, `>`, `<`) and validates tokenized commands against a strict whitelist.
2. **Drive & System Path Protection**: `plugins/files.py` blocks deletion or modification of drive anchors (`C:\`) and protected system directories (`C:\Windows`, `C:\Program Files`, `C:\Users`).
3. **SSRF Blocking**: Real-time URL resolution rejects attempts to access localhost (`127.0.0.1`, `::1`) or private network ranges (`192.168.x.x`, `10.x.x.x`).
4. **Leak-Free Database Connections**: Context-managed SQLite connections guarantee immediate socket release.

---

## 📊 Benchmarks & Performance

*Tested on **AMD Ryzen 7 7840HS** (8C/16T) + **NVIDIA GeForce RTX 4060 Laptop GPU** (8GB VRAM) + **16GB RAM**:*

| Stage / Component | Metric / Latency | Implementation Detail |
| :--- | :--- | :--- |
| **Intent Classification** | `< 2 ms` | Pre-compiled regex decision tree |
| **Command Execution** | `< 45 ms` | Direct OS / Python API execution |
| **ChromaDB Vector Query** | `6.8 ms` | HNSW cosine index + Embedding Cache |
| **LLM Time-To-First-Token (TTFT)**| `2.83 s` | `qwen3:8b` via Ollama (Streaming, GPU layer offload 99) |
| **Piper TTS Generation** | `< 120 ms` | ONNX Runtime (Float32 / 22.05kHz) |
| **Person / Motion Detection** | `< 15 ms` | OpenCV HOG + Haar Cascade |
| **Face Biometric Extraction** | `< 2 ms` | 128-dim Spatial Gradient Vector |

---

## 🚀 Installation & Setup

### Prerequisites
1. **Python 3.11+** installed on Windows.
2. **NVIDIA GPU Drivers** with CUDA support.
3. **[Ollama](https://ollama.com)** installed and running.

### 1. Clone & Setup Virtual Environment
```bash
git clone https://github.com/piyusz12/SON---My-personal-ai-assistant.git
cd SON---My-personal-ai-assistant

python -m venv .venv
.venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Pull Ollama Models
```bash
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
ollama pull llama3.2-vision
ollama pull nomic-embed-text
```

### 4. Run SON V3
```bash
# Interactive Keyboard / Terminal Mode
python son.py

# Voice-First Mode
python son.py --voice

# Wake Word Mode ("Hey SON")
python son.py --wakeword
```

---

## 💬 Capabilities & Example Commands

### 🖥️ PC & System Control
* *"Open Chrome"* / *"Close Spotify"* / *"Open VS Code"*
* *"Volume 60"* / *"Mute sound"* / *"Brightness 80"*
* *"Take a screenshot"* / *"Show system status"*
* *"Lock workstation"* / *"Put PC to sleep"*

### 👁️ Vision & Camera Commands
* *"Is anyone in the room?"* ➔ Instant occupancy detection.
* *"How many people do you see?"* ➔ Human count verification.
* *"Do you recognize this person?"* ➔ Local biometric matching against enrolled users.
* *"Enroll person Piyush"* ➔ Registers user face template into local SQLite DB.
* *"Pause camera"* / *"Resume camera"* / *"Camera status"* ➔ Privacy controls.
* *"What's on my screen?"* ➔ Llama 3.2 Vision screen analysis.

### 🐘 Memory & Knowledge
* *"Remember that my primary workspace is C:\AI\SON"*
* *"What did we talk about earlier?"*
* *"Show memory stats"* / *"Forget about [topic]"*

### 🛠️ Developer & DevOps
* *"Run docker ps"* / *"Start container web_app"*
* *"Scan codebase C:\AI\MyProject"*
* *"Explain why my FastAPI server is throwing a 500 error"*

---

## 🧪 Testing & Verification Suite

Run the comprehensive test suite and GPU benchmark:

```bash
# Run the 13-category unit and security test suite
python test_v3_comprehensive.py

# Run GPU utilization and inference benchmark
python -m benchmarks.benchmark_gpu
```

---

## 📂 Project Structure

```text
SON/
│
├── core/                   # Central Framework & Infrastructure
│   ├── brain.py            # LLM reasoning engine & model router
│   ├── intent_router.py    # Sub-50ms intent classifier
│   ├── ollama_client.py    # Resilient Ollama client with retry & TTFT
│   ├── profiler.py         # RequestTracer stage profiler
│   ├── health.py           # Unified service health monitor
│   ├── config.py           # Central security policies & settings
│   └── state.py            # Global system state bus
│
├── vision/                 # Dedicated Vision Subsystem
│   ├── camera/             # Camera Vision Engine
│   │   ├── capture.py      # Frame grabber with hardware privacy killswitch
│   │   ├── detection.py    # Person presence & count detector
│   │   ├── face.py         # 128-dim biometric face embedder
│   │   ├── recognition.py  # Local opt-in face recognition
│   │   └── events.py       # 1 FPS episodic vision loop
│   └── screen/             # Desktop Screen Vision Engine
│       ├── capture.py      # Screen grabber (720p LANCZOS)
│       ├── ocr.py          # Screen OCR utility
│       └── analysis.py     # Llama 3.2 Vision visual analyzer
│
├── memory/                 # 3-Layer Memory System
│   ├── ram_memory.py       # L1: Working turn deque
│   ├── structured_memory.py# L2: SQLite facts, preferences, enrolled people, events
│   ├── semantic_memory.py  # L3: ChromaDB vector search
│   └── manager.py          # Unified MemoryManager coordinator
│
├── tools/                  # Deterministic OS & PC Control Tools
│   ├── windows_control.py  # App management, volume, brightness, processes
│   ├── docker_control.py   # Docker CLI container orchestrator
│   ├── web.py              # SSRF-protected search, weather, news
│   └── automation.py       # Multi-step deterministic routine runner
│
├── plugins/                # Extensible Plugin Matrix
├── benchmarks/             # GPU, TTFT, and ChromaDB benchmarking suite
├── audio.py & stt.py       # Silero VAD & Faster-Whisper (CUDA)
├── tts.py                  # Piper ONNX Text-to-Speech
├── wakeword.py             # OpenWakeWord ("Hey SON") listener
├── son.py                  # Main Application Orchestrator
└── test_v3_comprehensive.py# Comprehensive automated test suite
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

<div align="center">
  <sub>Built with ❤️ as a local-first personal AI assistant.</sub>
</div>
