# SON Desktop — Component Hierarchy & MVVM Structure

## 1. Desktop Client Component Hierarchy (C# / .NET 8 WPF)

```
SonDesktop.App (Entry Point & DI Host)
├── App.xaml / App.xaml.cs
│   ├── IHost / Microsoft.Extensions.DependencyInjection
│   ├── UnhandledException & Crash Reporter
│   └── Global Resource Dictionaries (Colors, Brushes, Styles, Templates)
│
├── Views/
│   ├── MainWindow.xaml (Shell Window)
│   │   ├── NavigationSidebarControl.xaml (Left 10-Item Nav Rail)
│   │   ├── TopHeaderControl.xaml (Global Search, Window Controls, Mini Telemetry)
│   │   ├── NotificationHostControl.xaml (Toasts, Floating Approval Banners)
│   │   ├── BottomStatusBarControl.xaml (Ollama status, IPC latency, VRAM bar)
│   │   └── ContentPresenter (Hosts Active View)
│   │
│   ├── Home/
│   │   ├── HomeView.xaml
│   │   └── Controls/ (HardwareGauge, TelemetryCard, QuickActionTile)
│   ├── Chat/
│   │   ├── ChatView.xaml
│   │   └── Controls/ (MessageList, ChatInputBox, ThinkingExpander, ApprovalCard, CodeBlock)
│   ├── Voice/
│   │   ├── VoiceView.xaml
│   │   └── Controls/ (AudioWaveformVisualizer, MicSensitivityBar, DeviceSelector)
│   ├── Memory/
│   │   ├── MemoryView.xaml
│   │   └── Controls/ (MemoryCardList, RagCollectionGrid, AddMemoryModal)
│   ├── Vision/
│   │   ├── VisionView.xaml
│   │   └── Controls/ (ScreenPreviewCanvas, MarqueeSelector, OcrResultPanel)
│   ├── PcControl/
│   │   ├── PcControlView.xaml
│   │   └── Controls/ (AppLauncherGrid, ScopedFileTree, SliderGroup)
│   ├── Automation/
│   │   ├── AutomationView.xaml
│   │   └── Controls/ (RoutineList, StepTimeline, RoutineHistoryTable)
│   ├── Models/
│   │   ├── ModelView.xaml
│   │   └── Controls/ (ModelCatalogCard, VramBudgetMeter, DownloadProgressBar)
│   ├── Security/
│   │   ├── SecurityView.xaml
│   │   └── Controls/ (PendingApprovalInbox, SecurityAuditStream, ToolRiskMatrix)
│   └── Settings/
│       ├── SettingsView.xaml
│       └── Controls/ (ThemeSelector, AudioConfigGroup, PrivacyToggles)
│
├── ViewModels/ (CommunityToolkit.Mvvm ObservableObjects)
│   ├── MainWindowViewModel.cs (Navigation orchestration, Global hotkeys, Status bar)
│   ├── HomeViewModel.cs (Hardware telemetry polling, Quick launch commands)
│   ├── ChatViewModel.cs (Streaming message buffers, Cancellation tokens, History)
│   ├── VoiceViewModel.cs (NAudio recording events, Audio player state, PTT hotkey)
│   ├── MemoryViewModel.cs (Memory search queries, RAG collection state)
│   ├── VisionViewModel.cs (Screenshot capture trigger, Image decoding)
│   ├── PcControlViewModel.cs (Application launch triggers, Scoped directory navigation)
│   ├── AutomationViewModel.cs (Routine execution controls, Status listeners)
│   ├── ModelViewModel.cs (Ollama model queries, Model switch dispatch)
│   ├── SecurityViewModel.cs (Pending approval collection, Audit log live updates)
│   └── SettingsViewModel.cs (Configuration binding, Theme updates)
│
├── Services/ (Client Side Core Services)
│   ├── IIpcClientService.cs / NamedPipeIpcClient.cs (Low-level named pipe transport)
│   ├── INavigationService.cs / NavigationService.cs (View switching & history)
│   ├── IHardwareMonitorService.cs / HardwareMonitorService.cs (WMI & NVML telemetry)
│   ├── IAudioService.cs / AudioService.cs (NAudio capture, Waveform FFT, Sound playback)
│   ├── INotificationService.cs / NotificationService.cs (Toasts & Approval popups)
│   └── IThemeService.cs / ThemeService.cs (Dynamic brush and accent management)
│
└── Models/ (Strongly-Typed DTOs matching Python Contract)
    ├── IpcMessage.cs (Type, RequestId, Action, Payload)
    ├── ChatMessageModel.cs (Id, Role, Content, IsThinking, ToolCalls)
    ├── HardwareTelemetryModel.cs (CpuPercent, RamUsed, GpuPercent, VramUsedBytes)
    ├── ApprovalRequestModel.cs (RequestId, ToolName, Arguments, RiskLevel, ExpiresAt)
    └── InstalledModelInfo.cs (Name, SizeBytes, ParameterCount, Quantization)
```

---

## 2. Backend Service Component Hierarchy (Python 3.13)

```
C:\AI\SON\
├── core/
│   ├── orchestrator.py (SonOrchestrator: Central turn dispatcher & coordinator)
│   ├── action_executor.py (ActionExecutor: Typed gateway, bounds, timeouts, result validation)
│   ├── router.py (SecurityRouter: Fail-closed fallback verification)
│   ├── brain.py (Reasoning turn management)
│   │
│   ├── security/
│   │   ├── schemas.py (Pydantic models: ToolExecutionRequest, ToolExecutionResult, StrictToolParams)
│   │   ├── policy_engine.py (SecurityPolicyEngine: Risk tiers, tool authorization)
│   │   ├── approval_manager.py (ApprovalManager: Cryptographic token verification & single-use consumption)
│   │   ├── tool_registry.py (DefensiveToolRegistry: 25 strictly typed tool registrations)
│   │   ├── result_validator.py (ResultValidator: 512KB size bound, secret redaction, untrusted XML fences)
│   │   ├── identity.py (IdentityManager: User roles, RBAC authorization)
│   │   ├── session_manager.py (SessionManager: Cryptographic session lifecycle)
│   │   ├── audit_logger.py (SecurityAuditLogger: Tamper-resistant JSONL structured audit trail)
│   │   ├── secure_file_service.py (SecureFileService: Canonical workspace boundaries)
│   │   └── secure_database_service.py (SecureDatabaseService: Parameterized SQLite queries)
│   │
│   └── interfaces/
│       ├── contract.py (InterfaceRequest, InterfaceResponse, Standard Enums)
│       ├── base_adapter.py (BaseInterfaceAdapter: Asynchronous thread pool dispatch)
│       └── desktop_adapter.py (DesktopInterfaceAdapter: GUI telemetry & approval hooks)
│
├── services/
│   ├── ipc/ (NEW: Dedicated Local IPC Service)
│   │   ├── named_pipe_server.py (Asyncio Named Pipe listener: \\.\pipe\son_desktop_ipc)
│   │   ├── protocol_dispatcher.py (JSON message parsing, routing, and response serialization)
│   │   └── push_broadcaster.py (Push stream for token generation, telemetry, and approvals)
│   │
│   └── sandbox/
│       └── e2b_service.py (E2BSandboxService: Isolated MicroVM code execution)
│
└── tools/
    ├── windows_control.py (Native Windows controls via shell=False)
    ├── web.py (DuckDuckGo search & SSRF-protected webpage reader)
    ├── docker_control.py (Docker CLI subprocess control)
    └── automation.py (Routine workflow engine)
```

