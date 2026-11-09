// SON.Desktop/Services/BackendProcessManager.cs — Safe Python Backend Lifecycle Supervisor
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace SON.Desktop.Services
{
    public class BackendProcessManager : IBackendProcessManager
    {
        private readonly IIpcClient _ipcClient;
        private Process? _backendProcess;
        private readonly SemaphoreSlim _lock = new(1, 1);
        private bool _disposed;

        public bool IsBackendRunning => (_backendProcess != null && !_backendProcess.HasExited) || _ipcClient.IsConnected;
        public bool WasSpawnedByUs => _backendProcess != null;
        public string? LastError { get; private set; }

        public event EventHandler<string>? OutputReceived;
        public event EventHandler<string>? ErrorReceived;
        public event EventHandler<int>? BackendExited;

        public BackendProcessManager(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
        }

        public async Task<bool> EnsureBackendRunningAsync(CancellationToken cancellationToken = default)
        {
            await _lock.WaitAsync(cancellationToken);
            try
            {
                // 1. Check if backend is already listening on the pipe
                bool connected = await _ipcClient.ConnectAsync(cancellationToken);
                if (connected)
                {
                    await _ipcClient.HandshakeAsync("usr_primary", cancellationToken);
                    return true;
                }

                // 2. If not connected, start the Python backend process safely (No Shell Execution)
                string pythonExe = FindPythonExecutable();
                string projectRoot = @"C:\AI\SON";

                var startInfo = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = "-m services.ipc.named_pipe_server",
                    WorkingDirectory = projectRoot,
                    UseShellExecute = false, // Critical security requirement: Never use shell execution
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                };

                startInfo.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
                startInfo.EnvironmentVariables["PYTHONPATH"] = projectRoot;

                _backendProcess = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
                _backendProcess.OutputDataReceived += (s, e) =>
                {
                    if (e.Data != null) OutputReceived?.Invoke(this, e.Data);
                };
                _backendProcess.ErrorDataReceived += (s, e) =>
                {
                    if (e.Data != null)
                    {
                        LastError = e.Data;
                        ErrorReceived?.Invoke(this, e.Data);
                    }
                };
                _backendProcess.Exited += (s, e) =>
                {
                    int exitCode = _backendProcess?.ExitCode ?? -1;
                    BackendExited?.Invoke(this, exitCode);
                };

                _backendProcess.Start();
                _backendProcess.BeginOutputReadLine();
                _backendProcess.BeginErrorReadLine();

                // 3. Retry connecting to the pipe for up to 8 seconds
                for (int attempt = 0; attempt < 16; attempt++)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (_backendProcess.HasExited)
                    {
                        LastError = $"Backend process exited prematurely with code {_backendProcess.ExitCode}.";
                        return false;
                    }

                    await Task.Delay(500, cancellationToken);
                    if (await _ipcClient.ConnectAsync(cancellationToken))
                    {
                        await _ipcClient.HandshakeAsync("usr_primary", cancellationToken);
                        return true;
                    }
                }

                LastError = "Timed out waiting for backend named pipe to become available.";
                return false;
            }
            catch (Exception ex)
            {
                LastError = ex.Message;
                return false;
            }
            finally
            {
                _lock.Release();
            }
        }

        public async Task StopBackendAsync()
        {
            await _lock.WaitAsync();
            try
            {
                await _ipcClient.DisconnectAsync();

                if (_backendProcess != null && !_backendProcess.HasExited)
                {
                    try
                    {
                        _backendProcess.Kill(entireProcessTree: true);
                        await _backendProcess.WaitForExitAsync();
                    }
                    catch (Exception)
                    {
                        // Ignore process cleanup errors on shutdown
                    }
                    finally
                    {
                        _backendProcess.Dispose();
                        _backendProcess = null;
                    }
                }
            }
            finally
            {
                _lock.Release();
            }
        }

        private static string FindPythonExecutable()
        {
            // 1. Check virtual environment
            string venvPy = @"C:\AI\SON\.venv\Scripts\python.exe";
            if (File.Exists(venvPy)) return venvPy;

            string venvPy2 = @"C:\AI\SON\venv\Scripts\python.exe";
            if (File.Exists(venvPy2)) return venvPy2;

            // 2. Fall back to installed Python
            string sysPy = @"C:\Program Files\Python313\python.exe";
            if (File.Exists(sysPy)) return sysPy;

            return "python";
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            try
            {
                StopBackendAsync().GetAwaiter().GetResult();
            }
            catch { }
            _lock.Dispose();
        }
    }
}

