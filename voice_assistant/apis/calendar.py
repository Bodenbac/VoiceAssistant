from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from ..interfaces import CalendarClient


class RestCalendarClient(CalendarClient):
    def __init__(self, base_url: str = "https://api.responsible-nlp.net/calendar.php"):
        self.base_url = base_url

    def create_event(
        self,
        title: str,
        description: str,
        start_time: str,
        end_time: str,
        location: str
    ) -> Dict[str, any]:
        """
        Create a new calendar event.
        """
        payload = {
            "title": title,
            "description": description,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
        }

        response = requests.post(self.base_url, json=payload)
        if response.status_code == 200:
            return response.json().get("entry", response.json())
        else:
            raise Exception(f"API error {response.status_code}: {response.text}")

    def update_event(
        self,
        event_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Update an existing calendar event.
        Only the provided fields will be updated.
        """
        payload = {}
        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        if start_time is not None:
            payload["start_time"] = start_time
        if end_time is not None:
            payload["end_time"] = end_time
        if location is not None:
            payload["location"] = location

        response = requests.put(f"{self.base_url}?id={event_id}", json=payload)
        if response.status_code == 200:
            return response.json().get("entry", response.json())
        else:
            raise Exception(f"API error {response.status_code}: {response.text}")

    def get_event(self, event_id: int) -> Dict[str, Any]:
        response = requests.get(self.base_url + f"?id={event_id}")
        if response.status_code == 200:
            return response.json()["entry"]
        else:
            raise Exception(f"API error {response.status_code}: {response.text}")

    def delete_event(self, event_id: int) -> Dict[str, Any]:
        response = requests.delete(self.base_url + f"?id={event_id}")
        if response.status_code == 200:
            response = response.json()
            if response["message"] == "deleted":
                return response.json()["entry"]
            else:
                raise Exception(f"Could not delete the event from calender."
                                f" message: {response["message"]}")
        else:
            raise Exception(f"API error {response.status_code}: {response.text}")

    def list_events(self) -> Dict[str, Any]:
        response = requests.get(self.base_url)
        if response.status_code == 200:
            return response.json()["entries"]
        else:
            raise Exception(f"API error {response.status_code}: {response.text}")
