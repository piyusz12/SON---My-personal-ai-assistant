# SON V3 — Four-Tier Execution Router

## 1. Architectural Role
The `ExecutionRouter` (`core/execution/execution_router.py`) is the central dispatching authority for all Windows computer interactions.
It strictly decouples model reasoning from operating system execution:
- **No Direct Shell Access**: The LLM outputs structured tool requests, never raw command strings.
- **Fail-Closed Risk Tiers**: Operations in the `DENIED` tier are rejected immediately without execution.
- **Highest Reliable Tier Preference**: The router always prioritizes Tier 1 (Native) over Tier 2 (Shell).

---

## 2. Execution Tiers

| Tier | Subsystem | Implementation | Status |
|---|---|---|---|
| **Tier 1** | Native Windows APIs | `core/execution/tier1_native/` (ctypes, psutil, pathlib, win32) | **Operational** |
| **Tier 2** | Controlled PowerShell & CLI | `core/execution/tier2_shell/` (allowlisted templates, shell=False) | **Operational** |
| **Tier 3** | Windows UI Automation | `core/execution/tier3_uia/` (accessibility tree interaction) | Planned (Phase 3) |
| **Tier 4** | Visual Computer Use | `core/execution/tier4_visual/` (screen vision & coordinate click) | Planned (Phase 4) |

---

## 3. Request Pipeline

```
HostAgent.route_execution(tool_name, arguments, context)
    │
    ▼
ExecutionRouter.route()
    ├── 1. Evaluate OperationPolicy (READ / LOCAL_REVERSIBLE / HIGH_IMPACT / DENIED)
    ├── 2. Check Context Timeout (reject if expired)
    ├── 3. If DENIED -> Return ExecutionResult(status=DENIED)
    ├── 4. Select Tier Adapter (NativeTier or ShellTier)
    ├── 5. Execute Action under explicit timeout
    ├── 6. Post-Execution Verification (check_path_exists, check_no_error, etc.)
    └── 7. Return Structured ExecutionResult
```

---

## 4. Structured Results & Verification

Every execution returns an `ExecutionResult` containing:
- `status`: `SUCCESS`, `FAILURE`, `DENIED`, `TIMEOUT`, `PENDING_APPROVAL`, `UNAVAILABLE`
- `output`: Result payload (dictionaries, lists, or text)
- `error`: Error details if failed
- `tier_used`: TierLevel utilized
- `duration_ms`: Wall-clock execution time
- `verified`: Boolean indicating whether the state-change verification strategy passed
- `routing_decision`: Complete trace of the routing policy, permissions, and timeout
