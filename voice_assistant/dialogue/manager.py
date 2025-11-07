from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..apis.weather import RestWeatherClient
from ..interfaces import DialogueManager as DialogueManagerIF, Intent


class SimpleDialogueManager(DialogueManagerIF):

    def __init__(self):
        self.weather_client = RestWeatherClient()

    def handle(self, intent: Optional[Intent], raw_text: str) -> str:
        if intent is None:
            return ""

        if intent.name == "weather_query":
            return self.create_weather_response(intent, raw_text)

        if intent.name == "calendar_query":
            return "Calendar API is not available yet."

        if intent.name == "get_time":
            return "It is " + datetime.now().strftime("%H:%M")
        if intent.name == "greet":
            return "Hello! How can I help?"
        if intent.name == "exit":
            return "Goodbye!"

        # fallback
        return "Sorry, I didn't get that."

    def create_weather_response(self, intent, raw_text):
        location = intent.slots.get("location", "Marburg")
        day_index = intent.slots.get("day", 0)

        weather = self.weather_client.current(location)
        forecast = weather.get("forecast", [])

        if day_index >= len(forecast):
            return f"Sorry, I only have weather data for {len(forecast)} days ahead."

        day_weather = forecast[day_index]
        week_day = day_weather["day"]
        condition = day_weather["weather"]
        min_temp = day_weather["temperature"]["min"]
        max_temp = day_weather["temperature"]["max"]

        if day_index == 0:
            day_phrase = "today"
        elif day_index == 1:
            day_phrase = "tomorrow"
        else:
            day_phrase = f"on {week_day}"

        return (
            f"The weather in {location} {day_phrase} is {condition}, "
            f"with temperatures between {min_temp} and {max_temp} degrees Celsius."
        )
