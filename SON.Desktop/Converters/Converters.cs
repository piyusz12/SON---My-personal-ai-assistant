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

    public class RiskToColorConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
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

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }

    public class ConnectionStatusToBrushConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            bool isConnected = value is bool b && b;
            return isConnected
                ? new SolidColorBrush(Color.FromRgb(16, 185, 129)) // Emerald #10B981
                : new SolidColorBrush(Color.FromRgb(239, 68, 68));  // Red #EF4444
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }
}

