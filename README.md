# <img src="images/icon.png" alt="Voice Assistant" width="64" height="64"> VoiceAssistant

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)](#)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-black.svg)](https://black.readthedocs.io/)

Build a local, modular voice assistant that takes spoken English as input and produces spoken English as output. The system runs offline (no cloud models) and integrates a Weather API and a Calendar API in later milestones.

## Overview

- Offline-first design: all processing happens locally.
- Modular architecture (ASR, TTS, NLU, Dialogue, APIs).
- Simple, swappable interfaces to enable parallel development.

## Quick Start

Prerequisites
- Python 3.8+
- An English Vosk model placed at `models/voskmodel`

Install dependencies
- `pip install -r requirements.txt`

Run the assistant
- `python -m voice_assistant`

## Project Structure

- `voice_assistant/interfaces.py` — shared interfaces for ASR, TTS, NLU, Dialogue, Weather, Calendar
- `voice_assistant/asr/` — ASR implementations (Vosk/Kaldi)
- `voice_assistant/tts/` — TTS implementations (pyttsx3 / SAPI on Windows)
- `voice_assistant/nlu/` — NLU modules (rule-based intent parser for MS1)
- `voice_assistant/dialogue/` — Dialogue manager (simple rule-based for MS1)
- `voice_assistant/apis/` — Weather and Calendar API clients (stubs for MS2)
- `voice_assistant/config.py` — core configuration (sample rate, block size, model path)
- `voice_assistant/app.py` — orchestrates ASR → NLU → Dialogue → TTS
- `voice_assistant/__main__.py` — enables `python -m voice_assistant`
- `models/voskmodel/` — local Vosk model files (not included in repo)
- `tests/` — basic tests (e.g., NLU rules)



### Layout

```
VoiceAssistant/
├─ voice_assistant/
│  ├─ __main__.py
│  ├─ __init__.py
│  ├─ app.py
│  ├─ config.py
│  ├─ interfaces.py
│  ├─ asr/
│  │  ├─ __init__.py
│  │  └─ vosk_asr.py
│  ├─ tts/
│  │  ├─ __init__.py
│  │  └─ pyttsx_tts.py
│  ├─ nlu/
│  │  ├─ __init__.py
│  │  └─ rule_based.py
│  ├─ dialogue/
│  │  ├─ __init__.py
│  │  └─ manager.py
│  └─ apis/
│     ├─ __init__.py
│     ├─ weather.py
│     └─ calendar.py
├─ models/
│  └─ voskmodel/   (place Vosk model here)
├─ tests/
│  └─ test_nlu.py
├─ images/
│  └─ icon.png
├─ requirements.txt
├─ Dockerfile
├─ task_ownership.md
└─ README.md
```

## Milestone 1 (ASR + TTS)

- ASR: `voice_assistant/asr/vosk_asr.py` uses Vosk (Kaldi-based), fully offline.
- TTS: `voice_assistant/tts/pyttsx_tts.py` uses pyttsx3 (SAPI on Windows), fully offline.
- Both comply with the local-only requirement (no cloud dependencies).

## Configuration

`voice_assistant/config.py`
- `SAMPLE_RATE`: default 16000
- `BLOCKSIZE`: default 8000
- `MODEL_PATH`: default `models/voskmodel`

Tip: Ensure `MODEL_PATH` points to an English model to meet “English in/out” for MS1.

## Docker

Build
- `docker build -t voice-assistant .`

Run
- `docker run --rm -it voice-assistant`

Note: Audio I/O inside containers depends on host setup (ALSA/PulseAudio passthrough). Adjust run flags for your environment.

## Tests

- Install `pytest` and run: `pytest -q`
- Example: `tests/test_nlu.py` validates rule-based NLU intents.

## Notes

- Only the Weather and Calendar APIs are allowed as external resources. No cloud ASR/TTS.
