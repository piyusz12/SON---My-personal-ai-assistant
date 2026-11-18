---
name: vscode
description: VS Code workspaces, Python environments, and project test management.
version: 1.0.0
---

# VS Code & Development Skill

Manages Python developer workflows and IDE windows.

## Highlights
- **Workspace Launch**: Opens directories and specific files in VS Code via controlled runner.
- **Isolated Environments**: Creates `.venv` directories to protect host Python installation.
- **Dependency Guard**: Runs `pip install` exclusively within verified local `.venv` targets.
- **Test Automation**: Executes `pytest` suites safely with output capture and timeouts.
