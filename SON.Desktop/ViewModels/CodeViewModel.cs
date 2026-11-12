// SON.Desktop/ViewModels/CodeViewModel.cs — AI Developer Coding Workspace
using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Models;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class CodeViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;

        [ObservableProperty]
        private string activeFilePath = @"C:\AI\SON\core\orchestrator.py";

        [ObservableProperty]
        private string activeFileName = "orchestrator.py";

        [ObservableProperty]
        private string codeSnippet = string.Empty;

        [ObservableProperty]
        private string aiSuggestion = string.Empty;

        [ObservableProperty]
        private bool isProcessingAi = false;

        [ObservableProperty]
        private string terminalInput = "python -m pytest tests/test_v3_remediation_waves.py -q";

        [ObservableProperty]
        private bool isRunningTerminal = false;

        [ObservableProperty]
        private string statusMessage = "Code workspace ready. Edit code or run terminal commands.";

        public ObservableCollection<string> TerminalLogs { get; } = new();

        public CodeViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
            LoadSourceFile(ActiveFilePath);
            TerminalLogs.Add($"[{DateTime.Now:HH:mm:ss}] [SON Terminal] Ready. Workspace: C:\\AI\\SON");
        }

        [RelayCommand]
        public void LoadSourceFile(string path)
        {
            if (File.Exists(path))
            {
                try
                {
                    ActiveFilePath = path;
                    ActiveFileName = Path.GetFileName(path);
                    CodeSnippet = File.ReadAllText(path);
                    StatusMessage = $"Loaded '{ActiveFileName}' ({CodeSnippet.Length} characters)";
                }
                catch (Exception ex)
                {
                    StatusMessage = $"Error loading file: {ex.Message}";
                }
            }
            else
            {
                CodeSnippet = "# Enter or paste source code here to analyze with AI...";
            }
        }

        [RelayCommand]
        public void SaveActiveFile()
        {
            if (string.IsNullOrWhiteSpace(ActiveFilePath)) return;

            try
            {
                File.WriteAllText(ActiveFilePath, CodeSnippet);
                StatusMessage = $"Saved changes to '{ActiveFileName}' successfully.";
                TerminalLogs.Insert(0, $"[{DateTime.Now:HH:mm:ss}] [FS] File '{ActiveFileName}' saved to disk.");
            }
            catch (Exception ex)
            {
                StatusMessage = $"Save error: {ex.Message}";
            }
        }

        [RelayCommand]
        public async Task ExecuteCodeActionAsync(string action)
        {
            if (string.IsNullOrWhiteSpace(CodeSnippet))
            {
                StatusMessage = "Code buffer is empty. Load or enter code to analyze.";
                return;
            }

            IsProcessingAi = true;
            StatusMessage = $"Running AI {action} on {ActiveFileName}...";
            AiSuggestion = string.Empty;

            try
            {
                string snippetSample = CodeSnippet.Length > 3000 ? CodeSnippet.Substring(0, 3000) : CodeSnippet;

                string prompt = action switch
                {
                    "Explain" => $"Explain the architecture, design patterns, and logic of this code ({ActiveFileName}):\n\n```\n{snippetSample}\n```",
                    "Refactor" => $"Suggest refactoring, async/await optimizations, and modern improvements for this code ({ActiveFileName}):\n\n```\n{snippetSample}\n```",
                    "Bugs" => $"Perform a static security and vulnerability audit on this code ({ActiveFileName}). Check for injection, race conditions, and unhandled errors:\n\n```\n{snippetSample}\n```",
                    "Tests" => $"Generate comprehensive unit tests for this code ({ActiveFileName}):\n\n```\n{snippetSample}\n```",
                    _ => $"Analyze this code:\n\n```\n{snippetSample}\n```"
                };

                if (_ipcClient.IsConnected)
                {
                    var resp = await _ipcClient.SendChatAsync(prompt, "conv_code");
                    if (resp != null && !string.IsNullOrEmpty(resp.Response))
                    {
                        AiSuggestion = resp.Response;
                        StatusMessage = $"AI {action} completed.";
                        TerminalLogs.Insert(0, $"[{DateTime.Now:HH:mm:ss}] [AI] Action '{action}' completed for {ActiveFileName}");
                        return;
                    }
                }

                // Explicit offline notice — zero fake simulation
                AiSuggestion = $"Backend Offline: Could not reach Python orchestrator.\n" +
                              $"• File: {ActiveFilePath}\n" +
                              $"• Action: {action}\n" +
                              $"• Connect the SON backend service to enable local LLM code assistance.";
                StatusMessage = "Backend disconnected.";
            }
            catch (Exception ex)
            {
                AiSuggestion = $"Error performing {action}: {ex.Message}";
            }
            finally
            {
                IsProcessingAi = false;
            }
        }

        [RelayCommand]
        public async Task RunTerminalCommandAsync()
        {
            if (string.IsNullOrWhiteSpace(TerminalInput) || IsRunningTerminal) return;

            string cmd = TerminalInput.Trim();
            IsRunningTerminal = true;
            StatusMessage = $"Executing: {cmd}...";
            TerminalLogs.Insert(0, $"[{DateTime.Now:HH:mm:ss}] > {cmd}");

            var sw = Stopwatch.StartNew();

            try
            {
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

                if (!string.IsNullOrWhiteSpace(stdout))
                {
                    var lines = stdout.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
                    foreach (var line in lines)
                    {
                        TerminalLogs.Insert(0, $"  {line}");
                    }
                }

                if (!string.IsNullOrWhiteSpace(stderr))
                {
                    TerminalLogs.Insert(0, $"[STDERR] {stderr.Trim()}");
                }

                TerminalLogs.Insert(0, $"[{DateTime.Now:HH:mm:ss}] Command exited with code {proc.ExitCode} in {sw.ElapsedMilliseconds}ms");
                StatusMessage = $"Command finished (code {proc.ExitCode}) in {sw.ElapsedMilliseconds}ms.";
            }
            catch (Exception ex)
            {
                TerminalLogs.Insert(0, $"[ERROR] Failed to run command: {ex.Message}");
                StatusMessage = "Execution failed.";
            }
            finally
            {
                IsRunningTerminal = false;
            }
        }
    }
}
