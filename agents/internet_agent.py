# agents/internet_agent.py — Web & Daily Briefing Agent for SON V3
import logging
from core.config import Config

logger = Config.get_logger(__name__)


class InternetAgent:
    """
    Handles web search, documentation fetching, and generates Daily Briefings.
    """

    def __init__(self, plugin_registry=None, state=None):
        self.plugins = plugin_registry
        self.state = state

    def generate_daily_briefing(self) -> str:
        """Generate a morning daily briefing summary."""
        brief = ["🌅 Good morning, Dad! Here is your daily briefing:\n"]

        # Weather
        from core.orchestrator import orchestrator as global_orch
        from core.security.context import create_trusted_context

        ctx = create_trusted_context(user_id="primary_user", interface_type="internet_agent")
        w_res = global_orch.execute_action("get_weather", {"city": "auto"}, context=ctx)
        brief.append(f"• Weather: {w_res.output}")

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
        except Exception as e:
            logger.error(f"Exception caught: {e}", exc_info=True)

        brief.append("\nYour workspace is ready. Let's build something awesome today!")
        return "\n".join(brief)
