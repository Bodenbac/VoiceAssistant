# handles NameErrors for missing type hints in older Python versions
from __future__ import annotations

# imports
import sys
from typing import Optional
import pyttsx3

try:
    import win32com.client as wincl
except Exception:
    wincl = None


# thin wrapper around pyttsx3 for simple TTS
# works as a fallback
class PyttsxSynthesizer:

    def __init__(self, *, language: Optional[str] = "en", voice_name: Optional[str] = None, rate: int = 170) -> None:
        self.engine = None
        self.sapi_voice = None
        self.sapi_output_bound = False
        self.sapi_output_desc: Optional[str] = None

        # selection of preferences
        self.pref_language = (language or "").lower() or None
        self.pref_voice_name = (voice_name or "").lower() or None
        self.pref_rate = rate

        # trigger init to validate environment
        self.init()

    # initialize pyttsx3 engine
    def init(self) -> None:
        try:
            if sys.platform.startswith("win"):
                self.engine = pyttsx3.init(driverName="sapi5")
            else:
                self.engine = pyttsx3.init()
        except Exception:
            self.engine = pyttsx3.init()

        self.choose_voice()
        self.engine.setProperty("rate", self.pref_rate)
        self.engine.setProperty("volume", 1.0)

        # handle windows SAPI specifics
        if wincl and sys.platform.startswith("win"):
            try:
                self.sapi_voice = wincl.Dispatch("SAPI.SpVoice")
                self.choose_sapi_voice()
                self.bind_sapi_output_device()
            except Exception:
                self.sapi_voice = None

    # helper to match language blobs
    # necessary because pyttsx3 exposes languages in various formats
    def voice_lang_matches(self, lang_blob: Optional[object]) -> bool:
        try:
            if not self.pref_language:
                return False
            if lang_blob is None:
                return False
            # pyttsx3 often exposes languages as list[bytes]
            if isinstance(lang_blob, (list, tuple)):
                for it in lang_blob:
                    s = (
                        it.decode(errors="ignore") if isinstance(it, (bytes, bytearray)) else str(it)
                    ).lower()
                    if self.pref_language in s:
                        return True
                return False
            s = (
                lang_blob.decode(errors="ignore") if isinstance(lang_blob, (bytes, bytearray)) else str(lang_blob)
            ).lower()
            return self.pref_language in s
        except Exception:
            return False

    # simple voice selection logic
    def choose_voice(self) -> None:
        try:
            voices = self.engine.getProperty("voices") or []
        except Exception:
            return
        if not voices:
            return

        # helper to set voice
        def use_voice(v: object) -> None:
            self.engine.setProperty("voice", getattr(v, "id", None))

        # try preferred voice
        if self.pref_voice_name:
            for voice in voices:
                name = (getattr(voice, "name", "") or "").lower()
                if self.pref_voice_name in name:
                    use_voice(voice)
                    return

        # try language match (must be english)
        for voice in voices:
            name = (getattr(voice, "name", "") or "").lower()
            vid = (getattr(voice, "id", "") or "").lower()
            langs = getattr(voice, "languages", None)

            if "en" in name or "english" in name:
                use_voice(voice)
                return
            if "en" in vid:
                use_voice(voice)
                return
            if self.voice_lang_matches(langs):
                use_voice(voice)
                return

        use_voice(voices[0])

    # WINDOWS ONLY
    # Bind SAPI output to the default Windows audio device for the COM fallback.
    def bind_sapi_output_device(self) -> None:
        try:
            if not self.sapi_voice:
                return
            outputs = self.sapi_voice.GetAudioOutputs()
            if outputs and outputs.Count:
                tok = outputs.Item(0)
                self.sapi_voice.AudioOutput = tok
                self.sapi_output_bound = True
                self.sapi_output_desc = tok.GetDescription()
        except Exception:
            self.sapi_output_bound = False

    # WINDOWS ONLY
    # Keep the COM voice aligned with the pyttsx3 preference for consistent output.
    def choose_sapi_voice(self) -> None:
        if not self.sapi_voice:
            return
        try:
            tokens = self.sapi_voice.GetVoices()
        except Exception:
            return
        if not tokens:
            return

        # helper to get token name and language
        def token_name(tok: object) -> str:
            try:
                return (tok.GetDescription() or "").lower()
            except Exception:
                return ""

        # helper to get token language
        def token_lang(tok: object) -> str:
            try:
                return (tok.GetAttribute("Language") or "").lower()
            except Exception:
                return ""

        # try preferred voice name
        if self.pref_voice_name:
            for i in range(tokens.Count):
                tok = tokens.Item(i)
                if self.pref_voice_name in token_name(tok):
                    self.sapi_voice.Voice = tok
                    return

        # try language match (must be english)
        for i in range(tokens.Count):
            tok = tokens.Item(i)
            name = token_name(tok)
            lang = token_lang(tok)
            if "en" in name or "english" in name:
                self.sapi_voice.Voice = tok
                return
            if any(code in lang for code in ("409", "0809", "0c09", "1009", "1409")):
                self.sapi_voice.Voice = tok
                return

        self.sapi_voice.Voice = tokens.Item(0)

    # handle text synthesis
    # lets model speak the input text
    def speak(self, text: str) -> None:
        if not text:
            return
        try:
            if self.sapi_voice is not None and self.sapi_output_bound:
                self.sapi_voice.Speak(text)
                return
        except Exception:
            pass

        try:
            self.engine.stop()
        except Exception:
            pass
        self.engine.say(text)
        self.engine.runAndWait()
