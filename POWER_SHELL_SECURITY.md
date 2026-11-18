# SON V3 — PowerShell & CLI Execution Security Model

## 1. Zero-Trust CLI Architecture
A key security vulnerability of AI agents is arbitrary shell execution (`os.system` or `subprocess.run(shell=True)`).
In SON V3 Phase 2, **arbitrary shell execution is completely eliminated**.

All subprocess executions are governed by `ControlledPowerShellRunner` (`core/execution/tier2_shell/powershell_runner.py`).

---

## 2. Hard Security Constraints

### A. Strict `shell=False`
All process spawning uses Python's `subprocess.Popen` with `shell=False`.
Arguments are passed as structured arrays (`list[str]`), preventing shell metacharacter injection (`;`, `&`, `|`, `` ` ``, `$`).

### B. Mandatory Safe Startup Flags
When PowerShell is invoked, it is strictly launched with:
```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -Command <Cmdlet>
```
- `-NoProfile`: Prevents user profile scripts from executing or hijacking cmdlets.
- `-NonInteractive`: Disallows interactive prompts that could stall the agent.
- `-ExecutionPolicy RemoteSigned`: Restricts script execution to signed or local scripts.

### C. Rejection of Arbitrary Scripts
The runner **never** accepts multiline or freeform PowerShell scripts from the model.
Only pre-approved `CommandTemplate` specifications or single allowlisted cmdlets with validated parameters are permitted.

### D. Parameter Validation & Token Denylist
Forbidden PowerShell tokens that trigger immediate execution refusal:
- `Invoke-Expression` / `iex`
- `DownloadString` / `Net.WebClient`
- `-EncodedCommand` / `-enc`
- `Start-Process`
- `System.Reflection`
- Semicolons and pipeline characters embedded in parameter values

### E. Centralized Binary Registry (`ExecutableRegistry`)
Executables cannot be run from arbitrary user paths.
The `ExecutableRegistry` validates binaries against a strict allowlist:
- `powershell.exe` / `pwsh.exe`
- `python.exe`
- `git.exe`
- `docker.exe`
- `code.cmd` / `code.exe`
- `wt.exe`
- `notepad.exe`
- `calc.exe`
Path resolution verifies that binaries reside inside trusted system directories (`System32`, `Program Files`, `LOCALAPPDATA\Programs`).
