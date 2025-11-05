from __future__ import annotations

import json
import queue
import threading
from typing import Callable, Optional

import sounddevice as sd
from vosk import KaldiRecognizer, Model


class VoskRecognizer:
    def __init__(self, model_path: str, sample_rate: int = 16000, blocksize: int = 8000,
                 device_index: Optional[int] = None) -> None:
        self.model_path = model_path
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self.device_index = device_index

        self._model: Optional[Model] = None
        self._recognizer: Optional[KaldiRecognizer] = None
        self._queue: "queue.Queue[bytes]" = queue.Queue()
        self._stream: Optional[sd.RawInputStream] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._on_text: Optional[Callable[[str], None]] = None

    def set_callback(self, on_text: Callable[[str], None]) -> None:
        self._on_text = on_text

    def _callback(self, indata, frames, time_info, status):  # type: ignore[no-redef]
        if status:
            # best-effort logging; avoid raising in audio callback
            try:
                print(status)
            except Exception:
                pass
        self._queue.put(bytes(indata))

    def start(self) -> None:
        if self._running:
            return
        self._running = True

        self._model = Model(self.model_path)
        self._recognizer = KaldiRecognizer(self._model, self.sample_rate)

        args = dict(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        if self.device_index is not None:
            args["device"] = self.device_index

        sd.default.samplerate = self.sample_rate
        self._stream = sd.RawInputStream(**args)
        self._stream.start()

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
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
                # partials are ignored here (can be exposed later)
                pass

