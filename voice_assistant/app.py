from __future__ import annotations

import sys
import time

from .config import BLOCKSIZE, MODEL_PATH, SAMPLE_RATE
from .interfaces import IntentRecognizer
from .asr.vosk_asr import VoskRecognizer
from .tts.pyttsx_tts import PyttsxSynthesizer
from .nlu.rule_based import SimpleRuleNLU
from .dialogue.manager import SimpleDialogueManager


def run() -> None:
    # Prefer English TTS voice explicitly
    tts = PyttsxSynthesizer(language="en")
    nlu: IntentRecognizer = SimpleRuleNLU()
    dm = SimpleDialogueManager()

    asr = VoskRecognizer(MODEL_PATH, SAMPLE_RATE, BLOCKSIZE)

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
