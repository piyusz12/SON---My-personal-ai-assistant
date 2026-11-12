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
            "llama3.1:latest",
            "Qwen3:8b",
            "qwen2.5-coder:7b",
            "deepseek-r1:8b",
            "qwen3-vl:8b",
            "llama3.2-vision:latest",
        };

        public SettingsViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
            LoadSettings();
        }

        partial void OnSelectedModelChanged(string value)
        {
            SaveSettings();
        }

        partial void OnSelectedThemeChanged(string value)
        {
            SaveSettings();
        }

        private static string GetSettingsFilePath()
        {
            string repoDir = @"C:\AI\SON\data";
            if (System.IO.Directory.Exists(repoDir))
            {
                return System.IO.Path.Combine(repoDir, "app_settings.json");
            }
            string appData = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SON", "data");
            System.IO.Directory.CreateDirectory(appData);
            return System.IO.Path.Combine(appData, "app_settings.json");
        }

        private void SaveSettings()
        {
            try
            {
                var file = GetSettingsFilePath();
                var json = System.Text.Json.JsonSerializer.Serialize(new
                {
                    DefaultModel = SelectedModel,
                    Theme = SelectedTheme,
                    OllamaHost = OllamaHost,
                    LaunchOnStartup = LaunchOnStartup
                }, new System.Text.Json.JsonSerializerOptions { WriteIndented = true });
                System.IO.File.WriteAllText(file, json);
            }
            catch { }
        }

        private void LoadSettings()
        {
            try
            {
                var file = GetSettingsFilePath();
                if (System.IO.File.Exists(file))
                {
                    var text = System.IO.File.ReadAllText(file);
                    using var doc = System.Text.Json.JsonDocument.Parse(text);
                    if (doc.RootElement.TryGetProperty("DefaultModel", out var modelProp) && modelProp.GetString() is string m && !string.IsNullOrWhiteSpace(m))
                    {
                        SelectedModel = m;
                    }
                }
            }
            catch { }
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

        [RelayCommand]
        public async Task TestConnectionAsync()
        {
            BackendStatus = "Testing connection...";
            try
            {
                if (!_ipcClient.IsConnected)
                {
                    await _ipcClient.ConnectAsync();
                }
                BackendStatus = _ipcClient.IsConnected
                    ? "Connection verified! Python IPC & AI Orchestrator reachable."
                    : "Failed: Backend Named Pipe not responding.";
            }
            catch (Exception ex)
            {
                BackendStatus = $"Connection test error: {ex.Message}";
            }
        }
    }
}

