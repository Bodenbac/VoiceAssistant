FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    espeak-ng \
    libespeak1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy your package and model data
COPY voice_assistant ./voice_assistant
COPY models ./models

# Set PYTHONPATH so python -m voice_assistant works correctly
ENV PYTHONPATH=/app

CMD ["python", "-m", "voice_assistant.app"]