import json
from core.config import SecurityLevel
from plugins.base import BasePlugin


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
        try:
            loc = "" if city.lower() == "auto" else city
            url = f"https://wttr.in/{loc}?format=4"
            req = urllib.request.Request(url, headers={"User-Agent": "SON-V3"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.read().decode("utf-8").strip()
        except Exception as e:
            return f"Could not get weather: {e}"

    def get_forecast(self, city: str = "auto") -> str:
        try:
            loc = "" if city.lower() == "auto" else city
            url = f"https://wttr.in/{loc}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "SON-V3"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            cur = data["current_condition"][0]
            area = data["nearest_area"][0]["areaName"][0]["value"]
            temp = cur["temp_C"]
            feels = cur["FeelsLikeC"]
            desc = cur["weatherDesc"][0]["value"]
            humidity = cur["humidity"]

            return (
                f"Weather for {area}:\n"
                f"• Condition: {desc}\n"
                f"• Temperature: {temp}°C (Feels like {feels}°C)\n"
                f"• Humidity: {humidity}%"
            )
        except Exception as e:
            return f"Could not get forecast: {e}"
