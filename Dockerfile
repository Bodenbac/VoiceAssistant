# NOTE: Audio I/O in containers is environment-specific and may require
# additional configuration (PulseAudio/ALSA). This Dockerfile is a starting point
# for packaging and running non-audio parts or with host audio passthrough.

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY voice_assistant ./voice_assistant
COPY models ./models

CMD ["python", "-m", "voice_assistant"]

