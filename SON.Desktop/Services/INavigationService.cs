// SON.Desktop/Services/INavigationService.cs — View Switching and Navigation Interface
using System;
using CommunityToolkit.Mvvm.ComponentModel;

namespace SON.Desktop.Services
{
    public enum NavigationPage
    {
        Home,
        Chat,
        Voice,
        Memory,
        Vision,
        Automation,
        Files,
        Code,
        Tasks,
        Security,
        Settings,
    }

    public interface INavigationService
    {
        NavigationPage CurrentPage { get; }
        ObservableObject? CurrentViewModel { get; }

        event EventHandler<NavigationPage>? Navigated;

        void NavigateTo(NavigationPage page);
    }
}
