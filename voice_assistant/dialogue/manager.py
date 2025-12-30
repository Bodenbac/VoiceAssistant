from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..apis.weather import RestWeatherClient
from ..interfaces import DialogueManager as DialogueManagerIF, Intent


class SimpleDialogueManager(DialogueManagerIF):

    def __init__(self):
        self.weather_client = RestWeatherClient()
        self.last_intent: Optional[Intent] = None

    def handle(self, intent: Optional[Intent], raw_text: str) -> str:
        if intent is None:
            print("NO INTENT FOUND!")
            response =  ""
            return ""

        elif intent.name == "weather_query":
            response =  self.create_weather_response(intent, raw_text)

        elif intent.name == "calendar_query":
            response = "Calendar API is not available yet."

        elif intent.name == "get_time":
            response =  "It is " + datetime.now().strftime("%H:%M")
        elif intent.name == "greet":
            response =  "Hello! How can I help?"
        elif intent.name == "exit":
            response =   "Goodbye!"

        # fallback
        elif intent.name == "fallback":
            response =  "Sorry, I didn't get that."
        else: 
            response = "Sorry, i didn't get that."
        self.last_intent = intent
        #TODO: Change to new response with intent information
        return response

    def create_weather_response(self, intent, raw_text):
        # inherit missing slots from previous intent
        if self.last_intent and self.last_intent.name == "weather_query":
            for key, value in self.last_intent.slots.items():
                intent.slots.setdefault(key, value)

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
