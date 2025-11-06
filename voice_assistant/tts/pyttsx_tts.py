from __future__ import annotations

import sys
from typing import Optional

import pyttsx3

try:
    import win32com.client as wincl  # type: ignore
except Exception:  # pragma: no cover - optional on non-Windows
    wincl = None  # type: ignore


class PyttsxSynthesizer:
    def __init__(self, *, language: Optional[str] = "en", voice_name: Optional[str] = None, rate: int = 170) -> None:
        self._engine = None  # lazy init
        self._sapi_voice = None
        self._sapi_output_bound = False
        self._sapi_output_desc: Optional[str] = None

        # selection preferences
        self._pref_language = (language or "").lower() or None
        self._pref_voice_name = (voice_name or "").lower() or None
        self._pref_rate = rate

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
        self._engine.setProperty("rate", self._pref_rate)
        self._engine.setProperty("volume", 1.0)

        if wincl and sys.platform.startswith("win"):
            try:
                self._sapi_voice = wincl.Dispatch("SAPI.SpVoice")
                self._choose_sapi_voice()
                self._bind_sapi_output_device()
            except Exception:
                self._sapi_voice = None

    def _voice_lang_matches(self, lang_blob: Optional[object]) -> bool:
        try:
            if not self._pref_language:
                return False
            if lang_blob is None:
                return False
            # pyttsx3 often exposes languages as list[bytes]
            if isinstance(lang_blob, (list, tuple)):
                for it in lang_blob:
                    s = (
                        it.decode(errors="ignore") if isinstance(it, (bytes, bytearray)) else str(it)
                    ).lower()
                    if self._pref_language in s:
                        return True
                return False
            s = (
                lang_blob.decode(errors="ignore") if isinstance(lang_blob, (bytes, bytearray)) else str(lang_blob)
            ).lower()
            return self._pref_language in s
        except Exception:
            return False

    def _choose_voice(self) -> None:
        try:
            voices = self._engine.getProperty("voices") or []
            # build a scoring function to pick the best English-capable voice
            def score(v: object) -> int:
                sc = 0
                try:
                    name = (getattr(v, "name", "") or "").lower()
                    vid = (getattr(v, "id", "") or "").lower()
                    langs = getattr(v, "languages", None)
                    if self._pref_voice_name and self._pref_voice_name in name:
                        sc += 1000
                    if self._pref_language:
                        # direct language hints
                        if "en" in self._pref_language:
                            # prefer common English voice names
                            for n in ("zira", "hazel", "david", "helen", "eva", "mark", "zira pro", "james"):
                                if n in name:
                                    sc += 300
                            # id often contains enus/engb markers
                            for t in ("en-us", "en-gb", "enus", "engb", "english", "en_"):
                                if t in name or t in vid:
                                    sc += 200
                        # check languages list
                        if self._voice_lang_matches(langs):
                            sc += 400
                    # de-prioritize obvious German voices
                    for de in ("german", "de-", "_de", " german"):
                        if de in name or de in vid:
                            sc -= 200
                except Exception:
                    pass
                return sc

            if voices:
                best = max(voices, key=score)
                self._engine.setProperty("voice", getattr(best, "id", None))
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

    def _choose_sapi_voice(self) -> None:  # pragma: no cover - environment specific
        try:
            if not self._sapi_voice:
                return
            tokens = self._sapi_voice.GetVoices()
            if not tokens:
                return

            def tok_attr(tok: object, attr: str) -> str:
                try:
                    return str(tok.GetAttribute(attr) or "")
                except Exception:
                    return ""

            def tok_score(tok: object) -> int:
                sc = 0
                try:
                    name = (tok_attr(tok, "Name") or tok.GetDescription()).lower()
                    lang = tok_attr(tok, "Language").lower()  # LCID string like "409", may be semicolon-separated
                    vendor = tok_attr(tok, "Vendor").lower()
                    idstr = str(getattr(tok, "Id", "") or "").lower()

                    if self._pref_voice_name and self._pref_voice_name in name:
                        sc += 1000
                    if self._pref_language:
                        if "en" in self._pref_language:
                            # Prefer English LCIDs: 0409 (en-US), 0809 (en-GB), 0c09 (en-AU), 1009 (en-CA), 1409 (en-NZ)
                            for lcid in ("409", "0809", "0409", "0c09", "1009", "1409"):
                                if lcid in lang:
                                    sc += 500
                            # Name/id hints
                            for hint in ("english", "en-us", "en-gb", "enus", "engb", "en_"):
                                if hint in name or hint in idstr:
                                    sc += 300
                    # De-prioritize German LCID 0407
                    if any(x in lang for x in ("407", "0407")) or "german" in name:
                        sc -= 400
                    # Small bias for Microsoft neural voices if present
                    if "microsoft" in vendor or "mstts" in idstr:
                        sc += 50
                except Exception:
                    pass
                return sc

            # Find best token
            best_tok = None
            best_score = -10**9
            for i in range(tokens.Count):
                tok = tokens.Item(i)
                s = tok_score(tok)
                if s > best_score:
                    best_score = s
                    best_tok = tok
            if best_tok is not None:
                self._sapi_voice.Voice = best_tok
        except Exception:
            # If selection fails, keep default
            pass

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
