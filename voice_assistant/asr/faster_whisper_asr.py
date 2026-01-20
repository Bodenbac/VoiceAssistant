import queue
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


class FasterWhisperASR:
    """
    Speech recognition using Faster-Whisper.
    Records audio from microphone and transcribes it using Whisper model.
    """

    def __init__(self,
                 model_size="base",
                 sample_rate=16000,
                 blocksize=8000,
                 device="cpu",
                 compute_type="int8"):
        """
        Initialize the ASR system.
        """
        # Model configuration
        self.model_size = model_size
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self.device = device
        self.compute_type = compute_type
        self.model = None

        # Audio streaming
        self.audio_queue = queue.Queue()
        self.stream = None
        self.worker_thread = None
        self.running = False
        self.paused = False
        self.on_text = None

        # Buffer for audio data
        self.audio_buffer = []
        self.max_buffer_seconds = 15.0

        # Voice detection settings
        self.silence_duration = 2.0  # seconds of silence before transcribing
        self.min_speech_duration = 0.4  # minimum speech length
        self.energy_threshold = 80.0  # volume threshold for detecting voice

        # Timing variables
        self.speech_start_time = None
        self.last_voice_time = None


    def set_callback(self, fn):
        """
        Set the callback function that receives the transcribed text.
        """
        self.on_text = fn


    def audio_callback(self, indata, _frames, _time_info, status):
        """
        Called by sounddevice when new audio data is available.
        _frames and _time_info are required by sounddevice but not used here.
        """
        if status:
            print(status)

        # Add audio to queue if not paused
        if not self.paused:
            self.audio_queue.put(bytes(indata))


    def start(self):
        """
        Start the speech recognition system.
        """
        if self.running:
            return

        self.running = True

        # Setup model directory
        model_dir = self._get_model_directory()
        model_dir.mkdir(parents=True, exist_ok=True)

        # Load Whisper model
        print("[Voice Assistant] Loading ASR model...")
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=str(model_dir),
        )
        print("[Voice Assistant] ASR model loaded. Starting audio stream...")

        # Start microphone input stream
        sd.default.samplerate = self.sample_rate
        self.stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=1,
            callback=self.audio_callback,
        )
        self.stream.start()

        # Start background worker thread
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)
        self.worker_thread.start()


    def pause(self):
        """
        Pause recognition temporarily.
        """
        self.paused = True


    def resume(self):
        """
        Resume recognition after pause.
        """
        self.paused = False

        # Clear old audio data
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        self.audio_buffer.clear()
        self.speech_start_time = None
        self.last_voice_time = None


    def stop(self):
        """
        Stop recognition and cleanup.
        """
        self.running = False

        # Close audio stream
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass

        self.stream = None


    def worker(self):
        """
        Background thread that processes audio and performs transcription.
        """
        while self.running:
            try:
                # Get audio data from queue (wait max 0.1 seconds)
                data = self.audio_queue.get(timeout=0.1)

                # Convert bytes to numpy array
                audio_data = np.frombuffer(data, dtype=np.int16)

                current_time = time.monotonic()

                # Check if voice is detected
                if self._detect_voice(audio_data):
                    # Mark when speech started
                    if self.speech_start_time is None:
                        self.speech_start_time = current_time
                    self.last_voice_time = current_time
                    self.audio_buffer.extend(audio_data)
                else:
                    # Keep silence after speech started (for context)
                    if self.speech_start_time is not None:
                        self.audio_buffer.extend(audio_data)

                # Check if we should transcribe now
                if self._should_transcribe(current_time):
                    self._transcribe_buffer()
                    self._reset_state()

                # Safety check: transcribe if buffer is too long
                max_buffer_size = int(self.sample_rate * self.max_buffer_seconds)
                if len(self.audio_buffer) >= max_buffer_size:
                    self._transcribe_buffer()
                    self._reset_state()

            except queue.Empty:
                # No new audio data, check if we should transcribe
                if self._should_transcribe(time.monotonic()):
                    self._transcribe_buffer()
                    self._reset_state()
                continue

            except Exception as e:
                print(f"[Voice Assistant] Worker error: {e}")
                continue


    def _transcribe_buffer(self):
        """
        Transcribe the audio in the buffer.
        """
        if not self.audio_buffer:
            return

        try:
            # Convert buffer to float32 format for Whisper
            audio_int16 = np.array(self.audio_buffer, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # Run transcription
            segments, info = self.model.transcribe(
                audio_float32,
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                language="en",
            )

            # Collect text from all segments
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            # Combine all text
            text = " ".join(text_parts).strip()

            # Send text to callback
            if text and self.on_text:
                print("[User]", text)
                self.on_text(text)

        except Exception as e:
            print(f"[Voice Assistant] Transcription error: {e}")

        finally:
            # Clear buffer for next transcription
            self.audio_buffer.clear()


    def _get_model_directory(self):
        """
        Get the directory where models are stored.
        """
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "models" / self.model_size


    def _detect_voice(self, audio_data):
        """
        Check if audio contains voice based on energy level.
        """
        if audio_data.size == 0:
            return False

        # Calculate RMS (root mean square) as energy measure
        rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))

        # Voice detected if energy is above threshold
        return rms >= self.energy_threshold


    def _should_transcribe(self, current_time):
        """
        Check if enough speech and silence has been recorded to transcribe.
        """
        # Need both speech start and last voice time
        if self.speech_start_time is None or self.last_voice_time is None:
            return False

        # Calculate durations
        speech_duration = current_time - self.speech_start_time
        silence_duration = current_time - self.last_voice_time

        # Transcribe if we have enough speech and enough silence
        return (silence_duration >= self.silence_duration and
                speech_duration >= self.min_speech_duration)


    def _reset_state(self):
        """
        Reset speech detection state variables.
        """
        self.speech_start_time = None
        self.last_voice_time = None
