# syntax=docker/dockerfile:1
FROM python:3.9-slim

# ffmpeg: required by pydub/whisper to decode audio.
# espeak-ng: pyttsx3's Linux TTS backend (it uses nsss on macOS, sapi5 on
# Windows) — needed only so the webapp's "Regenerate recording" toggle can
# re-synthesize the scripted demo dialogue inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install torch from the CPU-only wheel index first. The default PyPI build
# bundles multi-GB CUDA runtime libraries that are dead weight here — Docker
# Desktop (Mac/Windows) never passes GPU/MPS through to a Linux container,
# so CPU is what this image actually runs on regardless of host hardware.
#
# The pip cache is a BuildKit cache mount, not a layer: it survives even
# when requirements.txt changes and invalidates this RUN (e.g. adding
# faiss-cpu/sentence-transformers), so only new/changed packages hit the
# network on rebuild instead of every wheel (torch et al) downloading again.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch==2.8.0 --extra-index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

RUN python -c "import whisper; whisper.load_model('base')"

COPY . .

# Model caches (Whisper + Hugging Face) live under /cache so a mounted
# volume survives image rebuilds/restarts instead of re-downloading on every
# start — more if --provider mistral (local 7B) or TRANSCRIBE_ENGINE=voxtral
# (Voxtral-Mini-3B, ~9GB) is used.
ENV XDG_CACHE_HOME=/cache \
    HF_HOME=/cache/huggingface \
    PYTHONUNBUFFERED=1

EXPOSE 8743

CMD ["python", "webapp/server.py"]
