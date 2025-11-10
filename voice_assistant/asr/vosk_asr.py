import json
import queue
import threading

import sounddevice as sd
from vosk import KaldiRecognizer, Model


class ASR:
    """
    Small and simple version of Vosk speech recognition.
    Reads audio from microphone and prints recognized text.
    """

    # initialize the recognizer class
    def __init__(self, model_path, sample_rate=16000, blocksize=8000, device=None):

        self.model_path = model_path
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self.device = device

        self.model = None
        self.rec = None

        self.q = queue.Queue()
        self.stream = None
        self.thread = None
        self.running = False
        self.on_text = None

    # allow setting a custom callback function
    def set_callback(self, fn):
        self.on_text = fn

    # constantly called by sounddevice with new audio data
    def audio_callback(self, indata, frames, time_info, status):

        if status:
            print(status)
        self.q.put(bytes(indata))

    # start recognition
    def start(self):

        if self.running:
            return
        self.running = True

        self.model = Model(self.model_path)
        self.rec = KaldiRecognizer(self.model, self.sample_rate)

        sd.default.samplerate = self.sample_rate
        kwargs = dict(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=1,
            callback=self.audio_callback,
        )

        # create and start the microphone stream
        self.stream = sd.RawInputStream(**kwargs)
        self.stream.start()

        # create and start the background worker thread
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

    # stop recognition
    def stop(self):

        self.running = False
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        self.stream = None

    # background worker thread
    def worker(self):

        while self.running:
            data = self.q.get()
            if self.rec and self.rec.AcceptWaveform(data):
                try:
                    result = json.loads(self.rec.Result())
                except Exception:
                    result = {}
                text = result.get("text", "").strip()
                if text:
                    print(">>", text)
                    if self.on_text:
                        self.on_text(text)
