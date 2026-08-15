# tools/web.py — Internet & Web Tools for SON
"""
Web search, weather, news, and webpage reading.
All tools check config.INTERNET_ENABLED before making requests.
Uses free APIs that don't require API keys.
"""
import os
import json
import re
import socket
import urllib.parse
from ipaddress import ip_address
from pathlib import Path

import config


def _check_internet() -> str | None:
    """Return error message if internet is disabled, else None."""
    if not config.INTERNET_ENABLED:
        return "Internet access is disabled in config. Set INTERNET_ENABLED = True to enable."
    return None


def _validate_url(url: str) -> tuple[bool, str]:
    """
    Validate URL to prevent SSRF attacks.
    
    Checks:
    - Valid URL format
    - HTTP/HTTPS scheme only
    - Not a private/internal IP address
    - Not localhost or link-local
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parsed = urllib.parse.urlparse(url)
        
        # Check scheme
        if parsed.scheme.lower() not in ('http', 'https'):
            return False, f"Invalid scheme '{parsed.scheme}'. Only http/https allowed."
        
        # Check hostname exists
        hostname = parsed.hostname
        if not hostname:
            return False, "No hostname found in URL."
        
        # Block localhost
        if hostname.lower() in ('localhost', '127.0.0.1', '::1'):
            return False, "Localhost URLs are not allowed."
        
        # Block private/internal IPs
        # Resolve hostname to IP
        try:
            ip_addresses = socket.getaddrinfo(hostname, None)
            for fam, _, _, _, addr in ip_addresses:
                ip_str = addr[0]
                try:
                    ip = ip_address(ip_str)
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                        return False, f"Private/internal IP address not allowed: {ip_str}"
                except ValueError:
                    continue  # IPv6 with scope or other format
        except socket.gaierror:
            return False, f"Cannot resolve hostname: {hostname}"
        
        return True, ""
        
    except Exception as e:
        return False, f"URL validation failed: {e}"


# ═══════════════════════════════════════════════════════════
#  Web Search (DuckDuckGo — no API key needed)
# ═══════════════════════════════════════════════════════════

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return results."""
    err = _check_internet()
    if err:
        return err

    try:
        from duckduckgo_search import DDGS

        max_results = min(int(max_results), config.SEARCH_MAX_RESULTS)

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"No results found for '{query}'."

        lines = [f"Search results for '{query}':\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   {r.get('href', '')}")
            body = r.get('body', '')
            if body:
                lines.append(f"   {body[:200]}")
            lines.append("")

        return "\n".join(lines)

    except ImportError:
        return "duckduckgo-search is not installed. Run: pip install duckduckgo-search"
    except Exception as e:
        return f"Search failed: {e}"


# ═══════════════════════════════════════════════════════════
#  Website Navigation & Platform Search
# ═══════════════════════════════════════════════════════════

POPULAR_SITES: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
    "chatgpt": "https://chatgpt.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "wikipedia": "https://www.wikipedia.org",
    "stackoverflow": "https://stackoverflow.com",
    "linkedin": "https://www.linkedin.com",
    "huggingface": "https://huggingface.co",
    "twitch": "https://www.twitch.tv",
    "instagram": "https://www.instagram.com",
    "whatsapp": "https://web.whatsapp.com",
    "discord": "https://discord.com/app",
}

PLATFORM_SEARCH_TEMPLATES: dict[str, str] = {
    "google": "https://www.google.com/search?q={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "github": "https://github.com/search?q={query}",
    "reddit": "https://www.reddit.com/search/?q={query}",
    "wikipedia": "https://en.wikipedia.org/wiki/Special:Search?search={query}",
    "amazon": "https://www.amazon.com/s?k={query}",
    "stackoverflow": "https://stackoverflow.com/search?q={query}",
    "twitter": "https://x.com/search?q={query}",
    "x": "https://x.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
}


