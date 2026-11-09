// SON.Desktop/ViewModels/VoiceViewModel.cs — Voice Interface ViewModel
using System;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class VoiceViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;

        [ObservableProperty]
        private bool isRecording = false;

        [ObservableProperty]
        private string voiceStatus = "Standby — Microphone ready";

        [ObservableProperty]
        private string selectedAudioDevice = "Default System Microphone";

        [ObservableProperty]
        private string selectedTtsEngine = "Piper TTS (Local ONNX)";

        [ObservableProperty]
        private string selectedSttEngine = "Faster-Whisper (CUDA accelerated)";

        [ObservableProperty]
        private string backendStatus = "Offline";

        public VoiceViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
            _ipcClient.ConnectionChanged += (s, connected) =>
            {
                BackendStatus = connected ? "Online (Ready for streaming)" : "Offline (Backend disconnected)";
            };
        }

        public override void OnNavigatedTo()
        {
            base.OnNavigatedTo();
            BackendStatus = _ipcClient.IsConnected ? "Online (Ready for streaming)" : "Offline (Backend disconnected)";
        }

        [RelayCommand]
        private void ToggleRecording()
        {
            if (!_ipcClient.IsConnected)
            {
                VoiceStatus = "Cannot record: Python backend is offline.";
                IsRecording = false;
                return;
            }

            IsRecording = !IsRecording;
            VoiceStatus = IsRecording
                ? "Listening... Speak now into your microphone."
                : "Standby — Audio processing complete.";
        }
    }
}

