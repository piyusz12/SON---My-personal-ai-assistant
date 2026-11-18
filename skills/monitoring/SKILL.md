---
name: monitoring
description: Zero-overhead system telemetry (CPU, GPU NVML, RAM, Disk, Battery).
version: 1.0.0
---

# System Monitoring Skill

Provides real-time hardware telemetry and device controls.

## Performance Architecture
- **In-process NVML**: Reads RTX 4060 metrics via native C bindings without spawning expensive `nvidia-smi` subprocesses.
- **Telemetry Cache**: Caches non-critical metrics with a 2.5s TTL to prevent CPU polling spikes.
- **Hardware Controls**: Direct Win32 / pycaw integration for audio and brightness.
