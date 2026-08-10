<h1 align="center">
  <br>
  SON — Personal AI Assistant
  <br>
</h1>

<h4 align="center">A local-first, JARVIS-inspired AI assistant designed for your personal computer.</h4>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#key-features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#plugin-system">Plugins</a>
</p>

---

## 🌟 Overview

**SON** is a powerful, local-first AI assistant designed to run primarily on your own machine. Moving far beyond a traditional chatbot, SON understands natural language, interacts seamlessly with your desktop environment, and accelerates your everyday development and productivity tasks. 

By unifying cutting-edge local Large Language Models (LLMs), seamless voice interaction, and robust desktop automation, SON serves as your highly capable, extensible digital co-pilot.

## ✨ Key Features

- 🎙️ **Voice Interaction**: Speak naturally to SON and receive immediate, conversational voice responses.
- 🧠 **Local LLMs**: Powered by local models ensuring complete privacy, zero latency, and offline capabilities.
- 💻 **Desktop Automation**: Seamlessly launch applications, manage files, and automate OS-level interactions.
- 🔍 **Semantic File Search**: Instantly find what you need across your system using advanced semantic search.
- 🐘 **Persistent Memory**: SON remembers past conversations and adapts to your preferences over time.
- ⌨️ **Terminal Execution**: Safely execute terminal commands, build scripts, and manage environments via natural language.
- 👁️ **Computer Vision**: Capable of understanding screenshots and extracting visual context directly from your screen.
- 🛠️ **Developer Friendly**: Built-in assistance for VS Code coding, Docker management, and Ollama model orchestration.

## 🏗️ Architecture

SON is built on a highly modular architecture that cleanly separates core reasoning logic from specialized execution agents:

- **Core Reasoning**: The "brain" that routes tasks, maintains conversational context, and plans execution.
- **Voice Processing**: High-performance Speech-to-Text (STT) and Text-to-Speech (TTS) engines.
- **Desktop Control**: Interacts securely with underlying OS APIs.
- **Memory Management**: Manages short-term working memory and long-term vector/semantic storage.
- **Terminal Execution**: Safely runs and monitors CLI commands.
- **Vision**: Analyzes and interprets visual inputs.
- **Internet Access**: Fetches real-time web information when required.

## 🔌 Plugin System

Extensibility is at the heart of SON. The robust **Plugin System** allows you to add entirely new capabilities—such as custom API integrations, smart home controls, or specialized workflows—without modifying the core application codebase.

## 🚀 Getting Started

To run SON locally, follow these steps:

1. **Clone the repository**
   ```bash
   git clone https://github.com/piyusz12/SON.git
   cd SON
   ```

2. **Create a virtual environment (optional but recommended)**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the assistant**
   ```bash
   python main.py
   ```

## 📄 License

This project is distributed under the terms of the [LICENSE](LICENSE) file.
