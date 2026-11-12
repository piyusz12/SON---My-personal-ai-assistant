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
        private readonly IScreenCaptureService _screenCaptureService;

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

        public VisionViewModel(IIpcClient ipcClient, IScreenCaptureService screenCaptureService)
        {
            _ipcClient = ipcClient;
            _screenCaptureService = screenCaptureService;
        }

        public override void OnNavigatedTo()
        {
            base.OnNavigatedTo();
            ScreenResolutionText = "Primary Display: Ready to capture";
        }

        private BitmapSource? CapturePrimaryScreen()
        {
            try
            {
                var bsrc = _screenCaptureService.CapturePrimaryDisplay();
                if (bsrc != null)
                {
                    _screenCaptureService.CaptureAndSaveDisplay();
                }
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
                    string savedPath = @"C:\AI\SON\data\screenshots\latest_capture.png";
                    var visionResp = await _ipcClient.AnalyzeVisionAsync(savedPath, query, mode);
                    if (!string.IsNullOrEmpty(visionResp))
                    {
                        AnalysisResult = visionResp;
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
