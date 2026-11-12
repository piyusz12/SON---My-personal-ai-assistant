// SON.Desktop/Views/MainWindow.xaml.cs
using System;
using System.Windows;
using System.Windows.Input;
using Microsoft.Extensions.DependencyInjection;

namespace SON.Desktop.Views
{
    public partial class MainWindow : Window
    {
        private MiniCompanionWindow? _miniWindow;

        private static readonly string LogsDirectory = @"C:\AI\SON\logs";

        private static void SafeLogLifecycle(string message)
        {
            try
            {
                System.IO.Directory.CreateDirectory(LogsDirectory);
                System.IO.File.AppendAllText(System.IO.Path.Combine(LogsDirectory, "app_lifecycle.log"), $"[{System.DateTime.Now}] {message}\n");
            }
            catch { }
        }

        public MainWindow()
        {
            InitializeComponent();
            Loaded += (s, e) => {
                SafeLogLifecycle("MainWindow.Loaded event");
            };
            Closing += (s, e) => {
                SafeLogLifecycle($"MainWindow.Closing event (Cancel: {e.Cancel})");
            };
            Closed += (s, e) => {
                SafeLogLifecycle("MainWindow.Closed event");
                Application.Current.Shutdown();
            };
            IsVisibleChanged += (s, e) => {
                try
                {
                    if (IsVisible)
                    {
                        LivingAuroraStoryboard?.Resume(this);
                    }
                    else
                    {
                        LivingAuroraStoryboard?.Pause(this);
                    }
                }
                catch { }
            };
        }

        public void ShowMiniCompanion()
        {
            if (_miniWindow == null)
            {
                _miniWindow = App.Services.GetRequiredService<MiniCompanionWindow>();
            }

            var workArea = SystemParameters.WorkArea;
            _miniWindow.Left = workArea.Right - _miniWindow.Width - 24;
            _miniWindow.Top = workArea.Bottom - 260;
            if (_miniWindow.Top <= 0) _miniWindow.Top = workArea.Bottom - 220;

            this.Hide();
            _miniWindow.Show();
            _miniWindow.Activate();
        }

        public void RestoreFromMini()
        {
            if (_miniWindow != null)
            {
                _miniWindow.Hide();
            }
            this.Show();
            this.WindowState = WindowState.Normal;
            this.Activate();
        }

        protected override void OnStateChanged(EventArgs e)
        {
            base.OnStateChanged(e);
            if (WindowState == WindowState.Minimized)
            {
                ShowMiniCompanion();
            }
        }

        private void Header_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            if (e.ButtonState == MouseButtonState.Pressed)
            {
                if (e.ClickCount == 2)
                {
                    WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
                }
                else
                {
                    DragMove();
                }
            }
        }

        private void MinimizeButton_Click(object sender, RoutedEventArgs e)
        {
            ShowMiniCompanion();
        }

        private void MaximizeButton_Click(object sender, RoutedEventArgs e)
        {
            WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
        }

        private void CloseButton_Click(object sender, RoutedEventArgs e)
        {
            Close();
        }

        private bool _isAlwaysOnTop = false;

        private void PinButton_Click(object sender, RoutedEventArgs e)
        {
            _isAlwaysOnTop = !_isAlwaysOnTop;
            Topmost = _isAlwaysOnTop;
            if (sender is FrameworkElement fe)
            {
                fe.ToolTip = _isAlwaysOnTop ? "Always on Top: ON (Click to unpin)" : "Always on Top: OFF (Click to pin)";
            }
        }

        private void Window_PreviewKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Key == Key.M && (Keyboard.Modifiers & ModifierKeys.Control) == ModifierKeys.Control)
            {
                ShowMiniCompanion();
                e.Handled = true;
            }
            else if (e.Key == Key.K && (Keyboard.Modifiers & ModifierKeys.Control) == ModifierKeys.Control)
            {
                if (DataContext is ViewModels.MainWindowViewModel vm)
                {
                    vm.ToggleCommandPalette();
                    e.Handled = true;
                }
            }
            else if (e.Key == Key.B && (Keyboard.Modifiers & ModifierKeys.Control) == ModifierKeys.Control)
            {
                if (DataContext is ViewModels.MainWindowViewModel vm)
                {
                    vm.ToggleSidebar();
                    e.Handled = true;
                }
            }
            else if (e.Key == Key.Escape)
            {
                if (DataContext is ViewModels.MainWindowViewModel vm)
                {
                    if (vm.IsCommandPaletteOpen)
                    {
                        vm.CloseCommandPalette();
                        e.Handled = true;
                    }
                    else if (vm.IsPrivacyPopupOpen)
                    {
                        vm.TogglePrivacyPopup();
                        e.Handled = true;
                    }
                }
            }
        }
    }
}
