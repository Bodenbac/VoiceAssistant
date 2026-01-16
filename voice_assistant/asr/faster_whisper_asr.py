import queue
import threading
import time
from pathlib import Path

import numpy as np

import sounddevice as sd
from faster_whisper import WhisperModel


class FasterWhisperASR:
    """
    Faster-Whisper-based speech recognition.
    Reads audio from microphone and transcribes using OpenAI Whisper models.
    """

    def __init__(self, model_size="base", sample_rate=16000, blocksize=8000,
                 device="cpu", compute_type="int8"):

        self.model_size = model_size
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self.device = device
        self.compute_type = compute_type

        self.model = None

        self.q = queue.Queue()
        self.stream = None
        self.thread = None
        self.running = False
        self.paused = False
        self.on_text = None

        # Audio buffer settings
        self.max_buffer_duration = 15.0  # seconds, safety cap for long utterances
        self.max_buffer_size = int(self.sample_rate * self.max_buffer_duration)
        self.audio_buffer = []

        # End-of-utterance detection
        self.min_silence_duration = 2.0  # seconds of silence before processing
        self.min_speech_duration = 0.4  # seconds of speech required
        self.energy_threshold = 100.0  # RMS floor threshold for voice activity
        self.min_energy_threshold = 50.0  # Lower bound for adaptive threshold
        self.voice_multiplier = 3.0  # Noise floor multiplier for VAD
        self.noise_floor = 0.0
        self.noise_alpha = 0.95
        self.speech_start_ts = None
        self.last_voice_ts = None

    def set_callback(self, fn):
        """Set callback function that receives recognized text."""
        self.on_text = fn

    def audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice with new audio data."""
        if status:
            print(status)
        # Only queue audio data if not paused
        if not self.paused:
            self.q.put(bytes(indata))

    def start(self):
        """Start recognition: load model and begin audio capture."""
        if self.running:
            return
        self.running = True

        model_dir = self._resolve_model_dir()
        model_dir.mkdir(parents=True, exist_ok=True)

        # Load the Faster-Whisper model
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=str(model_dir),
        )

        print("[Voice Assistant] ASR model loaded. Initializing audio stream...")

        # Configure audio input
        sd.default.samplerate = self.sample_rate
        kwargs = dict(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=1,
            callback=self.audio_callback,
        )

        # Create and start the microphone stream
        self.stream = sd.RawInputStream(**kwargs)
        self.stream.start()

        # Create and start the background worker thread
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

    def pause(self):
        """Pause recognition (keep stream active but ignore input)."""
        self.paused = True

    def resume(self):
        """Resume recognition."""
        self.paused = False
        # Clear the queue to avoid processing old audio
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
        # Clear audio buffer as well
        self.audio_buffer.clear()
        self._reset_speech_state()

    def stop(self):
        """Stop recognition and cleanup resources."""
        self.running = False
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        self.stream = None

    def worker(self):
        """Background worker thread that processes audio and runs transcription."""
        while self.running:
            try:
                # Get audio data from queue (blocking with timeout)
                data = self.q.get(timeout=0.1)

                # Convert bytes to int16 numpy array
                audio_int16 = np.frombuffer(data, dtype=np.int16)

                now = time.monotonic()
                if self._is_voice_active(audio_int16):
                    if self.speech_start_ts is None:
                        self.speech_start_ts = now
                    self.last_voice_ts = now
                    self.audio_buffer.extend(audio_int16)
                else:
                    if self.speech_start_ts is not None:
                        # Keep trailing silence once speech has started
                        self.audio_buffer.extend(audio_int16)

                if self._should_transcribe(now):
                    self._transcribe_buffer()
                    self._reset_speech_state()
                elif len(self.audio_buffer) >= self.max_buffer_size:
                    # Safety cap to avoid unbounded memory growth
                    self._transcribe_buffer()
                    self._reset_speech_state()

            except queue.Empty:
                if self._should_transcribe(time.monotonic()):
                    self._transcribe_buffer()
                    self._reset_speech_state()
                continue
            except Exception as e:
                print(f"[Voice Assistant] Worker error: {e}")
                continue

    def _transcribe_buffer(self):
        """Transcribe the current audio buffer."""
        if not self.audio_buffer:
            return

        try:
            # Convert int16 buffer to float32 numpy array
            audio_int16 = np.array(self.audio_buffer, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # Transcribe with Faster-Whisper
            segments, info = self.model.transcribe(
                audio_float32,
                beam_size=1,  # Faster (greedy search)
                vad_filter=True,  # Voice activity detection
                vad_parameters=dict(min_silence_duration_ms=500),
                language="en",  # Set to English for better performance
            )

            # Extract text from segments
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            # Combine segments into full text
            text = " ".join(text_parts).strip()

            # Call callback if text is not empty
            if text and self.on_text:
                print("[User]", text)
                self.on_text(text)

        except Exception as e:
            print(f"[Voice Assistant] Transcription error: {e}")
        finally:
            # Clear the buffer for next transcription
            self.audio_buffer.clear()

    def _resolve_model_dir(self) -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "models" / self.model_size

    def _is_voice_active(self, audio_int16: np.ndarray) -> bool:
        if audio_int16.size == 0:
            return False
        rms = np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2))
        adaptive_threshold = max(self.min_energy_threshold, self.noise_floor * self.voice_multiplier)
        threshold = max(self.energy_threshold, adaptive_threshold)
        is_voice = rms >= threshold
        if not is_voice:
            if self.noise_floor == 0.0:
                self.noise_floor = rms
            else:
                self.noise_floor = (self.noise_alpha * self.noise_floor) + ((1.0 - self.noise_alpha) * rms)
        return is_voice

    def _should_transcribe(self, now: float) -> bool:
        if self.speech_start_ts is None or self.last_voice_ts is None:
            return False
        speech_elapsed = now - self.speech_start_ts
        silence_elapsed = now - self.last_voice_ts
        return (
            silence_elapsed >= self.min_silence_duration
            and speech_elapsed >= self.min_speech_duration
        )

    def _reset_speech_state(self) -> None:
        self.speech_start_ts = None
        self.last_voice_ts = None
