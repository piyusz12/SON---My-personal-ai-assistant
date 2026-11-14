# plugins/weather.py — Live Weather Plugin for SON V3
"""
Live Weather Plugin for SON V3.
Delegates all weather retrieval to tools.web.
"""
from core.config import SecurityLevel
from plugins.base import BasePlugin
from tools import web


class WeatherPlugin(BasePlugin):
    """
    Fetches live weather and forecasts using wttr.in API.
    """

    def __init__(self):
        super().__init__(name="weather", description="Live weather and forecast provider", category="weather")

    def initialize(self):
        self.register_tool(
            "get_weather", self.get_weather,
            description="Get current weather for a city or auto location",
            params={"city": {"type": "string", "default": "auto"}},
            security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "get_weather_forecast", self.get_forecast,
            description="Get detailed 3-day weather forecast for a city",
            params={"city": {"type": "string", "default": "auto"}},
            security_level=SecurityLevel.SAFE
        )

    def get_weather(self, city: str = "auto") -> str:
        return web.get_weather(city=city)

    def get_forecast(self, city: str = "auto") -> str:
        return web.get_weather_detailed(city=city)
