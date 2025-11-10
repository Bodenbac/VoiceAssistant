from __future__ import annotations

import sys
import time

from .config import BLOCKSIZE, MODEL_PATH, SAMPLE_RATE
from .interfaces import IntentRecognizer, SpeechSynthesizer
from .asr import ASR
from .tts import EspeakSynthesizer, PyttsxSynthesizer
from .nlu.rule_based import SimpleRuleNLU
from .dialogue.manager import SimpleDialogueManager
from .apis.weather import WeatherClientImpl
from .apis.calendar import CalendarClientImpl

_AVAILABLE_TTS = {
    "espeak": "eSpeak NG (CLI)",
    "pyttsx": "pyttsx3 (SAPI/OS built-in)",
}


def _determine_tts_backend(default: str = "espeak") -> str:
    if sys.stdin is None or not sys.stdin.isatty():
        print(f"[VoiceAssistant] No interactive terminal detected. Defaulting to {default}.")
        return default

    prompt = f"Select TTS backend (espeak / pyttsx) [{default}]: "
    while True:
        try:
            choice = input(prompt).strip().lower()
        except EOFError:
            choice = ""
        backend = choice or default
        if backend in _AVAILABLE_TTS:
            return backend
        supported = ", ".join(_AVAILABLE_TTS)
        print(f"Unsupported option '{choice}'. Please choose one of: {supported}.")


def _build_tts() -> SpeechSynthesizer:
    backend = _determine_tts_backend()
    print(f"[VoiceAssistant] Requested TTS backend: {backend} ({_AVAILABLE_TTS[backend]}).")
    try:
        if backend == "espeak":
            synth = EspeakSynthesizer()
            print("[VoiceAssistant] eSpeak NG TTS initialized successfully.")
            return synth
        synth = PyttsxSynthesizer(language="en")
        print("[VoiceAssistant] pyttsx3 initialized successfully.")
        return synth
    except Exception as exc:
        print(f"[VoiceAssistant] Failed to initialize '{backend}' backend: {exc}. Falling back to pyttsx3.")
        return PyttsxSynthesizer(language="en")


def _build_asr() -> ASR:
    print("[VoiceAssistant] Using ASR backend: vosk_asr (simple demo recognizer).")
    return ASR(MODEL_PATH, SAMPLE_RATE, BLOCKSIZE)


def run() -> None:
    tts = _build_tts()
    nlu: IntentRecognizer = SimpleRuleNLU()
    dm = SimpleDialogueManager(weather=WeatherClientImpl(), calendar=CalendarClientImpl())

    asr = _build_asr()

    def on_text(txt: str) -> None:
        intent = nlu.parse(txt)
        response = dm.handle(intent, txt)
        if response:
            tts.speak(response)
        if intent and intent.name == "exit":
            # small delay to allow TTS to finish
            time.sleep(0.3)
            asr.stop()
            sys.exit(0)

    asr.set_callback(on_text)

    tts.speak("Assistant starting. Loading speech model. Please wait.")
    try:
        asr.start()
    except Exception as e:
        print("Failed to start ASR:", e)
        tts.speak("Failed to load the speech model.")
        return

    tts.speak("Microphone is active. Ready to go.")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            asr.stop()
        except Exception:
            pass


if __name__ == "__main__":
    run()
