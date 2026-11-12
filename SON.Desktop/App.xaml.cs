// SON.Desktop/App.xaml.cs — Application Entry Point and DI Container Setup
using System;
using System.IO;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Microsoft.Extensions.DependencyInjection;
using SON.Desktop.Services;
using SON.Desktop.ViewModels;
using SON.Desktop.Views;

namespace SON.Desktop
{
    public partial class App : Application
    {
        private IServiceProvider? _serviceProvider;

        private static readonly string LogsDirectory = @"C:\AI\SON\logs";

        private static void SafeLogLifecycle(string message)
        {
            try
            {
                Directory.CreateDirectory(LogsDirectory);
                System.IO.File.AppendAllText(System.IO.Path.Combine(LogsDirectory, "app_lifecycle.log"), $"[{DateTime.Now}] {message}\n");
            }
            catch { }
        }

        private static void SafeWriteCrash(string filename, string content)
        {
            try
            {
                Directory.CreateDirectory(LogsDirectory);
                System.IO.File.WriteAllText(System.IO.Path.Combine(LogsDirectory, filename), $"[{DateTime.Now}]\n{content}\n");
            }
            catch { }
        }

        public static IServiceProvider Services { get; private set; } = null!;

        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            this.ShutdownMode = ShutdownMode.OnExplicitShutdown;

            SafeLogLifecycle("OnStartup started");

            // Prevent DirectX UCEERR_RENDERTHREADFAILURE crashes
            try
            {
                if ((RenderCapability.Tier >> 16) == 0)
                {
                    RenderOptions.ProcessRenderMode = RenderMode.SoftwareOnly;
                }
            }
            catch { }

            AppDomain.CurrentDomain.UnhandledException += (s, args) =>
            {
                SafeWriteCrash("crash.log", args.ExceptionObject?.ToString() ?? "Unknown AppDomain exception");
            };

            this.DispatcherUnhandledException += (s, args) =>
            {
                SafeWriteCrash("crash_dispatcher.log", args.Exception?.ToString() ?? "Unknown Dispatcher exception");
                if (args.Exception is System.Runtime.InteropServices.COMException comEx && (uint)comEx.ErrorCode == 0x88980406)
                {
                    try
                    {
                        RenderOptions.ProcessRenderMode = RenderMode.SoftwareOnly;
                        args.Handled = true;
                    }
                    catch { }
                }
            };

            var services = new ServiceCollection();
            ConfigureServices(services);
            _serviceProvider = services.BuildServiceProvider();
            Services = _serviceProvider;

            var mainWindow = _serviceProvider.GetRequiredService<MainWindow>();
            var mainVm = _serviceProvider.GetRequiredService<MainWindowViewModel>();
            this.MainWindow = mainWindow;
            mainWindow.DataContext = mainVm;

            try
            {
                mainWindow.Show();
            }
            catch (System.Runtime.InteropServices.COMException comEx) when ((uint)comEx.ErrorCode == 0x88980406)
            {
                SafeLogLifecycle("Encountered UCEERR_RENDERTHREADFAILURE, falling back to SoftwareOnly render mode");
                RenderOptions.ProcessRenderMode = RenderMode.SoftwareOnly;
                mainWindow.Show();
            }

            SafeLogLifecycle("MainWindow shown successfully");

            _ = mainVm.InitializeAsync();
        }

        private static void ConfigureServices(IServiceCollection services)
        {
            // Core IPC and Process Services
            services.AddSingleton<IIpcClient, NamedPipeIpcClient>();
            services.AddSingleton<IBackendProcessManager, BackendProcessManager>();
            services.AddSingleton<IScreenCaptureService, ScreenCaptureService>();

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
            SafeLogLifecycle($"OnExit called with exit code {e.ApplicationExitCode}");
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
