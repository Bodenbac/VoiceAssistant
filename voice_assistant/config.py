import os

SAMPLE_RATE = 16000
BLOCKSIZE = 8000
MODEL_PATH_LARGE = os.path.join("models", "vosk", "vosk-model-en-us-0.22")
MODEL_PATH_SMALL = os.path.join("models", "vosk", "vosk-model-small-en-us-0.15")
DOWNLOADS_PATH = os.path.join("models", "downloads")

VOSK_MODEL_URL_LARGE = "https://drive.google.com/uc?export=download&id=1UJDHKCc9MdMrL_EFN9b3Vg4LP6YyNFr4"
VOSK_MODEL_ARCHIVE_NAME_LARGE = "vosk-model-en-us-0.22.zip"

VOSK_MODEL_URL_SMALL = "https://drive.google.com/uc?export=download&id=19TRt8f-LZVObhd31xhchFKKxb-hyjiyY"
VOSK_MODEL_ARCHIVE_NAME_SMALL = "vosk-model-small-en-us-0.15.zip"
