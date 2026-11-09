// SON.Desktop/ViewModels/MemoryViewModel.cs — Structured Long-Term Memory ViewModel
using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Models;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class MemoryViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;

        [ObservableProperty]
        private string searchQuery = string.Empty;

        [ObservableProperty]
        private string newFactText = string.Empty;

        [ObservableProperty]
        private string newFactCategory = "general";

        [ObservableProperty]
        private MemoryFactItem? selectedFact;

        [ObservableProperty]
        private bool isLoading = false;

        [ObservableProperty]
        private string statusMessage = string.Empty;

        public ObservableCollection<MemoryFactItem> Facts { get; } = new();
        private readonly ObservableCollection<MemoryFactItem> _allFacts = new();

        public MemoryViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
        }

        public override void OnNavigatedTo()
        {
            base.OnNavigatedTo();
            _ = LoadFactsAsync();
        }

        [RelayCommand]
        public async Task LoadFactsAsync()
        {
            if (!_ipcClient.IsConnected)
            {
                StatusMessage = "Backend disconnected: Cannot load persistent memory facts.";
                return;
            }

            IsLoading = true;
            StatusMessage = "Loading memory facts from SQLite...";
            try
            {
                var facts = await _ipcClient.GetMemoryFactsAsync();
                _allFacts.Clear();
                Facts.Clear();

                foreach (var f in facts)
                {
                    _allFacts.Add(f);
                    Facts.Add(f);
                }

                StatusMessage = $"Loaded {facts.Count} persistent memory records.";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Failed to load memory: {ex.Message}";
            }
            finally
            {
                IsLoading = false;
            }
        }

        partial void OnSearchQueryChanged(string value)
        {
            Facts.Clear();
            var filtered = string.IsNullOrWhiteSpace(value)
                ? _allFacts
                : _allFacts.Where(f => f.Fact.Contains(value, StringComparison.OrdinalIgnoreCase) ||
                                       f.Category.Contains(value, StringComparison.OrdinalIgnoreCase));

            foreach (var f in filtered)
            {
                Facts.Add(f);
            }
        }

        [RelayCommand]
        public async Task AddFactAsync()
        {
            if (string.IsNullOrWhiteSpace(NewFactText)) return;
            if (!_ipcClient.IsConnected)
            {
                StatusMessage = "Error: Backend disconnected.";
                return;
            }

            IsLoading = true;
            try
            {
                bool success = await _ipcClient.AddMemoryFactAsync(NewFactText.Trim(), NewFactCategory);
                if (success)
                {
                    NewFactText = string.Empty;
                    StatusMessage = "Fact stored successfully in persistent SQLite memory.";
                    await LoadFactsAsync();
                }
                else
                {
                    StatusMessage = "Failed to store fact.";
                }
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error: {ex.Message}";
            }
            finally
            {
                IsLoading = false;
            }
        }

        [RelayCommand]
        public async Task DeleteSelectedFactAsync()
        {
            if (SelectedFact == null) return;
            if (!_ipcClient.IsConnected)
            {
                StatusMessage = "Error: Backend disconnected.";
                return;
            }

            IsLoading = true;
            try
            {
                bool success = await _ipcClient.DeleteMemoryFactAsync(SelectedFact.Id);
                if (success)
                {
                    StatusMessage = $"Deleted fact #{SelectedFact.Id}.";
                    await LoadFactsAsync();
                }
                else
                {
                    StatusMessage = "Failed to delete fact.";
                }
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error: {ex.Message}";
            }
            finally
            {
                IsLoading = false;
            }
        }
    }
}

