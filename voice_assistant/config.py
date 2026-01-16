import os

SAMPLE_RATE = 16000
BLOCKSIZE = 8000

# MODEL options: tiny (~75 MB), base (~145 MB), small (~466 MB), medium (~1.5 GB).
# Default stays on "small".
MODEL = "small"

WHISPER_MODEL_SIZES = {
    "tiny": ("tiny", "Tiny model (~75 MB)", 75),
    "base": ("base", "Base model (~145 MB)", 145),
    "small": ("small", "Small model (~466 MB)", 466),
    "medium": ("medium", "Medium model (~1.5 GB)", 1500),
}
WHISPER_DEFAULT_MODEL = MODEL
WHISPER_DEVICE = "cpu"  # cuda not possible on AMD GPU
WHISPER_COMPUTE_TYPE = "int8"  # CPU optimization (int8, int16, float32)
