// SON.Desktop/ViewModels/SecurityViewModel.cs — Security and Human-in-the-Loop Approvals ViewModel
using System;
using System.Collections.ObjectModel;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Models;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class SecurityViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;

        [ObservableProperty]
        private string securityEngineStatus = "ACTIVE / ENFORCING";

        [ObservableProperty]
        private string policyEngineStatus = "Active (Zero-Trust Model)";

        [ObservableProperty]
        private string approvalManagerStatus = "Active (Cryptographic Token Binding)";

        [ObservableProperty]
        private string auditLoggerStatus = "Active (Tamper-Resistant JSONL)";

        [ObservableProperty]
        private string statusMessage = string.Empty;

        [ObservableProperty]
        private bool isLoading = false;

        public ObservableCollection<ApprovalItem> PendingApprovals { get; } = new();
        public ObservableCollection<string> RecentAuditEvents { get; } = new();

        public SecurityViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
        }

        public override void OnNavigatedTo()
        {
            base.OnNavigatedTo();
            _ = RefreshSecurityDataAsync();
        }

        [RelayCommand]
        public async Task RefreshSecurityDataAsync()
        {
            if (!_ipcClient.IsConnected)
            {
                SecurityEngineStatus = "OFFLINE (Backend disconnected)";
                StatusMessage = "Backend disconnected: Cannot communicate with PolicyEngine.";
                return;
            }

            IsLoading = true;
            StatusMessage = "Fetching security state and audit trail...";
            try
            {
                // 1. Get security status & recent audit logs
                var secStatus = await _ipcClient.GetSecurityStatusAsync();
                if (secStatus != null)
                {
                    SecurityEngineStatus = secStatus.Status;
                    PolicyEngineStatus = secStatus.PolicyEngine;
                    ApprovalManagerStatus = secStatus.ApprovalManager;
                    AuditLoggerStatus = secStatus.AuditLogger;

                    RecentAuditEvents.Clear();
                    foreach (var evt in secStatus.RecentEvents)
                    {
                        string eventType = evt.TryGetValue("event_type", out var et) ? et?.ToString() ?? "EVENT" : "EVENT";
                        string status = evt.TryGetValue("status", out var st) ? st?.ToString() ?? "" : "";
                        string actor = evt.TryGetValue("actor", out var ac) ? ac?.ToString() ?? "" : "";
                        RecentAuditEvents.Add($"[{status}] {eventType} (by: {actor})");
                    }
                }

                // 2. Get pending approvals
                var approvals = await _ipcClient.GetPendingApprovalsAsync();
                PendingApprovals.Clear();
                foreach (var a in approvals)
                {
                    PendingApprovals.Add(a);
                }

                StatusMessage = $"Updated: {PendingApprovals.Count} pending approvals, {RecentAuditEvents.Count} recent events.";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Security fetch error: {ex.Message}";
            }
            finally
            {
                IsLoading = false;
            }
        }

        [RelayCommand]
        public async Task ApproveActionAsync(string approvalId)
        {
            if (string.IsNullOrEmpty(approvalId)) return;
            if (!_ipcClient.IsConnected)
            {
                StatusMessage = "Security Error: Backend is offline.";
                return;
            }

            IsLoading = true;
            try
            {
                bool success = await _ipcClient.ResolveApprovalAsync(approvalId, true, "Dad");
                StatusMessage = success ? $"Action {approvalId} APPROVED by Dad." : "Failed to record approval.";
                await RefreshSecurityDataAsync();
            }
            catch (Exception ex)
            {
                StatusMessage = $"Approval error: {ex.Message}";
            }
            finally
            {
                IsLoading = false;
            }
        }

        [RelayCommand]
        public async Task DenyActionAsync(string approvalId)
        {
            if (string.IsNullOrEmpty(approvalId)) return;
            if (!_ipcClient.IsConnected)
            {
                StatusMessage = "Security Error: Backend is offline.";
                return;
            }

            IsLoading = true;
            try
            {
                bool success = await _ipcClient.ResolveApprovalAsync(approvalId, false, "Dad");
                StatusMessage = success ? $"Action {approvalId} DENIED." : "Failed to record denial.";
                await RefreshSecurityDataAsync();
            }
            catch (Exception ex)
            {
                StatusMessage = $"Denial error: {ex.Message}";
            }
            finally
            {
                IsLoading = false;
            }
        }
    }
}

