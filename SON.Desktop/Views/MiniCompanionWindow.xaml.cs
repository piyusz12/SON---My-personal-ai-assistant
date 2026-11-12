// SON.Desktop/Views/MiniCompanionWindow.xaml.cs
using System;
using System.Windows;
using System.Windows.Input;
using SON.Desktop.ViewModels;

namespace SON.Desktop.Views
{
    public partial class MiniCompanionWindow : Window
    {
        private readonly MiniCompanionViewModel _viewModel;

        public MiniCompanionWindow(MiniCompanionViewModel viewModel)
        {
            InitializeComponent();
            _viewModel = viewModel;
            DataContext = _viewModel;

            _viewModel.RequestRestoreMainWindow += () =>
            {
                RestoreFullApp();
            };

            _viewModel.RequestCloseMini += () =>
            {
                RestoreFullApp();
            };

            IsVisibleChanged += (s, e) =>
            {
                try
                {
                    if (IsVisible)
                    {
                        MiniCompanionStoryboard?.Resume(this);
                    }
                    else
                    {
                        MiniCompanionStoryboard?.Pause(this);
                    }
                }
                catch { }
            };
        }

        private void RestoreFullApp()
        {
            this.Hide();
            if (Application.Current.MainWindow is MainWindow main)
            {
                main.RestoreFromMini();
            }
        }

        private void Window_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            if (e.ButtonState == MouseButtonState.Pressed)
            {
                if (e.ClickCount == 2)
                {
                    RestoreFullApp();
                }
                else
                {
                    DragMove();
                }
            }
        }

        private void MiniInputBox_PreviewKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Key == Key.Enter)
            {
                if ((Keyboard.Modifiers & ModifierKeys.Shift) != ModifierKeys.Shift)
                {
                    e.Handled = true;
                    if (_viewModel.SubmitPromptCommand.CanExecute(null))
                    {
                        _viewModel.SubmitPromptCommand.Execute(null);
                    }
                }
            }
        }
    }
}

