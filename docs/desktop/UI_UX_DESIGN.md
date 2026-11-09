# SON Desktop — UI/UX Design System & Wireframes

## 1. Design Philosophy & Visual Language

SON Desktop blends the ergonomic density of an engineering workstation with the polish of modern Windows 11 Fluent Design:
- **Default Aesthetic**: Deep Midnight Dark Theme with high-contrast emerald and cyan accents.
- **Hierarchy & Restraint**: Subtle 1px borders, gentle 8px/12px corner radii, and soft card drop shadows rather than loud gradients or neon glows.
- **Zero Clutter**: Clean information architecture; non-critical metadata is tucked into collapsible inspect panels.
- **Micro-Interactions**: Restrained 150ms ease-out transitions for view swaps, button hovers, and approval banners.

---

## 2. Design System Tokens

### A. Color Palette
```
Background Deep:       #0A0C10  (Main window frame & shell)
Surface Neutral:       #12161F  (Content views, stage background)
Card / Panel Surface:  #1A1F2C  (Cards, message bubbles, input boxes)
Card Border Subtle:    #262D3D  (1px borders on cards and dividers)
Card Border Hover:     #3B445C  (Interactive hover highlight)

Accent Primary (Green): #10B981  (Success, verified states, primary send actions)
Accent Cyan:           #06B6D4  (Streaming indicators, voice waveforms, telemetry)
Accent Purple:         #8B5CF6  (Memory, RAG, and knowledge tags)
Warning Amber:         #F59E0B  (Medium risk actions, VRAM warnings >85%)
Danger Crimson:        #EF4444  (High/Critical risk actions, policy denials, emergency stop)

Text Primary:          #F8FAFC  (High contrast text, 95% opacity)
Text Secondary:        #94A3B8  (Labels, descriptions, 70% opacity)
Text Muted / Disabled: #64748B  (Placeholders, timestamps, 45% opacity)
```

### B. Typography (Windows Native Segoe UI Variable)
- **Display Header**: `Segoe UI Variable Display`, 24pt SemiBold
- **Section Title**: `Segoe UI Variable Display`, 16pt SemiBold
- **Card Subtitle**: `Segoe UI Variable Text`, 12pt Medium
- **Body Text**: `Segoe UI Variable Text`, 10.5pt Regular (Line height 1.45)
- **Monospace & Code**: `Cascadia Code` / `Consolas`, 9.5pt Regular

---

## 3. Global Desktop Shell Wireframe

