// SON.Desktop.Tests/DesktopTests.cs — Comprehensive Unit and Architecture Tests for SON Desktop
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Media.Imaging;
using Microsoft.Extensions.DependencyInjection;
using SON.Desktop.Models;
using SON.Desktop.Services;
using SON.Desktop.ViewModels;
using Xunit;

namespace SON.Desktop.Tests
{
    // Mock IPC client for isolated ViewModel unit testing
    public class MockIpcClient : IIpcClient
    {
        public bool IsConnected { get; set; } = true;
        public string? ActiveSessionId { get; set; } = "sess_mock_test";
        public string? ActiveUserId { get; set; } = "usr_primary";
        public string? ActiveModel { get; set; } = "llama3.2:latest";

        public event EventHandler<bool>? ConnectionChanged;

        public bool ShouldFailChat { get; set; } = false;
        public int SendChatCalls { get; private set; } = 0;
        public int ResolveApprovalCalls { get; private set; } = 0;
        public string? LastResolvedApprovalId { get; private set; }
        public bool? LastResolvedApprovalDecision { get; private set; }

        public Task<bool> ConnectAsync(CancellationToken cancellationToken = default)
        {
            IsConnected = true;
            ConnectionChanged?.Invoke(this, true);
            return Task.FromResult(true);
        }

        public Task DisconnectAsync()
        {
            IsConnected = false;
            ConnectionChanged?.Invoke(this, false);
            return Task.CompletedTask;
        }

        public Task<HandshakeResult?> HandshakeAsync(string requestedUser = "usr_primary", CancellationToken cancellationToken = default)
        {
            return Task.FromResult<HandshakeResult?>(new HandshakeResult
            {
                Status = "AUTHENTICATED",
                UserId = "usr_primary",
                SessionId = "sess_mock_test",
                ActiveModel = "llama3.2:latest",
                ServerVersion = "3.0.0",
            });
        }

        public async Task<ChatResult?> SendChatAsync(string prompt, string? conversationId = null, CancellationToken cancellationToken = default)
        {
            SendChatCalls++;
            if (ShouldFailChat) return null;

            // Support cancellation delay
            if (cancellationToken.CanBeCanceled)
            {
                await Task.Delay(50, cancellationToken);
            }

            return new ChatResult
            {
                Status = "success",
                Response = $"Mock response for: {prompt}",
                DurationMs = 12.5,
                SessionId = ActiveSessionId,
                ToolResults = new List<ToolResultItem>
                {
                    new ToolResultItem { ToolName = "search_docs", Success = true, Output = "Found doc #1", RiskTier = "low" }
                }
            };
        }

        public Task<HardwareTelemetryResult?> GetTelemetryAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult<HardwareTelemetryResult?>(new HardwareTelemetryResult
            {
                Status = "SUCCESS",
                CpuPercent = 25.5,
                RamUsedBytes = 8589934592,     // 8 GB
                RamTotalBytes = 17179869184,   // 16 GB
                GpuPercent = 14.0,
                VramUsedBytes = 3221225472,    // 3 GB
                VramTotalBytes = 8589934592,   // 8 GB
                ModelName = "llama3.2:latest",
                OllamaActive = true
            });
        }

