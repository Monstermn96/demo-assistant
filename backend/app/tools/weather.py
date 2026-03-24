import httpx
from app.tools.base import BaseTool, ToolContext

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


class WeatherTool(BaseTool):
    name = "weather"
    description = "Get current weather and forecast for any location using Open-Meteo (free, no API key needed)."

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location (e.g. 'Chicago', 'New York')",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of forecast days (1-7, default 3)",
                    },
                },
                "required": ["location"],
            },
        }

    async def execute(self, ctx: ToolContext, location: str, days: int = 3, **kwargs) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            geo_resp = await client.get(GEOCODE_URL, params={"name": location, "count": 1})
            geo_resp.raise_for_status()
            geo = geo_resp.json()

            if not geo.get("results"):
                return {"error": f"Location not found: {location}"}

            place = geo["results"][0]
            lat, lon = place["latitude"], place["longitude"]

            weather_resp = await client.get(OPEN_METEO_URL, params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
                "forecast_days": min(days, 7),
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
            })
            weather_resp.raise_for_status()
            data = weather_resp.json()

            return {
                "location": place.get("name", location),
                "country": place.get("country", ""),
                "current": data.get("current", {}),
                "daily": data.get("daily", {}),
            }


tool = WeatherTool()