def open_website(site_or_url: str) -> str:
    """Open a website by name or URL in the default browser."""
    import webbrowser
    import urllib.parse
    cleaned = site_or_url.strip().lower()

    # Check if it is a local file or path first
    local_path = Path(site_or_url.strip())
    if local_path.exists():
        try:
            os.startfile(str(local_path.resolve()))
            return f"Opened local file {local_path.name}."
        except Exception as e:
            return f"Failed to open local file: {e}"

    # Check popular site shortcuts
    if cleaned in POPULAR_SITES:
        target_url = POPULAR_SITES[cleaned]
    elif cleaned.startswith(("http://", "https://")):
        target_url = site_or_url.strip()
    elif "." in cleaned and " " not in cleaned and not cleaned.endswith((".txt", ".py", ".html", ".json", ".log", ".md")):
        target_url = f"https://{cleaned}"
    else:
        # Fall back to Google search
        encoded = urllib.parse.quote_plus(site_or_url)
        target_url = f"https://www.google.com/search?q={encoded}"

    try:
        webbrowser.open(target_url, new=2)
        return f"Opened {target_url} in browser."
    except Exception as e:
        return f"Failed to open website: {e}"


def search_website(platform: str, query: str) -> str:
    """Search a specific platform (e.g. YouTube, Google, GitHub, Reddit) in browser."""
    import webbrowser
    import urllib.parse

    plat_lower = platform.strip().lower()
    encoded = urllib.parse.quote_plus(query.strip())

    if plat_lower in PLATFORM_SEARCH_TEMPLATES:
        url = PLATFORM_SEARCH_TEMPLATES[plat_lower].format(query=encoded)
    else:
        # Default to Google with site filter or direct search
        url = f"https://www.google.com/search?q={encoded}"

    try:
        webbrowser.open(url, new=2)
        return f"Searching {plat_lower.title()} for '{query}'..."
    except Exception as e:
        return f"Failed to open search: {e}"


# ═══════════════════════════════════════════════════════════
#  Webpage Reading
# ═══════════════════════════════════════════════════════════

def read_webpage(url: str) -> str:
    """Fetch a webpage and extract its main text content."""
    err = _check_internet()
    if err:
        return err

    # Validate URL to prevent SSRF
    is_valid, error_msg = _validate_url(url)
    if not is_valid:
        return f"Invalid URL: {error_msg}"

    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return f"Could not fetch URL: {url}"

        text = trafilatura.extract(downloaded)
        if not text:
            return f"Could not extract text from: {url}"

        # Truncate if very long
        if len(text) > 5000:
            text = text[:5000] + "\n\n... [truncated — full page is longer]"

        return f"Content from {url}:\n\n{text}"

    except ImportError:
        return "trafilatura is not installed. Run: pip install trafilatura"
    except Exception as e:
        return f"Failed to read webpage: {e}"


def summarize_url(url: str) -> str:
    """Fetch a webpage URL and return a summary (useful for voice responses)."""
    # Validate URL first
    is_valid, error_msg = _validate_url(url)
    if not is_valid:
        return f"Invalid URL: {error_msg}"
    
    content = read_webpage(url)
    if content.startswith(("Could not", "Failed", "trafilatura", "Internet", "Invalid")):
        return content

    # Return first 1000 chars as a summary (LLM can further summarize)
    return content[:1000]


# ═══════════════════════════════════════════════════════════
#  Weather (wttr.in — free, no API key)
# ═══════════════════════════════════════════════════════════

def get_weather(city: str = "auto") -> str:
    """Get current weather for a city. Use 'auto' for auto-detect location."""
    err = _check_internet()
    if err:
        return err

    try:
        import requests

        # wttr.in provides a simple text weather report
        location = "" if city.lower() == "auto" else city
        url = f"https://wttr.in/{location}?format=4"

        response = requests.get(url, timeout=10, headers={"User-Agent": "SON-Assistant"})
        response.raise_for_status()

        return response.text.strip()

    except ImportError:
        return "requests is not installed. Run: pip install requests"
    except Exception as e:
        return f"Could not get weather: {e}"


