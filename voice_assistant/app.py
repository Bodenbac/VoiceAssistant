from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from .config import (BLOCKSIZE, SAMPLE_RATE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)
from .interfaces import IntentRecognizer, SpeechSynthesizer
from .asr.faster_whisper_asr import FasterWhisperASR
from .tts import EspeakSynthesizer, PyttsxSynthesizer
from .nlu.rule_based import SimpleRuleNLU
from .dialogue.manager import SimpleDialogueManager

TTS_OPTIONS = {
    "e": ("espeak", "eSpeak NG"),
    "p": ("pyttsx", "pyttsx3"),
}
DEFAULT_TTS_CHOICE = "e"

ASR_OPTIONS = {
    "t": ("tiny", "tiny model (~75 MB)", "tiny"),
    "b": ("base", "base model (~145 MB)", "base"),
    "s": ("small", "small model (~466 MB)", "small"),
    "m": ("medium", "medium model (~1.5 GB)", "medium"),
}
DEFAULT_ASR_CHOICE = "b"


def determine_tts_backend(default_choice: str = DEFAULT_TTS_CHOICE) -> tuple[str, str]:
    default_backend, default_label = TTS_OPTIONS[default_choice]
    if sys.stdin is None or not sys.stdin.isatty():
        print(f"[VoiceAssistant] No interactive terminal detected. Defaulting to {default_label}.")
        return default_backend, default_label

    print("Multiple TTS backends available. Please choose one of the following:")
    for key, (_, label) in TTS_OPTIONS.items():
        print(f"{key}: {label}")
    print()
    
    while True:
        try:
            choice = input(f"Your choice [default: {default_choice}]: ").strip().lower()
        except EOFError:
            choice = ""
        key = choice or default_choice
        if key in TTS_OPTIONS:
            backend, label = TTS_OPTIONS[key]
            return backend, label
        supported = ", ".join(TTS_OPTIONS.keys())
        print(f"Unsupported option '{choice}'. Please choose one of: {supported}.")


def determine_asr_model(default_choice: str = DEFAULT_ASR_CHOICE) -> tuple[str, str, str]:
    default_model, default_label, default_size = ASR_OPTIONS[default_choice]
    if sys.stdin is None or not sys.stdin.isatty():
        print(f"[VoiceAssistant] No interactive terminal detected. Defaulting to {default_label}.")
        return default_model, default_label, default_size

    print("Multiple ASR models available. Please choose one of the following:")
    for key, (_, label, __) in ASR_OPTIONS.items():
        print(f"{key}: {label}")
    print()

    while True:
        try:
            choice = input(f"Your choice [default: {default_choice}]: ").strip().lower()
        except EOFError:
            choice = ""
        key = choice or default_choice
        if key in ASR_OPTIONS:
            model, label, size = ASR_OPTIONS[key]
            return model, label, size
        supported = ", ".join(ASR_OPTIONS.keys())
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


def build_asr(model_size: str, model_label: str) -> FasterWhisperASR:
    print(f"[VoiceAssistant] Selected ASR model: {model_label}.")
    print(f"[VoiceAssistant] Models will download automatically on first use from HuggingFace.")

    return FasterWhisperASR(
        model_size=model_size,
        sample_rate=SAMPLE_RATE,
        blocksize=BLOCKSIZE,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE
    )


def run() -> None:
    # Select ASR model first (before TTS)
    model_choice, model_label, model_size = determine_asr_model()

    tts = build_tts()
    nlu: IntentRecognizer = SimpleRuleNLU()
    dm = SimpleDialogueManager()

    asr = build_asr(model_size, model_label)

    def on_text(txt: str) -> None:
        # Pause microphone during processing
        asr.pause()
        print("[VoiceAssistant] Spoken text is being processed. Microphone deactivated.")
        
        try:
            intent = nlu.parse(txt)
            response = dm.handle(intent, txt)
            if response:
                tts.speak(response)
            if intent and intent.name == "exit":
                # small delay to allow TTS to finish
                time.sleep(0.3)
                asr.stop()
                sys.exit(0)
        finally:
            # Always resume microphone after processing (unless exiting)
            if not (intent and intent.name == "exit"):
                asr.resume()
                print("[VoiceAssistant] Processing complete. Microphone activated.")

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

    print("[VoiceAssistant] Loading speech recognition model into memory. This may take 30-60 seconds...")
    tts.speak("Assistant is starting. Loading speech model. Please wait.")

    if not start_event.wait(timeout=90):
        print("[VoiceAssistant] ASR startup timed out after 90 seconds.")
        tts.speak("The speech model did not load in time. Please try restarting the assistant.")
        return

    if start_error:
        print("Failed to start ASR:", start_error[0])
        tts.speak("Failed to load the speech model.")
        return

    tts.speak("Done! Ready to go.")
    print("[VoiceAssistant] Microphone activated. Listening for commands...")

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
