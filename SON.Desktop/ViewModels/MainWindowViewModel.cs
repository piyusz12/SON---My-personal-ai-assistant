// SON.Desktop/ViewModels/MainWindowViewModel.cs — Main Application Window Shell ViewModel
using System;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
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
        }

        public async Task InitializeAsync()
        {
            // Initial navigation to Home
            _navigationService.NavigateTo(NavigationPage.Home);

            // Connect or start backend
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
        private void Navigate(NavigationPage page)
        {
            _navigationService.NavigateTo(page);
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

