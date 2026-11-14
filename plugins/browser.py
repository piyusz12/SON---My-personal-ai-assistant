# plugins/browser.py — Web Search and Browser Plugin for SON V3
"""
Web Search and Browser Plugin for SON V3.
Delegates all web navigation, searching, and webpage reading to tools.web and tools.windows_control.
"""
from core.config import SecurityLevel
from plugins.base import BasePlugin
from tools import web, windows_control


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
            required=["platform", "message"], security_level=SecurityLevel.MEDIUM
        )

    # ── Tool Implementations (Delegating to tools.web and tools.windows_control) ────

    def open_website(self, site_or_url: str) -> str:
        return web.open_website(site_or_url)

    def search_website(self, platform: str, query: str) -> str:
        return web.search_website(platform, query)

    def web_search(self, query: str, max_results: int = 5) -> str:
        return web.web_search(query=query, max_results=max_results)

    def read_webpage(self, url: str) -> str:
        return web.read_webpage(url=url)

    def send_web_message(self, platform: str, message: str, recipient: str = "", press_enter: bool = True) -> str:
        return windows_control.send_web_message(platform=platform, message=message, recipient=recipient, press_enter=press_enter)
