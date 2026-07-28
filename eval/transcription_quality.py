import importlib.util
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone

import whisper
from pydub import AudioSegment
from pydub.generators import WhiteNoise

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "transcription_quality.json")

WHISPER_MODEL_SIZE = "base"

# The shared input is ONE project's 15 meetings, in audio-generation/output/
# (01-kickoff .. 15-launch-retro). Transcription is measured per recording —
# there are exactly 15 rows, named by meeting slug. No phase names appear
# here: "Phase N" is a separate axis (pipeline capability) that all draw from
# these same 15 recordings; it is not a property of a recording. Phase 4's own
# 3-voice re-recording of the kickoff is a Phase-4 concern, not part of this
# transcription dataset, so it is intentionally not scored here.

DIARIZATION_NOTE = (
    "Not implemented / not measurable here. whisper.load_model(...).transcribe() "
    "as used throughout this project returns a single undifferentiated text "
    "stream with no speaker labels at all — the 'Person A' / 'Person B' "
    "(and 'Assistant' in phase4-assistant) attribution seen in every summary is reconstructed "
    "entirely by the downstream LLM from conversational context, not from the "
    "ASR step. There is no diarization output to score for accuracy. A real "
    "diarization benchmark would need a diarization-capable pipeline (e.g. "
    "pyannote.audio or WhisperX), which this project does not include. The "
    "closest available proxy is downstream: whether the summarizer's own "
    "speaker attribution stays internally consistent (only 'Person A:' / "
    "'Person B:' ever prefix an Action) — see the Actions-prefix compliance "
    "check in eval/judge.py and eval/story_judge.py."
)

WER_BENCHMARK_NOTE = (
    "A commonly cited target is under 5-8% WER for domain-specific audio. "
    "Note: this project's ground truth is the exact TTS script text, so any "
    "gap here is genuine ASR error or transcript-formatting divergence (e.g. "
    "Whisper renders spoken numbers as digits — '88%' vs the script's "
    "'eighty-eight percent' — which counts as a substitution under strict "
    "WER even though no information was lost); see individual diffs."
)


def _load_module(path, unique_name):
    spec = importlib.util.spec_from_file_location(unique_name, os.path.join(PROJECT_ROOT, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reference_for_meeting(slug, dialogues_module):
    meeting = next(m for m in dialogues_module.MEETINGS if m["slug"] == slug)
    parts = [meeting["intro"]] + [line for _, line in meeting["dialogue"]]
    return " ".join(parts)


def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_error_rate(reference, hypothesis):
    ref_words = normalize(reference).split()
    hyp_words = normalize(hypothesis).split()
    n, m = len(ref_words), len(hyp_words)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])

    i, j = n, m
    subs = dels = ins = 0
    diffs = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_words[i - 1] == hyp_words[j - 1]:
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            subs += 1
            diffs.append({"op": "sub", "ref": ref_words[i - 1], "hyp": hyp_words[j - 1]})
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            dels += 1
            diffs.append({"op": "del", "ref": ref_words[i - 1], "hyp": None})
            i -= 1
        else:
            ins += 1
            diffs.append({"op": "ins", "ref": None, "hyp": hyp_words[j - 1]})
            j -= 1
    diffs.reverse()

    n_words = len(ref_words)
    wer = (subs + dels + ins) / n_words if n_words else 0.0
    return {
        "wer": wer,
        "substitutions": subs,
        "deletions": dels,
        "insertions": ins,
        "reference_word_count": n_words,
        "hypothesis_word_count": m,
        "diffs": diffs,
    }


# --- noise robustness: pydub (already a project dependency) synthesizes two
# degraded variants of each recording so WER-vs-noise-severity is an actual
# measured trend, not a documented gap like diarization/accent variety are.

def _add_noise(audio, snr_db):
    noise = WhiteNoise().to_audio_segment(duration=len(audio))
    target_noise_dbfs = audio.dBFS - snr_db
    gain = target_noise_dbfs - noise.dBFS
    noise = noise.apply_gain(gain)
    return audio.overlay(noise)


