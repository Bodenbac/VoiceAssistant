import os

SAMPLE_RATE = 16000
BLOCKSIZE = 8000

# Faster-Whisper Model Configuration

"""
ASR_OPTIONS = {
    "t": ("tiny", "tiny model (~75 MB)", "tiny"),
    "b": ("base", "base model (~145 MB)", "base"),
    "s": ("small", "small model (~466 MB)", "small"),
    "m": ("medium", "medium model (~1.5 GB)", "medium"),
}
"""

WHISPER_MODEL_SIZES = {
    "tiny": ("tiny", "Tiny model (~75 MB)", 75),
    "base": ("base", "Base model (~145 MB)", 145),
    "small": ("small", "Small model (~466 MB)", 466),
    "medium": ("medium", "Medium model (~1.5 GB)", 1500),
}
WHISPER_DEFAULT_MODEL = "base"
WHISPER_DEVICE = "cpu"  # cuda not possible on AMD GPU
WHISPER_COMPUTE_TYPE = "int8"  # CPU optimization (int8, int16, float32)
