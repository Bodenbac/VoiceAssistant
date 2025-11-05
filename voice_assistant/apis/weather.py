from __future__ import annotations

from typing import Any, Dict

from ..interfaces import WeatherClient


class StubWeatherClient(WeatherClient):
    def current(self, location: str) -> Dict[str, Any]:
        # TODO: Implement real API call (e.g., OpenWeather)
        return {"location": location, "temp_c": 21.0, "condition": "Sunny"}

