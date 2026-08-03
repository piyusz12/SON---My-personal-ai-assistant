# agents/internet_agent.py — Web & Daily Briefing Agent for SON V3


class InternetAgent:
    """
    Handles web search, documentation fetching, and generates Daily Briefings.
    """

    def __init__(self, plugin_registry=None, state=None):
        self.plugins = plugin_registry
        self.state = state

    def generate_daily_briefing(self) -> str:
        """Generate a morning daily briefing summary."""
        brief = ["🌅 Good morning, Piyush! Here is your daily briefing:\n"]

        # Weather
        if self.plugins and self.plugins.has_tool("get_weather"):
            w = self.plugins.call("get_weather", {"city": "auto"})
            brief.append(f"• Weather: {w}")

        # System telemetry
        if self.state:
            s = self.state.get_summary()
            brief.append(f"• System Health: CPU {s['cpu_percent']}%, RAM {s['ram_used_gb']}/{s['ram_total_gb']} GB ({s['ram_percent']}%), GPU VRAM {s['gpu_vram_used_mb']:.0f} MB")
            brief.append(f"• Ollama: {'Online (' + s['ollama_model'] + ')' if s['ollama_online'] else 'Offline'}")
            brief.append(f"• Docker: {'Online' if s['docker_online'] else 'Offline'}")

        # News
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                news = list(ddgs.news("technology", max_results=2))
            if news:
                brief.append("\n• Tech Headlines:")
                for item in news:
                    brief.append(f"  - {item.get('title')} ({item.get('source')})")
        except Exception:
            pass

        brief.append("\nYour workspace is ready. Let's build something awesome today!")
        return "\n".join(brief)
