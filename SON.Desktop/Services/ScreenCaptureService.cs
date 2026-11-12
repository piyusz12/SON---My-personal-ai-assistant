// SON.Desktop/Services/ScreenCaptureService.cs — High-Performance Native GDI Screen Capture with Handle Guards
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media.Imaging;

namespace SON.Desktop.Services
{
    public class ScreenCaptureService : IScreenCaptureService
    {
        [DllImport("user32.dll")]
        private static extern IntPtr GetDesktopWindow();

        [DllImport("user32.dll")]
        private static extern IntPtr GetWindowDC(IntPtr hwnd);

        [DllImport("user32.dll")]
        private static extern int ReleaseDC(IntPtr hwnd, IntPtr hdc);

        [DllImport("gdi32.dll")]
        private static extern IntPtr CreateCompatibleDC(IntPtr hdc);

        [DllImport("gdi32.dll")]
        private static extern IntPtr CreateCompatibleBitmap(IntPtr hdc, int nWidth, int nHeight);

        [DllImport("gdi32.dll")]
        private static extern IntPtr SelectObject(IntPtr hdc, IntPtr hgdiobj);

        [DllImport("gdi32.dll")]
        private static extern bool BitBlt(IntPtr hdcDest, int nXDest, int nYDest, int nWidth, int nHeight, IntPtr hdcSrc, int nXSrc, int nYSrc, int dwRop);

        [DllImport("gdi32.dll")]
        private static extern bool DeleteDC(IntPtr hdc);

        [DllImport("gdi32.dll")]
        private static extern bool DeleteObject(IntPtr hObject);

        [DllImport("user32.dll")]
        private static extern int GetSystemMetrics(int smIndex);

        private const int SRCCOPY = 0x00CC0020;
        private const int SM_CXSCREEN = 0;
        private const int SM_CYSCREEN = 1;

        public BitmapSource? CapturePrimaryDisplay()
        {
            IntPtr hDesk = IntPtr.Zero;
            IntPtr hdcSrc = IntPtr.Zero;
            IntPtr hdcDest = IntPtr.Zero;
            IntPtr hBitmap = IntPtr.Zero;
            IntPtr hOld = IntPtr.Zero;

            try
            {
                hDesk = GetDesktopWindow();
                hdcSrc = GetWindowDC(hDesk);
                int w = GetSystemMetrics(SM_CXSCREEN);
                int h = GetSystemMetrics(SM_CYSCREEN);
                if (w <= 0) w = 1920;
                if (h <= 0) h = 1080;

                hdcDest = CreateCompatibleDC(hdcSrc);
                hBitmap = CreateCompatibleBitmap(hdcSrc, w, h);
                hOld = SelectObject(hdcDest, hBitmap);

                BitBlt(hdcDest, 0, 0, w, h, hdcSrc, 0, 0, SRCCOPY);

                var bsrc = Imaging.CreateBitmapSourceFromHBitmap(
                    hBitmap,
                    IntPtr.Zero,
                    Int32Rect.Empty,
                    BitmapSizeOptions.FromEmptyOptions());

                bsrc.Freeze();
                return bsrc;
            }
            catch
            {
                return null;
            }
            finally
            {
                if (hdcDest != IntPtr.Zero && hOld != IntPtr.Zero)
                {
                    SelectObject(hdcDest, hOld);
                }
                if (hBitmap != IntPtr.Zero)
                {
                    DeleteObject(hBitmap);
                }
                if (hdcDest != IntPtr.Zero)
                {
                    DeleteDC(hdcDest);
                }
                if (hDesk != IntPtr.Zero && hdcSrc != IntPtr.Zero)
                {
                    ReleaseDC(hDesk, hdcSrc);
                }
            }
        }

        public string CaptureAndSaveDisplay(string? targetFilePath = null)
        {
            var bsrc = CapturePrimaryDisplay();
            if (bsrc == null) throw new InvalidOperationException("Failed to capture primary display.");

            string screenshotsDir = @"C:\AI\SON\data\screenshots";
            Directory.CreateDirectory(screenshotsDir);
            string filePath = targetFilePath ?? Path.Combine(screenshotsDir, "latest_capture.png");

            var encoder = new PngBitmapEncoder();
            encoder.Frames.Add(BitmapFrame.Create(bsrc));
            using (var stream = new FileStream(filePath, FileMode.Create, FileAccess.Write))
            {
                encoder.Save(stream);
            }

            return filePath;
        }
    }
}

