// SON.Desktop/Services/NamedPipeIpcClient.cs — High-Performance Named Pipe Client with Length Prefix Framing
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using SON.Desktop.Models;

namespace SON.Desktop.Services
{
    public class NamedPipeIpcClient : IIpcClient
    {
        private readonly string _pipeName;
        private const int MaxMessageSize = 10 * 1024 * 1024; // 10MB safety cap
        private NamedPipeClientStream? _pipeStream;
        private readonly SemaphoreSlim _ioLock = new(1, 1);
        private bool _disposed;
        private bool _wasConnected;

        public NamedPipeIpcClient(string pipeName = "son_desktop_ipc")
        {
            _pipeName = pipeName;
        }

        public bool IsConnected => _pipeStream != null && _pipeStream.IsConnected;
        public string? ActiveSessionId { get; private set; }
        public string? ActiveUserId { get; private set; }
        public string? ActiveModel { get; private set; }

        public event EventHandler<bool>? ConnectionChanged;

        private void NotifyConnectionState(bool isConnected)
        {
            if (_wasConnected != isConnected)
            {
                _wasConnected = isConnected;
                ConnectionChanged?.Invoke(this, isConnected);
            }
        }

        public async Task<bool> ConnectAsync(CancellationToken cancellationToken = default)
        {
            if (IsConnected) return true;

            await _ioLock.WaitAsync(cancellationToken);
            try
            {
                if (IsConnected) return true;

                _pipeStream?.Dispose();
                _pipeStream = new NamedPipeClientStream(".", _pipeName, PipeDirection.InOut, PipeOptions.Asynchronous);

                // Try connecting with a 2-second timeout
                using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                cts.CancelAfter(TimeSpan.FromSeconds(2));

                await _pipeStream.ConnectAsync(cts.Token);
                NotifyConnectionState(true);
                return true;
            }
            catch (Exception)
            {
                _pipeStream?.Dispose();
                _pipeStream = null;
                NotifyConnectionState(false);
                return false;
            }
            finally
            {
                _ioLock.Release();
            }
        }

        public async Task DisconnectAsync()
        {
            await _ioLock.WaitAsync();
            try
            {
                if (_pipeStream != null)
                {
                    _pipeStream.Dispose();
                    _pipeStream = null;
                    NotifyConnectionState(false);
                }
            }
            finally
            {
                _ioLock.Release();
            }
        }

        private async Task<IpcResponseEnvelope?> SendRequestAsync(string action, object? payload, CancellationToken cancellationToken = default)
        {
            if (!IsConnected)
            {
                var connected = await ConnectAsync(cancellationToken);
                if (!connected) return null;
            }

            var envelope = new IpcMessageEnvelope
            {
                Action = action,
                Payload = payload,
            };

            string json = JsonSerializer.Serialize(envelope);
            byte[] payloadBytes = Encoding.UTF8.GetBytes(json);
            byte[] headerBytes = new byte[4];
            BinaryPrimitives.WriteInt32BigEndian(headerBytes, payloadBytes.Length);

            await _ioLock.WaitAsync(cancellationToken);
            try
            {
                if (_pipeStream == null || !_pipeStream.IsConnected)
                {
                    NotifyConnectionState(false);
                    return null;
                }

                // 1. Write length prefix header + payload
                await _pipeStream.WriteAsync(headerBytes, 0, 4, cancellationToken);
                await _pipeStream.WriteAsync(payloadBytes, 0, payloadBytes.Length, cancellationToken);
                await _pipeStream.FlushAsync(cancellationToken);

                // 2. Read length prefix header from response
                byte[] respHeader = new byte[4];
                int totalRead = 0;
                while (totalRead < 4)
                {
                    int read = await _pipeStream.ReadAsync(respHeader.AsMemory(totalRead, 4 - totalRead), cancellationToken);
                    if (read == 0) throw new System.IO.EndOfStreamException("Backend pipe closed unexpectedly.");
                    totalRead += read;
                }

                uint rawLength = BinaryPrimitives.ReadUInt32BigEndian(respHeader);
                if (rawLength == 0 || rawLength > (uint)MaxMessageSize)
                {
                    throw new InvalidOperationException($"Invalid IPC response length: {rawLength} bytes.");
                }
                int respLength = (int)rawLength;

                // 3. Read payload bytes
                byte[] respPayload = new byte[respLength];
                totalRead = 0;
                while (totalRead < respLength)
                {
                    int read = await _pipeStream.ReadAsync(respPayload.AsMemory(totalRead, respLength - totalRead), cancellationToken);
                    if (read == 0) throw new System.IO.EndOfStreamException("Backend pipe closed while reading payload.");
                    totalRead += read;
                }

                string respJson = Encoding.UTF8.GetString(respPayload);
                return JsonSerializer.Deserialize<IpcResponseEnvelope>(respJson);
            }
            catch (Exception)
            {
                _pipeStream?.Dispose();
                _pipeStream = null;
                NotifyConnectionState(false);
                return null;
            }
            finally
            {
                _ioLock.Release();
            }
        }

