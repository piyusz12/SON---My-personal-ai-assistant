// SON.Desktop/Converters/Converters.cs — WPF Value Converters for UI Binding
using System;
using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;

namespace SON.Desktop.Converters
{
    public class BoolToVisibilityConverter : IValueConverter
    {
        public bool Invert { get; set; } = false;

        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            bool b = value is bool val && val;
            if (Invert) b = !b;
            return b ? Visibility.Visible : Visibility.Collapsed;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }

    public class InverseBoolConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            if (value is bool b) return !b;
            return false;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            if (value is bool b) return !b;
            return false;
        }
    }

    public class NotNullToBoolConverter : IValueConverter
    {
        public bool Invert { get; set; } = false;

        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            bool hasValue = value != null;
            if (value is string s) hasValue = !string.IsNullOrWhiteSpace(s);
            if (Invert) hasValue = !hasValue;
            return hasValue;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }

    public class NullToVisibilityConverter : IValueConverter
    {
        public bool Invert { get; set; } = false;

        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            bool isNull = value == null;
            if (value is string s) isNull = string.IsNullOrWhiteSpace(s);
            if (Invert) isNull = !isNull;
            return isNull ? Visibility.Visible : Visibility.Collapsed;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }

    internal static class BrushHelper
    {
        public static SolidColorBrush CreateFrozen(byte r, byte g, byte b)
        {
            var brush = new SolidColorBrush(Color.FromRgb(r, g, b));
            brush.Freeze();
            return brush;
        }
    }

    public class PageToNavBackgroundConverter : IValueConverter
    {
        private static readonly Brush ActiveBrush = BrushHelper.CreateFrozen(30, 41, 59); // #1E293B
        private static readonly Brush InactiveBrush = Brushes.Transparent;

        public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            if (value == null || parameter == null) return InactiveBrush;
            bool isMatch = string.Equals(value.ToString(), parameter.ToString(), StringComparison.OrdinalIgnoreCase);
            return isMatch ? ActiveBrush : InactiveBrush;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class PageToNavForegroundConverter : IValueConverter
    {
        private static readonly Brush ActiveBrush = BrushHelper.CreateFrozen(248, 250, 252); // #F8FAFC
        private static readonly Brush InactiveBrush = BrushHelper.CreateFrozen(148, 163, 184); // #94A3B8

        public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            if (value == null || parameter == null) return InactiveBrush;
            bool isMatch = string.Equals(value.ToString(), parameter.ToString(), StringComparison.OrdinalIgnoreCase);
            return isMatch ? ActiveBrush : InactiveBrush;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class PageToIndicatorVisibilityConverter : IValueConverter
    {
        public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            if (value == null || parameter == null) return Visibility.Collapsed;
            bool isMatch = string.Equals(value.ToString(), parameter.ToString(), StringComparison.OrdinalIgnoreCase);
            return isMatch ? Visibility.Visible : Visibility.Collapsed;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class RiskToColorConverter : IValueConverter
    {
        private static readonly Brush CriticalBrush = BrushHelper.CreateFrozen(239, 68, 68);    // Red
        private static readonly Brush HighBrush = BrushHelper.CreateFrozen(249, 115, 22);       // Orange
        private static readonly Brush MediumBrush = BrushHelper.CreateFrozen(234, 179, 8);      // Yellow
        private static readonly Brush LowBrush = BrushHelper.CreateFrozen(16, 185, 129);        // Emerald

        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            string risk = value?.ToString()?.ToUpperInvariant() ?? "LOW";
            return risk switch
            {
                "CRITICAL" => CriticalBrush,
                "HIGH" => HighBrush,
                "MEDIUM" => MediumBrush,
                _ => LowBrush,
            };
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class ConnectionStatusToBrushConverter : IValueConverter
    {
        private static readonly Brush ConnectedBrush = BrushHelper.CreateFrozen(16, 185, 129); // Emerald #10B981
        private static readonly Brush DisconnectedBrush = BrushHelper.CreateFrozen(239, 68, 68);  // Red #EF4444

        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            bool isConnected = value is bool b && b;
            return isConnected ? ConnectedBrush : DisconnectedBrush;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class AuditEventColorConverter : IValueConverter
    {
        private static readonly Brush SuccessBrush = BrushHelper.CreateFrozen(16, 185, 129); // Emerald #10B981
        private static readonly Brush ErrorBrush = BrushHelper.CreateFrozen(239, 68, 68); // Red #EF4444
        private static readonly Brush PendingBrush = BrushHelper.CreateFrozen(245, 158, 11); // Amber #F59E0B
        private static readonly Brush MutedBrush = BrushHelper.CreateFrozen(148, 163, 184); // Muted slate #94A3B8

        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            string text = value?.ToString() ?? string.Empty;
            if (text.Contains("[ALLOWED]") || text.Contains("SUCCESS") || text.Contains("APPROVED"))
            {
                return SuccessBrush;
            }
            if (text.Contains("[DENIED]") || text.Contains("FAILED") || text.Contains("ERROR"))
            {
                return ErrorBrush;
            }
            if (text.Contains("PENDING") || text.Contains("APPROVAL_REQUESTED"))
            {
                return PendingBrush;
            }
            return MutedBrush;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class ValueToPercentageBrushConverter : IValueConverter
    {
        private static readonly Brush RedBrush = BrushHelper.CreateFrozen(239, 68, 68); // Red
        private static readonly Brush AmberBrush = BrushHelper.CreateFrozen(245, 158, 11); // Amber
        private static readonly Brush EmeraldBrush = BrushHelper.CreateFrozen(16, 185, 129); // Emerald

        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            double val = 0;
            if (value is double d) val = d;
            else if (value != null && double.TryParse(value.ToString(), out double parsed)) val = parsed;

            if (val >= 85) return RedBrush;
            if (val >= 70) return AmberBrush;
            return EmeraldBrush;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class EqualityToBoolConverter : IValueConverter
    {
        public bool Invert { get; set; } = false;

        public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            string valStr = value?.ToString() ?? string.Empty;
            string paramStr = parameter?.ToString() ?? string.Empty;
            bool match = string.Equals(valStr, paramStr, StringComparison.OrdinalIgnoreCase);
            if (Invert) match = !match;
            return match;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class CountToVisibilityConverter : IValueConverter
    {
        public bool Invert { get; set; } = false;

        public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            int count = 0;
            if (value is int i) count = i;
            else if (value != null && int.TryParse(value.ToString(), out int parsed)) count = parsed;

            int target = 0;
            if (parameter != null && int.TryParse(parameter.ToString(), out int pTarget)) target = pTarget;

            bool isMatch = count == target;
            if (Invert) isMatch = !isMatch;
            return isMatch ? Visibility.Visible : Visibility.Collapsed;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class BoolToSidebarWidthConverter : IValueConverter
    {
        public double ExpandedWidth { get; set; } = 248;
        public double CollapsedWidth { get; set; } = 68;

        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            bool collapsed = value is bool b && b;
            return collapsed ? CollapsedWidth : ExpandedWidth;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class ResourceKeyToGeometryConverter : IValueConverter
    {
        public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            if (value is string key && Application.Current.TryFindResource(key) is Geometry geom)
            {
                return geom;
            }
            return Application.Current.TryFindResource("GeometryCommand") as Geometry;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }
}
