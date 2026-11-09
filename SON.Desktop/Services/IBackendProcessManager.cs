// SON.Desktop/Services/IBackendProcessManager.cs — Python Backend Lifecycle Interface
using System;
using System.Threading;
using System.Threading.Tasks;

namespace SON.Desktop.Services
{
    public interface IBackendProcessManager : IDisposable
    {
        bool IsBackendRunning { get; }
        bool WasSpawnedByUs { get; }
        string? LastError { get; }

        event EventHandler<string>? OutputReceived;
        event EventHandler<string>? ErrorReceived;
        event EventHandler<int>? BackendExited;

        Task<bool> EnsureBackendRunningAsync(CancellationToken cancellationToken = default);
        Task StopBackendAsync();
    }
}

