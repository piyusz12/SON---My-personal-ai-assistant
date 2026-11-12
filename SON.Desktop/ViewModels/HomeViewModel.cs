// SON.Desktop/ViewModels/HomeViewModel.cs — Dashboard and System Telemetry ViewModel
using System;
using System.Threading;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Models;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class HomeViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;
        private readonly INavigationService _navigationService;
        private CancellationTokenSource? _telemetryCts;

        [ObservableProperty]
        private string connectionStatus = "Connecting...";

        [ObservableProperty]
        private bool isConnected = false;

        [ObservableProperty]
        private string activeUser = "Dad (Primary Owner)";

        [ObservableProperty]
        private string activeModel = "llama3.2:latest";

        [ObservableProperty]
        private double cpuPercent = 0;

        [ObservableProperty]
        private double ramPercent = 0;

        [ObservableProperty]
        private string ramUsageText = "0 / 16 GB";

        [ObservableProperty]
        private double gpuPercent = 0;

        [ObservableProperty]
        private double vramPercent = 0;

        [ObservableProperty]
        private string vramUsageText = "0 / 8 GB (RTX 4060)";

        [ObservableProperty]
        private string uptimeText = "0m";

        private readonly DateTime _sessionStart = DateTime.Now;

        public HomeViewModel(IIpcClient ipcClient, INavigationService navigationService)
        {
            _ipcClient = ipcClient;
            _navigationService = navigationService;
            _ipcClient.ConnectionChanged += OnConnectionChanged;
        }

        private void OnConnectionChanged(object? sender, bool connected)
        {
            IsConnected = connected;
            ConnectionStatus = connected ? "Connected" : "Disconnected (Searching for backend)";
            if (connected && !string.IsNullOrEmpty(_ipcClient.ActiveModel))
            {
                ActiveModel = _ipcClient.ActiveModel;
            }
        }

        public override void OnNavigatedTo()
        {
            base.OnNavigatedTo();
            IsConnected = _ipcClient.IsConnected;
            ConnectionStatus = IsConnected ? "Connected" : "Disconnected";
            if (!string.IsNullOrEmpty(_ipcClient.ActiveModel))
            {
                ActiveModel = _ipcClient.ActiveModel;
            }
            StartTelemetryPolling();
        }

        public override void OnNavigatedFrom()
        {
            base.OnNavigatedFrom();
            _telemetryCts?.Cancel();
            _telemetryCts?.Dispose();
            _telemetryCts = null;
        }

        private void StartTelemetryPolling()
        {
            _telemetryCts?.Cancel();
            _telemetryCts = new CancellationTokenSource();
            var token = _telemetryCts.Token;

            Task.Run(async () =>
            {
                while (!token.IsCancellationRequested)
                {
                    try
                    {
                        if (_ipcClient.IsConnected)
                        {
                            var telemetry = await _ipcClient.GetTelemetryAsync(token);
                            if (telemetry != null)
                            {
                                if (System.Windows.Application.Current?.Dispatcher != null)
                                {
                                    await System.Windows.Application.Current.Dispatcher.InvokeAsync(() => UpdateTelemetry(telemetry));
                                }
                                else
                                {
                                    UpdateTelemetry(telemetry);
                                }
                            }
                        }

                        await Task.Delay(2000, token);
                    }
                    catch (OperationCanceledException)
                    {
                        break;
                    }
                    catch (Exception) { }
                }
            }, token);
        }

        private void UpdateTelemetry(HardwareTelemetryResult t)
        {
            CpuPercent = Math.Round(t.CpuPercent, 1);
            if (t.RamTotalBytes > 0)
            {
                RamPercent = Math.Round((double)t.RamUsedBytes / t.RamTotalBytes * 100, 1);
                RamUsageText = $"{t.RamUsedGb:F1} / {t.RamTotalGb:F1} GB";
            }
            GpuPercent = Math.Round(t.GpuPercent, 1);
            if (t.VramTotalBytes > 0)
            {
                VramPercent = Math.Round((double)t.VramUsedBytes / t.VramTotalBytes * 100, 1);
                VramUsageText = $"{t.VramUsedGb:F1} / {t.VramTotalGb:F1} GB";
            }
            if (!string.IsNullOrEmpty(t.ModelName))
            {
                ActiveModel = t.ModelName;
            }

            var elapsed = DateTime.Now - _sessionStart;
            UptimeText = elapsed.TotalHours >= 1
                ? $"{(int)elapsed.TotalHours}h {elapsed.Minutes:D2}m"
                : $"{elapsed.Minutes}m {elapsed.Seconds:D2}s";
        }

        [ObservableProperty]
        private string heroPromptText = string.Empty;

        [RelayCommand]
        private void NavigateToChat() => _navigationService.NavigateTo(NavigationPage.Chat);

        [RelayCommand]
        private void NavigateToVoice() => _navigationService.NavigateTo(NavigationPage.Voice);

        [RelayCommand]
        private void NavigateToMemory() => _navigationService.NavigateTo(NavigationPage.Memory);

        [RelayCommand]
        private void NavigateToVision() => _navigationService.NavigateTo(NavigationPage.Vision);

        [RelayCommand]
        private void NavigateToAutomation() => _navigationService.NavigateTo(NavigationPage.Automation);

        [RelayCommand]
        private void NavigateToFiles() => _navigationService.NavigateTo(NavigationPage.Files);

        [RelayCommand]
        private void NavigateToCode() => _navigationService.NavigateTo(NavigationPage.Code);

        [RelayCommand]
        private void NavigateToTasks() => _navigationService.NavigateTo(NavigationPage.Tasks);

        [RelayCommand]
        private void NavigateToSettings() => _navigationService.NavigateTo(NavigationPage.Settings);

        [RelayCommand]
        private void NavigateToSecurity() => _navigationService.NavigateTo(NavigationPage.Security);

        [RelayCommand]
        private void SubmitHeroPrompt()
        {
            if (string.IsNullOrWhiteSpace(HeroPromptText))
            {
                _navigationService.NavigateTo(NavigationPage.Chat);
                return;
            }

            // Transfer hero prompt to chat viewmodel
            _navigationService.NavigateTo(NavigationPage.Chat);
            if (_navigationService.CurrentViewModel is ChatViewModel chatVm)
            {
                chatVm.InputText = HeroPromptText;
                HeroPromptText = string.Empty;
                if (chatVm.SendMessageCommand.CanExecute(null))
                {
                    chatVm.SendMessageCommand.Execute(null);
                }
            }
        }
    }
}

