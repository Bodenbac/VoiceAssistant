import pyttsx3, time

# This test tries to get a spoken response of TTS, because in main the answer is only written as text, not spoken

e = pyttsx3.init(driverName='sapi5')
print("Voices:")
for v in e.getProperty('voices'):
    print("-", v.id, v.name)


# chose english voice
for v in e.getProperty('voices'):
    if 'zira' in v.name.lower() or 'hazel' in v.name.lower() or 'english' in v.name.lower():
        e.setProperty('voice', v.id)
        break
e.setProperty('rate', 170)
e.setProperty('volume', 1.0)
print("Saying hello…")
e.say("Hello! This is a test.")
e.runAndWait()
time.sleep(0.5)
