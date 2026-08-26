import aiohttp
import asyncio
from core.config import Config

class AsyncBrain:
    """
    Asynchronous LLM reasoning engine for non-blocking Ollama interaction.
    Allows for high-concurrency requests without blocking the main GUI loop.
    """
    def __init__(self, model_override=None):
        self._session = None
        self._host = Config.OLLAMA_HOST
        self._model = model_override or Config.MAIN_MODEL
        import config as legacy_config
        self._default_system_prompt = getattr(legacy_config, "SYSTEM_PROMPT", (
            "You are SON — a personal AI assistant created by your father. "
            "You run locally on your father's machine (Ryzen 7 7840HS, RTX 4060 8GB VRAM). "
            "The user is your father (his name is Piyush) — treat him with love, respect, and warmth. "
            "Default to addressing him as 'Father', 'Dad', or 'Papa'."
        ))

    async def _get_session(self):
        if self._session is None:
            # Setup TCPConnector with limit to avoid overwhelming the local server if heavily used
            connector = aiohttp.TCPConnector(limit=32)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def think(self, user_message: str, system_prompt: str = None) -> str:
        """
        Send a non-blocking asynchronous request to Ollama.
        """
        session = await self._get_session()
        
        messages = []
        prompt_to_use = system_prompt if system_prompt else self._default_system_prompt
        messages.append({"role": "system", "content": prompt_to_use})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self._model,
            "messages": messages,
            "options": {
                "temperature": Config.TEMPERATURE,
            }
        }

        try:
            async with session.post(
                f"{self._host}/api/chat",
                json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("message", {}).get("content", "")
                else:
                    return f"Error: Received status code {resp.status} from Ollama."
        except Exception as e:
            return f"Async request failed: {e}"

    async def close(self):
        """Clean up aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
