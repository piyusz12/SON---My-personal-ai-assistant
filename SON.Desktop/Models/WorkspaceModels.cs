// SON.Desktop/Models/WorkspaceModels.cs — Core Models for SON V3 Workspaces
using System;
using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;

namespace SON.Desktop.Models
{
    public class CommandPaletteItem
    {
        public string Title { get; set; } = string.Empty;
        public string Subtitle { get; set; } = string.Empty;
        public string Category { get; set; } = "Actions"; // Actions, Navigation, Local AI, Settings
        public string Shortcut { get; set; } = string.Empty;
        public string IconKey { get; set; } = "GeometryCommand";
        public Action ExecuteAction { get; set; } = () => { };
    }

    public partial class AutomationItem : ObservableObject
    {
        public string Id { get; set; } = Guid.NewGuid().ToString("N");

        [ObservableProperty]
        private string name = string.Empty;

        [ObservableProperty]
        private string description = string.Empty;

        [ObservableProperty]
        private string trigger = "Scheduled (Daily 09:00)";

        [ObservableProperty]
        private bool isActive = true;

        [ObservableProperty]
        private string lastRun = "Today, 09:00";

        [ObservableProperty]
        private string nextRun = "Tomorrow, 09:00";

        [ObservableProperty]
        private string status = "Success";

        [ObservableProperty]
        private ObservableCollection<string> steps = new();
    }

    public partial class FileWorkspaceItem : ObservableObject
    {
        public string Name { get; set; } = string.Empty;
        public string FullPath { get; set; } = string.Empty;
        public string Extension { get; set; } = ".py";
        public long SizeBytes { get; set; } = 0;
        public DateTime LastModified { get; set; } = DateTime.Now;
        public string Category { get; set; } = "Code";

        public string FormattedSize => SizeBytes > 1024 * 1024
            ? $"{SizeBytes / (1024.0 * 1024.0):F1} MB"
            : $"{SizeBytes / 1024.0:F1} KB";
    }

    public partial class CodeTreeNode : ObservableObject
    {
        public string Name { get; set; } = string.Empty;
        public string RelativePath { get; set; } = string.Empty;
        public bool IsDirectory { get; set; } = false;
        public ObservableCollection<CodeTreeNode> Children { get; set; } = new();

        [ObservableProperty]
        private bool isExpanded = false;

        [ObservableProperty]
        private bool isSelected = false;
    }

    public partial class AgentTaskStep : ObservableObject
    {
        public int StepNumber { get; set; } = 1;

        [ObservableProperty]
        private string title = string.Empty;

        [ObservableProperty]
        private string description = string.Empty;

        [ObservableProperty]
        private string status = "Completed"; // Completed, Running, Pending, Failed, WaitingApproval

        [ObservableProperty]
        private string duration = "1.2s";

        [ObservableProperty]
        private string toolUsed = string.Empty;

        [ObservableProperty]
        private string output = string.Empty;
    }
}
