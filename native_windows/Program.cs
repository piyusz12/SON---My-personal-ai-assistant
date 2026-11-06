using System;
using System.Diagnostics;
using System.Text.RegularExpressions;

namespace SonWindowsInt
{
    /// <summary>
    /// SON V3 — Windows Desktop Specialist (.NET 8)
    /// Handles secure desktop integration, OS default browser launching for verified
    /// WhatsApp Click to Chat URLs, and Windows system interaction.
    /// </summary>
    class Program
    {
        private static readonly Regex WaMeUrlRegex = new Regex(
            @"^https://wa\.me/\d{7,15}\?text=.+$",
            RegexOptions.Compiled | RegexOptions.IgnoreCase
        );

        static int Main(string[] args)
        {
            if (args.Length == 0)
            {
                Console.WriteLine("SON V3 — C# Windows Desktop Specialist");
                Console.WriteLine("Usage: SonWindowsInt.exe open-draft <wa_me_url>");
                return 0;
            }

            string command = args[0].ToLowerInvariant();

            if (command == "open-draft")
            {
                if (args.Length < 2)
                {
                    Console.Error.WriteLine("[ERROR] Missing required WhatsApp URL argument.");
                    return 1;
                }

                string url = args[1];
                return OpenWhatsAppDraftUrl(url);
            }
            else if (command == "health")
            {
                Console.WriteLine("{\"status\":\"healthy\",\"specialist\":\"SonWindowsInt\",\".net_version\":\"8.0\"}");
                return 0;
            }
            else
            {
                Console.Error.WriteLine($"[ERROR] Unknown command: {command}");
                return 1;
            }
        }

        /// <summary>
        /// Validates that the URL strictly matches the official https://wa.me/ Click to Chat
        /// domain and launches it using the Windows default browser via shell execute.
        /// NEVER simulates clicks or keystrokes on WhatsApp's Send button.
        /// </summary>
        private static int OpenWhatsAppDraftUrl(string url)
        {
            try
            {
                // Security verification: allowlist enforcement
                if (!WaMeUrlRegex.IsMatch(url))
                {
                    Console.Error.WriteLine($"[SECURITY ERROR] URL rejected by security policy: {url}");
                    return 2;
                }

                var psi = new ProcessStartInfo
                {
                    FileName = url,
                    UseShellExecute = true
                };

                Process.Start(psi);
                Console.WriteLine("[OK] Opened approved WhatsApp Click to Chat URL in default browser.");
                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[ERROR] Failed to launch default browser: {ex.Message}");
                return 3;
            }
        }
    }
}
