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

            this.ShutdownMode = ShutdownMode.OnExplicitShutdown;

            System.IO.File.AppendAllText(@"C:\AI\SON\app_lifecycle.log", $"[{DateTime.Now}] OnStartup started\n");

            AppDomain.CurrentDomain.UnhandledException += (s, args) =>
            {
                try
                {
                    System.IO.File.WriteAllText(@"C:\AI\SON\crash.log", args.ExceptionObject?.ToString() ?? "Unknown AppDomain exception");
                }
                catch { }
            };

            this.DispatcherUnhandledException += (s, args) =>
            {
                try
                {
                    System.IO.File.WriteAllText(@"C:\AI\SON\crash_dispatcher.log", args.Exception?.ToString() ?? "Unknown Dispatcher exception");
                }
                catch { }
            };

            var services = new ServiceCollection();
            ConfigureServices(services);
            _serviceProvider = services.BuildServiceProvider();
            Services = _serviceProvider;

            var mainWindow = _serviceProvider.GetRequiredService<MainWindow>();
            var mainVm = _serviceProvider.GetRequiredService<MainWindowViewModel>();
            this.MainWindow = mainWindow;
            mainWindow.DataContext = mainVm;
            mainWindow.Show();

            System.IO.File.AppendAllText(@"C:\AI\SON\app_lifecycle.log", $"[{DateTime.Now}] MainWindow shown successfully\n");

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
            services.AddSingleton<VisionViewModel>();
            services.AddSingleton<AutomationViewModel>();
            services.AddSingleton<FilesViewModel>();
            services.AddSingleton<CodeViewModel>();
            services.AddSingleton<TasksViewModel>();
            services.AddSingleton<SettingsViewModel>();
            services.AddSingleton<SecurityViewModel>();
            services.AddSingleton<MiniCompanionViewModel>();

            // Navigation Service with ViewModel factory
            services.AddSingleton<INavigationService>(sp =>
            {
                return new NavigationService(page => page switch
                {
                    NavigationPage.Home => sp.GetRequiredService<HomeViewModel>(),
                    NavigationPage.Chat => sp.GetRequiredService<ChatViewModel>(),
                    NavigationPage.Voice => sp.GetRequiredService<VoiceViewModel>(),
                    NavigationPage.Memory => sp.GetRequiredService<MemoryViewModel>(),
                    NavigationPage.Vision => sp.GetRequiredService<VisionViewModel>(),
                    NavigationPage.Automation => sp.GetRequiredService<AutomationViewModel>(),
                    NavigationPage.Files => sp.GetRequiredService<FilesViewModel>(),
                    NavigationPage.Code => sp.GetRequiredService<CodeViewModel>(),
                    NavigationPage.Tasks => sp.GetRequiredService<TasksViewModel>(),
                    NavigationPage.Security => sp.GetRequiredService<SecurityViewModel>(),
                    NavigationPage.Settings => sp.GetRequiredService<SettingsViewModel>(),
                    _ => sp.GetRequiredService<HomeViewModel>(),
                });
            });

            // Views
            services.AddSingleton<MainWindow>();
            services.AddSingleton<MiniCompanionWindow>();
        }

        protected override void OnExit(ExitEventArgs e)
        {
            System.IO.File.AppendAllText(@"C:\AI\SON\app_lifecycle.log", $"[{DateTime.Now}] OnExit called with exit code {e.ApplicationExitCode}\n");
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