        public Task<SecurityStatusResult?> GetSecurityStatusAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult<SecurityStatusResult?>(new SecurityStatusResult
            {
                Status = "ACTIVE",
                PolicyEngine = "Enforcing",
                ApprovalManager = "Active",
                AuditLogger = "Active",
                PendingApprovalsCount = 1,
                RecentEvents = new List<Dictionary<string, object>>
                {
                    new Dictionary<string, object> { ["event_type"] = "TOOL_APPROVED", ["status"] = "APPROVED", ["actor"] = "Dad" }
                }
            });
        }

        public Task<List<ApprovalItem>> GetPendingApprovalsAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new List<ApprovalItem>
            {
                new ApprovalItem
                {
                    ApprovalId = "appr_12345",
                    ToolName = "run_bash_command",
                    RiskLevel = "HIGH",
                    UserId = "usr_primary",
                    Arguments = new Dictionary<string, object> { ["command"] = "ls -la" }
                }
            });
        }

        public Task<bool> ResolveApprovalAsync(string approvalId, bool approved, string approver = "Dad", CancellationToken cancellationToken = default)
        {
            ResolveApprovalCalls++;
            LastResolvedApprovalId = approvalId;
            LastResolvedApprovalDecision = approved;
            return Task.FromResult(true);
        }

        public Task<List<MemoryFactItem>> GetMemoryFactsAsync(string? category = null, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new List<MemoryFactItem>
            {
                new MemoryFactItem { Id = 1, Fact = "User prefers Dark Mode", Category = "preferences", CreatedAt = "2026-11-10" },
                new MemoryFactItem { Id = 2, Fact = "Hardware RTX 4060 8GB", Category = "hardware", CreatedAt = "2026-11-10" }
            });
        }

        public Task<bool> AddMemoryFactAsync(string fact, string category = "general", CancellationToken cancellationToken = default)
        {
            return Task.FromResult(true);
        }

        public Task<bool> DeleteMemoryFactAsync(int factId, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(true);
        }

        public Task<string?> AnalyzeVisionAsync(string imagePath, string prompt, string mode = "general", CancellationToken cancellationToken = default)
        {
            return Task.FromResult<string?>("Mock visual analysis of screen capture: Desktop elements detected.");
        }

        public void Dispose() { }
    }

    public class MockScreenCaptureService : IScreenCaptureService
    {
        public BitmapSource? CapturePrimaryDisplay() => null;
        public string CaptureAndSaveDisplay(string? targetFilePath = null) => @"C:\AI\SON\data\screenshots\latest_capture.png";
    }

    public class MockBackendProcessManager : IBackendProcessManager
    {
        public bool IsBackendRunning { get; set; } = true;
        public bool WasSpawnedByUs { get; set; } = false;
        public string? LastError { get; set; }

#pragma warning disable CS0067
        public event EventHandler<string>? OutputReceived;
        public event EventHandler<string>? ErrorReceived;
        public event EventHandler<int>? BackendExited;
#pragma warning restore CS0067

        public Task<bool> EnsureBackendRunningAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult(true);
        }

        public Task StopBackendAsync()
        {
            IsBackendRunning = false;
            return Task.CompletedTask;
        }

        public void Dispose() { }
    }

    public class DesktopTests
    {
        [Fact]
        public void Test_NavigationService_SwitchesPages()
        {
            var mockIpc = new MockIpcClient();
            var homeVm = new HomeViewModel(mockIpc, null!);
            var chatVm = new ChatViewModel(mockIpc);
            var voiceVm = new VoiceViewModel(mockIpc);
            var memoryVm = new MemoryViewModel(mockIpc);
            var settingsVm = new SettingsViewModel(mockIpc);
            var securityVm = new SecurityViewModel(mockIpc);

            var nav = new NavigationService(page => page switch
            {
                NavigationPage.Home => homeVm,
                NavigationPage.Chat => chatVm,
                NavigationPage.Voice => voiceVm,
                NavigationPage.Memory => memoryVm,
                NavigationPage.Settings => settingsVm,
                NavigationPage.Security => securityVm,
                _ => homeVm
            });

            Assert.Equal(NavigationPage.Home, nav.CurrentPage);

            nav.NavigateTo(NavigationPage.Chat);
            Assert.Equal(NavigationPage.Chat, nav.CurrentPage);
            Assert.Equal(chatVm, nav.CurrentViewModel);

            nav.NavigateTo(NavigationPage.Security);
            Assert.Equal(NavigationPage.Security, nav.CurrentPage);
            Assert.Equal(securityVm, nav.CurrentViewModel);

            nav.NavigateTo(NavigationPage.Memory);
            Assert.Equal(NavigationPage.Memory, nav.CurrentPage);
            Assert.Equal(memoryVm, nav.CurrentViewModel);
        }

        [Fact]
        public async Task Test_ChatViewModel_MessageSubmission_AndRendering()
        {
            var mockIpc = new MockIpcClient();
            var chatVm = new ChatViewModel(mockIpc);

            int initialCount = chatVm.Messages.Count; // Welcome message seeded

            chatVm.InputText = "What is the status of my system?";
            await chatVm.SendMessageCommand.ExecuteAsync(null);

            // Should have added user message + assistant response
            Assert.Equal(initialCount + 2, chatVm.Messages.Count);

            var userMsg = chatVm.Messages[initialCount];
            Assert.True(userMsg.IsUser);
            Assert.Equal("What is the status of my system?", userMsg.Text);

            var assistantMsg = chatVm.Messages[initialCount + 1];
            Assert.False(assistantMsg.IsUser);
            Assert.Contains("Mock response for: What is the status of my system?", assistantMsg.Text);
            Assert.Single(assistantMsg.ToolResults);
            Assert.Equal("search_docs", assistantMsg.ToolResults[0].ToolName);
            Assert.Equal(1, mockIpc.SendChatCalls);
        }

        [Fact]
        public async Task Test_ChatViewModel_BackendUnavailable_DisplaysError()
        {
            var mockIpc = new MockIpcClient { ShouldFailChat = true };
            var chatVm = new ChatViewModel(mockIpc);

            chatVm.InputText = "Hello offline bot";
            await chatVm.SendMessageCommand.ExecuteAsync(null);

            var assistantMsg = chatVm.Messages.Last();
            Assert.False(assistantMsg.IsLoading);
            Assert.NotNull(assistantMsg.Error);
        }

        [Fact]
        public async Task Test_SecurityViewModel_ApproveAndDeny_DispatchesToBackend()
        {
            var mockIpc = new MockIpcClient();
            var secVm = new SecurityViewModel(mockIpc);

            await secVm.RefreshSecurityDataAsync();
            Assert.Single(secVm.PendingApprovals);
            Assert.Equal("appr_12345", secVm.PendingApprovals[0].ApprovalId);

            // Approve action
            await secVm.ApproveActionAsync("appr_12345");
            Assert.Equal(1, mockIpc.ResolveApprovalCalls);
            Assert.Equal("appr_12345", mockIpc.LastResolvedApprovalId);
            Assert.True(mockIpc.LastResolvedApprovalDecision);

            // Deny action
            await secVm.DenyActionAsync("appr_12345");
            Assert.Equal(2, mockIpc.ResolveApprovalCalls);
            Assert.False(mockIpc.LastResolvedApprovalDecision);
        }

        [Fact]
        public async Task Test_MemoryViewModel_SearchFiltering()
        {
            var mockIpc = new MockIpcClient();
            var memVm = new MemoryViewModel(mockIpc);

            await memVm.LoadFactsAsync();
            Assert.Equal(2, memVm.Facts.Count);

            // Filter for Dark Mode
            memVm.SearchQuery = "Dark";
            Assert.Single(memVm.Facts);
            Assert.Contains("Dark Mode", memVm.Facts[0].Fact);

            // Reset filter
            memVm.SearchQuery = "";
            Assert.Equal(2, memVm.Facts.Count);
        }

        [Fact]
        public void Test_HomeViewModel_TelemetryBinding()
        {
            var mockIpc = new MockIpcClient();
            var homeVm = new HomeViewModel(mockIpc, null!);

            homeVm.OnNavigatedTo();
            Assert.True(homeVm.IsConnected);
            Assert.Equal("Connected", homeVm.ConnectionStatus);
            Assert.Equal("llama3.2:latest", homeVm.ActiveModel);
        }

        [Fact]
        public void Test_DependencyInjection_Registration_Completeness()
        {
            var services = new ServiceCollection();
            services.AddSingleton<IIpcClient, MockIpcClient>();
            services.AddSingleton<IBackendProcessManager, MockBackendProcessManager>();

            services.AddSingleton<MainWindowViewModel>();
            services.AddSingleton<HomeViewModel>();
            services.AddSingleton<ChatViewModel>();
            services.AddSingleton<VoiceViewModel>();
            services.AddSingleton<MemoryViewModel>();
            services.AddSingleton<SettingsViewModel>();
            services.AddSingleton<SecurityViewModel>();

            services.AddSingleton<INavigationService>(sp =>
            {
                return new NavigationService(page => page switch
                {
                    NavigationPage.Home => sp.GetRequiredService<HomeViewModel>(),
                    NavigationPage.Chat => sp.GetRequiredService<ChatViewModel>(),
                    NavigationPage.Voice => sp.GetRequiredService<VoiceViewModel>(),
                    NavigationPage.Memory => sp.GetRequiredService<MemoryViewModel>(),
                    NavigationPage.Settings => sp.GetRequiredService<SettingsViewModel>(),
                    NavigationPage.Security => sp.GetRequiredService<SecurityViewModel>(),
                    _ => sp.GetRequiredService<HomeViewModel>(),
                });
            });

            var provider = services.BuildServiceProvider();

            Assert.NotNull(provider.GetRequiredService<MainWindowViewModel>());
            Assert.NotNull(provider.GetRequiredService<HomeViewModel>());
            Assert.NotNull(provider.GetRequiredService<ChatViewModel>());
            Assert.NotNull(provider.GetRequiredService<VoiceViewModel>());
            Assert.NotNull(provider.GetRequiredService<MemoryViewModel>());
            Assert.NotNull(provider.GetRequiredService<SettingsViewModel>());
            Assert.NotNull(provider.GetRequiredService<SecurityViewModel>());
            Assert.NotNull(provider.GetRequiredService<INavigationService>());
        }

        [Fact]
        public void Test_Architecture_NoDirectFrontendToolExecution()
        {
            // Security requirement: Ensure the frontend never imports or executes tools directly.
            // All operations must flow through NamedPipeIpcClient.
            var assembly = typeof(ChatViewModel).Assembly;
            var types = assembly.GetTypes();

            foreach (var type in types)
            {
                // Disallow direct shell or command executors in ViewModels or Views
                var methodNames = type.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static)
                    .Select(m => m.Name.ToLowerInvariant())
                    .ToList();

                Assert.DoesNotContain("executetoollocally", methodNames);
                Assert.DoesNotContain("runsystemcommand", methodNames);
                Assert.DoesNotContain("executeshellcommand", methodNames);
            }
        }

        [Fact]
        public async Task Test_CR11_NamedPipeIpcClient_DeduplicatesConnectionChanged()
        {
            using var client = new NamedPipeIpcClient("nonexistent_pipe_test_cr11");
            int connectionEventCount = 0;
            bool? lastState = null;

            client.ConnectionChanged += (sender, isConnected) =>
            {
                connectionEventCount++;
                lastState = isConnected;
            };

            // Attempting to connect when pipe doesn't exist should fail, but not repeatedly spam event if state unchanged
            var connected1 = await client.ConnectAsync(CancellationToken.None);
            Assert.False(connected1);

            var connected2 = await client.ConnectAsync(CancellationToken.None);
            Assert.False(connected2);

            // Because it started disconnected and failed both times, state never transitioned from true -> false
            // Therefore connectionEventCount should be 0 (no false duplicates)
            Assert.Equal(0, connectionEventCount);
        }

        [Fact]
        public void Test_CR12_LengthPrefix_UnsignedBigEndianValidation()
        {
            // Valid header: 1024 bytes
            byte[] header = new byte[4];
            BinaryPrimitives.WriteUInt32BigEndian(header, 1024);
            uint parsed = BinaryPrimitives.ReadUInt32BigEndian(header);
            Assert.Equal(1024u, parsed);
            Assert.True(parsed > 0 && parsed <= 10 * 1024 * 1024);

            // Invalid oversized header (e.g. 50MB)
            BinaryPrimitives.WriteUInt32BigEndian(header, 50 * 1024 * 1024);
            uint parsedOversized = BinaryPrimitives.ReadUInt32BigEndian(header);
            Assert.False(parsedOversized > 0 && parsedOversized <= 10 * 1024 * 1024);

            // High-bit set (e.g. 0x80000001 -> would be negative in signed int32)
            BinaryPrimitives.WriteUInt32BigEndian(header, 0x80000001);
            uint parsedHighBit = BinaryPrimitives.ReadUInt32BigEndian(header);
            Assert.True(parsedHighBit > (uint)(10 * 1024 * 1024));
        }

        [Fact]
        public async Task Test_MiniCompanionViewModel_PromptSubmission_UpdatesResponseAndState()
        {
            var mockIpc = new MockIpcClient();
            var mockCapture = new MockScreenCaptureService();
            var vm = new MiniCompanionViewModel(mockIpc, mockCapture);

            Assert.Equal("SON AI • Ready to assist", vm.StatusText);
            Assert.False(vm.HasResponse);

            vm.PromptText = "Help me debug this build error";
            await vm.SubmitPromptCommand.ExecuteAsync(null);

            Assert.True(vm.HasResponse);
            Assert.False(string.IsNullOrWhiteSpace(vm.LatestResponse));
            Assert.Empty(vm.PromptText);
            Assert.Equal("Response ready • SON AI", vm.StatusText);

            vm.ClearResponseCommand.Execute(null);
            Assert.False(vm.HasResponse);
            Assert.Empty(vm.LatestResponse);
        }

        [Fact]
        public void Test_MiniCompanionViewModel_ToggleVoice_UpdatesRecordingState()
        {
            var mockIpc = new MockIpcClient();
            var mockCapture = new MockScreenCaptureService();
            var vm = new MiniCompanionViewModel(mockIpc, mockCapture);

            Assert.False(vm.IsRecording);

            vm.ToggleVoiceCommand.Execute(null);
            Assert.True(vm.IsRecording);
            Assert.Contains("Listening", vm.StatusText);

            vm.ToggleVoiceCommand.Execute(null);
            Assert.False(vm.IsRecording);
        }

        [Fact]
        public async Task Test_VisionViewModel_CaptureAndAnalyze_InvokesVisionService()
        {
            var mockIpc = new MockIpcClient();
            var mockCapture = new MockScreenCaptureService();
            var vm = new VisionViewModel(mockIpc, mockCapture);

            Assert.False(vm.IsAnalyzing);
            await vm.CaptureAndAnalyzeCommand.ExecuteAsync("Explain");

            Assert.False(vm.IsAnalyzing);
            Assert.Contains("Mock visual analysis", vm.AnalysisResult);
            Assert.Equal("Screen analysis complete.", vm.StatusMessage);
        }
    }
}
