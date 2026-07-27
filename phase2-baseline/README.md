# phase2-baseline — Baseline pipeline (Phase 2)

Part of the [voice-to-summary](../README.md) progression. This is the baseline: transcript in, structured summary out, no extra grounding.

A small end-to-end demo pipeline, entirely local (no API keys required):

1. **Generate** a synthetic ~3-minute two-person dialogue as a `.wav` recording, using offline text-to-speech.
2. **Transcribe** the recording with local [Whisper](https://github.com/openai/whisper).
3. **Summarize** the transcript into a structured, anonymized brief (Topic / Key Points / Decisions / Actions) using a local instruction-following LLM — speakers are always referred to as "Person A" / "Person B", never by name.

## Run

From the project root, after completing the shared [Setup](../README.md#setup):

```bash
python phase2-baseline/src/main.py
```

This will create, on first run:
- `output/recording.wav` — the synthetic dialogue
- `output/transcript.txt` — the Whisper transcript
- `output/summary.txt` — the generated summary

On later runs, the existing recording is reused. Pass `--regenerate` to create a fresh one:

```bash
python phase2-baseline/src/main.py --regenerate
```

## Notes

- First run downloads models locally: Whisper `base` (~140MB) and `Qwen/Qwen2.5-1.5B-Instruct` (~3GB). Expect the first run to take a few minutes; subsequent runs are much faster since models are cached.
- The dummy recording uses two distinct macOS system voices if available (e.g. Samantha and Fred), falling back to a single voice with varied speaking rate if only one is installed.
- The transcript (`output/transcript.txt`) is a faithful, unredacted transcription. Only the summary (`output/summary.txt`) anonymizes speakers — names known from the dummy dialogue are redacted before and after the LLM call as a safety net, and the LLM is instructed to only ever refer to speakers as "Person A" / "Person B".
- Each stage (`src/generate_dummy_audio.py`, `src/transcribe.py`, `src/summarize.py`) can also be run standalone for debugging.
- See [phase2-context](../phase2-context/README.md) for what adding meeting context improves on top of this baseline.
