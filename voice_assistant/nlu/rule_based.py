from __future__ import annotations

import re
from typing import Optional

from ..interfaces import Intent, IntentRecognizer


class SimpleRuleNLU(IntentRecognizer):
    def parse(self, text: str) -> Optional[Intent]:
        t = (text or "").lower().strip()
        if not t:
            return None

        if re.search(r"\b(time|current time|what time is it|what('s| is) the time)\b", t):
            return Intent(name="get_time", slots={})
        if re.search(r"\b(hi|hello|hey|good (morning|afternoon|evening))\b", t):
            return Intent(name="greet", slots={})
        if re.search(r"\b(exit|quit|stop|close|goodbye)\b", t):
            return Intent(name="exit", slots={})

        return Intent(name="fallback", slots={"text": t})

