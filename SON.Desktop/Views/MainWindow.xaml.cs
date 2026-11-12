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

        public MainWindow()
        {
            InitializeComponent();
            Loaded += (s, e) => {
                System.IO.File.AppendAllText(@"C:\AI\SON\app_lifecycle.log", $"[{System.DateTime.Now}] MainWindow.Loaded event\n");
            };
            Closing += (s, e) => {
                System.IO.File.AppendAllText(@"C:\AI\SON\app_lifecycle.log", $"[{System.DateTime.Now}] MainWindow.Closing event (Cancel: {e.Cancel})\n");
            };
            Closed += (s, e) => {
                System.IO.File.AppendAllText(@"C:\AI\SON\app_lifecycle.log", $"[{System.DateTime.Now}] MainWindow.Closed event\n");
                Application.Current.Shutdown();
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
