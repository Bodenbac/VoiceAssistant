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

        # -------------------------
        # 2) Route intent
        # -------------------------
        if intent.name == "weather_query":
            # pass current intent slots for yes/no question detection
            response = self.create_weather_response(current_intent_slots)

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


    def create_weather_response(self, current_intent_slots):

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

        # check if this is a yes/no question about specific weather condition
        # like "will it rain?" or "will it snow?"
        question_type = self.state.slots.get("question_type")
        asked_condition = self.state.slots.get("asked_condition")

        if question_type == "yes_no" and asked_condition:
            # Check if the actual weather matches what they asked about
            condition_lower = condition.lower()
            asked_lower = asked_condition.lower()

            # check for matches (rain includes "rain" and "shower rain")
            is_match = False
            if "rain" in asked_lower and "rain" in condition_lower:
                is_match = True
            elif "snow" in asked_lower and "snow" in condition_lower:
                is_match = True
            elif "sunny" in asked_lower and "clear sky" in condition_lower:
                is_match = True
            elif "cloud" in asked_lower and "cloud" in condition_lower:
                is_match = True
            elif asked_lower in condition_lower:
                is_match = True

            # build yes/no response
            if is_match:
                return f"Yes, it will {asked_condition} {day_phrase} in {location}. Temperatures will be between {min_temp} and {max_temp} degrees Celsius."
            else:
                return f"No, it will not {asked_condition} {day_phrase}. The weather in {location} will be {condition}, with temperatures between {min_temp} and {max_temp} degrees Celsius."

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
        day_offset = self.state.slots.get("day", 0)  # defaults to today
        time_str = self.state.slots.get("time", "09:00")  # default time is 9am
        location = self.state.slots.get("location", "")

        # we NEED a title, otherwise we Cant create anything
        if not title:
            return "What should I call this appointment?"

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

        # if they said "my appointment tomorrow" we can use the last query results
        if not event_id and self.state.last_queried_events:
            event_id = self.state.last_queried_events[0].get("id")

        if not event_id:
            return "Which appointment should I update?"

        # build the update dictionary with whatever fields the user wants to change
        updates = {}
        if "location" in self.state.slots:
            updates["location"] = self.state.slots["location"]
        if "title" in self.state.slots:
            updates["title"] = self.state.slots["title"]
        # could add more fields here like time or description

        if not updates:
            # user didnt specify what to change
            return "What should I change about the appointment?"

        # send the update to the API
        try:
            self.calendar_client.update_event(event_id=event_id, **updates)
        except Exception as e:
            return f"Sorry, I couldn't update that appointment: {e}"

        # tell user what we changed
        changes = ", ".join([f"{k} to '{v}'" for k, v in updates.items()])
        return f"Updated appointment: changed {changes}."

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
