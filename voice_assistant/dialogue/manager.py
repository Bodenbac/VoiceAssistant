from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..apis.weather import RestWeatherClient
from ..apis.calendar import RestCalendarClient
from ..interfaces import DialogueManager as DialogueManagerIF, Intent


class DialogueState:
    """
    Keeps track of the conversation state so we can handle follow-up questions.
    Like if the user asks "what about tomorrow?" we need to remeber what they were talking about
    """
    def __init__(self):
        self.active_intent: Optional[str] = None
        self.slots: dict = {}

        # we need to remember stuff for calendar operations
        # like when user says "delete the previously created appointment" we need the ID
        self.last_location: Optional[str] = None  # for weather queries like "what about there?"
        self.last_created_event_id: Optional[int] = None  # stores last event we created
        self.last_queried_events: list = []  # list of events from last query
        self.last_weather_day: Optional[int] = None

    def reset(self):
        self.active_intent = None
        self.slots.clear()
        # don't reset the history stuff becuase we might need it later

class SimpleDialogueManager(DialogueManagerIF):

    def __init__(self):
        self.weather_client = RestWeatherClient()
        self.calendar_client = RestCalendarClient()
        self.state = DialogueState()

    def handle(self, intent: Optional[Intent], raw_text: str) -> str:
        if intent is None:
            print("NO INTENT FOUND!")
            return ""

        # handle follow-up replies for missing slots in create flow
        if self.state.active_intent == "create_event" and self.state.slots.get("awaiting"):
            follow_up_response = self._handle_create_followup(intent, raw_text)
            if follow_up_response is not None:
                return follow_up_response
        # handle follow-up replies for missing slots in update flow
        if self.state.active_intent == "update_event" and self.state.slots.get("awaiting"):
            follow_up_response = self._handle_update_followup(intent, raw_text)
            if follow_up_response is not None:
                return follow_up_response

        # save the current intent slots before updating state
        # (we'll need this for yes/no questions)
        current_intent_slots = intent.slots.copy()

        # -------------------------
        # 1) Update dialogue state
        # -------------------------
        if intent.name == self.state.active_intent:
            self.state.slots.update(intent.slots)
        else:
            self.state.active_intent = intent.name
            self.state.slots = intent.slots.copy()
        if "location" in intent.slots and intent.slots.get("location"):
            self.state.last_location = intent.slots.get("location")

        # -------------------------
        # 2) Route intent
        # -------------------------
        if intent.name == "weather_query":
            # pass current intent slots for yes/no question detection
            response = self.create_weather_response(current_intent_slots, raw_text)

        elif intent.name in ["create_event", "list_events", "update_event", "delete_event"]:
            response = self.handle_calendar_intent(intent.name)

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

    def _normalize_condition_input(self, asked_condition: str) -> str:
        """Normalize user input - only handles thunderstorms plural."""
        condition_lower = asked_condition.lower().strip()

        # Only normalize thunderstorms (plural) to thunderstorm (singular)
        if condition_lower == "thunderstorms":
            return "thunderstorm"

        return condition_lower

    def _match_weather_condition(self, asked_condition: str, actual_condition: str) -> bool:
        """Determine if asked condition matches actual forecast - exact match only."""
        actual_lower = actual_condition.lower().strip()
        asked_lower = asked_condition.lower().strip()

        # Normalize thunderstorms to thunderstorm
        normalized_asked = self._normalize_condition_input(asked_lower)

        # Exact match only
        return normalized_asked == actual_lower

    def _get_natural_phrasing(self, condition: str, is_affirmative: bool) -> str:
        """Generate response phrasing using exact condition names."""
        condition_lower = condition.lower().strip()

        # Use exact condition names with "there will be" format
        # Handle thunderstorms plural
        if condition_lower == "thunderstorms":
            condition_text = "a thunderstorm"
        else:
            condition_text = condition_lower

        if is_affirmative:
            return f"there will be {condition_text}"
        else:
            return f"there will not be {condition_text}"

    def create_weather_response(self, current_intent_slots, raw_text: str):

        if self.state.slots.get("location"):
            self.state.last_location = self.state.slots.get("location")
        elif raw_text and "there" in raw_text.lower() and self.state.last_location:
            self.state.slots["location"] = self.state.last_location

        location = self.state.slots.get("location", "Marburg")
        if "day" in self.state.slots:
            day_index = self.state.slots.get("day", 0)
            self.state.last_weather_day = day_index
        elif self.state.last_weather_day is not None:
            day_index = self.state.last_weather_day
        else:
            day_index = 0

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

        # check if this is a yes/no question about specific weather condition
        # like "will it rain?" or "will it snow?"
        question_type = self.state.slots.get("question_type")
        asked_condition = self.state.slots.get("asked_condition")

        if question_type == "yes_no" and asked_condition:
            # Use new matching system
            is_match = self._match_weather_condition(asked_condition, condition)

            # Generate grammatically correct response
            if is_match:
                phrasing = self._get_natural_phrasing(asked_condition, True)
                return f"Yes, {phrasing} {day_phrase} in {location}. Temperatures will be between {min_temp} and {max_temp} degrees Celsius."
            else:
                phrasing_no = self._get_natural_phrasing(asked_condition, False)
                return f"No, {phrasing_no} {day_phrase}. The weather in {location} will be {condition}, with temperatures between {min_temp} and {max_temp} degrees Celsius."

        # default response for general weather questions
        return (
            f"The weather in {location} {day_phrase} is {condition}, "
            f"with temperatures between {min_temp} and {max_temp} degrees Celsius."
        )

    def handle_calendar_intent(self, intent_name: str) -> str:
        """
        Router function for calendar stuff - basically just calls the right function
        depending on what the user wants to do (create, delete, update, list)
        """
        try:
            if intent_name == "create_event":
                return self._handle_create_event()
            elif intent_name == "list_events":
                return self._handle_list_events()
            elif intent_name == "update_event":
                return self._handle_update_event()
            elif intent_name == "delete_event":
                return self._handle_delete_event()
            else:
                return "Sorry, I don't understand that calendar command."
        except Exception as e:
            # if something goes wrong just tell the user
            print(f"[Calendar Error] {e}")
            return "Sorry, I had trouble with that calendar operation."

    def _handle_create_event(self) -> str:
        """
        Creates a new calendar event when user says something like
        "add appointment titled Meeting tomorrow at 3pm"
        """
        # first get all the info we need from the slots
        # slots are basically the extracted Information from what the user said
        title = self.state.slots.get("title")
        day_offset = self.state.slots.get("day")
        time_str = self.state.slots.get("time")
        location = self.state.slots.get("location")

        # we NEED a title, otherwise we Cant create anything
        if not title:
            self.state.slots["awaiting"] = "title"
            return "What should I call this appointment?"

        if day_offset is None:
            self.state.slots["awaiting"] = "day"
            return "When is the appointment?"

        if not time_str:
            self.state.slots["awaiting"] = "time"
            return "What time is it?"

        if not location:
            self.state.slots["awaiting"] = "location"
            return "Where is it?"

        # calculate the actual date from the day offset
        # so if day_offset=1 and today is monday, target_date will be tuesday
        target_date = datetime.now() + timedelta(days=day_offset)
        date_str = target_date.strftime("%Y-%m-%d")

        # build the start time in ISO format (thats what the API wants)
        hour, minute = time_str.split(":")
        start_time = f"{date_str}T{hour}:{minute}"

        # assume all meetings are 1 hour long (we could make this configurable later)
        end_datetime = target_date.replace(hour=int(hour), minute=int(minute)) + timedelta(hours=1)
        end_time = end_datetime.strftime("%Y-%m-%dT%H:%M")

        # now actually create the event via the API
        try:
            result = self.calendar_client.create_event(
                title=title,
                description="",
                start_time=start_time,
                end_time=end_time,
                location=location
            )

            # save the event ID so we can reference it later
            # (like when user says "delete the previously created appointment")
            self.state.last_created_event_id = result.get("id")

        except Exception as e:
            return f"Sorry, I couldn't create that appointment: {e}"

        # build a nice response to tell the user what we did
        day_phrase = self._naturalize_day(day_offset)
        loc_phrase = f" in {location}" if location else ""
        return f"Created appointment '{title}' for {day_phrase} at {time_str}{loc_phrase}."

    def _handle_create_followup(self, intent: Intent, raw_text: str) -> Optional[str]:
        awaiting = self.state.slots.get("awaiting")
        text = (raw_text or "").strip()

        if awaiting == "title":
            title = text.strip(" .!?\"'")
            if not title:
                return "What should I call this appointment?"
            self.state.slots["title"] = title
            self.state.slots.pop("awaiting", None)
            return self._handle_create_event()

        if awaiting == "day":
            day_offset = intent.slots.get("day")
            if day_offset is None:
                day_offset = self._parse_day_offset(text)
            if day_offset is None:
                return "When should I schedule it?"
            self.state.slots["day"] = day_offset
            self.state.slots.pop("awaiting", None)
            return self._handle_create_event()

        if awaiting == "time":
            time_str = intent.slots.get("time")
            if not time_str:
                time_str = self._parse_time(text)
            if not time_str:
                return "What time should I set?"
            self.state.slots["time"] = time_str
            self.state.slots.pop("awaiting", None)
            return self._handle_create_event()

        if awaiting == "location":
            location = intent.slots.get("location")
            if not location:
                location = self._parse_location(text)
            if not location:
                return "Where should it take place?"
            self.state.slots["location"] = location
            self.state.slots.pop("awaiting", None)
            return self._handle_create_event()

        return None

    def _parse_time(self, text: str) -> Optional[str]:
        import re
        lower_text = (text or "").lower()
        time_match = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?\b", lower_text)
        if not time_match:
            time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b", lower_text)
        if not time_match:
            time_match = re.search(r"\b(\d{1,2})\s*o'?clock\b", lower_text)
        if not time_match:
            time_match = re.search(r"\b(\d{1,2})[.:](\d{2})\b", lower_text)
        if not time_match:
            time_match = re.search(r"\b(\d{1,2})\b", lower_text)
        if not time_match:
            return None
        hour = int(time_match.group(1))
        minute = time_match.group(2) or "00"
        meridiem = time_match.group(3) if len(time_match.groups()) >= 3 else None
        if meridiem:
            meridiem = meridiem.replace(".", "")
        if meridiem and 'p' in meridiem and hour < 12:
            hour += 12
        elif meridiem and 'a' in meridiem and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute}"

    def _parse_day_offset(self, text: str) -> Optional[int]:
        import re
        lower_text = (text or "").lower()
        if "tomorrow" in lower_text:
            return 1
        if "today" in lower_text:
            return 0
        if "yesterday" in lower_text:
            return -1

        # day of week
        days = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        for day_name, day_num in days.items():
            if day_name in lower_text:
                today = datetime.now().weekday()
                offset = (day_num - today) % 7
                if offset == 0:
                    offset = 7
                return offset

        # specific date like "12th of January"
        match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(\w+)", text, re.IGNORECASE)
        if not match:
            return None
        day = int(match.group(1))
        month_str = match.group(2).lower()
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }
        month = months.get(month_str)
        if not month:
            return None
        try:
            today = datetime.now()
            target = datetime(today.year, month, day)
            if target < today:
                target = datetime(today.year + 1, month, day)
            return (target.date() - today.date()).days
        except ValueError:
            return None

    def _parse_location(self, text: str) -> Optional[str]:
        import re
        loc_match = re.search(
            r"\b(?:in|at|to)\s+(?:the\s+)?(?:location\s+)?([a-zA-Z][a-zA-Z0-9\s\-]+)\b",
            text,
            re.IGNORECASE,
        )
        if loc_match:
            return loc_match.group(1).strip()
        return text.strip(" .!?\"'") or None

    def _normalize_title(self, title: Optional[str]) -> str:
        if not title:
            return ""
        t = title.strip().lower()
        if t.startswith("my "):
            t = t[3:].strip()
        elif t.startswith("the "):
            t = t[4:].strip()
        if t.endswith(" appointment"):
            t = t[: -len(" appointment")].strip()
        return t

    def _handle_list_events(self) -> str:
        """
        shows the user their appointments when they ask
        "where is my next appointment?" or "show my appointments"
        """
        # get all events from the calendar API
        try:
            events = self.calendar_client.list_events()
        except Exception as e:
            return f"Sorry, I couldn't retrieve your appointments: {e}"

        # check if there are any events at all
        if not events or len(events) == 0:
            return "You have no appointments scheduled."

        # save events to state so we can reference them later
        # (useful for "update that one" or similar commands)
        self.state.last_queried_events = events

        # if user asked for a specific day, filter the results
        # like "show my appointments tomorrow"
        day_offset = self.state.slots.get("day")
        if day_offset is not None:
            target_date = (datetime.now() + timedelta(days=day_offset)).date()
            filtered = []

            # loop through all events and keep only the ones on the target date
            for event in events:
                event_date_str = event.get("start_time", "").split("T")[0]
                try:
                    event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
                    if event_date == target_date:
                        filtered.append(event)
                except:
                    # if date parsing fails just skip this event
                    continue

            events = filtered

            # if no events on that day, tell the user
            if not events:
                day_phrase = self._naturalize_day(day_offset)
                return f"You have no appointments {day_phrase}."

        # if user asked for next appointment, pick the soonest by start time
        if self.state.slots.get("list_mode") == "next":
            next_event = self._get_next_event(events)
            if not next_event:
                return "You have no upcoming appointments."
            time_part = next_event.get("start_time", "").split("T")[1] if "T" in next_event.get("start_time", "") else ""
            loc_part = f" in {next_event.get('location')}" if next_event.get('location') else ""
            return f"Your next appointment is '{next_event.get('title')}' at {time_part}{loc_part}."

        # format the response depending on how many events there are
        if len(events) == 1:
            # just one event - give details
            evt = events[0]
            time_part = evt.get("start_time", "").split("T")[1] if "T" in evt.get("start_time", "") else ""
            loc_part = f" in {evt.get('location')}" if evt.get('location') else ""
            return f"Your next appointment is '{evt.get('title')}' at {time_part}{loc_part}."
        else:
            # multiple events - list first 3 and count the rest
            titles = [f"'{e.get('title')}'" for e in events[:3]]
            count_phrase = f" and {len(events) - 3} more" if len(events) > 3 else ""
            return f"You have {len(events)} appointments: {', '.join(titles)}{count_phrase}."

    def _handle_delete_event(self) -> str:
        """
        Deletes an appointment. handles phrases like "delete the previously created appointment"
        or "delete appointment called School" by looking up the event ID
        """
        # try to get event ID from slots first
        event_id = self.state.slots.get("event_id")

        # if user said something like "previously created" or "last one"
        # we need to look it up from our history
        if not event_id and self.state.slots.get("reference") == "previous":
            event_id = self.state.last_created_event_id
            if not event_id:
                # we dont have any Saved ID, so we cant delete anything
                return "I don't remember creating any recent appointments."

        # NEW: check if user specified a title like "delete appointment called School"
        if not event_id and "title" in self.state.slots:
            title_to_find = self.state.slots["title"].lower()

            # first check if we have recent query results
            if self.state.last_queried_events:
                matching_events = [e for e in self.state.last_queried_events
                                 if title_to_find in e.get("title", "").lower()]
            else:
                # otherwise query all events
                try:
                    all_events = self.calendar_client.list_events()
                    matching_events = [e for e in all_events
                                     if title_to_find in e.get("title", "").lower()]
                except:
                    matching_events = []

            if len(matching_events) == 1:
                event_id = matching_events[0].get("id")
            elif len(matching_events) > 1:
                return f"Found {len(matching_events)} appointments with that title. Can you be more specific?"
            else:
                return f"Couldn't find an appointment with title '{self.state.slots['title']}'."

        # if we still don't have an ID, ask the user which one they mean
        if not event_id:
            return "Which appointment should I delete?"

        # actually delete the event using the API
        try:
            self.calendar_client.delete_event(event_id)
        except Exception as e:
            return f"Sorry, I couldn't delete that appointment: {e}"

        return "Appointment deleted."

    def _handle_update_event(self) -> str:
        """
        Updates an existing appointment. like when user says
        "change the location of my appointment tomorrow to Room 15"
        """
        # figure out which event the user wants to update
        event_id = self.state.slots.get("event_id")

        # check if they're refering to something we created earlier
        if not event_id and self.state.slots.get("reference") == "previous":
            event_id = self.state.last_created_event_id

        # if they referenced a specific day, find the appointment on that day
        if not event_id and "day" in self.state.slots:
            day_offset = self.state.slots.get("day")
            try:
                events = self.calendar_client.list_events()
            except Exception as e:
                return f"Sorry, I couldn't retrieve your appointments: {e}"

            target_date = (datetime.now() + timedelta(days=day_offset)).date()
            matching = []
            for event in events:
                event_date_str = event.get("start_time", "").split("T")[0]
                try:
                    event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
                except Exception:
                    continue
                if event_date == target_date:
                    matching.append(event)

            # save for possible follow-ups
            self.state.last_queried_events = matching

            if not matching:
                day_phrase = self._naturalize_day(day_offset)
                return f"You have no appointments {day_phrase}."
            if len(matching) == 1:
                event_id = matching[0].get("id")
            else:
                day_phrase = self._naturalize_day(day_offset)
                return f"I found {len(matching)} appointments {day_phrase}. Which one should I update?"

        # if they said "my appointment tomorrow" we can use the last query results
        if not event_id and self.state.last_queried_events:
            event_id = self.state.last_queried_events[0].get("id")

        # try to resolve by title if provided
        if not event_id and "title" in self.state.slots:
            title_to_find = self._normalize_title(self.state.slots.get("title"))
            if title_to_find:
                if self.state.last_queried_events:
                    matching_events = [
                        e for e in self.state.last_queried_events
                        if title_to_find in e.get("title", "").lower()
                    ]
                else:
                    try:
                        all_events = self.calendar_client.list_events()
                        matching_events = [
                            e for e in all_events
                            if title_to_find in e.get("title", "").lower()
                        ]
                    except Exception:
                        matching_events = []

                if len(matching_events) == 1:
                    event_id = matching_events[0].get("id")
                elif len(matching_events) > 1:
                    return f"Found {len(matching_events)} appointments with that title. Can you be more specific?"
                else:
                    return f"Couldn't find an appointment with title '{self.state.slots.get('title')}'."

        if not event_id:
            self.state.slots["awaiting"] = "title"
            return "Which appointment should I update?"

        # build the update dictionary with whatever fields the user wants to change
        updates = {}
        if "location" in self.state.slots:
            updates["location"] = self.state.slots["location"]
        if self.state.slots.get("update_field") == "title" and "title" in self.state.slots:
            updates["title"] = self.state.slots["title"]
        # could add more fields here like time or description

        if not updates:
            # user didnt specify what to change
            if self.state.slots.get("update_field") == "location":
                self.state.slots["awaiting"] = "location"
                return "What is the new location?"
            return "What should I change about the appointment?"

        # send the update to the API
        try:
            self.calendar_client.update_event(event_id=event_id, **updates)
        except Exception as e:
            return f"Sorry, I couldn't update that appointment: {e}"

        # tell user what we changed
        changes = ", ".join([f"{k} to '{v}'" for k, v in updates.items()])
        return f"Updated appointment: changed {changes}."

    def _handle_update_followup(self, intent: Intent, raw_text: str) -> Optional[str]:
        awaiting = self.state.slots.get("awaiting")
        text = (raw_text or "").strip()

        if awaiting == "title":
            title = text.strip(" .!?\"'")
            if not title:
                return "Which appointment should I update?"
            self.state.slots["title"] = title
            self.state.slots.pop("awaiting", None)
            return self._handle_update_event()

        if awaiting == "location":
            location = intent.slots.get("location") or self._parse_location(text)
            if not location:
                return "Where should it take place?"
            self.state.slots["location"] = location
            self.state.slots.pop("awaiting", None)
            return self._handle_update_event()

        return None

    def _get_next_event(self, events: list) -> Optional[dict]:
        parsed = []
        now = datetime.now()
        for event in events:
            start = event.get("start_time", "")
            try:
                dt = datetime.strptime(start, "%Y-%m-%dT%H:%M")
            except Exception:
                continue
            parsed.append((dt, event))
        if not parsed:
            return None
        parsed.sort(key=lambda item: item[0])
        for dt, event in parsed:
            if dt >= now:
                return event
        return parsed[0][1]

    def _naturalize_day(self, day_offset: int) -> str:
        """
        helper function to convert day offsets (like 0, 1, -1) into
        natural language (like "today", "tomorrow", "yesterday")
        makes the responses sound more human
        """
        if day_offset == 0:
            return "today"
        elif day_offset == 1:
            return "tomorrow"
        elif day_offset == -1:
            return "yesterday"
        else:
            # for other days just return the actual date
            target = datetime.now() + timedelta(days=day_offset)
            return f"on {target.strftime('%A, %B %d')}"
