# tools/web.py — Internet & Web Tools for SON
"""
Web search, weather, news, and webpage reading.
All tools check config.INTERNET_ENABLED before making requests.
Uses free APIs that don't require API keys.
"""
import json

import config


def _check_internet() -> str | None:
    """Return error message if internet is disabled, else None."""
    if not config.INTERNET_ENABLED:
        return "Internet access is disabled in config. Set INTERNET_ENABLED = True to enable."
    return None


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
#  Webpage Reading
# ═══════════════════════════════════════════════════════════

def read_webpage(url: str) -> str:
    """Fetch a webpage and extract its main text content."""
    err = _check_internet()
    if err:
        return err

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
    """Fetch a webpage and return a summary (useful for voice responses)."""
    content = read_webpage(url)
    if content.startswith(("Could not", "Failed", "trafilatura", "Internet")):
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

    registry.register(
        name="web_search",
        func=web_search,
        description="Search the web using DuckDuckGo. Returns titles, URLs, and snippets.",
        params={
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Maximum number of results", "default": 5},
        },
        required=["query"],
        category="web",
    )

    registry.register(
        name="read_webpage",
        func=read_webpage,
        description="Fetch a webpage URL and extract its main text content",
        params={"url": {"type": "string", "description": "The URL to read"}},
        required=["url"],
        category="web",
    )

    registry.register(
        name="summarize_url",
        func=summarize_url,
        description="Fetch a webpage and return a short summary of its content",
        params={"url": {"type": "string", "description": "The URL to summarize"}},
        required=["url"],
        category="web",
    )

    registry.register(
        name="get_weather",
        func=get_weather,
        description="Get current weather. Use city name or 'auto' for automatic location.",
        params={
            "city": {"type": "string", "description": "City name or 'auto'", "default": "auto"},
        },
        category="web",
    )

    registry.register(
        name="get_weather_detailed",
        func=get_weather_detailed,
        description="Get detailed weather forecast with temperature, humidity, wind, etc.",
        params={
            "city": {"type": "string", "description": "City name or 'auto'", "default": "auto"},
        },
        category="web",
    )

    registry.register(
        name="get_news",
        func=get_news,
        description="Get latest news headlines on a topic",
        params={
            "topic": {"type": "string", "description": "News topic to search for", "default": "technology"},
            "max_results": {"type": "integer", "description": "Number of headlines", "default": 5},
        },
        category="web",
    )
