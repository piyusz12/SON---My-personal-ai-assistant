# plugins/browser.py — Web Search & Documentation Reader Plugin for SON V3
from core.config import SecurityLevel, Config
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

    # ── Implementations ───────────────────────────────────────

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
