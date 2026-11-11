// SON.Desktop/ViewModels/ChatViewModel.cs — Chat Conversation Interface ViewModel
using System;
using System.Collections.ObjectModel;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Models;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class ChatViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;
        private readonly IBackendProcessManager? _backendProcessManager;
        private CancellationTokenSource? _sendCts;

        [ObservableProperty]
        private string inputText = string.Empty;

        [ObservableProperty]
        private bool isSending = false;

        [ObservableProperty]
        private bool isConnected = false;

        [ObservableProperty]
        private string? errorMessage;

        public ObservableCollection<ChatMessage> Messages { get; } = new();

        public ChatViewModel(IIpcClient ipcClient, IBackendProcessManager? backendProcessManager = null)
        {
            _ipcClient = ipcClient;
            _backendProcessManager = backendProcessManager;
            _ipcClient.ConnectionChanged += (s, connected) =>
            {
                IsConnected = connected;
                if (!connected)
                {
                    ErrorMessage = "Backend disconnected. Please check that the Python service is active.";
                }
                else
                {
                    ErrorMessage = null;
                }
            };

            // Seed initial greeting
            Messages.Add(new ChatMessage
            {
                Sender = "SON",
                IsUser = false,
                Text = "Hello! I am SON, your personal AI desktop assistant. How can I assist you today?",
                Timestamp = DateTime.Now,
            });
        }

        public override void OnNavigatedTo()
        {
            base.OnNavigatedTo();
            IsConnected = _ipcClient.IsConnected;
        }

        [RelayCommand]
        private async Task SendMessageAsync()
        {
            if (string.IsNullOrWhiteSpace(InputText) || IsSending) return;

            string prompt = InputText.Trim();
            InputText = string.Empty;
            ErrorMessage = null;

            // 1. Add user message
            var userMsg = new ChatMessage
            {
                Sender = "You",
                IsUser = true,
                Text = prompt,
                Timestamp = DateTime.Now,
            };
            Messages.Add(userMsg);

            // 2. Add loading assistant bubble
            var assistantMsg = new ChatMessage
            {
                Sender = "SON",
                IsUser = false,
                IsLoading = true,
                Text = string.Empty,
                Timestamp = DateTime.Now,
            };
            Messages.Add(assistantMsg);

            IsSending = true;
            _sendCts?.Dispose();
            _sendCts = new CancellationTokenSource();

            try
            {
                if (!_ipcClient.IsConnected)
                {
                    bool connected = false;
                    if (_backendProcessManager != null)
                    {
                        connected = await _backendProcessManager.EnsureBackendRunningAsync(_sendCts.Token);
                    }
                    else
                    {
                        connected = await _ipcClient.ConnectAsync(_sendCts.Token);
                        if (connected)
                        {
                            await _ipcClient.HandshakeAsync("usr_primary", _sendCts.Token);
                        }
                    }

                    if (!connected)
                    {
                        assistantMsg.IsLoading = false;
                        string detail = _backendProcessManager?.LastError ?? "Named pipe '\\\\.\\pipe\\son_desktop_ipc' is unreachable.";
                        assistantMsg.Error = $"Unable to connect to Python backend. {detail}";
                        assistantMsg.Text = $"Connection Error: Failed to reach the Python AI orchestrator.\n\nDetails: {detail}";
                        ErrorMessage = assistantMsg.Error;
                        return;
                    }
                }

                var result = await _ipcClient.SendChatAsync(prompt, "conv_desktop", _sendCts.Token);

                assistantMsg.IsLoading = false;
                if (result != null)
                {
                    assistantMsg.Text = !string.IsNullOrEmpty(result.Response) ? result.Response : (result.Error ?? "Turn completed with no output.");
                    if (result.ToolResults != null && result.ToolResults.Count > 0)
                    {
                        assistantMsg.ToolResults = result.ToolResults;
                    }
                    if (result.Status == "PENDING_APPROVAL" || result.Status == "awaiting_approval")
                    {
                        assistantMsg.Text += "\n\n⚠️ Action paused: This operation requires human approval before proceeding.";
                    }
                    if (!string.IsNullOrEmpty(result.Error))
                    {
                        assistantMsg.Error = result.Error;
                    }
                }
                else
                {
                    assistantMsg.Text = "No response received from the backend service.";
                    assistantMsg.Error = "Timeout or empty response.";
                }
            }
            catch (OperationCanceledException)
            {
                assistantMsg.IsLoading = false;
                assistantMsg.Text = "Turn cancelled by user.";
            }
            catch (Exception ex)
            {
                assistantMsg.IsLoading = false;
                assistantMsg.Error = ex.Message;
                assistantMsg.Text = $"Error processing request: {ex.Message}";
                ErrorMessage = ex.Message;
            }
            finally
            {
                IsSending = false;
                _sendCts?.Dispose();
                _sendCts = null;
            }
        }

        [RelayCommand]
        private void StopGeneration()
        {
            if (IsSending && _sendCts != null)
            {
                _sendCts.Cancel();
            }
        }

        [RelayCommand]
        private void ClearChat()
        {
            Messages.Clear();
            Messages.Add(new ChatMessage
            {
                Sender = "SON",
                IsUser = false,
                Text = "Conversation cleared. How can I help you?",
                Timestamp = DateTime.Now,
            });
        }

        [RelayCommand]
        private void CopyMessageText(string? text)
        {
            if (!string.IsNullOrEmpty(text))
            {
                try
                {
                    Clipboard.SetText(text);
                }
                catch (Exception) { }
            }
        }
    }
}