NOISE_TIERS = {
    "light_noise": lambda audio: _add_noise(audio, snr_db=20),
    "heavy_noise": lambda audio: _add_noise(audio, snr_db=8).low_pass_filter(3000),
}

NOISE_TIERS_NOTE = (
    "light_noise: white noise mixed in at ~20dB below the speech level "
    "(mild background hiss). heavy_noise: white noise at ~8dB below speech "
    "(much more prominent) plus a 3kHz low-pass filter, simulating a "
    "muffled/low-quality microphone. Real accent variety is not tested — "
    "all recordings use the same one or two macOS system TTS voices."
)

TIMING_NOTE = (
    "seconds = wall-clock time of the Whisper transcribe() call for that "
    "tier; rtf (real-time factor) = seconds / audio length, so 0.05 means "
    "the recording transcribed 20x faster than real time. These times are "
    "specific to the machine that generated this file (Whisper '{model}' on "
    "CPU) and will differ on other hardware. Note: the 'clean' tier is now "
    "transcribed fresh here (timed) rather than read from each phase's "
    "stored transcript, so its WER and its time describe the same run — "
    "clean WER may therefore differ very slightly from a phase's own stored "
    "transcript, since Whisper decoding is not bit-for-bit reproducible."
)


def _transcribe(model, audio_path):
    """Transcribe and return (text, wall_clock_seconds)."""
    t0 = time.perf_counter()
    result = model.transcribe(audio_path)
    elapsed = time.perf_counter() - t0
    return result["text"].strip(), elapsed


def _timed_tier(reference, text, seconds, audio_seconds):
    tier = word_error_rate(reference, text)
    tier["seconds"] = round(seconds, 2)
    tier["rtf"] = round(seconds / audio_seconds, 3) if audio_seconds else None
    return tier


def evaluate_recording(model, recording_path, reference):
    original_audio = AudioSegment.from_file(recording_path)
    audio_seconds = round(len(original_audio) / 1000.0, 1)

    # clean: transcribe the recording as-is (timed) so this tier's WER and
    # its transcription time both describe one real operation measured here.
    clean_text, clean_secs = _transcribe(model, recording_path)
    tiers = {"clean": _timed_tier(reference, clean_text, clean_secs, audio_seconds)}

    for tier_name, transform in NOISE_TIERS.items():
        tmp_path = tempfile.mkstemp(suffix=".wav")[1]
        try:
            noisy_audio = transform(original_audio)
            noisy_audio.export(tmp_path, format="wav")
            text, secs = _transcribe(model, tmp_path)
            tiers[tier_name] = _timed_tier(reference, text, secs, audio_seconds)
        finally:
            os.remove(tmp_path)

    return tiers, audio_seconds


def main():
    print("Loading Whisper model...")
    model = whisper.load_model(WHISPER_MODEL_SIZE)

    scenarios_out = []
    dialogues_module = _load_module("audio-generation/src/dialogues.py", "_ref_audio_generation_dialogues")

    # Exactly the 15 recordings of the shared project dataset, named by
    # meeting slug (01-kickoff .. 15-launch-retro).
    for meeting in dialogues_module.MEETINGS:
        slug = meeting["slug"]
        print(f"Evaluating {slug}...")
        reference = _reference_for_meeting(slug, dialogues_module)
        tiers, audio_seconds = evaluate_recording(
            model,
            os.path.join(PROJECT_ROOT, "audio-generation", "output", slug, "recording.wav"),
            reference,
        )
        scenarios_out.append({"id": slug, "audio_seconds": audio_seconds, "tiers": tiers})

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "whisper_model": WHISPER_MODEL_SIZE,
        "wer_benchmark_note": WER_BENCHMARK_NOTE,
        "noise_tiers_note": NOISE_TIERS_NOTE,
        "timing_note": TIMING_NOTE.format(model=WHISPER_MODEL_SIZE),
        "diarization_note": DIARIZATION_NOTE,
        "scenarios": scenarios_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
