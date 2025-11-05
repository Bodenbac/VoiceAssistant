from __future__ import annotations

import sys
from typing import Optional

import pyttsx3

try:
    import win32com.client as wincl  # type: ignore
except Exception:  # pragma: no cover - optional on non-Windows
    wincl = None  # type: ignore


class PyttsxSynthesizer:
    def __init__(self) -> None:
        self._engine = None  # lazy init
        self._sapi_voice = None
        self._sapi_output_bound = False
        self._sapi_output_desc: Optional[str] = None

        # eager init to validate environment
        self._init()

    def _init(self) -> None:
        try:
            if sys.platform.startswith("win"):
                self._engine = pyttsx3.init(driverName="sapi5")
            else:
                self._engine = pyttsx3.init()
        except Exception:
            self._engine = pyttsx3.init()

        self._choose_voice()
        self._engine.setProperty("rate", 170)
        self._engine.setProperty("volume", 1.0)

        if wincl and sys.platform.startswith("win"):
            try:
                self._sapi_voice = wincl.Dispatch("SAPI.SpVoice")
                self._bind_sapi_output_device()
            except Exception:
                self._sapi_voice = None

    def _choose_voice(self) -> None:
        try:
            voices = self._engine.getProperty("voices") or []
            pref = ["zira", "hazel", "david", "helen", "eva", "mark", "english", "en-us", "en-gb"]
            for v in voices:
                name = (getattr(v, "name", "") or "").lower()
                if any(p in name for p in pref):
                    self._engine.setProperty("voice", v.id)
                    return
        except Exception:
            pass

    def _bind_sapi_output_device(self) -> None:  # pragma: no cover - environment specific
        try:
            cat = wincl.Dispatch("SAPI.SpObjectTokenCategory")
            cat.SetId("HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\AudioOutput")
            tokens = cat.EnumerateTokens()
            if tokens:
                tok = tokens.Item(0)
                self._sapi_voice.AudioOutput = tok
                self._sapi_output_bound = True
                self._sapi_output_desc = tok.GetDescription()
        except Exception:
            self._sapi_output_bound = False

    def speak(self, text: str) -> None:
        if not text:
            return
        try:
            if self._sapi_voice is not None and self._sapi_output_bound:
                self._sapi_voice.Speak(text)  # type: ignore[attr-defined]
                return
        except Exception:
            pass

        try:
            self._engine.stop()
        except Exception:
            pass
        self._engine.say(text)
        self._engine.runAndWait()