```
+----------------------------------------------------------------------------------------------------+
|  [SON LOGO]  SON Desktop v3.0            [ Global Command Bar / Search (Ctrl+K) ]   [GPU: 3.8GB] [-][#][X] |
+---+------------------------------------------------------------------------------------------------+
| H |                                                                                                |
| O |  [ VIEW HEADER: Title, Breadcrumbs, Action Toolbar ]                                           |
| M |------------------------------------------------------------------------------------------------|
| E |                                                                                                |
|---|                                                                                                |
| C |                                                                                                |
| H |                                                                                                |
| A |                                                                                                |
| T |                                     MAIN CONTENT STAGE                                         |
|---|                        (Swappable Views: Home, Chat, Voice, Memory,                           |
| V |                         Vision, PC Control, Auto, Models, Security, Settings)                 |
| O |                                                                                                |
| I |                                                                                                |
|---|                                                                                                |
| M |                                                                                                |
| E |                                                                                                |
| M |                                                                                                |
|---|                                                                                                |
| S |                                                                                                |
| E |                                                                                                |
| C |                                                                                                |
+---+------------------------------------------------------------------------------------------------+
| [OLLAMA: llama3.2 (Active)]  |  [IPC: Connected (2ms)]  |  [VRAM: 42% (3.4/8GB)]  |  [Approvals: 0] |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Key Module Screen Wireframes

### A. Home Dashboard
```
+----------------------------------------------------------------------------------------------------+
| Good evening, Dad. SON is standing by.                                  [+ New Conversation] [Voice] |
+------------------------------------+-----------------------------------+---------------------------+
| SYSTEM HARDWARE VITALS             | AI ENGINE HEALTH                  | QUICK ACTIONS             |
| CPU:  [||||||||..........] 38%     | Active Model: llama3.2:latest     | [>] Open VS Code          |
| RAM:  [||||||||||||......] 9.2/16GB| Ollama Status: Healthy (Loopback) | [>] Check Daily Weather   |
| GPU:  [||||..............] 18%     | Backend IPC: Connected (1.2ms)    | [>] Clean System Temp     |
| VRAM: [||||||||..........] 3.4/8GB | Fast Whisper: Ready (CUDA)        | [>] Start Docker Dev      |
+------------------------------------+-----------------------------------+---------------------------+
| RECENT ACTIVITIES (AUDIT STREAM)                                       | PENDING SECURITY TASKS    |
| [18:24] Tool 'web_search' -> Completed (184ms)                         | No pending approvals.     |
| [18:22] Tool 'docker_list_containers' -> Success (12ms)                | All systems protected by  |
| [18:15] Security Policy: Replay token test -> BLOCKED                  | PolicyEngine.             |
+------------------------------------------------------------------------+---------------------------+
```

### B. AI Chat View (with Embedded Approval Card)
```
+----------------------------------------------------------------------------------------------------+
| Thread: Workstation Deployment Plan                            Model: llama3.2 [v]  [Clear] [Export]|
+----------------------------------------------------------------------------------------------------+
| (User) Dad: Delete the obsolete temporary build folder at C:\AI\SON\tmp_build                       |
|                                                                                                    |
| (SON Assistant):                                                                                   |
| > [Thinking: User requested directory deletion. Tool 'delete_path' classified as HIGH RISK.]       |
|                                                                                                    |
| +------------------------------------------------------------------------------------------------+ |
| | [!] SECURITY APPROVAL REQUIRED                                              Expires in: 01:48  | |
| | Action: delete_path                                                         Risk Tier: HIGH    | |
| | Target: C:\AI\SON\tmp_build                                                                    | |
| | Justification: Destructive directory removal requested by primary user.                        | |
| |                                                                                                | |
| |                                          [ DENY ACTION ]     [ APPROVE & EXECUTE (Dad) ]       | |
| +------------------------------------------------------------------------------------------------+ |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
| [Type a message or press Shift+Enter for newline...                       ] [Attach] [Mic] [ Send ] |
+----------------------------------------------------------------------------------------------------+
```

### C. Voice Assistant (HUD / Canvas View)
```
+----------------------------------------------------------------------------------------------------+
| VOICE COMMAND STATION                                                                              |
|                                                                                                    |
|                           ((((((((   LISTENING...   ))))))))                                       |
|                                                                                                    |
|                    ~.~^~^~_~-~^~^~_~-~^~^~_~-~^~^~_~-~^~^~_~-~^~                                  |
|                                   (Live Waveform Canvas)                                           |
|                                                                                                    |
| Last Transcription: "SON, what is my current GPU temperature and VRAM usage?"                      |
| Synthesizer Status: Speaking ("Your RTX 4060 is running at 48 degrees with 3.4 gigabytes...")      |
|                                                                                                    |
| [ Push to Talk (Hold Space) ]           [ Cancel / Stop Speaking (Esc) ]        [ Settings ]       |
+----------------------------------------------------------------------------------------------------+
```

---

## 5. Keyboard Navigation & Accessibility

- `Ctrl + K`: Open Global Command Palette / Search.
- `Ctrl + N`: Create new chat thread.
- `Ctrl + 1` through `Ctrl + 0`: Switch directly between navigation views.
- `Space` (Hold): Push-to-Talk voice dictation (when in Voice mode).
- `Esc`: Stop LLM generation or cancel active TTS playback.
- `Tab` / `Shift + Tab`: Predictable focus traversal across interactive controls.
- All controls feature explicit high-contrast focus rings and `AutomationProperties.Name` for Windows Narrator support.

