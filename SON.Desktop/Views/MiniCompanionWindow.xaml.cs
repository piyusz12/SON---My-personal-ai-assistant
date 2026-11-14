// SON.Desktop/Views/MiniCompanionWindow.xaml.cs
using System;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Effects;
using SON.Desktop.Services;
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

            Loaded += (s, e) =>
            {
                WindowBackdropHelper.ApplyLiquidGlassBackdrop(this, 0x33080D1A);
            };

            _viewModel.RequestRestoreMainWindow += () =>
            {
                RestoreFullApp();
            };

            _viewModel.RequestMinimizeToTaskbar += () =>
            {
                MinimizeToTaskbar();
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
                        WindowBackdropHelper.ApplyLiquidGlassBackdrop(this, 0x33080D1A);
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

        private void MinimizeToTaskbar()
        {
            this.Hide();
            if (Application.Current.MainWindow is MainWindow main)
            {
                main.MinimizeToTaskbar();
            }
        }

        private void OuterGlassCapsule_MouseMove(object sender, MouseEventArgs e)
        {
            try
            {
                var pos = e.GetPosition(OuterGlassCapsule);
                double w = Math.Max(1.0, OuterGlassCapsule.ActualWidth);
                double h = Math.Max(1.0, OuterGlassCapsule.ActualHeight);

                double nx = Math.Clamp(pos.X / w, 0.0, 1.0);
                double ny = Math.Clamp(pos.Y / h, 0.0, 1.0);

                // Fluid liquid refraction specular tracking
                LiquidLightSpot.Center = new Point(nx, ny);
                LiquidLightSpot.GradientOrigin = new Point(nx, ny);

                // Dynamic liquid rim tilt tracking
                LiquidBorderBrush.StartPoint = new Point(nx * 0.4, 0.0);
                LiquidBorderBrush.EndPoint = new Point(1.0 - (nx * 0.4), 1.0);
            }
            catch { }
        }

        private void OuterGlassCapsule_MouseEnter(object sender, MouseEventArgs e)
        {
            try
            {
                var da = new DoubleAnimation(0.55, TimeSpan.FromMilliseconds(220));
                LiquidGlowEffect.BeginAnimation(DropShadowEffect.OpacityProperty, da);

                var db = new DoubleAnimation(34, TimeSpan.FromMilliseconds(220));
                LiquidGlowEffect.BeginAnimation(DropShadowEffect.BlurRadiusProperty, db);
            }
            catch { }
        }

        private void OuterGlassCapsule_MouseLeave(object sender, MouseEventArgs e)
        {
            try
            {
                var da = new DoubleAnimation(0.32, TimeSpan.FromMilliseconds(300));
                LiquidGlowEffect.BeginAnimation(DropShadowEffect.OpacityProperty, da);

                var db = new DoubleAnimation(28, TimeSpan.FromMilliseconds(300));
                LiquidGlowEffect.BeginAnimation(DropShadowEffect.BlurRadiusProperty, db);

                var pa = new PointAnimation(new Point(0.5, 0.0), TimeSpan.FromMilliseconds(350));
                LiquidLightSpot.BeginAnimation(RadialGradientBrush.CenterProperty, pa);
                LiquidLightSpot.BeginAnimation(RadialGradientBrush.GradientOriginProperty, pa);
            }
            catch { }
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


