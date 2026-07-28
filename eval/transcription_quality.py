import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

import whisper
from pydub import AudioSegment
from pydub.generators import WhiteNoise

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "transcription_quality.json")

WHISPER_MODEL_SIZE = "base"

# phase1-baseline/phase2-checklist/phase3-context/phase5-office-agent all
# transcribe the exact same shared recording (audio-generation/output/01-kickoff/) —
# one entry for it, rather than four near-duplicate entries, since it's
# genuinely one recording now, not four independent copies. phase4-assistant
# still synthesizes its own (3-voice) recording, so it keeps a normal entry.
SHARED_KICKOFF_RECORDING = "audio-generation/output/01-kickoff/recording.wav"
VERSION_SCENARIOS = [
    {
        "id": "audio-generation-01-kickoff",
        "recording": SHARED_KICKOFF_RECORDING,
        "transcript": "phase1-baseline/output/transcript.txt",
        "meeting_slug": "01-kickoff",
    },
    {
        "id": "phase4-assistant",
        "recording": "phase4-assistant/output/recording.wav",
        "transcript": "phase4-assistant/output/transcript.txt",
        "dialogue_module": "phase4-assistant/src/generate_dummy_audio.py",
    },
]

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


def _reference_for_version(scenario):
    mod = _load_module(scenario["dialogue_module"], f"_ref_{scenario['id']}")
    parts = []
    intro = getattr(mod, "INTRO_TEXT", None)
    if intro:
        parts.append(intro)
    parts.extend(line for _, line in mod.DIALOGUE)
    return " ".join(parts)


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


def _transcribe(model, audio_path):
    result = model.transcribe(audio_path)
    return result["text"].strip()


def evaluate_recording(model, recording_path, reference, clean_transcript):
    tiers = {"clean": word_error_rate(reference, clean_transcript)}

    original_audio = AudioSegment.from_file(recording_path)
    for tier_name, transform in NOISE_TIERS.items():
        tmp_path = tempfile.mkstemp(suffix=".wav")[1]
        try:
            noisy_audio = transform(original_audio)
            noisy_audio.export(tmp_path, format="wav")
            text = _transcribe(model, tmp_path)
            tiers[tier_name] = word_error_rate(reference, text)
        finally:
            os.remove(tmp_path)

    return tiers


def main():
    print("Loading Whisper model...")
    model = whisper.load_model(WHISPER_MODEL_SIZE)

    scenarios_out = []
    dialogues_module = _load_module("audio-generation/src/dialogues.py", "_ref_audio_generation_dialogues")

    for scenario in VERSION_SCENARIOS:
        print(f"Evaluating {scenario['id']}...")
        if "meeting_slug" in scenario:
            reference = _reference_for_meeting(scenario["meeting_slug"], dialogues_module)
        else:
            reference = _reference_for_version(scenario)
        with open(os.path.join(PROJECT_ROOT, scenario["transcript"])) as f:
            clean_transcript = f.read()
        tiers = evaluate_recording(
            model,
            os.path.join(PROJECT_ROOT, scenario["recording"]),
            reference,
            clean_transcript,
        )
        scenarios_out.append({"id": scenario["id"], "tiers": tiers})

    for meeting in dialogues_module.MEETINGS:
        slug = meeting["slug"]
        scenario_id = f"phase6-history-{slug}"
        print(f"Evaluating {scenario_id}...")
        reference = _reference_for_meeting(slug, dialogues_module)
        meeting_dir = os.path.join(PROJECT_ROOT, "phase6-history", "output", slug)
        with open(os.path.join(meeting_dir, "transcript.txt")) as f:
            clean_transcript = f.read()
        tiers = evaluate_recording(
            model,
            os.path.join(PROJECT_ROOT, "audio-generation", "output", slug, "recording.wav"),
            reference,
            clean_transcript,
        )
        scenarios_out.append({"id": scenario_id, "tiers": tiers})

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "whisper_model": WHISPER_MODEL_SIZE,
        "wer_benchmark_note": WER_BENCHMARK_NOTE,
        "noise_tiers_note": NOISE_TIERS_NOTE,
        "diarization_note": DIARIZATION_NOTE,
        "scenarios": scenarios_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
