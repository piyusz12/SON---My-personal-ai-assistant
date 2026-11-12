// SON.Desktop/Services/IIpcClient.cs — IPC Client Interface
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using SON.Desktop.Models;

namespace SON.Desktop.Services
{
    public interface IIpcClient : IDisposable
    {
        bool IsConnected { get; }
        string? ActiveSessionId { get; }
        string? ActiveUserId { get; }
        string? ActiveModel { get; }
        string? AuthToken { get; set; }

        event EventHandler<bool>? ConnectionChanged;

        Task<bool> ConnectAsync(CancellationToken cancellationToken = default);
        Task DisconnectAsync();

        Task<HandshakeResult?> HandshakeAsync(string requestedUser = "usr_primary", CancellationToken cancellationToken = default);
        Task<ChatResult?> SendChatAsync(string prompt, string? conversationId = null, CancellationToken cancellationToken = default);
        Task<HardwareTelemetryResult?> GetTelemetryAsync(CancellationToken cancellationToken = default);
        Task<SecurityStatusResult?> GetSecurityStatusAsync(CancellationToken cancellationToken = default);
        Task<List<ApprovalItem>> GetPendingApprovalsAsync(CancellationToken cancellationToken = default);
        Task<bool> ResolveApprovalAsync(string approvalId, bool approved, string approver = "Dad", CancellationToken cancellationToken = default);
        Task<List<MemoryFactItem>> GetMemoryFactsAsync(string? category = null, CancellationToken cancellationToken = default);
        Task<bool> AddMemoryFactAsync(string fact, string category = "general", CancellationToken cancellationToken = default);
        Task<bool> DeleteMemoryFactAsync(int factId, CancellationToken cancellationToken = default);
        Task<string?> AnalyzeVisionAsync(string imagePath, string prompt, string mode = "general", CancellationToken cancellationToken = default);
    }
}