        public async Task<HandshakeResult?> HandshakeAsync(string requestedUser = "usr_primary", CancellationToken cancellationToken = default)
        {
            var resp = await SendRequestAsync("handshake", new HandshakePayload
            {
                ClientVersion = "1.0.0",
                ClientType = "wpf_desktop",
                RequestedUserId = requestedUser,
            }, cancellationToken);

            if (resp?.Payload.ValueKind == JsonValueKind.Object)
            {
                var result = JsonSerializer.Deserialize<HandshakeResult>(resp.Payload.GetRawText());
                if (result != null && result.Status == "AUTHENTICATED")
                {
                    ActiveSessionId = result.SessionId;
                    ActiveUserId = result.UserId;
                    ActiveModel = result.ActiveModel;
                }
                return result;
            }
            return null;
        }

        public async Task<ChatResult?> SendChatAsync(string prompt, string? conversationId = null, CancellationToken cancellationToken = default)
        {
            var payload = new ChatSendPayload
            {
                Prompt = prompt,
                UserId = ActiveUserId ?? "usr_primary",
                SessionId = ActiveSessionId,
                ConversationId = conversationId ?? "conv_desktop",
            };

            var resp = await SendRequestAsync("chat_send", payload, cancellationToken);
            if (resp?.Payload.ValueKind == JsonValueKind.Object)
            {
                var result = JsonSerializer.Deserialize<ChatResult>(resp.Payload.GetRawText());
                if (result != null && !string.IsNullOrEmpty(result.SessionId))
                {
                    ActiveSessionId = result.SessionId;
                }
                return result;
            }
            return null;
        }

        public async Task<HardwareTelemetryResult?> GetTelemetryAsync(CancellationToken cancellationToken = default)
        {
            var resp = await SendRequestAsync("hardware_telemetry", new { }, cancellationToken);
            if (resp?.Payload.ValueKind == JsonValueKind.Object)
            {
                return JsonSerializer.Deserialize<HardwareTelemetryResult>(resp.Payload.GetRawText());
            }
            return null;
        }

        public async Task<SecurityStatusResult?> GetSecurityStatusAsync(CancellationToken cancellationToken = default)
        {
            var resp = await SendRequestAsync("security_status", new { }, cancellationToken);
            if (resp?.Payload.ValueKind == JsonValueKind.Object)
            {
                return JsonSerializer.Deserialize<SecurityStatusResult>(resp.Payload.GetRawText());
            }
            return null;
        }

        public async Task<List<ApprovalItem>> GetPendingApprovalsAsync(CancellationToken cancellationToken = default)
        {
            var resp = await SendRequestAsync("approvals_list", new { }, cancellationToken);
            if (resp?.Payload.ValueKind == JsonValueKind.Object && resp.Payload.TryGetProperty("approvals", out var approvalsElement))
            {
                var list = JsonSerializer.Deserialize<List<ApprovalItem>>(approvalsElement.GetRawText());
                return list ?? new List<ApprovalItem>();
            }
            return new List<ApprovalItem>();
        }

        public async Task<bool> ResolveApprovalAsync(string approvalId, bool approved, string approver = "Dad", CancellationToken cancellationToken = default)
        {
            var resp = await SendRequestAsync("approval_resolve", new
            {
                approval_id = approvalId,
                approved = approved,
                decision_by = approver,
            }, cancellationToken);

            if (resp?.Payload.ValueKind == JsonValueKind.Object && resp.Payload.TryGetProperty("success", out var successElem))
            {
                return successElem.GetBoolean();
            }
            return false;
        }

        public async Task<List<MemoryFactItem>> GetMemoryFactsAsync(string? category = null, CancellationToken cancellationToken = default)
        {
            var resp = await SendRequestAsync("memory_list", new { category = category, limit = 50 }, cancellationToken);
            if (resp?.Payload.ValueKind == JsonValueKind.Object && resp.Payload.TryGetProperty("facts", out var factsElement))
            {
                var list = JsonSerializer.Deserialize<List<MemoryFactItem>>(factsElement.GetRawText());
                return list ?? new List<MemoryFactItem>();
            }
            return new List<MemoryFactItem>();
        }

        public async Task<bool> AddMemoryFactAsync(string fact, string category = "general", CancellationToken cancellationToken = default)
        {
            var resp = await SendRequestAsync("memory_add", new { fact = fact, category = category }, cancellationToken);
            if (resp?.Payload.ValueKind == JsonValueKind.Object && resp.Payload.TryGetProperty("status", out var statusElem))
            {
                return statusElem.GetString() == "SUCCESS";
            }
            return false;
        }

        public async Task<bool> DeleteMemoryFactAsync(int factId, CancellationToken cancellationToken = default)
        {
            var resp = await SendRequestAsync("memory_delete", new { id = factId }, cancellationToken);
            if (resp?.Payload.ValueKind == JsonValueKind.Object && resp.Payload.TryGetProperty("status", out var statusElem))
            {
                return statusElem.GetString() == "SUCCESS";
            }
            return false;
        }

        public async Task<string?> AnalyzeVisionAsync(string imagePath, string prompt, string mode = "general", CancellationToken cancellationToken = default)
        {
            var resp = await SendRequestAsync("vision_analyze", new
            {
                image_path = imagePath,
                prompt = prompt,
                mode = mode,
            }, cancellationToken);

            if (resp?.Payload.ValueKind == JsonValueKind.Object)
            {
                if (resp.Payload.TryGetProperty("analysis", out var analysisElem))
                {
                    return analysisElem.GetString();
                }
                if (resp.Payload.TryGetProperty("message", out var msgElem))
                {
                    return msgElem.GetString();
                }
            }
            return null;
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            _pipeStream?.Dispose();
            _ioLock.Dispose();
        }
    }
}

