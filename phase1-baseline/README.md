# phase1-baseline — Baseline pipeline (Phase 1)

Part of the [voice-to-summary](../README.md) progression. This is the baseline: transcript in, structured summary out, no extra grounding.

A small end-to-end demo pipeline, entirely local (no API keys required):

1. **Transcribe** the shared kickoff recording (`audio-generation/output/01-kickoff/recording.wav` — see [`audio-generation/README.md`](../audio-generation/README.md)) with local [Whisper](https://github.com/openai/whisper).
2. **Summarize** the transcript into a structured, anonymized brief (Topic / Key Points / Decisions / Actions) using a local instruction-following LLM — speakers are always referred to as "Person A" / "Person B", never by name.

## Run

From the project root, after completing the shared [Setup](../README.md#setup) and generating the input recordings (`python audio-generation/src/main.py`):

```bash
python phase1-baseline/src/main.py
```

This will create:
- `output/transcript.txt` — the Whisper transcript
- `output/summary.txt` — the generated summary

`--regenerate` is accepted for interface parity with other phases but is a no-op here — the input recording lives in `audio-generation/output/01-kickoff/`, shared across Phases 1-3 and 5, not something this phase generates itself.

## Notes

- First run downloads models locally: Whisper `base` (~140MB) and `Qwen/Qwen2.5-1.5B-Instruct` (~3GB). Expect the first run to take a few minutes; subsequent runs are much faster since models are cached.
- The transcript (`output/transcript.txt`) is a faithful, unredacted transcription. Only the summary (`output/summary.txt`) anonymizes speakers — names known from the source dialogue (Jordan/Priya, per `audio-generation/src/dialogues.py`) are redacted before and after the LLM call as a safety net, and the LLM is instructed to only ever refer to speakers as "Person A" / "Person B".
- Each stage (`src/transcribe.py`, `src/summarize.py`) can also be run standalone for debugging.
- See [phase3-context](../phase3-context/README.md) for what adding meeting context improves on top of this baseline.
