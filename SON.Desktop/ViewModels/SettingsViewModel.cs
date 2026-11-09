// SON.Desktop/ViewModels/SettingsViewModel.cs — Application Settings ViewModel
using System;
using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class SettingsViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;

        [ObservableProperty]
        private string selectedTheme = "Midnight Dark (Default)";

        [ObservableProperty]
        private string ipcPipeName = @"\\.\pipe\son_desktop_ipc";

        [ObservableProperty]
        private string selectedModel = "llama3.2:latest";

        [ObservableProperty]
        private string ollamaHost = "http://localhost:11434";

        [ObservableProperty]
        private bool launchOnStartup = false;

        [ObservableProperty]
        private bool hardwareAccelEnabled = true;

        [ObservableProperty]
        private string hardwareSpecs = "AMD Ryzen 7 7840HS (16 Threads) | NVIDIA GeForce RTX 4060 Laptop GPU (8GB VRAM) | 16GB DDR5 RAM";

        [ObservableProperty]
        private string appVersion = "SON Desktop v3.0.0 (Phase 1 LTS)";

        [ObservableProperty]
        private string backendStatus = "Checking...";

        public ObservableCollection<string> AvailableThemes { get; } = new()
        {
            "Midnight Dark (Default)",
            "Slate Dark",
            "OLED Black",
        };

        public ObservableCollection<string> AvailableModels { get; } = new()
        {
            "llama3.2:latest",
            "qwen2.5-coder:7b",
            "deepseek-r1:8b",
            "qwen3-vl:8b",
            "llama3.2-vision:latest",
        };

        public SettingsViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
        }

        public override void OnNavigatedTo()
        {
            base.OnNavigatedTo();
            BackendStatus = _ipcClient.IsConnected ? "Connected (Local Named Pipe)" : "Disconnected";
            if (!string.IsNullOrEmpty(_ipcClient.ActiveModel))
            {
                SelectedModel = _ipcClient.ActiveModel;
            }
        }
    }
}

