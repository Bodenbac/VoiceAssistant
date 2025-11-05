from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


# ---- Core Data Types ----

@dataclass
class Intent:
    name: str
    slots: Dict[str, Any]


# ---- Interfaces ----

class SpeechRecognizer(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def set_callback(self, on_text: Callable[[str], None]) -> None: ...


class SpeechSynthesizer(ABC):
    @abstractmethod
    def speak(self, text: str) -> None: ...


class IntentRecognizer(ABC):
    @abstractmethod
    def parse(self, text: str) -> Optional[Intent]: ...


class DialogueManager(ABC):
    @abstractmethod
    def handle(self, intent: Optional[Intent], raw_text: str) -> str: ...


# ---- API Clients ----

class WeatherClient(ABC):
    @abstractmethod
    def current(self, location: str) -> Dict[str, Any]: ...


class CalendarClient(ABC):
    @abstractmethod
    def create_event(self, **kwargs: Any) -> Dict[str, Any]: ...

    @abstractmethod
    def list_events(self, **kwargs: Any) -> Dict[str, Any]: ...

