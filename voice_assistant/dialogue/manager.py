from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..interfaces import DialogueManager as DialogueManagerIF, Intent


class SimpleDialogueManager(DialogueManagerIF):
    def handle(self, intent: Optional[Intent], raw_text: str) -> str:
        if intent is None:
            return ""

        if intent.name == "get_time":
            return "It is " + datetime.now().strftime("%H:%M")
        if intent.name == "greet":
            return "Hello! How can I help?"
        if intent.name == "exit":
            return "Goodbye!"

        # fallback
        return "Sorry, I didn't get that."

