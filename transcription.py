"""Shared Whisper transcription, used by every phaseN-*/, phase6-history/, and webapp/."""

DEFAULT_MODEL_SIZE = "base"

_whisper_models = {}


def transcribe(audio_path, model_size=DEFAULT_MODEL_SIZE):
    import whisper

    if model_size not in _whisper_models:
        _whisper_models[model_size] = whisper.load_model(model_size)
    result = _whisper_models[model_size].transcribe(audio_path)
    return result["text"].strip()
