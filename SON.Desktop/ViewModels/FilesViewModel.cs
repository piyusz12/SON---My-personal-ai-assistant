// SON.Desktop/ViewModels/FilesViewModel.cs — AI File Interaction Workspace
using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Models;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class FilesViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;

        [ObservableProperty]
        private string currentDirectory = @"C:\AI\SON";

        [ObservableProperty]
        private string searchQuery = string.Empty;

        [ObservableProperty]
        private FileWorkspaceItem? selectedFile;

        [ObservableProperty]
        private string filePreviewContent = string.Empty;

        [ObservableProperty]
        private string aiSummary = string.Empty;

        [ObservableProperty]
        private bool isAnalyzing = false;

        [ObservableProperty]
        private string statusMessage = "Project files scanned. Click any file to inspect or summarize.";

        public ObservableCollection<FileWorkspaceItem> Files { get; } = new();
        private readonly ObservableCollection<FileWorkspaceItem> _allLoadedFiles = new();

        public FilesViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
            LoadDirectory(CurrentDirectory);
        }

        [RelayCommand]
        public void LoadDirectory(string? dirPath)
        {
            string path = string.IsNullOrWhiteSpace(dirPath) ? @"C:\AI\SON" : dirPath.Trim();
            if (!Directory.Exists(path))
            {
                StatusMessage = $"Directory not found: {path}";
                return;
            }

            CurrentDirectory = path;
            Files.Clear();
            _allLoadedFiles.Clear();

            try
            {
                var dirInfo = new DirectoryInfo(path);

                // Add subdirectories first
                foreach (var dir in dirInfo.GetDirectories().OrderBy(d => d.Name))
                {
                    if (dir.Name.StartsWith(".") || dir.Name == "__pycache__" || dir.Name == "bin" || dir.Name == "obj")
                        continue;

                    var item = new FileWorkspaceItem
                    {
                        Name = $"📁 {dir.Name}",
                        FullPath = dir.FullName,
                        Extension = "[DIR]",
                        SizeBytes = 0,
                        LastModified = dir.LastWriteTime,
                        Category = "Directory"
                    };
                    _allLoadedFiles.Add(item);
                    Files.Add(item);
                }

                // Add files
                foreach (var fi in dirInfo.GetFiles().OrderBy(f => f.Name))
                {
                    if (fi.Name.StartsWith(".") || fi.Extension == ".pyc")
                        continue;

                    string cat = fi.Extension switch
                    {
                        ".py" => "Python Source",
                        ".cs" => "C# Source",
                        ".xaml" => "WPF XAML",
                        ".json" => "JSON Config",
                        ".md" => "Markdown Doc",
                        ".ico" or ".png" or ".jpg" => "Image Asset",
                        _ => "File"
                    };

                    var item = new FileWorkspaceItem
                    {
                        Name = fi.Name,
                        FullPath = fi.FullName,
                        Extension = fi.Extension,
                        SizeBytes = fi.Length,
                        LastModified = fi.LastWriteTime,
                        Category = cat
                    };
                    _allLoadedFiles.Add(item);
                    Files.Add(item);
                }

                StatusMessage = $"Loaded {Files.Count} items from {path}";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Directory scan error: {ex.Message}";
            }

            if (Files.Count > 0)
            {
                SelectedFile = Files.FirstOrDefault(f => f.Category != "Directory") ?? Files[0];
            }
        }

        [RelayCommand]
        public void NavigateUp()
        {
            try
            {
                var parent = Directory.GetParent(CurrentDirectory);
                if (parent != null && parent.Exists)
                {
                    LoadDirectory(parent.FullName);
                }
            }
            catch { }
        }

        partial void OnSearchQueryChanged(string value)
        {
            Files.Clear();
            var matches = string.IsNullOrWhiteSpace(value)
                ? _allLoadedFiles
                : _allLoadedFiles.Where(f => f.Name.Contains(value, StringComparison.OrdinalIgnoreCase) ||
                                             f.Category.Contains(value, StringComparison.OrdinalIgnoreCase));

            foreach (var m in matches) Files.Add(m);
        }

        partial void OnSelectedFileChanged(FileWorkspaceItem? value)
        {
            if (value != null && value.Category == "Directory")
            {
                // Navigate into clicked directory
                LoadDirectory(value.FullPath);
                return;
            }

            LoadPreviewForSelectedFile();
        }

        private void LoadPreviewForSelectedFile()
        {
            if (SelectedFile == null || !File.Exists(SelectedFile.FullPath))
            {
                FilePreviewContent = "// Select a file to preview its contents.";
                AiSummary = string.Empty;
                return;
            }

            try
            {
                string text = File.ReadAllText(SelectedFile.FullPath);
                if (text.Length > 8000)
                {
                    text = text.Substring(0, 8000) + "\n\n... [Content truncated for preview performance] ...";
                }
                FilePreviewContent = text;
                AiSummary = string.Empty;
                StatusMessage = $"Viewing '{SelectedFile.Name}' ({SelectedFile.FormattedSize})";
            }
            catch (Exception ex)
            {
                FilePreviewContent = $"Error reading file: {ex.Message}";
            }
        }

        [RelayCommand]
        public async Task SummarizeWithAiAsync()
        {
            if (SelectedFile == null || !File.Exists(SelectedFile.FullPath)) return;

            IsAnalyzing = true;
            StatusMessage = $"Summarizing {SelectedFile.Name} with local model...";
            AiSummary = string.Empty;

            try
            {
                string fileContent = File.ReadAllText(SelectedFile.FullPath);
                if (fileContent.Length > 3000) fileContent = fileContent.Substring(0, 3000);

                string prompt = $"Analyze the purpose, key functions, and security considerations of this source file ({SelectedFile.Name}):\n\n```\n{fileContent}\n```\nProvide 4 concise, high-value bullet points.";

                if (_ipcClient.IsConnected)
                {
                    var resp = await _ipcClient.SendChatAsync(prompt, "conv_files");
                    if (resp != null && !string.IsNullOrEmpty(resp.Response))
                    {
                        AiSummary = resp.Response;
                        StatusMessage = "Summary generated by local AI.";
                        return;
                    }
                }

                // Explicit offline notice — zero fake simulation
                AiSummary = $"Backend Offline: Could not reach Python orchestrator.\n" +
                            $"• File: {SelectedFile.FullPath}\n" +
                            $"• Size: {SelectedFile.FormattedSize} | Last Modified: {SelectedFile.LastModified}\n" +
                            $"• Connect the SON backend service to enable full AI file summarization.";
                StatusMessage = "Backend disconnected.";
            }
            catch (Exception ex)
            {
                AiSummary = $"Analysis error: {ex.Message}";
                StatusMessage = "Summarization failed.";
            }
            finally
            {
                IsAnalyzing = false;
            }
        }
    }
}
