// SON.Desktop/Services/IScreenCaptureService.cs — Unified Screen Capture Service Interface
using System.Windows.Media.Imaging;

namespace SON.Desktop.Services
{
    public interface IScreenCaptureService
    {
        BitmapSource? CapturePrimaryDisplay();
        string CaptureAndSaveDisplay(string? targetFilePath = null);
    }
}

