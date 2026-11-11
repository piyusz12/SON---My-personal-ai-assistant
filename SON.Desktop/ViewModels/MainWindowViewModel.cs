// SON.Desktop/ViewModels/MainWindowViewModel.cs — Main Application Window Shell ViewModel
using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Models;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class MainWindowViewModel : ViewModelBase
    {
        private readonly INavigationService _navigationService;
        private readonly IIpcClient _ipcClient;
        private readonly IBackendProcessManager _backendProcessManager;

        [ObservableProperty]
        private string windowTitle = "SON Desktop — AI Operating Companion";

        [ObservableProperty]
        private NavigationPage activePage = NavigationPage.Home;

        [ObservableProperty]
        private ObservableObject? currentView;

        [ObservableProperty]
        private string connectionStatus = "Connecting...";

        [ObservableProperty]
        private bool isConnected = false;

        [ObservableProperty]
        private string activeUser = "Dad";

        [ObservableProperty]
        private string activeModel = "llama3.2:latest";

        [ObservableProperty]
        private string statusMessage = "SON Desktop Ready";

        [ObservableProperty]
        private bool isSidebarCollapsed = false;

        [ObservableProperty]
        private bool isCommandPaletteOpen = false;

        [ObservableProperty]
        private string commandPaletteSearch = string.Empty;

        [ObservableProperty]
        private bool isPrivacyPopupOpen = false;

        public ObservableCollection<CommandPaletteItem> AllCommands { get; } = new();
        public ObservableCollection<CommandPaletteItem> FilteredCommands { get; } = new();

        public MainWindowViewModel(
            INavigationService navigationService,
            IIpcClient ipcClient,
            IBackendProcessManager backendProcessManager)
        {
            _navigationService = navigationService;
            _ipcClient = ipcClient;
            _backendProcessManager = backendProcessManager;

            _navigationService.Navigated += (s, page) =>
            {
                ActivePage = page;
                CurrentView = _navigationService.CurrentViewModel;
            };

            _ipcClient.ConnectionChanged += (s, connected) =>
            {
                IsConnected = connected;
                ConnectionStatus = connected ? "Backend Online" : "Backend Offline";
                StatusMessage = connected ? "Connected to SON AI Orchestrator" : "Searching for backend service...";
                if (connected && !string.IsNullOrEmpty(_ipcClient.ActiveModel))
                {
                    ActiveModel = _ipcClient.ActiveModel;
                }
            };

            InitializeCommandPaletteItems();
        }

        private void InitializeCommandPaletteItems()
        {
            AllCommands.Clear();

            // Workspaces Navigation
            AllCommands.Add(new CommandPaletteItem { Title = "Go to Dashboard", Subtitle = "System overview & telemetry", Category = "Workspaces", Shortcut = "Ctrl+1", IconKey = "GeometryHome", ExecuteAction = () => Navigate(NavigationPage.Home) });
            AllCommands.Add(new CommandPaletteItem { Title = "Open AI Chat", Subtitle = "Converse with defensive AI agent", Category = "Workspaces", Shortcut = "Ctrl+2", IconKey = "GeometryChat", ExecuteAction = () => Navigate(NavigationPage.Chat) });
            AllCommands.Add(new CommandPaletteItem { Title = "Voice Interaction Mode", Subtitle = "Hands-free voice recognition", Category = "Workspaces", Shortcut = "Ctrl+3", IconKey = "GeometryVoice", ExecuteAction = () => Navigate(NavigationPage.Voice) });
            AllCommands.Add(new CommandPaletteItem { Title = "Browse Memory & Knowledge", Subtitle = "Structured facts store", Category = "Workspaces", Shortcut = "Ctrl+4", IconKey = "GeometryMemory", ExecuteAction = () => Navigate(NavigationPage.Memory) });
            AllCommands.Add(new CommandPaletteItem { Title = "Vision & Screen Analysis", Subtitle = "Screen understanding & OCR", Category = "Workspaces", Shortcut = "Ctrl+5", IconKey = "GeometryVision", ExecuteAction = () => Navigate(NavigationPage.Vision) });
            AllCommands.Add(new CommandPaletteItem { Title = "Automation Center", Subtitle = "Manage scheduled background tasks", Category = "Workspaces", Shortcut = "Ctrl+6", IconKey = "GeometryAutomation", ExecuteAction = () => Navigate(NavigationPage.Automation) });
            AllCommands.Add(new CommandPaletteItem { Title = "Files Workspace", Subtitle = "Inspect and summarize files", Category = "Workspaces", Shortcut = "Ctrl+7", IconKey = "GeometryFiles", ExecuteAction = () => Navigate(NavigationPage.Files) });
            AllCommands.Add(new CommandPaletteItem { Title = "Coding Studio", Subtitle = "AI code assistance & terminal", Category = "Workspaces", Shortcut = "Ctrl+8", IconKey = "GeometryCode", ExecuteAction = () => Navigate(NavigationPage.Code) });
            AllCommands.Add(new CommandPaletteItem { Title = "Task & Agent Execution", Subtitle = "Multi-step workflow monitor", Category = "Workspaces", Shortcut = "Ctrl+9", IconKey = "GeometryTasks", ExecuteAction = () => Navigate(NavigationPage.Tasks) });
            AllCommands.Add(new CommandPaletteItem { Title = "Security & Approvals Gateway", Subtitle = "Human authorization inbox", Category = "Workspaces", Shortcut = "Ctrl+0", IconKey = "GeometrySecurity", ExecuteAction = () => Navigate(NavigationPage.Security) });
            AllCommands.Add(new CommandPaletteItem { Title = "System Settings", Subtitle = "Configure runtime & themes", Category = "Workspaces", Shortcut = "Ctrl+,", IconKey = "GeometrySettings", ExecuteAction = () => Navigate(NavigationPage.Settings) });

            // Quick Actions
            AllCommands.Add(new CommandPaletteItem { Title = "Reconnect Python Backend", Subtitle = "Restart Named Pipe IPC handshake", Category = "Actions", Shortcut = "F5", IconKey = "GeometryCommand", ExecuteAction = () => _ = ReconnectBackendAsync() });
            AllCommands.Add(new CommandPaletteItem { Title = "Toggle Sidebar Collapse", Subtitle = "Maximize workspace area", Category = "Actions", Shortcut = "Ctrl+B", IconKey = "GeometrySidebar", ExecuteAction = ToggleSidebar });
            AllCommands.Add(new CommandPaletteItem { Title = "Inspect Zero-Trust Privacy", Subtitle = "Verify local execution status", Category = "Privacy", Shortcut = "", IconKey = "GeometrySecurity", ExecuteAction = TogglePrivacyPopup });

            FilterCommands(string.Empty);
        }

        partial void OnCommandPaletteSearchChanged(string value)
        {
            FilterCommands(value);
        }

        private void FilterCommands(string query)
        {
            FilteredCommands.Clear();
            var matches = string.IsNullOrWhiteSpace(query)
                ? AllCommands
                : AllCommands.Where(c => c.Title.Contains(query, StringComparison.OrdinalIgnoreCase) ||
                                         c.Subtitle.Contains(query, StringComparison.OrdinalIgnoreCase) ||
                                         c.Category.Contains(query, StringComparison.OrdinalIgnoreCase));

            foreach (var item in matches)
            {
                FilteredCommands.Add(item);
            }
        }

        public async Task InitializeAsync()
        {
            _navigationService.NavigateTo(NavigationPage.Home);

            StatusMessage = "Establishing connection with Python orchestrator...";
            bool ready = await _backendProcessManager.EnsureBackendRunningAsync();
            if (ready)
            {
                IsConnected = true;
                ConnectionStatus = "Backend Online";
                StatusMessage = "Connected to SON AI Orchestrator";
                if (!string.IsNullOrEmpty(_ipcClient.ActiveModel))
                {
                    ActiveModel = _ipcClient.ActiveModel;
                }
            }
            else
            {
                IsConnected = false;
                ConnectionStatus = "Backend Offline";
                StatusMessage = _backendProcessManager.LastError ?? "Could not connect to backend.";
            }
        }

        [RelayCommand]
        public void Navigate(NavigationPage page)
        {
            _navigationService.NavigateTo(page);
            IsCommandPaletteOpen = false;
        }

        [RelayCommand]
        public void ToggleSidebar()
        {
            IsSidebarCollapsed = !IsSidebarCollapsed;
        }

        [RelayCommand]
        public void ToggleCommandPalette()
        {
            IsCommandPaletteOpen = !IsCommandPaletteOpen;
            if (IsCommandPaletteOpen)
            {
                CommandPaletteSearch = string.Empty;
                FilterCommands(string.Empty);
            }
        }

        [RelayCommand]
        public void CloseCommandPalette()
        {
            IsCommandPaletteOpen = false;
        }

        [RelayCommand]
        public void ExecuteCommand(CommandPaletteItem? item)
        {
            if (item == null) return;
            IsCommandPaletteOpen = false;
            item.ExecuteAction?.Invoke();
        }

        [RelayCommand]
        public void TogglePrivacyPopup()
        {
            IsPrivacyPopupOpen = !IsPrivacyPopupOpen;
        }

        [RelayCommand]
        private async Task ReconnectBackendAsync()
        {
            StatusMessage = "Reconnecting to backend...";
            bool ready = await _backendProcessManager.EnsureBackendRunningAsync();
            StatusMessage = ready ? "Reconnected to SON AI Orchestrator." : "Reconnection failed.";
        }
    }
}
