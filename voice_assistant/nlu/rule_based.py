from __future__ import annotations

import re
from typing import Optional

from ..interfaces import Intent, IntentRecognizer


class SimpleRuleNLU(IntentRecognizer):
    """
    This is the Natural Language Understanding component.
    it takes what the user says and figures out what they want (the intent)
    and extracts important information (slots) like dates, times, locations etc
    """
    def parse(self, text: str) -> Optional[Intent]:
        # convert to lowercase for easier matching
        t = (text or "").lower().strip()
        if not t:
            return None

        # check if user is asking about weather
        # note: includes common weather-related words
        if re.search(r"\b(weather|temperature|forecast|rain|shower|clear|clouds|cloud|snow|mist|thunderstorms?)\b", t):
            return self.get_weather_intent(text)

        # check for calendar/appointment related stuff
        # handles both "calendar" and "calender" (common typo)
        if re.search(r"\b(calendar|calender|meeting|meet|event|schedule|appointment|appointments|reminder)\b", t):
            return self.get_calendar_intent(text)

        # simple intents that dont need slot extraction
        if re.search(r"\b(time|current time|what time is it|what('s| is) the time)\b", t):
            return Intent(name="get_time", slots={})
        if re.search(r"\b(hi|hello|hey|good (morning|afternoon|evening))\b", t):
            return Intent(name="greet", slots={})
        if re.search(r"\b(exit|quit|stop|close|goodbye)\b", t):
            return Intent(name="exit", slots={})

        # handle follow-up queries like "what about tomorrow?" or "and in Marburg"
        # assumes they're continuing previous weather conversation
        if re.search(r"\b(tomorrow|today|then|that day|yesterday|and in|and on|in\s+[a-zA-Z])\b", t):
            return self.get_weather_intent(text)

        # if nothing matches, return fallback intent
        return Intent(name="fallback", slots={"text": t})

    def get_weather_intent(self, text: str) -> Optional[Intent]:
        slots = {}
        lower_text = text.lower()

        # check if this is a yes/no question
        # like "will it rain?" "is it going to snow?" etc
        if re.search(r"\b(will it|is it going to|is it gonna|will there be)\b", lower_text):
            slots["question_type"] = "yes_no"

            # extract what weather condition they're asking about
            # only the exact 9 API conditions
            # "will there be rain?" -> "rain"
            # "will there be shower rain?" -> "shower rain"
            # "will there be clear sky?" -> "clear sky"
            condition_match = re.search(
                r"\b(?:will it|is it going to|is it gonna|will there be)\s+(?:be\s+)?(?:a\s+)?(?:the\s+)?(shower\s+rain|clear\s+sky|few\s+clouds|scattered\s+clouds|broken\s+clouds|thunderstorms?|rain|snow|mist)\b",
                lower_text
            )
            if condition_match:
                slots["asked_condition"] = condition_match.group(1).strip()

        # Time/day slot extraction
        if "tomorrow" in lower_text:
            slots["day"] = 1
        elif "today" in lower_text:
            slots["day"] = 0
        elif "yesterday" in lower_text:
            slots["day"] = -1
        else:
            # Try to extract day of week (Friday, Saturday, etc.)
            day_offset = self._parse_day_of_week(lower_text)
            if day_offset is not None:
                slots["day"] = day_offset

        m = re.search(r"after\s+(\d+)\s+day", lower_text)
        if m:
            slots["day"] = int(m.group(1))

        # Location slot extraction
        # also handle "there" which refers to previous location
        if "there" in lower_text:
            # location will be filled from dialogue state
            pass
        else:
            loc_match = re.search(
                r"\b(?:in|at|for)\s+(?!\b(?:the\s+)?(?:tomorrow|today|yesterday|after|on|this|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|weekend|tonight)\b)([a-zA-Z][a-zA-Z\s\-]+?)(?=\b(?:tomorrow|today|yesterday|after|on|for|this|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|weekend|tonight)\b|[?.!,]|$)",
                text,
                re.IGNORECASE,
            )
            if loc_match:
                slots["location"] = loc_match.group(1).strip()
            else:
                follow_match = re.search(
                    r"\b(?:and\s+then|and)\s+(?:in|at|for)\s+(?!\b(?:the\s+)?(?:tomorrow|today|yesterday|after|on|this|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|weekend|tonight)\b)([a-zA-Z][a-zA-Z\s\-]+?)(?=\b(?:tomorrow|today|yesterday|after|on|for|this|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|weekend|tonight)\b|[?.!,]|$)",
                    text,
                    re.IGNORECASE,
                )
                if follow_match:
                    slots["location"] = follow_match.group(1).strip()

        return Intent(name="weather_query", slots=slots)

    def get_calendar_intent(self, text: str) -> Optional[Intent]:
        """
        parses calendar-related commands and extracts all the relevant information
        like what action (create/delete/update), when, where, what title etc
        """
        slots = {}
        lower_text = text.lower()

        # First figure out what action the user wants to do
        # checking for common verbs that indicate create/delete/update/list
        if re.search(r"\b(change|update|modify|move)\b", lower_text) and re.search(r"\b(place|location)\b", lower_text):
            slots["action"] = "update"
        elif re.search(r"\b(call this appointment|name this appointment)\b", lower_text):
            slots["action"] = "create"
        elif re.search(r"\b(add|create|schedule|book|make)\b", lower_text):
            slots["action"] = "create"
        elif re.search(r"\b(delete|remove|cancel)\b", lower_text):
            slots["action"] = "delete"
        elif re.search(r"\b(update|change|modify|move)\b", lower_text):
            slots["action"] = "update"
        elif re.search(r"\b(show|list|get|find|where|what('?s| is).*appointment)\b", lower_text):
            slots["action"] = "list"
        else:
            # if we cant figure it out, assume they want to list events
            slots["action"] = "list"

        if slots.get("action") == "list" and re.search(r"\b(next|upcoming)\s+appointment\b", lower_text):
            slots["list_mode"] = "next"

        # extract when the event is (day offset from today)
        # handles "tomorrow", "today", specific days like "Friday", or dates like "12th of january"
        if "tomorrow" in lower_text:
            slots["day"] = 1
        elif "today" in lower_text:
            slots["day"] = 0
        elif "yesterday" in lower_text:
            slots["day"] = -1
        else:
            # try specific dates like "12th of January" first
            date_offset = self._parse_specific_date(text)
            if date_offset is not None:
                slots["day"] = date_offset
            else:
                # fall back to day of week (Friday, Monday, etc.)
                day_offset = self._parse_day_of_week(lower_text)
                if day_offset is not None:
                    slots["day"] = day_offset

        # extract the appointment title
        # looks for patterns like "titled Meeting" or "called Conference"
        title_match = re.search(
            r"\b(?:titled|called|named|name|with the name)\s+(['\"]?)([a-zA-Z0-9][^'\",.?!]*?)\1(?=\s+(?:for|on|at|tomorrow|today)\b|[,.?!]|$)",
            text,
            re.IGNORECASE
        )
        if not title_match:
            title_match = re.search(
                r"\bcall\s+this\s+appointment\s+(['\"]?)([a-zA-Z0-9][^'\",.?!]*?)\1\b",
                text,
                re.IGNORECASE,
            )
        if title_match:
            slots["title"] = title_match.group(2).strip()
        else:
            # fallback for simpler patterns like "delete appointment School"
            # only for delete/update actions
            if slots.get("action") in ["delete", "update"]:
                simple_title = re.search(
                    r"\bappointment\s+(?!on\b|for\b|at\b|tomorrow\b|today\b|yesterday\b)([a-zA-Z][a-zA-Z0-9\s]*?)(?:\.|$)",
                    text,
                    re.IGNORECASE,
                )
                if simple_title:
                    slots["title"] = simple_title.group(1).strip()
                else:
                    # handle "change ... for the meeting X"
                    meeting_title = re.search(
                        r"\bfor\s+(?:the\s+)?([a-zA-Z][a-zA-Z0-9\s]*?)(?:\s+appointment\b|[?.!,]|$)",
                        text,
                        re.IGNORECASE,
                    )
                    if meeting_title:
                        title = meeting_title.group(1).strip()
                        title = re.sub(r"^(my|the)\s+", "", title, flags=re.IGNORECASE)
                        slots["title"] = title
                    else:
                        # handle "my XYZ appointment"
                        my_title = re.search(
                            r"\b(?:my|the)\s+([a-zA-Z][a-zA-Z0-9\s]*?)\s+appointment\b",
                            text,
                            re.IGNORECASE,
                        )
                        if my_title:
                            slots["title"] = my_title.group(1).strip()

        # extract location
        # handles "in Room 12", "at Building A", or "to Room 15" (for updates)
        loc_match = re.search(
            r"\b(?:in|at|to)\s+(?:the\s+)?(?:location\s+)?([a-zA-Z][a-zA-Z0-9\s\-]+?)(?=\b(?:tomorrow|today|on|for)\b|[?.!,]|$)",
            text,
            re.IGNORECASE,
        )
        if not loc_match:
            loc_match = re.search(
                r"\blocation\s+([a-zA-Z][a-zA-Z0-9\s\-]+?)(?=\b(?:tomorrow|today|on|for)\b|[?.!,]|$)",
                text,
                re.IGNORECASE,
            )
        if loc_match:
            slots["location"] = loc_match.group(1).strip()

        # if they mention "place" or "location" while updating but didn't provide a value
        if slots.get("action") == "update" and re.search(r"\b(place|location)\b", lower_text):
            slots.setdefault("update_field", "location")

        # extract time of day
        # needs to have "at" before it or "am/pm" after to avoid matching random numbers
        # (like "Room 12" shouldnt be parsed as time)
        time_match = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*([ap]m?)?\b", lower_text)
        if not time_match:
            # if no "at", look for explicit am/pm
            time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]m)\b", lower_text)

        if time_match:
            hour = int(time_match.group(1))
            minute = time_match.group(2) or "00"
            meridiem = time_match.group(3)

            # convert to 24-hour format
            if meridiem and 'p' in meridiem and hour < 12:
                hour += 12  # 3pm -> 15
            elif meridiem and 'a' in meridiem and hour == 12:
                hour = 0  # 12am -> 0
            slots["time"] = f"{hour:02d}:{minute}"

        # check for references to previous stuff
        # like "the previously created appointment" or "that one"
        if re.search(r"\b(previously created|last|previous|that one|it)\b", lower_text):
            slots["reference"] = "previous"

        # map the action to the specific intent name
        action = slots.get("action", "list")
        intent_map = {
            "create": "create_event",
            "delete": "delete_event",
            "update": "update_event",
            "list": "list_events"
        }

        return Intent(name=intent_map[action], slots=slots)

    def _parse_day_of_week(self, text: str) -> Optional[int]:
        """
        converts day names like "Friday" or "Monday" into a day offset
        for example if today is Tuesday and user says "Friday", returns 3
        """
        from datetime import datetime

        # map day names to their weekday numbers (monday=0, sunday=6)
        days = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }

        for day_name, day_num in days.items():
            if day_name in text:
                # figure out how many days from now until that day
                today = datetime.now().weekday()
                offset = (day_num - today) % 7

                # if its the same day, assume they mean next week
                # (otherwise offset would be 0 which means today)
                if offset == 0:
                    offset = 7
                return offset

        return None

    def _parse_specific_date(self, text: str) -> Optional[int]:
        """
        parses specific dates like "12th of January" or "5th March"
        and converts them to a day offset from today
        """
        from datetime import datetime

        # regex to match date patterns
        # handles "12th of january", "5 march", "3rd of april" etc
        match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(\w+)", text, re.IGNORECASE)
        if not match:
            return None

        day = int(match.group(1))
        month_str = match.group(2).lower()

        # map month names to numbers
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }

        month = months.get(month_str)
        if not month:
            # month name not recognized
            return None

        try:
            today = datetime.now()
            target = datetime(today.year, month, day)

            # if the date already Happend this year, assume they mean next year
            # (like if its december and they say "january 5th")
            if target < today:
                target = datetime(today.year + 1, month, day)

            # calculate how many days from today
            # use .date() to compare just dates, not times
            # otherwise "tomorrow at midnight" - "today at 10pm" = 0 days
            offset = (target.date() - today.date()).days
            return offset
        except ValueError:
            # invalid date (like february 30th)
            return None
