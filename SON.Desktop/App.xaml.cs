// SON.Desktop/App.xaml.cs — Application Entry Point and DI Container Setup
using System;
using System.Windows;
using Microsoft.Extensions.DependencyInjection;
using SON.Desktop.Services;
using SON.Desktop.ViewModels;
using SON.Desktop.Views;

namespace SON.Desktop
{
    public partial class App : Application
    {
        private IServiceProvider? _serviceProvider;

        public static IServiceProvider Services { get; private set; } = null!;

        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            var services = new ServiceCollection();
            ConfigureServices(services);
            _serviceProvider = services.BuildServiceProvider();
            Services = _serviceProvider;

            var mainWindow = _serviceProvider.GetRequiredService<MainWindow>();
            var mainVm = _serviceProvider.GetRequiredService<MainWindowViewModel>();
            mainWindow.DataContext = mainVm;
            mainWindow.Show();

            _ = mainVm.InitializeAsync();
        }

        private static void ConfigureServices(IServiceCollection services)
        {
            // Core IPC and Process Services
            services.AddSingleton<IIpcClient, NamedPipeIpcClient>();
            services.AddSingleton<IBackendProcessManager, BackendProcessManager>();

            // ViewModels
            services.AddSingleton<MainWindowViewModel>();
            services.AddSingleton<HomeViewModel>();
            services.AddSingleton<ChatViewModel>();
            services.AddSingleton<VoiceViewModel>();
            services.AddSingleton<MemoryViewModel>();
            services.AddSingleton<SettingsViewModel>();
            services.AddSingleton<SecurityViewModel>();

            // Navigation Service with ViewModel factory
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

            // Views
            services.AddSingleton<MainWindow>();
        }

        protected override void OnExit(ExitEventArgs e)
        {
            if (_serviceProvider != null)
            {
                var backendManager = _serviceProvider.GetService<IBackendProcessManager>();
                backendManager?.Dispose();

                var ipcClient = _serviceProvider.GetService<IIpcClient>();
                ipcClient?.Dispose();
            }
            base.OnExit(e);
        }
    }
}
