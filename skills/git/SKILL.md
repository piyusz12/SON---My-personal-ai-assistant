---
name: git
description: Typed, permission-controlled Git SCM operations.
version: 1.0.0
---

# Git Integration Skill

Provides structured Git commands via `GitRunner`.

## Policies
- **READ Operations**: `git_status`, `git_log`, `git_diff`, `git_branch`, `git_remote` execute automatically.
- **Local Mutations**: `git_add` executes automatically; `git_commit` requires approval.
- **Remote Mutations**: `git_pull` and `git_push` strictly require human confirmation.
- **Safety**: Direct invocation of git.exe with argument arrays (no shell interpretation).
