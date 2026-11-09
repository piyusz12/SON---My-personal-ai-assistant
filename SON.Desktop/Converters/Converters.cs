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

    public class PageToNavBackgroundConverter : IValueConverter
    {
        private static readonly Brush ActiveBrush = new SolidColorBrush(Color.FromRgb(30, 41, 59)); // #1E293B
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
        private static readonly Brush ActiveBrush = new SolidColorBrush(Color.FromRgb(248, 250, 252)); // #F8FAFC
        private static readonly Brush InactiveBrush = new SolidColorBrush(Color.FromRgb(148, 163, 184)); // #94A3B8

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
        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            string risk = value?.ToString()?.ToUpperInvariant() ?? "LOW";
            return risk switch
            {
                "CRITICAL" => new SolidColorBrush(Color.FromRgb(239, 68, 68)),    // Red
                "HIGH" => new SolidColorBrush(Color.FromRgb(249, 115, 22)),       // Orange
                "MEDIUM" => new SolidColorBrush(Color.FromRgb(234, 179, 8)),      // Yellow
                _ => new SolidColorBrush(Color.FromRgb(16, 185, 129)),            // Emerald
            };
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class ConnectionStatusToBrushConverter : IValueConverter
    {
        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            bool isConnected = value is bool b && b;
            return isConnected
                ? new SolidColorBrush(Color.FromRgb(16, 185, 129)) // Emerald #10B981
                : new SolidColorBrush(Color.FromRgb(239, 68, 68));  // Red #EF4444
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class AuditEventColorConverter : IValueConverter
    {
        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            string text = value?.ToString() ?? string.Empty;
            if (text.Contains("[ALLOWED]") || text.Contains("SUCCESS") || text.Contains("APPROVED"))
            {
                return new SolidColorBrush(Color.FromRgb(16, 185, 129)); // Emerald #10B981
            }
            if (text.Contains("[DENIED]") || text.Contains("FAILED") || text.Contains("ERROR"))
            {
                return new SolidColorBrush(Color.FromRgb(239, 68, 68)); // Red #EF4444
            }
            if (text.Contains("PENDING") || text.Contains("APPROVAL_REQUESTED"))
            {
                return new SolidColorBrush(Color.FromRgb(245, 158, 11)); // Amber #F59E0B
            }
            return new SolidColorBrush(Color.FromRgb(148, 163, 184)); // Muted slate #94A3B8
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }

    public class ValueToPercentageBrushConverter : IValueConverter
    {
        public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        {
            double val = 0;
            if (value is double d) val = d;
            else if (value != null && double.TryParse(value.ToString(), out double parsed)) val = parsed;

            if (val >= 85) return new SolidColorBrush(Color.FromRgb(239, 68, 68)); // Red
            if (val >= 70) return new SolidColorBrush(Color.FromRgb(245, 158, 11)); // Amber
            return new SolidColorBrush(Color.FromRgb(16, 185, 129)); // Emerald
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotImplementedException();
    }
}
