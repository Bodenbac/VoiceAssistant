
import json, queue, re, sys, os
from datetime import datetime

import pyttsx3
import sounddevice as sd
from vosk import Model, KaldiRecognizer

SAMPLE_RATE = 16000
MODEL_PATH = r"models\voskmodel"

# ---------- TTS ----------
tts = pyttsx3.init()

def try_set_english_voice():
    for v in tts.getProperty("voices"):
        name = (v.name or "").lower()
        lang = "".join(getattr(v, "languages", [])).lower()
        if "en" in name or "english" in name or "en" in lang:
            tts.setProperty("voice", v.id)
            break

try_set_english_voice()

def say(text: str):
    print("[Assistent]", text)
    tts.say(text)
    tts.runAndWait()

def handle(text: str):
    t = text.lower().strip()
    if not t:
        return
    print(f"[Intent-Input] {t}")

    # time
    if re.search(r"\b(time|what('s| is) the time|current time)\b", t):
        say("It is " + datetime.now().strftime("%H:%M"))
    # greeting
    elif re.search(r"\b(hi|hello|hey|good (morning|afternoon|evening))\b", t):
        say("Hello! How can I help?")
    # exit
    elif re.search(r"\b(exit|quit|stop|close|goodbye)\b", t):
        say("Goodbye!")
        sys.exit(0)
    else:
        say("Sorry, I didn't get that.")

def main():
    print("Model path:", os.path.abspath(MODEL_PATH))
    print("Model path exists:", os.path.exists(MODEL_PATH))
    if os.path.exists(MODEL_PATH):
        try:
            print("Contains:", os.listdir(MODEL_PATH)[:5])
        except Exception:
            pass

    say("Assistant starting.")
    try:
        model = Model(MODEL_PATH)
    except Exception as e:
        print("Failed to load Vosk model:", e)
        print("➡️ Prüfe, ob MODEL_PATH auf den entpackten Modellordner zeigt (mit am/, conf/, ...).")
        return

    rec = KaldiRecognizer(model, SAMPLE_RATE)
    q = queue.Queue()

    def callback(indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        q.put(bytes(indata))

    say("Ready. Speak a command. Say 'exit' to quit.")
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000,
                           dtype="int16", channels=1, callback=callback):
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text:
                    handle(text)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
