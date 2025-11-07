from __future__ import annotations

from typing import Any, Dict

from ..interfaces import WeatherClient

import requests

class RestWeatherClient(WeatherClient):

    def __init__(self, base_url: str = "https://api.responsible-nlp.net/weather.php"):
        self.base_url = base_url

    def current(self, location: str) -> Dict[str, Any]:
        data = {"place": location}
        response = requests.post(self.base_url, data=data)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API error {response.status_code}: {response.text}")
