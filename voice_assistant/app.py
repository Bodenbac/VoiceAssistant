from __future__ import annotations

import sys
import threading
import time

from .config import BLOCKSIZE, MODEL_PATH, SAMPLE_RATE
from .interfaces import IntentRecognizer, SpeechSynthesizer
from .asr import ASR
from .tts import EspeakSynthesizer, PyttsxSynthesizer
from .nlu.rule_based import SimpleRuleNLU
from .dialogue.manager import SimpleDialogueManager

TTS_OPTIONS = {
    "e": ("espeak", "eSpeak NG"),
    "p": ("pyttsx", "pyttsx3"),
}
DEFAULT_TTS_CHOICE = "e"


def determine_tts_backend(default_choice: str = DEFAULT_TTS_CHOICE) -> tuple[str, str]:
    default_backend, default_label = TTS_OPTIONS[default_choice]
    if sys.stdin is None or not sys.stdin.isatty():
        print(f"[VoiceAssistant] No interactive terminal detected. Defaulting to {default_label}.")
        return default_backend, default_label

    opts = ", ".join(f"{key} ({label})" for key, (_, label) in TTS_OPTIONS.items())
    prompt = f"Select TTS backend [{opts}] [default: {default_choice}]: "
    while True:
        try:
            choice = input(prompt).strip().lower()
        except EOFError:
            choice = ""
        key = choice or default_choice
        if key in TTS_OPTIONS:
            backend, label = TTS_OPTIONS[key]
            return backend, label
        supported = ", ".join(TTS_OPTIONS)
        print(f"Unsupported option '{choice}'. Please choose one of: {supported}.")


def build_tts() -> SpeechSynthesizer:
    backend, label = determine_tts_backend()
    print(f"[VoiceAssistant] Requested TTS backend: {backend} ({label}).")
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


def build_asr() -> ASR:
    print("[VoiceAssistant] Using ASR backend: vosk_asr (simple demo recognizer).")
    return ASR(MODEL_PATH, SAMPLE_RATE, BLOCKSIZE)


def run() -> None:
    tts = build_tts()
    nlu: IntentRecognizer = SimpleRuleNLU()
    dm = SimpleDialogueManager()

    asr = build_asr()

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

    start_event = threading.Event()
    start_error: list[Exception] = []

    def bootstrap_asr() -> None:
        try:
            asr.start()
        except Exception as exc:
            start_error.append(exc)
        finally:
            start_event.set()

    threading.Thread(target=bootstrap_asr, daemon=True).start()

    tts.speak("Assistant is starting. Loading speech model. Please wait.")

    if not start_event.wait(timeout=30):
        print("[VoiceAssistant] ASR startup timed out after 30 seconds.")
        tts.speak("The speech model did not load in time. Please try restarting the assistant.")
        return

    if start_error:
        print("Failed to start ASR:", start_error[0])
        tts.speak("Failed to load the speech model.")
        return

    tts.speak("Done! Ready to go.")

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
