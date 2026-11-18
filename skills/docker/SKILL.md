---
name: docker
description: Docker Desktop container management and daemon health checks.
version: 1.0.0
---

# Docker Integration Skill

Manages local container infrastructure via `DockerRunner`.

## Features
- Container status, inspection, and log monitoring.
- Safe start, stop, and restart with configurable shutdown timeouts.
- Container identifier validation (prevents flag injection).
- Graceful degradation if Docker Desktop daemon is offline.
