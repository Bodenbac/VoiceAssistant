from __future__ import annotations

from typing import Any, Dict

from ..interfaces import CalendarClient


class StubCalendarClient(CalendarClient):
    def create_event(self, **kwargs: Any) -> Dict[str, Any]:
        # TODO: Hook up to Google/Microsoft Calendar
        return {"status": "created", **kwargs}

    def list_events(self, **kwargs: Any) -> Dict[str, Any]:
        return {"events": [], **kwargs}

