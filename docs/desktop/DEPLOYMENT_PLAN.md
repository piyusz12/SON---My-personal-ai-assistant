# SON Desktop — Packaging, Deployment & Distribution Plan

## 1. Distribution Architecture

SON Desktop is distributed as a self-contained, professional Windows desktop installer package (`SON-Desktop-Setup.exe`) designed for Windows 11 x64 systems.

```
SON-Desktop-Setup.exe (Inno Setup / WiX Installer)
├── Client Binary: SonDesktop.exe (.NET 8 Self-Contained, Win-x64, ReadyToRun)
├── Embedded Python Engine: python-3.13-embed-amd64/ (or Virtualenv Bundle)
├── AI Engine Scripts: C:\AI\SON\ (Core orchestrator, agents, tools, security)
├── Application Assets: Icons, Sound Effects, Default Configuration
└── Dependency Checkers: Ollama presence, NVIDIA GPU / CUDA 13.3 detection
```

---

## 2. Directory Layout & Storage Segregation

To maintain clean separation between read-only application binaries and mutable user data:

| Directory | Location | Purpose |
| :--- | :--- | :--- |
| **Application Binaries** | `%LocalAppData%\Programs\SON-Desktop\` | `SonDesktop.exe`, DLLs, embedded Python runtime, core scripts (Read-Only) |
| **User Data & Database** | `%AppData%\SON-Desktop\data\` | SQLite memory database, conversation history, RAG documents |
| **Audit & Diagnostics** | `%AppData%\SON-Desktop\logs\` | Tamper-resistant `audit.jsonl`, engine crash logs |
| **Cache & Temp Storage**| `%LocalAppData%\Temp\SON-Desktop\` | Ephemeral audio recordings, screenshot staging, scratch scripts |

---

## 3. Compilation & Packaging Commands

### A. C# WPF Frontend (Single-File Self-Contained)
```powershell
dotnet publish src/desktop/SonDesktop/SonDesktop.csproj `
    -c Release `
    -r win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:PublishReadyToRun=true `
    -o dist/desktop/
```

### B. Python Backend Environment Freezing
```powershell
pip freeze > dist/backend/requirements.txt
# Package core source files into dist/backend/
Copy-Item -Recurse core, agents, services, tools, brain.py, son.py dist/backend/
```

### C. Inno Setup Compiler (`setup.iss`)
```iss
[Setup]
AppName=SON Desktop
AppVersion=3.0.0
DefaultDirName={localappdata}\Programs\SON-Desktop
DefaultGroupName=SON Desktop
OutputDir=dist\installer
OutputBaseFilename=SON-Desktop-Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Launch SON Desktop automatically on Windows startup"; GroupDescription: "Startup:"

[Files]
Source: "dist\desktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "dist\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\SON Desktop"; Filename: "{app}\SonDesktop.exe"
Name: "{commondesktop}\SON Desktop"; Filename: "{app}\SonDesktop.exe"; Tasks: desktopicon
Name: "{userstartup}\SON Desktop"; Filename: "{app}\SonDesktop.exe"; Parameters: "--minimized"; Tasks: startupicon
```

---

## 4. Uninstallation Cleanliness

The installer includes a complete, safe uninstaller (`unins000.exe`):
1. Prompts user: *"Would you like to preserve your conversation history and memories?"*
   - **If Yes**: Keeps `%AppData%\SON-Desktop\data\`.
   - **If No**: Completely purges `%AppData%\SON-Desktop\`.
2. Removes all files in `%LocalAppData%\Programs\SON-Desktop\`.
3. Cleans up Windows registry startup keys and Start Menu shortcuts.
4. Leaves no orphaned processes or background services.

