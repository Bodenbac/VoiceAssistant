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


# get model info. used for logging purposes
def get_model_info(model_size: str) -> tuple[str, int]:

    key = (model_size or "").strip().lower()
    info = WHISPER_MODEL_SIZES.get(key)
    if not info:
        supported = ", ".join(sorted(WHISPER_MODEL_SIZES.keys()))
        raise ValueError(f"Unsupported ASR model '{model_size}'. Supported: {supported}.")
    return info[0], info[2]


# build and return the ASR instance
def build_asr(model_size: str) -> FasterWhisperASR:
    return FasterWhisperASR(
        model_size=model_size,
        sample_rate=SAMPLE_RATE,
        blocksize=BLOCKSIZE,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
    )


# build and return the TTS instance
def build_tts() -> SpeechSynthesizer:
    try:
        return PyttsxSynthesizer(language="en")
    except Exception as exc:
        print(f"[Voice Assistant] Failed to initialize pyttsx3: {exc}.")
        raise


def run() -> None:
    # 1. Setup Models
    model_name, _ = get_model_info(MODEL)
    asr = build_asr(model_name)
    nlu: IntentRecognizer = SimpleRuleNLU()
    dm = SimpleDialogueManager()
    tts = build_tts()

    def process_text(txt: str):
        """Helper to run the NLU/DM/TTS logic on any text string."""
        print(f"\nTranscription: {txt}")
        intent = nlu.parse(txt)
        
        if intent:
            print(f"Intent: {intent.name} | Slots: {intent.slots}")
        
        response = dm.handle(intent, txt)
        if response:
            tts.speak(response)

    # 2. CHECK: Are we processing a file or using the mic?
    # Usage: python -m voice_assistant.app path/to/audio.wav
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
        if os.path.exists(audio_path):
            print(f"[MODE] File Processing: {audio_path}")

            # Attempt playback (skipped if fails, e.g. in Docker)
            try:
                import wave
                import numpy as np
                import sounddevice as sd

                with wave.open(audio_path, 'rb') as wf:
                    samplerate = wf.getframerate()
                    # Read all frames -> byte string
                    raw_data = wf.readframes(wf.getnframes())
                    # Convert to int16 (standard WAV PCM)
                    # Note: This assumes 16-bit audio. For robust parsing one might need soundfile,
                    # but pure wave+numpy is a decent fallback for standard files.
                    audio_np = np.frombuffer(raw_data, dtype=np.int16)
                    
                    # If stereo, reshape? wave returns interleaved.
                    # sounddevice handles interleaved by default if channels match.
                    channels = wf.getnchannels()
                    if channels > 1:
                        # Reshape to (frames, channels)
                        audio_np = audio_np.reshape(-1, channels)

                    print(f"[Audio] Playing file ({samplerate} Hz)...")
                    sd.play(audio_np, samplerate)
                    sd.wait()
                    print("[Audio] Playback complete.")
            except Exception as e:
                print(f"[Audio] Playback skipped: {e}")

            # Initialize model if not already loaded (e.g. running in Docker without mic)
            if asr.model is None:
                print(f"[ASR] Initializing ASR model for file input...")
                from faster_whisper import WhisperModel
                
                # Ensure model directory exists
                model_dir = asr._get_model_directory()
                if not os.path.exists(model_dir):
                    os.makedirs(model_dir, exist_ok=True)

                asr.model = WhisperModel(
                    asr.model_size,
                    device=asr.device,
                    compute_type=asr.compute_type,
                    download_root=str(model_dir),
                )

            # Faster-Whisper transcribe takes the file path directly
            segments, _ = asr.model.transcribe(audio_path)
            full_text = " ".join([s.text for s in segments]).strip()
            process_text(full_text)
            print("\n[Done] File processed. Exiting.")
            return
        else:
            print(f"Error: File {audio_path} not found.")
            return

    # 3. ORIGINAL MIC LOGIC (Only runs if no file argument is given)
    print("[MODE] Microphone Streaming activated.")
    
    def on_text_callback(txt: str) -> None:
        asr.pause()
        try:
            process_text(txt)
        finally:
            asr.resume()

    asr.set_callback(on_text_callback)
    asr.start()
    
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        asr.stop()


if __name__ == "__main__":
    run()
