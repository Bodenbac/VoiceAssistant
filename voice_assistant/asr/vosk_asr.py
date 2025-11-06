from __future__ import annotations

import json
import queue
import threading
from typing import Callable, Optional

import sounddevice as sd
from vosk import KaldiRecognizer, Model


class VoskRecognizer:
    # simple class around Vosk to keep microphone capture and recognition logic in one place.
    def __init__(self, model_path: str, sample_rate: int = 16000, blocksize: int = 8000,
                 device_index: Optional[int] = None) -> None:
        # path to vosk model
        self.model_path = model_path
        # microphone sampling rate (Hz)
        self.sample_rate = sample_rate
        # Number of frames per audio block.
        self.blocksize = blocksize
        # Optional sounddevice input device index. If None, uses default device.
        self.device_index = device_index

        # Lazily created Vosk model and recognizer.
        self._model: Optional[Model] = None
        self._recognizer: Optional[KaldiRecognizer] = None
        # Thread-safe queue of raw PCM bytes from the audio callback.
        self._queue: "queue.Queue[bytes]" = queue.Queue()
        # Active microphone stream and worker thread (both started in start()).
        self._stream: Optional[sd.RawInputStream] = None
        self._thread: Optional[threading.Thread] = None
        # Flag to stop the worker loop cleanly.
        self._running = False
        # User-supplied function called with final recognized text.
        self._on_text: Optional[Callable[[str], None]] = None

    def set_callback(self, on_text: Callable[[str], None]) -> None:
        # Let the caller provide a function to receive final transcripts.
        self._on_text = on_text

    def _callback(self, indata, frames, time_info, status):
        # This runs in sounddevice's audio thread. Keep it tiny.
        if status:
            try:
                print(status)
            except Exception:
                pass
        # Push raw bytes (16‑bit mono PCM) into the queue for the worker.
        self._queue.put(bytes(indata))

    def start(self) -> None:
        # stop if already running.
        if self._running:
            return
        self._running = True

        # Load the Vosk model and create the streaming recognizer.
        self._model = Model(self.model_path)
        self._recognizer = KaldiRecognizer(self._model, self.sample_rate)

        # Configure the microphone stream. We use 16-bit samples and 1 channel.
        args = dict(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        if self.device_index is not None:
            args["device"] = self.device_index

        # Ensure sounddevice uses our intended sample rate.
        sd.default.samplerate = self.sample_rate
        # Create and start the non-blocking input stream.
        self._stream = sd.RawInputStream(**args)
        self._stream.start()

        # Spin up a background thread to feed audio to Vosk and collect results.
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # tell worker loop to exit and try to shut down the stream.
        self._running = False
        try:
            if self._stream is not None and getattr(self._stream, "active", False):
                self._stream.stop()
        except Exception:
            pass
        try:
            if self._stream is not None:
                self._stream.close()
        except Exception:
            pass
        self._stream = None

    def _loop(self) -> None:
        # Runs on the background thread: pull audio from the queue and feed it to the recognizer. Emit only finalized results.
        assert self._recognizer is not None
        while self._running:
            data = self._queue.get()
            if self._recognizer.AcceptWaveform(data):
                try:
                    result = json.loads(self._recognizer.Result())
                except Exception:
                    result = {}
                txt = result.get("text", "")
                if txt and self._on_text:
                    self._on_text(txt)
            else:
                # Partial hypotheses are available via self._recognizer.PartialResult(), but we ignore them here.
                pass
