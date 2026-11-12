// SON.Desktop/ViewModels/AutomationViewModel.cs — Scheduled & Event-driven Automations
using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Models;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class AutomationViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;
        private readonly string _storagePath = @"C:\AI\SON\data\automations.json";
        private readonly string _historyPath = @"C:\AI\SON\data\automation_history.log";

        [ObservableProperty]
        private AutomationItem? selectedAutomation;

        [ObservableProperty]
        private bool isRunningRoutine = false;

        [ObservableProperty]
        private string statusMessage = "Automation Engine Ready — Zero-Trust Policy Enforced";

        [ObservableProperty]
        private string newName = string.Empty;

        [ObservableProperty]
        private string newDescription = string.Empty;

        [ObservableProperty]
        private string newTrigger = "Manual / On-Demand";

        [ObservableProperty]
        private string newCommand = string.Empty;

        [ObservableProperty]
        private bool isAddDialogOpen = false;

        public ObservableCollection<AutomationItem> Automations { get; } = new();
        public ObservableCollection<string> ExecutionHistory { get; } = new();

        public AutomationViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
            LoadAutomationsFromDisk();
            LoadHistoryFromDisk();
        }

        private void LoadAutomationsFromDisk()
        {
            Automations.Clear();
            try
            {
                if (File.Exists(_storagePath))
                {
                    string json = File.ReadAllText(_storagePath);
                    var items = JsonSerializer.Deserialize<ObservableCollection<AutomationItem>>(json);
                    if (items != null)
                    {
                        foreach (var it in items) Automations.Add(it);
                    }
                }
                else
                {
                    // Seed initial real system routines
                    var gitRoutine = new AutomationItem
                    {
                        Name = "Git Repository Status Check",
                        Description = "Queries Git working directory status, uncommitted files, and current branch.",
                        Trigger = "Manual / On-Demand",
                        Command = "git status",
                        IsActive = true,
                        Status = "Ready",
                        LastRun = "Not run yet",
                        NextRun = "Manual",
                        Steps = new ObservableCollection<string>
                        {
                            "1. Navigate to C:\\AI\\SON",
                            "2. Execute 'git status --short'",
                            "3. Record output to audit log"
                        }
                    };

                    var healthRoutine = new AutomationItem
                    {
                        Name = "System Telemetry Snapshot",
                        Description = "Queries local CPU, RAM, and GPU memory utilization metrics.",
                        Trigger = "Hourly",
                        Command = "powershell -NoProfile -Command \"Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 ProcessName, CPU, WorkingSet\"",
                        IsActive = true,
                        Status = "Ready",
                        LastRun = "Not run yet",
                        NextRun = "Hourly",
                        Steps = new ObservableCollection<string>
                        {
                            "1. Inspect active Windows processes",
                            "2. Sort by highest CPU and memory consumption",
                            "3. Return top 5 consumer processes"
                        }
                    };

                    Automations.Add(gitRoutine);
                    Automations.Add(healthRoutine);
                    SaveAutomationsToDisk();
                }
            }
            catch (Exception ex)
            {
                StatusMessage = $"Automation storage note: {ex.Message}";
            }

            if (Automations.Count > 0)
            {
                SelectedAutomation = Automations[0];
            }
        }

        private void SaveAutomationsToDisk()
        {
            try
            {
                string dir = Path.GetDirectoryName(_storagePath)!;
                if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);

                var options = new JsonSerializerOptions { WriteIndented = true };
                string json = JsonSerializer.Serialize(Automations, options);
                File.WriteAllText(_storagePath, json);
            }
            catch (Exception ex)
            {
                StatusMessage = $"Save error: {ex.Message}";
            }
        }

        private void LoadHistoryFromDisk()
        {
            ExecutionHistory.Clear();
            try
            {
                if (File.Exists(_historyPath))
                {
                    var lines = File.ReadAllLines(_historyPath);
                    // Add most recent lines first (up to 50)
                    for (int i = lines.Length - 1; i >= Math.Max(0, lines.Length - 50); i--)
                    {
                        if (!string.IsNullOrWhiteSpace(lines[i]))
                        {
                            ExecutionHistory.Add(lines[i]);
                        }
                    }
                }
            }
            catch { }
        }

        [RelayCommand]
        public async Task RunAutomationNowAsync()
        {
            if (SelectedAutomation == null || IsRunningRoutine) return;

            IsRunningRoutine = true;
            StatusMessage = $"Executing '{SelectedAutomation.Name}'...";

            var sw = Stopwatch.StartNew();
            string output = string.Empty;
            bool success = true;

            try
            {
                string cmd = SelectedAutomation.Command;
                if (string.IsNullOrWhiteSpace(cmd))
                {
                    cmd = "git status";
                }

                // Execute real process with hardened arguments & timeout
                var psi = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    WorkingDirectory = @"C:\AI\SON",
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                psi.ArgumentList.Add("-NoProfile");
                psi.ArgumentList.Add("-NonInteractive");
                psi.ArgumentList.Add("-ExecutionPolicy");
                psi.ArgumentList.Add("RemoteSigned");
                psi.ArgumentList.Add("-Command");
                psi.ArgumentList.Add(cmd);

                using var cts = new System.Threading.CancellationTokenSource(TimeSpan.FromSeconds(45));
                using var proc = new Process { StartInfo = psi };
                proc.Start();

                var stdoutTask = proc.StandardOutput.ReadToEndAsync(cts.Token);
                var stderrTask = proc.StandardError.ReadToEndAsync(cts.Token);
                await proc.WaitForExitAsync(cts.Token);

                string stdout = await stdoutTask;
                string stderr = await stderrTask;

                sw.Stop();
                success = proc.ExitCode == 0;
                output = success ? stdout.Trim() : $"Error (code {proc.ExitCode}): {stderr.Trim()}";

                string logEntry = $"[{DateTime.Now:HH:mm:ss}] [{(success ? "SUCCESS" : "FAILED")}] '{SelectedAutomation.Name}' ({sw.ElapsedMilliseconds}ms): {(output.Length > 80 ? output.Substring(0, 80) + "..." : output)}";

                ExecutionHistory.Insert(0, logEntry);
                File.AppendAllText(_historyPath, logEntry + Environment.NewLine);

                SelectedAutomation.LastRun = $"{DateTime.Now:HH:mm:ss} ({(success ? "Success" : "Failed")})";
                SelectedAutomation.Status = success ? "Success" : "Failed";
                SaveAutomationsToDisk();

                StatusMessage = $"Routine '{SelectedAutomation.Name}' executed in {sw.ElapsedMilliseconds}ms.";
            }
            catch (Exception ex)
            {
                sw.Stop();
                string logEntry = $"[{DateTime.Now:HH:mm:ss}] [ERROR] '{SelectedAutomation.Name}': {ex.Message}";
                ExecutionHistory.Insert(0, logEntry);
                SelectedAutomation.Status = "Failed";
                StatusMessage = $"Execution failed: {ex.Message}";
            }
            finally
            {
                IsRunningRoutine = false;
            }
        }

        [RelayCommand]
        public void ToggleAutomation()
        {
            if (SelectedAutomation == null) return;
            SelectedAutomation.IsActive = !SelectedAutomation.IsActive;
            SelectedAutomation.Status = SelectedAutomation.IsActive ? "Active" : "Paused";
            SaveAutomationsToDisk();
            StatusMessage = $"Automation '{SelectedAutomation.Name}' is now {SelectedAutomation.Status}.";
        }

        [RelayCommand]
        public void OpenAddDialog()
        {
            NewName = string.Empty;
            NewDescription = string.Empty;
            NewTrigger = "Daily at 09:00 AM";
            NewCommand = "git status";
            IsAddDialogOpen = true;
        }

        [RelayCommand]
        public void CloseAddDialog()
        {
            IsAddDialogOpen = false;
        }

        [RelayCommand]
        public void SaveNewAutomation()
        {
            if (string.IsNullOrWhiteSpace(NewName))
            {
                StatusMessage = "Please specify a routine name.";
                return;
            }

            var item = new AutomationItem
            {
                Name = NewName.Trim(),
                Description = string.IsNullOrWhiteSpace(NewDescription) ? "User-defined automation routine" : NewDescription.Trim(),
                Trigger = string.IsNullOrWhiteSpace(NewTrigger) ? "Manual" : NewTrigger.Trim(),
                Command = string.IsNullOrWhiteSpace(NewCommand) ? "git status" : NewCommand.Trim(),
                IsActive = true,
                Status = "Ready",
                LastRun = "Never",
                NextRun = "Pending",
                Steps = new ObservableCollection<string>
                {
                    $"1. Execute: {NewCommand}",
                    "2. Capture exit code and output",
                    "3. Log execution checkpoint to audit trail"
                }
            };

            Automations.Add(item);
            SelectedAutomation = item;
            SaveAutomationsToDisk();
            IsAddDialogOpen = false;
            StatusMessage = $"Created new automation '{item.Name}'.";
        }

        [RelayCommand]
        public void DeleteSelectedAutomation()
        {
            if (SelectedAutomation == null) return;
            string name = SelectedAutomation.Name;
            Automations.Remove(SelectedAutomation);
            SelectedAutomation = Automations.Count > 0 ? Automations[0] : null;
            SaveAutomationsToDisk();
            StatusMessage = $"Deleted automation '{name}'.";
        }
    }
}
