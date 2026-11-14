// NativeWindowBridge.cs — Windows 11 Native Integration Layer for SON Mini Assistant
// Provides direct Win32 and DWM (Desktop Window Manager) P/Invoke bindings.
// Gracefully handles Windows version detection, Acrylic backdrops, rounded corners,
// and optional click-through / no-activate modes.

using System;
using System.Runtime.InteropServices;
using Godot;

namespace SON.GodotIntegration
{
    public static class NativeWindowBridge
    {
        // ── DWM Constants ──────────────────────────────────────────────────
        public const int DWMWA_USE_IMMERSIVE_DARK_MODE = 20;
        public const int DWMWA_WINDOW_CORNER_PREFERENCE = 33;
        public const int DWMWA_BORDER_COLOR = 34;
        public const int DWMWA_SYSTEMBACKDROP_TYPE = 38;

        public const int DWMWCP_DEFAULT = 0;
        public const int DWMWCP_DONOTROUND = 1;
        public const int DWMWCP_ROUND = 2;
        public const int DWMWCP_ROUNDSMALL = 3;

        public const int DWMSBT_AUTO = 0;
        public const int DWMSBT_NONE = 1;
        public const int DWMSBT_MAINWINDOW = 2;       // Mica
        public const int DWMSBT_TRANSIENTWINDOW = 3;  // Acrylic
        public const int DWMSBT_TABBEDWINDOW = 4;     // Mica Alt

        // ── Window Styles Constants ────────────────────────────────────────
        public const int GWL_EXSTYLE = -20;
        public const int WS_EX_TOPMOST = 0x00000008;
        public const int WS_EX_TRANSPARENT = 0x00000020;  // Click-through
        public const int WS_EX_TOOLWINDOW = 0x00000080;
        public const int WS_EX_LAYERED = 0x00080000;
        public const int WS_EX_NOACTIVATE = 0x08000000;   // Does not steal focus

        public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
        public static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);

        public const uint SWP_NOMOVE = 0x0002;
        public const uint SWP_NOSIZE = 0x0001;
        public const uint SWP_NOACTIVATE = 0x0010;
        public const uint SWP_SHOWWINDOW = 0x0040;

        // ── OS Version Struct ──────────────────────────────────────────────
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        public struct OSVERSIONINFOEX
        {
            public int dwOSVersionInfoSize;
            public int dwMajorVersion;
            public int dwMinorVersion;
            public int dwBuildNumber;
            public int dwPlatformId;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
            public string szCSDVersion;
            public ushort wServicePackMajor;
            public ushort wServicePackMinor;
            public ushort wSuiteMask;
            public byte wProductType;
            public byte wReserved;
        }

        // ── P/Invoke Declarations ──────────────────────────────────────────
        [DllImport("ntdll.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern int RtlGetVersion(ref OSVERSIONINFOEX versionInfo);

        [DllImport("dwmapi.dll", PreserveSig = true)]
        public static extern int DwmSetWindowAttribute(IntPtr hwnd, int dwAttribute, ref int pvAttribute, int cbAttribute);

        [DllImport("user32.dll", EntryPoint = "GetWindowLongPtr")]
        private static extern IntPtr GetWindowLongPtr64(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll", EntryPoint = "GetWindowLong")]
        private static extern IntPtr GetWindowLong32(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll", EntryPoint = "SetWindowLongPtr")]
        private static extern IntPtr SetWindowLongPtr64(IntPtr hWnd, int nIndex, IntPtr dwNewLong);

        [DllImport("user32.dll", EntryPoint = "SetWindowLong")]
        private static extern IntPtr SetWindowLong32(IntPtr hWnd, int nIndex, IntPtr dwNewLong);

        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        public static IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex)
        {
            return IntPtr.Size == 8 ? GetWindowLongPtr64(hWnd, nIndex) : GetWindowLong32(hWnd, nIndex);
        }

        public static IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr dwNewLong)
        {
            return IntPtr.Size == 8 ? SetWindowLongPtr64(hWnd, nIndex, dwNewLong) : SetWindowLong32(hWnd, nIndex, dwNewLong);
        }

        // ── Version Detection ──────────────────────────────────────────────
        private static int _cachedBuildNumber = -1;

        public static int GetWindowsBuildNumber()
        {
            if (_cachedBuildNumber >= 0) return _cachedBuildNumber;

            if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                try
                {
                    var osInfo = new OSVERSIONINFOEX();
                    osInfo.dwOSVersionInfoSize = Marshal.SizeOf(osInfo);
                    if (RtlGetVersion(ref osInfo) == 0)
                    {
                        _cachedBuildNumber = osInfo.dwBuildNumber;
                        return _cachedBuildNumber;
                    }
                }
                catch
                {
                    // Fall back to Environment
                }
                _cachedBuildNumber = Environment.OSVersion.Version.Build;
            }
            else
            {
                _cachedBuildNumber = 0;
            }
            return _cachedBuildNumber;
        }

        public static bool IsWindows11()
        {
            return GetWindowsBuildNumber() >= 22000;
        }

        public static bool SupportsAcrylicBackdrop()
        {
            // DWMWA_SYSTEMBACKDROP_TYPE requires Windows 11 Build 22621 (22H2) or higher
            return GetWindowsBuildNumber() >= 22621;
        }

        // ── Window Styling Integrations ────────────────────────────────────
        public static bool ApplyRoundedCorners(IntPtr hwnd, int cornerPreference = DWMWCP_ROUND)
        {
            if (hwnd == IntPtr.Zero || !IsWindows11()) return false;
            try
            {
                int pref = cornerPreference;
                int hr = DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ref pref, sizeof(int));
                return hr == 0;
            }
            catch (Exception ex)
            {
                GD.PrintErr($"[NativeBridge] Failed to set rounded corners: {ex.Message}");
                return false;
            }
        }

