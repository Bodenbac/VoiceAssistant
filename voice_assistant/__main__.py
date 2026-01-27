import argparse

from .app import run
from .config import WHISPER_MODEL_SIZES, WHISPER_DEFAULT_MODEL

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice Assistant")
    parser.add_argument(
        "--asr-model",
        default=WHISPER_DEFAULT_MODEL,
        choices=sorted(WHISPER_MODEL_SIZES.keys()),
        help="ASR model size to use (default from config).",
    )
    args = parser.parse_args()
    run(model_override=args.asr_model)
