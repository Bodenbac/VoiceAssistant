from __future__ import annotations

import os
import sys
import threading
import time

from .config import (
    BLOCKSIZE,
    MODEL,
    SAMPLE_RATE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZES,
)
from .interfaces import IntentRecognizer, SpeechSynthesizer
from .asr.faster_whisper_asr import FasterWhisperASR
from .tts import PyttsxSynthesizer
from .nlu.rule_based import SimpleRuleNLU
from .dialogue.manager import SimpleDialogueManager


def get_model_info(model_size: str) -> tuple[str, int]:



    key = (model_size or "").strip().lower()
    info = WHISPER_MODEL_SIZES.get(key)
    if not info:
        supported = ", ".join(sorted(WHISPER_MODEL_SIZES.keys()))
        raise ValueError(f"Unsupported ASR model '{model_size}'. Supported: {supported}.")
    return info[0], info[2]


# build and return the ASR instance
def build_tts() -> SpeechSynthesizer:
    try:
        return PyttsxSynthesizer(language="en")
    except Exception as exc:
        print(f"[Voice Assistant] Failed to initialize pyttsx3: {exc}.")
        raise


# build and return the ASR instance
def build_asr(model_size: str) -> FasterWhisperASR:
    return FasterWhisperASR(
        model_size=model_size,
        sample_rate=SAMPLE_RATE,
        blocksize=BLOCKSIZE,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
    )


def run() -> None:
    # 1. line in console: Display ASR model info
    model_name, model_size_mb = get_model_info(MODEL)
    print(f'[ASR] Selected model: Faster-Whisper "{model_name}" model ({model_size_mb}mb)')

    # 2. line in console: Load ASR (downloads automatically if missing)
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    print(f'[ASR] Loading "{model_name}" model (downloads if needed)...')

    # 3. line in console: Build and start ASR
    asr = build_asr(model_name)

    nlu: IntentRecognizer = SimpleRuleNLU()
    dm = SimpleDialogueManager()

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

    # 4. line in console: Wait for ASR to finish loading
    if not start_event.wait(timeout=90):
        print("[Voice Assistant] ASR startup timed out after 90 seconds.")
        return

    if start_error:
        print(f"[Voice Assistant] Failed to start ASR: {start_error[0]}")
        return

    print()

    # 5. line in console: Now initialize TTS
    print("[TTS] Selected model: Pyttsx3")
    tts = build_tts()
    print("[TTS] Model initialized successfully")
    print()

    # 6. line in console: Setup callback
    def on_text(txt: str) -> None:
        # Pause microphone during processing so that only one command is handled at a time
        asr.pause()
        print("[Voice Assistant] Spoken text is being processed. Microphone deactivated.")

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
                print("[Voice Assistant] Processing complete. Microphone activated.")

    asr.set_callback(on_text)

    # 7. line in console: Ready, user can start speakin
    tts.speak("Done! Ready to go.")
    print("[Voice Assistant] Microphone activated. Listening for commands...")

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
