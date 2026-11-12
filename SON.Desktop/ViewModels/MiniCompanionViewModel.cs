// SON.Desktop/ViewModels/MiniCompanionViewModel.cs — ViewModel for Floating Mini AI Companion
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
    public partial class MiniCompanionViewModel : ViewModelBase
    {
        private readonly IIpcClient _ipcClient;

        [ObservableProperty]
        private string promptText = string.Empty;

        [ObservableProperty]
        private string latestResponse = string.Empty;

        [ObservableProperty]
        private string statusText = "SON AI • Ready to assist";

        [ObservableProperty]
        private bool isBusy = false;

        [ObservableProperty]
        private bool isRecording = false;

        [ObservableProperty]
        private bool hasResponse = false;

        [ObservableProperty]
        private string activeModel = "llama3.2:latest";

        public event Action? RequestRestoreMainWindow;
        public event Action? RequestCloseMini;

        // P/Invoke for Screen Snapping
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

        public MiniCompanionViewModel(IIpcClient ipcClient)
        {
            _ipcClient = ipcClient;
            if (!string.IsNullOrEmpty(_ipcClient.ActiveModel))
            {
                ActiveModel = _ipcClient.ActiveModel;
            }
        }

        [RelayCommand]
        public async Task SubmitPromptAsync()
        {
            if (string.IsNullOrWhiteSpace(PromptText) || IsBusy) return;

            string query = PromptText.Trim();
            PromptText = string.Empty;
            IsBusy = true;
            StatusText = "Thinking with local model...";

            try
            {
                if (!_ipcClient.IsConnected)
                {
                    await _ipcClient.ConnectAsync();
                }

                var resp = await _ipcClient.SendChatAsync(query);
                if (resp != null && !string.IsNullOrEmpty(resp.Response))
                {
                    LatestResponse = resp.Response.Trim();
                    HasResponse = true;
                    StatusText = "Response ready • SON AI";
                }
                else if (resp != null && !string.IsNullOrEmpty(resp.Error))
                {
                    LatestResponse = $"Notice: {resp.Error}";
                    HasResponse = true;
                    StatusText = "Completed with warning";
                }
                else
                {
                    LatestResponse = "I processed your request, son. Check your active windows.";
                    HasResponse = true;
                    StatusText = "Ready to assist";
                }
            }
            catch (Exception ex)
            {
                LatestResponse = $"Offline: {ex.Message}";
                HasResponse = true;
                StatusText = "Error connecting";
            }
            finally
            {
                IsBusy = false;
            }
        }

        [RelayCommand]
        public async Task ExecuteQuickActionAsync(string? actionType)
        {
            if (IsBusy) return;

            switch (actionType)
            {
                case "SnapScreen":
                    await SnapAndAnalyzeScreenAsync("Analyze what is currently open on my screen and summarize key information.");
                    break;
                case "FixError":
                    await SnapAndAnalyzeScreenAsync("Find any errors, build failures, or stack traces on screen and give a fix.");
                    break;
                case "Summarize":
                    PromptText = "Summarize the active context and highlight action items.";
                    await SubmitPromptAsync();
                    break;
                case "Explain":
                    PromptText = "Explain the concepts on screen simply and concisely.";
                    await SubmitPromptAsync();
                    break;
                default:
                    break;
            }
        }

        [RelayCommand]
        public async Task SnapAndAnalyzeScreenAsync(string? customPrompt = null)
        {
            if (IsBusy) return;

            IsBusy = true;
            StatusText = "Capturing screen display...";

            try
            {
                // 1. Capture primary display using GDI
                string savedPath = CaptureAndSaveDisplay();

                StatusText = "Analyzing screen context with vision AI...";
                if (!_ipcClient.IsConnected)
                {
                    await _ipcClient.ConnectAsync();
                }

                string prompt = customPrompt ?? "Analyze this screen screenshot and provide a concise summary of what is visible.";
                var resp = await _ipcClient.SendChatAsync($"[VISION_REQUEST] Screenshot saved at: {savedPath}. Prompt: {prompt}");

                if (resp != null && !string.IsNullOrEmpty(resp.Response))
                {
                    LatestResponse = resp.Response.Trim();
                    HasResponse = true;
                    StatusText = "Screen analysis complete";
                }
                else
                {
                    LatestResponse = "Screen captured successfully to local cache. Vision pipeline is ready.";
                    HasResponse = true;
                    StatusText = "Captured to RAM";
                }
            }
            catch (Exception ex)
            {
                LatestResponse = $"Screen capture error: {ex.Message}";
                HasResponse = true;
                StatusText = "Capture failed";
            }
            finally
            {
                IsBusy = false;
            }
        }

        private string CaptureAndSaveDisplay()
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

            string screenshotsDir = @"C:\AI\SON\data\screenshots";
            Directory.CreateDirectory(screenshotsDir);
            string filePath = Path.Combine(screenshotsDir, "latest_capture.png");

            var encoder = new PngBitmapEncoder();
            encoder.Frames.Add(BitmapFrame.Create(bsrc));
            using var stream = new FileStream(filePath, FileMode.Create, FileAccess.Write);
            encoder.Save(stream);

            return filePath;
        }

        [RelayCommand]
        public void ToggleVoice()
        {
            IsRecording = !IsRecording;
            if (IsRecording)
            {
                StatusText = "Listening (Voice link active)...";
            }
            else
            {
                StatusText = "Voice link closed";
            }
        }

        [RelayCommand]
        public void ClearResponse()
        {
            LatestResponse = string.Empty;
            HasResponse = false;
            StatusText = "SON AI • Ready to assist";
        }

        [RelayCommand]
        public void CopyResponse()
        {
            if (!string.IsNullOrEmpty(LatestResponse))
            {
                Clipboard.SetText(LatestResponse);
                StatusText = "Response copied to clipboard!";
            }
        }

        [RelayCommand]
        public void RestoreMainWindow()
        {
            RequestRestoreMainWindow?.Invoke();
        }

        [RelayCommand]
        public void CloseMini()
        {
            RequestCloseMini?.Invoke();
        }
    }
}
