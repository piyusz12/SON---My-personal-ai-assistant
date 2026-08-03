# SON — My Personal AI Assistant

SON is a local-first, AI-powered personal computer assistant inspired by JARVIS.

It extends beyond a traditional chatbot by understanding natural language, interacting with the desktop environment, and assisting with everyday development and productivity tasks while running primarily on the user's own machine.

## What SON Combines

SON brings together:
- Voice interaction
- Local large language models
- Desktop automation
- Semantic file search
- Memory
- Modular plugins

These components form a single, extensible assistant.

## What SON Can Do

SON can:
- Launch applications
- Manage files
- Execute terminal commands
- Assist with coding in VS Code
- Manage Ollama models and Docker containers
- Understand screenshots
- Provide contextual responses based on previous conversations and user preferences

## Architecture

SON uses a modular architecture that separates core reasoning from specialized agents responsible for:
- Voice processing
- Desktop control
- Memory management
- Terminal execution
- Vision
- Internet access

## Plugin System

A plugin system allows new capabilities to be added without modifying the core application.
