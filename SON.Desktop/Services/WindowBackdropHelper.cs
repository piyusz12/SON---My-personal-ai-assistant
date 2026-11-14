// SON.Desktop/Services/WindowBackdropHelper.cs — Native Windows 11 Liquid Glass & Backdrop Blur
using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

namespace SON.Desktop.Services
{
    /// <summary>
    /// Provides hardware-accelerated Windows 11 / Windows 10 Acrylic & Backdrop Blur
    /// allowing SON windows to react like genuine liquid glass with other running applications.
    /// </summary>
    public static class WindowBackdropHelper
    {
        [DllImport("user32.dll")]
        private static extern int SetWindowCompositionAttribute(IntPtr hwnd, ref WindowCompositionAttributeData data);

        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int attrValue, int attrSize);

        [DllImport("dwmapi.dll")]
        private static extern int DwmExtendFrameIntoClientArea(IntPtr hwnd, ref MARGINS pMarInset);

        [StructLayout(LayoutKind.Sequential)]
        private struct MARGINS
        {
            public int cxLeftWidth;
            public int cxRightWidth;
            public int cyTopHeight;
            public int cyBottomHeight;
        }

        private enum AccentState
        {
            ACCENT_DISABLED = 0,
            ACCENT_ENABLE_GRADIENT = 1,
            ACCENT_ENABLE_TRANSPARENTGRADIENT = 2,
            ACCENT_ENABLE_BLURBEHIND = 3,
            ACCENT_ENABLE_ACRYLICBLURBEHIND = 4,
            ACCENT_ENABLE_HOSTBACKDROP = 5,
            ACCENT_INVALID_STATE = 6
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct AccentPolicy
        {
            public AccentState AccentState;
            public int AccentFlags;
            public int GradientColor; // 0xAABBGGRR
            public int AnimationId;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct WindowCompositionAttributeData
        {
            public WindowCompositionAttribute Attribute;
            public IntPtr Data;
            public int SizeOfData;
        }

        private enum WindowCompositionAttribute
        {
            WCA_ACCENT_POLICY = 19
        }

        private const int DWMWA_SYSTEMBACKDROP_TYPE = 38;
        private const int DWMSBT_AUTO = 0;
        private const int DWMSBT_NONE = 1;
        private const int DWMSBT_MAINWINDOW = 2;       // Mica
        private const int DWMSBT_TRANSIENTWINDOW = 3;   // Acrylic
        private const int DWMSBT_TABBEDWINDOW = 4;      // Mica Alt

        /// <summary>
        /// Applies genuine liquid glass acrylic blur-behind to the window,
        /// blurring other applications behind it in real time.
        /// </summary>
        /// <param name="window">Target WPF Window</param>
        /// <param name="tintColor">0xAABBGGRR hex color for the subtle liquid tint (default 0x33080D1A)</param>
        public static void ApplyLiquidGlassBackdrop(Window window, uint tintColor = 0x33080D1A)
        {
            try
            {
                var hwnd = new WindowInteropHelper(window).EnsureHandle();
                if (hwnd == IntPtr.Zero) return;

                // 1. Extend DWM frame into client area
                var margins = new MARGINS { cxLeftWidth = -1, cxRightWidth = -1, cyTopHeight = -1, cyBottomHeight = -1 };
                DwmExtendFrameIntoClientArea(hwnd, ref margins);

                // 2. Request Windows 11 DWM TransientWindow (Acrylic) backdrop
                int backdrop = DWMSBT_TRANSIENTWINDOW;
                DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ref backdrop, sizeof(int));

                // 3. Apply SetWindowCompositionAttribute with ACCENT_ENABLE_ACRYLICBLURBEHIND
                SetAcrylicAccent(hwnd, tintColor);
            }
            catch
            {
                // Graceful fallback for non-DWM or restricted sandbox environments
            }
        }

        private static void SetAcrylicAccent(IntPtr hwnd, uint tintColor)
        {
            var accent = new AccentPolicy
            {
                AccentState = AccentState.ACCENT_ENABLE_ACRYLICBLURBEHIND,
                AccentFlags = 2, // 2 = draw all borders with blur
                GradientColor = (int)tintColor
            };

            int accentSize = Marshal.SizeOf(accent);
            IntPtr accentPtr = Marshal.AllocHGlobal(accentSize);
            try
            {
                Marshal.StructureToPtr(accent, accentPtr, false);
                var data = new WindowCompositionAttributeData
                {
                    Attribute = WindowCompositionAttribute.WCA_ACCENT_POLICY,
                    Data = accentPtr,
                    SizeOfData = accentSize
                };
                int res = SetWindowCompositionAttribute(hwnd, ref data);
                if (res != 1)
                {
                    // Fallback to standard blur behind if acrylic is unsupported
                    accent.AccentState = AccentState.ACCENT_ENABLE_BLURBEHIND;
                    accent.GradientColor = 0;
                    Marshal.StructureToPtr(accent, accentPtr, false);
                    SetWindowCompositionAttribute(hwnd, ref data);
                }
            }
            finally
            {
                Marshal.FreeHGlobal(accentPtr);
            }
        }
    }
}