        public static bool ApplyDarkImmersiveMode(IntPtr hwnd, bool enable = true)
        {
            if (hwnd == IntPtr.Zero || !RuntimeInformation.IsOSPlatform(OSPlatform.Windows)) return false;
            try
            {
                int val = enable ? 1 : 0;
                int hr = DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ref val, sizeof(int));
                return hr == 0;
            }
            catch
            {
                return false;
            }
        }

        public static bool ApplyAcrylicBackdrop(IntPtr hwnd)
        {
            if (hwnd == IntPtr.Zero || !SupportsAcrylicBackdrop()) return false;
            try
            {
                int backdropType = DWMSBT_TRANSIENTWINDOW; // Acrylic
                int hr = DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ref backdropType, sizeof(int));
                return hr == 0;
            }
            catch (Exception ex)
            {
                GD.PrintErr($"[NativeBridge] Acrylic backdrop application failed: {ex.Message}");
                return false;
            }
        }

        public static bool ApplyMicaBackdrop(IntPtr hwnd)
        {
            if (hwnd == IntPtr.Zero || !IsWindows11()) return false;
            try
            {
                int backdropType = DWMSBT_MAINWINDOW; // Mica
                int hr = DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ref backdropType, sizeof(int));
                return hr == 0;
            }
            catch
            {
                return false;
            }
        }

        public static bool SetClickThrough(IntPtr hwnd, bool enable)
        {
            if (hwnd == IntPtr.Zero || !RuntimeInformation.IsOSPlatform(OSPlatform.Windows)) return false;
            try
            {
                long style = GetWindowLongPtr(hwnd, GWL_EXSTYLE).ToInt64();
                if (enable)
                {
                    style |= WS_EX_TRANSPARENT | WS_EX_LAYERED;
                }
                else
                {
                    style &= ~WS_EX_TRANSPARENT;
                }
                SetWindowLongPtr(hwnd, GWL_EXSTYLE, new IntPtr(style));
                return true;
            }
            catch (Exception ex)
            {
                GD.PrintErr($"[NativeBridge] Click-through update failed: {ex.Message}");
                return false;
            }
        }

        public static bool SetNoActivate(IntPtr hwnd, bool enable)
        {
            if (hwnd == IntPtr.Zero || !RuntimeInformation.IsOSPlatform(OSPlatform.Windows)) return false;
            try
            {
                long style = GetWindowLongPtr(hwnd, GWL_EXSTYLE).ToInt64();
                if (enable)
                {
                    style |= WS_EX_NOACTIVATE;
                }
                else
                {
                    style &= ~WS_EX_NOACTIVATE;
                }
                SetWindowLongPtr(hwnd, GWL_EXSTYLE, new IntPtr(style));
                return true;
            }
            catch
            {
                return false;
            }
        }

        public static bool SetAlwaysOnTop(IntPtr hwnd, bool enable)
        {
            if (hwnd == IntPtr.Zero || !RuntimeInformation.IsOSPlatform(OSPlatform.Windows)) return false;
            try
            {
                IntPtr insertAfter = enable ? HWND_TOPMOST : HWND_NOTOPMOST;
                return SetWindowPos(hwnd, insertAfter, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);
            }
            catch
            {
                return false;
            }
        }
    }
}
