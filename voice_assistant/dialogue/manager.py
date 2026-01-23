from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..apis.weather import RestWeatherClient
from ..interfaces import DialogueManager as DialogueManagerIF, Intent


class DialogueState:
    def __init__(self):
        self.active_intent: Optional[str] = None
        self.slots: dict = {}

    def reset(self):
        self.active_intent = None
        self.slots.clear()

class SimpleDialogueManager(DialogueManagerIF):

    def __init__(self):
        self.weather_client = RestWeatherClient()
        self.state = DialogueState()

class SimpleDialogueManager(DialogueManagerIF):

    def __init__(self):
        self.weather_client = RestWeatherClient()
        self.state = DialogueState()

    def handle(self, intent: Optional[Intent], raw_text: str) -> str:
        if intent is None:
            print("NO INTENT FOUND!")
            return ""

        # -------------------------
        # 1) Update dialogue state
        # -------------------------
        if intent.name == self.state.active_intent:
            self.state.slots.update(intent.slots)
        else:
            self.state.active_intent = intent.name
            self.state.slots = intent.slots.copy()

        # -------------------------
        # 2) Route intent
        # -------------------------
        if intent.name == "weather_query":
            response = self.create_weather_response()

        elif intent.name == "calendar_query":
            response = self.create_calendar_response()

        elif intent.name == "get_time":
            response = "It is " + datetime.now().strftime("%H:%M")

        elif intent.name == "greet":
            response = "Hello! How can I help?"

        elif intent.name == "exit":
            response = "Goodbye!"

        else:
            response = "Sorry, I didn't get that."

        # -------------------------
        # 3) Reset state if needed
        # -------------------------
        if intent.name in {"exit", "fallback"}:
            self.state.reset()

        return response


    def create_weather_response(self):

        location = self.state.slots.get("location", "Marburg")
        day_index = self.state.slots.get("day", 0)

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

