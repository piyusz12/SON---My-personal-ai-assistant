// SON.Desktop/Views/MainWindow.xaml.cs
using System;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;
using Microsoft.Extensions.DependencyInjection;

namespace SON.Desktop.Views
{
    public partial class MainWindow : Window
    {
        private MiniCompanionWindow? _miniWindow;
        private HwndSource? _hwndSource;

        private const int WM_NCHITTEST = 0x0084;
        private const int HTMAXBUTTON = 9;

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

        protected override void OnSourceInitialized(EventArgs e)
        {
            base.OnSourceInitialized(e);
            _hwndSource = PresentationSource.FromVisual(this) as HwndSource;
            _hwndSource?.AddHook(WndProc);

            // Auto-fit to laptop screen size dynamically
            try
            {
                var workArea = SystemParameters.WorkArea;
                MaxWidth = workArea.Width;
                MaxHeight = workArea.Height;
                if (Width > workArea.Width) Width = Math.Max(MinWidth, workArea.Width * 0.92);
                if (Height > workArea.Height) Height = Math.Max(MinHeight, workArea.Height * 0.90);
                Left = workArea.Left + (workArea.Width - Width) / 2;
                Top = workArea.Top + (workArea.Height - Height) / 2;
            }
            catch { }
        }

        private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if (msg == WM_NCHITTEST)
            {
                int x = (short)(lParam.ToInt32() & 0xFFFF);
                int y = (short)((lParam.ToInt32() >> 16) & 0xFFFF);
                var screenPoint = new Point(x, y);

                if (IsPointInsideElement(screenPoint, TitlebarMaximizeButton) ||
                    IsPointInsideElement(screenPoint, TrafficLightMaximizeButton))
                {
                    handled = true;
                    return new IntPtr(HTMAXBUTTON);
                }
            }
            return IntPtr.Zero;
        }

        private bool IsPointInsideElement(Point screenPoint, FrameworkElement? element)
        {
            if (element == null || !element.IsVisible) return false;
            try
            {
                var pos = element.PointToScreen(new Point(0, 0));
                var source = PresentationSource.FromVisual(this);
                double dpiScale = source?.CompositionTarget?.TransformToDevice.M11 ?? 1.0;
                var rect = new Rect(pos.X, pos.Y, element.ActualWidth * dpiScale, element.ActualHeight * dpiScale);
                return rect.Contains(screenPoint);
            }
            catch
            {
                return false;
            }
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

            if (WindowState != WindowState.Minimized)
            {
                WindowState = WindowState.Minimized;
            }

            _miniWindow.Show();
            _miniWindow.Activate();
        }

        public void HideMiniCompanion()
        {
            if (_miniWindow != null && _miniWindow.IsVisible)
            {
                _miniWindow.Hide();
            }
        }

        public void RestoreFromMini()
        {
            HideMiniCompanion();
            if (WindowState == WindowState.Minimized)
            {
                WindowState = WindowState.Normal;
            }
            Show();
            Activate();
        }

        protected override void OnStateChanged(EventArgs e)
        {
            base.OnStateChanged(e);
            if (WindowState == WindowState.Minimized)
            {
                ShowMiniCompanion();
            }
            else if (WindowState == WindowState.Normal || WindowState == WindowState.Maximized)
            {
                HideMiniCompanion();
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
            WindowState = WindowState.Minimized;
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
