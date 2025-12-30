from __future__ import annotations

import re
from typing import Optional

from ..interfaces import Intent, IntentRecognizer


class SimpleRuleNLU(IntentRecognizer):
    def parse(self, text: str) -> Optional[Intent]:
        t = (text or "").lower().strip()
        if not t:
            return None

        # Weather-related queries
        if re.search(r"\b(weather|temperature|forecast|rain|raining|sunny|cloudy|snow)\b", t):
            return self.get_weather_intent(text)

        # Calendar-related queries
        if re.search(r"\b(calendar|calender|meeting|meet|event|schedule|appointment|reminder)\b", t):
            return Intent(name="calendar_query", slots={})

        if re.search(r"\b(time|current time|what time is it|what('s| is) the time)\b", t):
            return Intent(name="get_time", slots={})
        if re.search(r"\b(hi|hello|hey|good (morning|afternoon|evening))\b", t):
            return Intent(name="greet", slots={})
        if re.search(r"\b(exit|quit|stop|close|goodbye)\b", t):
            return Intent(name="exit", slots={})
        # follow-up like "what about tomorrow?"
        if re.search(r"\b(tomorrow|today|then|that day)\b", t):
            return self.get_weather_intent(text)

        return Intent(name="fallback", slots={"text": t})

    def get_weather_intent(self, text: str) -> Optional[Intent]:
        slots = {}
        if "tomorrow" in text.lower():
            slots["day"] = 1
        elif "today" in text.lower():
            slots["day"] = 0
        m = re.search(r"after\s+(\d+)\s+day", text.lower())
        if m:
            slots["day"] = int(m.group(1))
        return Intent(name="weather_query", slots=slots)