def get_weather_detailed(city: str = "auto") -> str:
    """Get detailed weather forecast for a city."""
    err = _check_internet()
    if err:
        return err

    try:
        import requests

        location = "" if city.lower() == "auto" else city
        url = f"https://wttr.in/{location}?format=j1"

        response = requests.get(url, timeout=10, headers={"User-Agent": "SON-Assistant"})
        response.raise_for_status()
        data = response.json()

        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]

        city_name = area.get("areaName", [{}])[0].get("value", "Unknown")
        temp_c = current.get("temp_C", "?")
        feels_like = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        desc = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
        wind = current.get("windspeedKmph", "?")
        wind_dir = current.get("winddir16Point", "")

        lines = [
            f"Weather in {city_name}:",
            f"  Condition: {desc}",
            f"  Temperature: {temp_c}°C (feels like {feels_like}°C)",
            f"  Humidity: {humidity}%",
            f"  Wind: {wind} km/h {wind_dir}",
        ]

        return "\n".join(lines)

    except Exception as e:
        return f"Could not get detailed weather: {e}"


# ═══════════════════════════════════════════════════════════
#  News (DuckDuckGo News — no API key)
# ═══════════════════════════════════════════════════════════

def get_news(topic: str = "technology", max_results: int = 5) -> str:
    """Get latest news headlines on a topic."""
    err = _check_internet()
    if err:
        return err

    try:
        from duckduckgo_search import DDGS

        max_results = min(int(max_results), 10)

        with DDGS() as ddgs:
            results = list(ddgs.news(topic, max_results=max_results))

        if not results:
            return f"No news found for '{topic}'."

        lines = [f"Latest news on '{topic}':\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   Source: {r.get('source', 'Unknown')} | {r.get('date', '')}")
            body = r.get('body', '')
            if body:
                lines.append(f"   {body[:150]}")
            lines.append("")

        return "\n".join(lines)

    except ImportError:
        return "duckduckgo-search is not installed. Run: pip install duckduckgo-search"
    except Exception as e:
        return f"News fetch failed: {e}"


# ═══════════════════════════════════════════════════════════
#  Registration
# ═══════════════════════════════════════════════════════════

def register_all(registry):
    """Register all web tools with a ToolRegistry."""
    from core.config import SecurityLevel

    registry.register(
        name="web_search",
        func=web_search,
        description="Search the web for information using DuckDuckGo. Returns titles, URLs, and snippets.",
        params={
            "query": {"type": "string", "description": "The search query keywords"},
            "max_results": {"type": "integer", "description": "Number of results to return (1-10)", "default": 5},
        },
        required=["query"],
        category="web",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="read_webpage",
        func=read_webpage,
        description="Fetch a webpage URL and extract its main text content",
        params={"url": {"type": "string", "description": "The URL to read"}},
        required=["url"],
        category="web",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="summarize_url",
        func=summarize_url,
        description="Fetch a webpage and return a short summary of its content",
        params={"url": {"type": "string", "description": "The URL to summarize"}},
        required=["url"],
        category="web",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="get_weather",
        func=get_weather,
        description="Get current weather. Use city name or 'auto' for automatic location.",
        params={
            "city": {"type": "string", "description": "City name or 'auto'", "default": "auto"},
        },
        category="web",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="get_weather_detailed",
        func=get_weather_detailed,
        description="Get detailed weather forecast with temperature, humidity, wind, etc.",
        params={
            "city": {"type": "string", "description": "City name or 'auto'", "default": "auto"},
        },
        category="web",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="open_website",
        func=open_website,
        description="Open a website or popular platform (YouTube, GitHub, Reddit, etc.) in the default browser",
        params={
            "site_or_url": {"type": "string", "description": "Website name (e.g. 'youtube', 'github') or full URL"},
        },
        required=["site_or_url"],
        category="web",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="search_website",
        func=search_website,
        description="Search directly on Google, YouTube, GitHub, Reddit, Wikipedia, Amazon, or StackOverflow in the browser",
        params={
            "platform": {"type": "string", "description": "Platform to search ('google', 'youtube', 'github', 'reddit', 'wikipedia', 'amazon', 'stackoverflow')"},
            "query": {"type": "string", "description": "Search query keywords"},
        },
        required=["platform", "query"],
        category="web",
        security_level=SecurityLevel.SAFE,
    )

