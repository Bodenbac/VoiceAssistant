from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional


class EspeakSynthesizer:
    """Thin wrapper around the eSpeak NG CLI for simple, offline TTS."""

    def __init__(
        self,
        *,
        voice: str = "en-us",
        rate: int = 180,
        volume: int = 120,
        binary: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
    ) -> None:
        self._binary = binary or shutil.which("espeak-ng") or shutil.which("espeak")
        if not self._binary:
            raise RuntimeError("eSpeak NG executable not found. Install 'espeak-ng' and ensure it is on PATH.")

        self._voice = voice
        self._rate = max(80, min(rate, 450))
        self._volume = max(0, min(volume, 200))
        self._extra_args = list(extra_args or [])

    def speak(self, text: str) -> None:
        if not text:
            return

        cmd = [
            self._binary,
            "-v",
            self._voice,
            "-s",
            str(self._rate),
            "-a",
            str(self._volume),
            *self._extra_args,
            text,
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"eSpeak NG synthesis failed with exit code {exc.returncode}") from exc
