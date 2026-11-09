// SON.Desktop/Models/ChatMessage.cs — Chat message model for WPF UI binding
using System;
using System.Collections.Generic;
using CommunityToolkit.Mvvm.ComponentModel;

namespace SON.Desktop.Models
{
    public partial class ChatMessage : ObservableObject
    {
        public string Id { get; set; } = Guid.NewGuid().ToString("N");

        [ObservableProperty]
        private string sender = "User";

        [ObservableProperty]
        private string text = string.Empty;

        public DateTime Timestamp { get; set; } = DateTime.Now;

        [ObservableProperty]
        private bool isUser = true;

        public bool IsAssistant => !IsUser;

        [ObservableProperty]
        private bool isLoading = false;

        [ObservableProperty]
        private string? error;

        [ObservableProperty]
        private List<ToolResultItem> toolResults = new();

        public bool HasTools => ToolResults != null && ToolResults.Count > 0;

        [ObservableProperty]
        private string? pendingApprovalId;

        public bool HasPendingApproval => !string.IsNullOrEmpty(PendingApprovalId);

        public string FormattedTime => Timestamp.ToString("HH:mm:ss");
    }
}

