---
name: files
description: Safe local filesystem operations with canonicalization and traversal security.
version: 1.0.0
---

# File System Skill

Provides controlled, canonicalized file operations.

## Security Guarantees
- Canonical path resolution via `Path.resolve()`
- Directory traversal guards (Zip-Slip and relative escape detection)
- Protected system paths (`C:\Windows`, `C:\Program Files`, drive roots) cannot be mutated or deleted
- High-impact deletions strictly require human approval
