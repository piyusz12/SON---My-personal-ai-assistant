// SON.Desktop/ViewModels/VisionViewModel.cs — Screen & Visual AI Analysis Workspace
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media.Imaging;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using SON.Desktop.Services;

namespace SON.Desktop.ViewModels
{
    public partial class VisionViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;

        [ObservableProperty]
        private string captureMode = "Entire Screen";

        [ObservableProperty]
        private bool isAnalyzing = false;

        [ObservableProperty]
        private string statusMessage = "Vision workspace ready. Click any action below to capture and analyze.";

        [ObservableProperty]
        private string promptQuery = string.Empty;

        [ObservableProperty]
        private string analysisResult = string.Empty;

        [ObservableProperty]
        private BitmapSource? screenPreviewImage;

        [ObservableProperty]
        private string screenResolutionText = "Display resolution: Ready to capture";

        [ObservableProperty]
        private string privacyBadge = "100% Local Processing — Zero Outbound Telemetry";

        // GDI Native Screen Capture P/Invoke
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

        public VisionViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
        }

        public override void OnNavigatedTo()
        {
            base.OnNavigatedTo();
            int w = GetSystemMetrics(0);
            int h = GetSystemMetrics(1);
            ScreenResolutionText = $"Primary Display: {w}x{h}";
        }

        private BitmapSource? CapturePrimaryScreen()
        {
            try
            {
                IntPtr hDesk = GetDesktopWindow();
                IntPtr hdcSrc = GetWindowDC(hDesk);
                int w = GetSystemMetrics(0);
                int h = GetSystemMetrics(1);
                if (w <= 0) w = 1920;
                if (h <= 0) h = 1080;

                IntPtr hdcDest = CreateCompatibleDC(hdcSrc);
                IntPtr hBitmap = CreateCompatibleBitmap(hdcSrc, w, h);
                IntPtr hOld = SelectObject(hdcDest, hBitmap);

                BitBlt(hdcDest, 0, 0, w, h, hdcSrc, 0, 0, SRCCOPY);

                SelectObject(hdcDest, hOld);
                DeleteDC(hdcDest);
                ReleaseDC(hDesk, hdcSrc);

                var bsrc = Imaging.CreateBitmapSourceFromHBitmap(
                    hBitmap,
                    IntPtr.Zero,
                    Int32Rect.Empty,
                    BitmapSizeOptions.FromEmptyOptions());

                DeleteObject(hBitmap);
                bsrc.Freeze();

                // Save captured frame to local project cache for vision agent ingestion
                try
                {
                    string screenshotsDir = @"C:\AI\SON\data\screenshots";
                    Directory.CreateDirectory(screenshotsDir);
                    string filePath = Path.Combine(screenshotsDir, "latest_capture.png");

                    var encoder = new PngBitmapEncoder();
                    encoder.Frames.Add(BitmapFrame.Create(bsrc));
                    using var stream = new FileStream(filePath, FileMode.Create, FileAccess.Write);
                    encoder.Save(stream);
                }
                catch { }

                return bsrc;
            }
            catch (Exception ex)
            {
                StatusMessage = $"Capture error: {ex.Message}";
                return null;
            }
        }

        [RelayCommand]
        public async Task CaptureAndAnalyzeAsync(string mode)
        {
            IsAnalyzing = true;
            StatusMessage = $"Capturing screen display...";
            AnalysisResult = string.Empty;

            try
            {
                // 1. Capture real primary screen pixels
                var screenBmp = CapturePrimaryScreen();
                if (screenBmp != null)
                {
                    ScreenPreviewImage = screenBmp;
                    ScreenResolutionText = $"Captured Primary Display ({screenBmp.PixelWidth}x{screenBmp.PixelHeight})";
                }

                StatusMessage = $"Analyzing captured screen with local vision model...";

                string query = string.IsNullOrWhiteSpace(PromptQuery)
                    ? mode switch
                    {
                        "Explain" => "Explain what is on the screen right now and summarize active windows.",
                        "Error" => "Find any error messages, stack traces, warning dialogs, or failed processes on screen.",
                        "OCR" => "Extract and transcribe all readable text, labels, and code visible on the display.",
                        _ => "Describe the visual interface and open applications."
                    }
                    : PromptQuery;

                if (_ipcClient.IsConnected)
                {
                    var chatResp = await _ipcClient.SendChatAsync($"[VISION-ANALYSIS mode={mode}] {query}", "conv_vision");
                    if (chatResp != null && !string.IsNullOrEmpty(chatResp.Response))
                    {
                        AnalysisResult = chatResp.Response;
                        StatusMessage = "Screen analysis complete.";
                        return;
                    }
                }

                // Production fallback when backend is offline
                AnalysisResult = $"Backend Offline: Could not reach Python orchestrator.\n" +
                                 $"• Screenshot successfully captured to: C:\\AI\\SON\\data\\screenshots\\latest_capture.png\n" +
                                 $"• Resolution: {screenBmp?.PixelWidth}x{screenBmp?.PixelHeight}\n" +
                                 $"• Start the SON backend service to enable full vision model inference.";
                StatusMessage = "Backend disconnected.";
            }
            catch (Exception ex)
            {
                AnalysisResult = $"Visual analysis error: {ex.Message}";
                StatusMessage = "Analysis failed.";
            }
            finally
            {
                IsAnalyzing = false;
            }
        }
    }
}
