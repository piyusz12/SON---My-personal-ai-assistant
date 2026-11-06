from core.config import SecurityLevel
from plugins.base import BasePlugin


class BrowserPlugin(BasePlugin):
    """
    Handles DuckDuckGo web search, webpage reading, and documentation lookup.
    """

    def __init__(self):
        super().__init__(name="browser", description="Web search and documentation lookup plugin", category="web")

    def initialize(self):
        self.register_tool(
            "web_search", self.web_search,
            description="Search Google/DuckDuckGo for real-time web results",
            params={
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "default": 5}
            },
            required=["query"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "read_webpage", self.read_webpage,
            description="Fetch a URL and extract its main text content",
            params={"url": {"type": "string", "description": "Webpage URL"}},
            required=["url"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "open_website", self.open_website,
            description="Open a website or popular platform (YouTube, GitHub, Reddit, etc.) in the default browser",
            params={"site_or_url": {"type": "string", "description": "Website name or URL"}},
            required=["site_or_url"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "search_website", self.search_website,
            description="Search directly on Google, YouTube, GitHub, Reddit, or Wikipedia in browser",
            params={
                "platform": {"type": "string", "description": "Platform to search (e.g. 'google', 'youtube', 'github', 'reddit')"},
                "query": {"type": "string", "description": "Search keywords"}
            },
            required=["platform", "query"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "send_web_message", self.send_web_message,
            description="Send a message on behalf of Dad to a web chat platform (WhatsApp Web, Discord, Slack, Telegram, ChatGPT)",
            params={
                "platform": {"type": "string", "description": "Target web platform (e.g. 'whatsapp', 'discord', 'slack', 'telegram', 'chatgpt')"},
                "message": {"type": "string", "description": "The message to send"},
                "recipient": {"type": "string", "description": "Optional recipient name or phone number", "default": ""},
                "press_enter": {"type": "boolean", "description": "Whether to press Enter to send", "default": True},
            },
            required=["platform", "message"], security_level=SecurityLevel.SAFE
        )

    # ── Implementations ───────────────────────────────────────

    def open_website(self, site_or_url: str) -> str:
        from tools.web import open_website
        return open_website(site_or_url)

    def search_website(self, platform: str, query: str) -> str:
        from tools.web import search_website
        return search_website(platform, query)

    def web_search(self, query: str, max_results: int = 5) -> str:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=min(max_results, 5)))
            if not results:
                return f"No web results found for '{query}'."

            out = [f"Web search results for '{query}':\n"]
            for i, r in enumerate(results, 1):
                out.append(f"{i}. {r.get('title')}\n   URL: {r.get('href')}\n   Snippet: {r.get('body', '')[:180]}\n")
            return "\n".join(out)
        except Exception as e:
            return f"Web search failed: {e}"

    def read_webpage(self, url: str) -> str:
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return f"Could not fetch webpage: {url}"
            text = trafilatura.extract(downloaded)
            if not text:
                return f"Could not extract text from: {url}"
            return f"Content from {url}:\n\n{text[:4000]}"
        except Exception as e:
            return f"Error reading webpage: {e}"

    def send_web_message(self, platform: str, message: str, recipient: str = "", press_enter: bool = True) -> str:
        from tools.windows_control import send_web_message
        return send_web_message(platform=platform, message=message, recipient=recipient, press_enter=press_enter)
