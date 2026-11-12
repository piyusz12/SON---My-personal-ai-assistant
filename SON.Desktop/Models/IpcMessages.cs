// SON.Desktop/Models/IpcMessages.cs — Strongly-typed IPC DTOs matching IPC_PROTOCOL.md
using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace SON.Desktop.Models
{
    public class IpcMessageEnvelope
    {
        [JsonPropertyName("protocol_version")]
        public string ProtocolVersion { get; set; } = "1.0";

        [JsonPropertyName("message_id")]
        public string MessageId { get; set; } = $"msg_{Guid.NewGuid():N}";

        [JsonPropertyName("request_id")]
        public string RequestId { get; set; } = $"req_{Guid.NewGuid():N}";

        [JsonPropertyName("message_type")]
        public string MessageType { get; set; } = "REQUEST";

        [JsonPropertyName("action")]
        public string Action { get; set; } = string.Empty;

        [JsonPropertyName("timestamp")]
        public double Timestamp { get; set; } = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;

        [JsonPropertyName("payload")]
        public object? Payload { get; set; }

        [JsonPropertyName("error")]
        public string? Error { get; set; }
    }

    public class IpcResponseEnvelope
    {
        [JsonPropertyName("protocol_version")]
        public string ProtocolVersion { get; set; } = "1.0";

        [JsonPropertyName("message_id")]
        public string MessageId { get; set; } = string.Empty;

        [JsonPropertyName("request_id")]
        public string RequestId { get; set; } = string.Empty;

        [JsonPropertyName("message_type")]
        public string MessageType { get; set; } = string.Empty;

        [JsonPropertyName("action")]
        public string Action { get; set; } = string.Empty;

        [JsonPropertyName("timestamp")]
        public double Timestamp { get; set; }

        [JsonPropertyName("payload")]
        public JsonElement Payload { get; set; }

        [JsonPropertyName("error")]
        public string? Error { get; set; }
    }

    public class HandshakePayload
    {
        [JsonPropertyName("client_version")]
        public string ClientVersion { get; set; } = "1.0.0";

        [JsonPropertyName("client_type")]
        public string ClientType { get; set; } = "wpf_desktop";

        [JsonPropertyName("requested_user_id")]
        public string RequestedUserId { get; set; } = "usr_primary";

        [JsonPropertyName("auth_token")]
        public string? AuthToken { get; set; }
    }

    public class HandshakeResult
    {
        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("user_id")]
        public string UserId { get; set; } = string.Empty;

        [JsonPropertyName("session_id")]
        public string SessionId { get; set; } = string.Empty;

        [JsonPropertyName("server_version")]
        public string ServerVersion { get; set; } = string.Empty;

        [JsonPropertyName("active_model")]
        public string ActiveModel { get; set; } = string.Empty;

        [JsonPropertyName("features_enabled")]
        public List<string> FeaturesEnabled { get; set; } = new();
    }

    public class ChatSendPayload
    {
        [JsonPropertyName("prompt")]
        public string Prompt { get; set; } = string.Empty;

        [JsonPropertyName("user_id")]
        public string UserId { get; set; } = "usr_primary";

        [JsonPropertyName("session_id")]
        public string? SessionId { get; set; }

        [JsonPropertyName("conversation_id")]
        public string ConversationId { get; set; } = "conv_desktop";
    }

    public class ToolResultItem
    {
        [JsonPropertyName("tool_name")]
        public string ToolName { get; set; } = string.Empty;

        [JsonPropertyName("success")]
        public bool Success { get; set; }

        [JsonPropertyName("output")]
        public string Output { get; set; } = string.Empty;

        [JsonPropertyName("error")]
        public string? Error { get; set; }

        [JsonPropertyName("risk_tier")]
        public string RiskTier { get; set; } = "low";

        [JsonPropertyName("requires_approval")]
        public bool RequiresApproval { get; set; }
    }

    public class ChatResult
    {
        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("response")]
        public string Response { get; set; } = string.Empty;

        [JsonPropertyName("error")]
        public string? Error { get; set; }

        [JsonPropertyName("duration_ms")]
        public double DurationMs { get; set; }

        [JsonPropertyName("session_id")]
        public string? SessionId { get; set; }

        [JsonPropertyName("tool_results")]
        public List<ToolResultItem> ToolResults { get; set; } = new();

        [JsonPropertyName("pending_approval")]
        public JsonElement? PendingApproval { get; set; }
    }

    public class HardwareTelemetryResult
    {
        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("cpu_percent")]
        public double CpuPercent { get; set; }

        [JsonPropertyName("ram_used_bytes")]
        public long RamUsedBytes { get; set; }

        [JsonPropertyName("ram_total_bytes")]
        public long RamTotalBytes { get; set; }

        [JsonPropertyName("gpu_percent")]
        public double GpuPercent { get; set; }

        [JsonPropertyName("vram_used_bytes")]
        public long VramUsedBytes { get; set; }

        [JsonPropertyName("vram_total_bytes")]
        public long VramTotalBytes { get; set; }

        [JsonPropertyName("ollama_active")]
        public bool OllamaActive { get; set; }

        [JsonPropertyName("model_name")]
        public string ModelName { get; set; } = string.Empty;

        public double RamUsedGb => RamUsedBytes / (1024.0 * 1024.0 * 1024.0);
        public double RamTotalGb => RamTotalBytes / (1024.0 * 1024.0 * 1024.0);
        public double VramUsedGb => VramUsedBytes / (1024.0 * 1024.0 * 1024.0);
        public double VramTotalGb => VramTotalBytes / (1024.0 * 1024.0 * 1024.0);
    }

    public class ApprovalItem
    {
        [JsonPropertyName("approval_id")]
        public string ApprovalId { get; set; } = string.Empty;

        [JsonPropertyName("tool_name")]
        public string ToolName { get; set; } = string.Empty;

        [JsonPropertyName("risk_level")]
        public string RiskLevel { get; set; } = "MEDIUM";

        [JsonPropertyName("arguments")]
        public Dictionary<string, object> Arguments { get; set; } = new();

        [JsonPropertyName("status")]
        public string Status { get; set; } = "PENDING";

        [JsonPropertyName("created_at")]
        public double CreatedAt { get; set; }

        [JsonPropertyName("expires_at")]
        public double ExpiresAt { get; set; }

        [JsonPropertyName("user_id")]
        public string UserId { get; set; } = string.Empty;

        public string ArgumentsSummary
        {
            get
            {
                if (Arguments == null || Arguments.Count == 0) return "none";
                return JsonSerializer.Serialize(Arguments);
            }
        }
    }

    public class SecurityStatusResult
    {
        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("policy_engine")]
        public string PolicyEngine { get; set; } = string.Empty;

        [JsonPropertyName("approval_manager")]
        public string ApprovalManager { get; set; } = string.Empty;

        [JsonPropertyName("audit_logger")]
        public string AuditLogger { get; set; } = string.Empty;

        [JsonPropertyName("pending_approvals_count")]
        public int PendingApprovalsCount { get; set; }

        [JsonPropertyName("recent_events")]
        public List<Dictionary<string, object>> RecentEvents { get; set; } = new();
    }

    public class MemoryFactItem
    {
        [JsonPropertyName("id")]
        public int Id { get; set; }

        [JsonPropertyName("fact")]
        public string Fact { get; set; } = string.Empty;

        [JsonPropertyName("category")]
        public string Category { get; set; } = "general";

        [JsonPropertyName("confidence")]
        public double Confidence { get; set; } = 1.0;

        [JsonPropertyName("created_at")]
        public string CreatedAt { get; set; } = string.Empty;
    }
}

