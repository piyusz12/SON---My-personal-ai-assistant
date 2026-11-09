// SON.Desktop/Services/NavigationService.cs — Page Navigation Implementation
using System;
using CommunityToolkit.Mvvm.ComponentModel;
using SON.Desktop.ViewModels;

namespace SON.Desktop.Services
{
    public class NavigationService : ObservableObject, INavigationService
    {
        private readonly Func<NavigationPage, ViewModelBase> _viewModelFactory;
        private NavigationPage _currentPage = NavigationPage.Home;
        private ViewModelBase? _currentViewModel;

        public NavigationPage CurrentPage => _currentPage;

        public ObservableObject? CurrentViewModel => _currentViewModel;

        public event EventHandler<NavigationPage>? Navigated;

        public NavigationService(Func<NavigationPage, ViewModelBase> viewModelFactory)
        {
            _viewModelFactory = viewModelFactory;
        }

        public void NavigateTo(NavigationPage page)
        {
            if (_currentPage == page && _currentViewModel != null) return;

            _currentViewModel?.OnNavigatedFrom();
            _currentPage = page;
            _currentViewModel = _viewModelFactory(page);
            _currentViewModel?.OnNavigatedTo();

            OnPropertyChanged(nameof(CurrentPage));
            OnPropertyChanged(nameof(CurrentViewModel));
            Navigated?.Invoke(this, page);
        }
    }
}

