"""Shared transcription backend, used by every phaseN-*/, phase6-history/, and webapp/.

Two engines, both fully local:
  - "whisper": OpenAI Whisper (openai-whisper). Small, fast, the default.
  - "voxtral": Mistral Voxtral Mini 3B via transformers. Larger and much
    slower (a 3B model), but also runs entirely on-device.

Engine selection precedence: explicit `engine` argument > TRANSCRIBE_ENGINE
env var > "whisper" (unchanged default behavior for anyone not opting in).
Model selection follows the same pattern via `model_size` (Whisper) /
VOXTRAL_MODEL (Voxtral). This mirrors the provider abstraction in
llm_provider.py so both halves of the pipeline (ASR + summarization) are
swappable the same way.
"""
import os

DEFAULT_MODEL_SIZE = "base"  # Whisper model size
VOXTRAL_MODEL = "mistralai/Voxtral-Mini-3B-2507"

# Generous cap so a several-minute meeting is never truncated; generation
# stops at the model's end-of-transcript token well before this on short
# audio, so a high value only bounds the worst case (it is not a fixed cost).
VOXTRAL_MAX_NEW_TOKENS = 8192

ENGINES = ("whisper", "voxtral")

_whisper_models = {}
_voxtral_models = {}  # model_name -> (model, processor)


def resolve_engine(engine=None):
    engine = engine or os.environ.get("TRANSCRIBE_ENGINE", "whisper")
    if engine not in ENGINES:
        raise ValueError(f"Unknown transcription engine {engine!r}; expected one of {ENGINES}")
    return engine


def transcribe(audio_path, model_size=DEFAULT_MODEL_SIZE, engine=None, language="en"):
    """Transcribe `audio_path` to plain text.

    `model_size` applies only to the Whisper engine (kept as the first
    keyword for backward compatibility with every existing caller). `engine`
    picks the backend; `language` is a hint for Voxtral (Whisper
    auto-detects).
    """
    engine = resolve_engine(engine)
    if engine == "voxtral":
        return _transcribe_voxtral(audio_path, language=language)
    return _transcribe_whisper(audio_path, model_size=model_size)


def _transcribe_whisper(audio_path, model_size=DEFAULT_MODEL_SIZE):
    import whisper

    if model_size not in _whisper_models:
        _whisper_models[model_size] = whisper.load_model(model_size)
    result = _whisper_models[model_size].transcribe(audio_path)
    return result["text"].strip()


def _voxtral_model(model_name):
    if model_name not in _voxtral_models:
        import torch
        from transformers import AutoProcessor, VoxtralForConditionalGeneration

        # bfloat16 needs GPU/MPS kernels that don't exist (or are unreliable)
        # on plain CPU — which is what any container without GPU passthrough
        # gets, since Docker Desktop on Mac never exposes Apple Silicon's MPS
        # to a Linux container. Fall back to float32 there (same rule as
        # llm_provider._local_pipeline). On CPU this is a heavy, slow model.
        has_accel = torch.cuda.is_available() or torch.backends.mps.is_available()
        dtype = torch.bfloat16 if has_accel else torch.float32

        processor = AutoProcessor.from_pretrained(model_name)
        model = VoxtralForConditionalGeneration.from_pretrained(
            model_name, dtype=dtype, device_map="auto",
        )
        _voxtral_models[model_name] = (model, processor)
    return _voxtral_models[model_name]


def _transcribe_voxtral(audio_path, language="en"):
    model_name = os.environ.get("VOXTRAL_MODEL", VOXTRAL_MODEL)
    model, processor = _voxtral_model(model_name)

    # Voxtral's dedicated transcription mode: the processor builds the
    # request (audio + a transcribe instruction), and .batch_decode over the
    # newly generated tokens (past the prompt) yields the transcript.
    inputs = processor.apply_transcription_request(
        language=language, audio=audio_path, model_id=model_name,
    )
    inputs = inputs.to(model.device, dtype=model.dtype)
    outputs = model.generate(**inputs, max_new_tokens=VOXTRAL_MAX_NEW_TOKENS)
    decoded = processor.batch_decode(
        outputs[:, inputs.input_ids.shape[1]:], skip_special_tokens=True,
    )
    return decoded[0].strip()
