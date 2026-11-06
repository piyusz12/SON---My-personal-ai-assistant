# services/whatsapp/url_builder.py — Official WhatsApp Click to Chat URL Builder
"""
Strict WhatsApp Click to Chat URL construction following official WhatsApp specifications:
https://wa.me/<number>?text=<urlencodedtext>

Security & Compliance:
- Strictly enforces domain allowlist (https://wa.me only).
- Proper RFC 3986 percent-encoding (handling Hindi, emojis, newlines, ampersands, quotes).
- Strict phone number format (digits only, 7-15 digits, international format without leading plus).
- No arbitrary redirection or protocol smuggling (e.g. javascript:, file:, data: are blocked).
"""
import re
import urllib.parse
from typing import Tuple


class WhatsAppURLBuilder:
    """
    Constructs and verifies official WhatsApp Click to Chat URLs.
    """
    ALLOWED_SCHEME = "https"
    ALLOWED_NETLOC = "wa.me"
    PHONE_DIGITS_REGEX = re.compile(r"^\d{7,15}$")

    @classmethod
    def build_click_to_chat_url(cls, phone_number: str, message: str) -> str:
        """
        Build an approved WhatsApp Click to Chat URL.

        Args:
            phone_number: International phone digits without '+' (e.g. '919876541234')
            message: Raw text to prefill (can contain Unicode, Hindi, emojis, newlines)

        Returns:
            Secure, fully-encoded URL string: https://wa.me/PHONE?text=ENCODED_MESSAGE
        """
        clean_phone = "".join(c for c in phone_number if c.isdigit())
        if not cls.PHONE_DIGITS_REGEX.match(clean_phone):
            raise ValueError(
                f"Invalid phone number format '{phone_number}'. Must be 7-15 digits in international format without '+'."
            )

        if not message or not message.strip():
            raise ValueError("Message body cannot be empty.")

        # RFC 3986 safe URL encoding. safe='' ensures ampersands, slashes, equals, etc. are properly encoded
        # so they do not conflict with the URL query parameter structure.
        encoded_message = urllib.parse.quote(message, safe="")
        url = f"https://{cls.ALLOWED_NETLOC}/{clean_phone}?text={encoded_message}"

        # Validate that parsed result strictly complies with security policy
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != cls.ALLOWED_SCHEME or parsed.netloc != cls.ALLOWED_NETLOC:
            raise ValueError(f"Generated URL violated security policy: {url}")

        return url

    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Verify that a URL is a legitimate HTTPS wa.me Click to Chat URL."""
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme != cls.ALLOWED_SCHEME:
                return False
            if parsed.netloc != cls.ALLOWED_NETLOC:
                return False
            # Path should be /<phone_digits>
            path_digits = parsed.path.lstrip("/")
            if not cls.PHONE_DIGITS_REGEX.match(path_digits):
                return False
            return True
        except Exception:
            return False
