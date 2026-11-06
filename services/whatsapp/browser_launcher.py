# services/whatsapp/browser_launcher.py — Secure Browser Integration for WhatsApp Click to Chat
"""
Handoff layer for launching verified WhatsApp Click to Chat URLs.
Strict Rules:
- Validates URL against approved HTTPS wa.me domain before any OS invocation.
- Prefers C# desktop integration (native_windows/SonWindowsInt.exe) if available.
- Falls back safely to standard OS default browser invocation (webbrowser.open / os.startfile).
- NEVER simulates clicks or keystrokes on the WhatsApp Web 'Send' button.
- NEVER injects scripts, accesses cookies, or manipulates DOM.
"""
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional, Tuple

from core.config import Config
from services.whatsapp.url_builder import WhatsAppURLBuilder

logger = Config.get_logger(__name__)


class BrowserLauncher:
    """
    Launches verified WhatsApp Click to Chat URLs in the default web browser.
    """

    @classmethod
    def get_csharp_executable_path(cls) -> Optional[Path]:
        """Locate compiled C# .NET desktop specialist if present."""
        project_root = Path(__file__).parent.parent.parent
        possible_paths = [
            project_root / "native_windows" / "bin" / "Release" / "net8.0" / "SonWindowsInt.exe",
            project_root / "native_windows" / "bin" / "Debug" / "net8.0" / "SonWindowsInt.exe",
        ]
        for p in possible_paths:
            if p.exists():
                return p
        return None

    @classmethod
    def open_draft_url(cls, url: str) -> Tuple[bool, str]:
        """
        Open the WhatsApp Click to Chat URL in the user's default browser.

        Args:
            url: Approved https://wa.me/... Click to Chat URL

        Returns:
            Tuple of (success_bool, status_message)
        """
        # 1. Security Gate: Strictly reject any non-wa.me URL
        if not WhatsAppURLBuilder.validate_url(url):
            error_msg = f"Security Policy Violation: Refusing to open non-allowlisted WhatsApp URL: {url}"
            logger.error(error_msg)
            return False, error_msg

        # 2. Attempt C# Desktop Integration if built
        csharp_exe = cls.get_csharp_executable_path()
        if csharp_exe:
            try:
                logger.info(f"Delegating URL launch to C# specialist: {csharp_exe}")
                env = os.environ.copy()
                if "DOTNET_ROOT" not in env:
                    local_dotnet = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\dotnet")
                    if os.path.exists(local_dotnet):
                        env["DOTNET_ROOT"] = local_dotnet
                result = subprocess.run(
                    [str(csharp_exe), "open-draft", url],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    env=env,
                )
                if result.returncode == 0:
                    return True, "Opened via C# desktop integration."
                else:
                    logger.warning(f"C# launcher exited with code {result.returncode}: {result.stderr}")
            except Exception as e:
                logger.warning(f"C# desktop integration invocation failed ({e}), using OS default browser fallback.")

        # 3. Standard OS Default Browser Launch
        try:
            logger.info("Opening approved WhatsApp Click to Chat URL in default browser.")
            if sys.platform == "win32":
                # os.startfile reliably triggers the user's default browser on Windows
                os.startfile(url)
            else:
                webbrowser.open(url)
            return True, "Opened in default browser."
        except Exception as ex:
            error_msg = f"Failed to launch web browser for WhatsApp: {ex}"
            logger.error(error_msg)
            return False, error_msg
