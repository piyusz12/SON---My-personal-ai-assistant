# SON V3 — Skill Manifest Architecture

## 1. Overview
Skills in SON V3 represent modular capabilities organized into self-contained directories.
Each skill contains:
- `manifest.json`: Machine-readable specification with schema, triggers, permissions, and timeout definitions.
- `SKILL.md`: Human-readable and agent-interpretable operational guide.

---

## 2. Directory Layout
```
skills/
  ├── windows/       # Window management, application launch, and process supervision
  ├── files/         # Canonicalized file search, read, write, copy, move, compress
  ├── vscode/        # VS Code workspaces, Python virtual environments, and tests
  ├── terminal/      # Controlled PowerShell cmdlets and process executions
  ├── git/           # Typed Git SCM operations (status, diff, log, commit, push)
  ├── docker/        # Container lifecycle management (status, start, stop, restart, logs)
  └── monitoring/    # In-process GPU NVML, CPU, RAM, Disk, and hardware controls
```

---

## 3. Manifest Specification (`manifest.json`)
Every `manifest.json` conforms to the following schema:
```json
{
  "name": "skill_name",
  "display_name": "Human Readable Title",
  "version": "1.0.0",
  "description": "Functional description of the skill",
  "triggers": ["list of user intent phrases"],
  "execution_tier": "tier1_native | tier2_shell | tier3_uia | tier4_visual",
  "risk_tier": "READ | LOCAL_REVERSIBLE | HIGH_IMPACT | DENIED",
  "required_permissions": ["LIST_OF_PERMISSIONS"],
  "default_timeout_seconds": 30.0,
  "validation_requirements": "Verification strategy description",
  "tools": [
    {
      "name": "tool_name",
      "description": "Tool functionality",
      "execution_tier": "tier1_native | tier2_shell",
      "risk_tier": "READ | LOCAL_REVERSIBLE | HIGH_IMPACT | DENIED",
      "timeout": 15.0,
      "requires_approval": false,
      "parameters": { ... }
    }
  ]
}
```

---

## 4. Integration with HostAgent
Skills register their tools into `DefensiveToolRegistry` and configure routing parameters in `OPERATION_POLICIES`.
When `HostAgent` classifies a request, it matches triggers to the relevant skill and delegates execution to `ExecutionRouter`.
