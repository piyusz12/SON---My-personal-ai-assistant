// SON.Desktop/Views/MainWindow.xaml.cs
using System.Windows;
using System.Windows.Input;

namespace SON.Desktop.Views
{
    public partial class MainWindow : Window
    {
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
    }
}
