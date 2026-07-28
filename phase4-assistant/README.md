# phase4-assistant — AI Assistant as a third actor in the recording (Phase 4)

Part of the [voice-to-summary](../README.md) progression. Unlike phase1-baseline through phase3-context (which all transcribe the shared `audio-generation/output/01-kickoff/` recording as-is), the **recording itself** changes here: a third voice, "Assistant," joins the kickoff meeting, so this phase synthesizes its own audio.

## What's new

`src/generate_dummy_audio.py` has a `DIALOGUE` with three speaker tags (`A`, `B`, `ASSISTANT`), synthesized in three distinct system voices (Assistant gets a different accent from the two participants so it's audibly distinguishable). Person A/B's lines are copied verbatim from `audio-generation/src/dialogues.py`'s `"01-kickoff"` entry — the same kickoff meeting phase1-baseline/phase2-checklist/phase3-context transcribe — with the assistant's note-taking/checklist/closing-summary lines interleaved:

1. Person A announces the assistant's role up front: *"Assistant will be taking notes for us today and will summarize the meeting once we're done."*
2. The assistant briefly acknowledges.
3. The meeting proceeds through the real kickoff content (goal-setting, the four workstreams, the payments-vendor risk, localization deferred to requirements review) — after each major point, A calls out to the assistant and the assistant confirms/paraphrases.
4. Near the end, the assistant is asked whether the checklist was fully covered, and correctly flags the one gap: budget/cost impact.
5. The assistant is asked to summarize, and gives a short spoken closing summary.

No personal names are used — "Assistant" is a role label, not personal data, consistent with the anonymization requirement from phase1-baseline.

`src/summarize.py` reuses phase2-checklist's context + keyword-based checklist pipeline, with one added instruction: the assistant's own spoken remarks are not meeting content and must never generate a Key Point, Decision, or Action — only what Person A / Person B actually said counts.

`output/summary.txt` is still produced independently by the offline transcribe→summarize pipeline (not copied from the assistant's spoken words) — running it should closely reproduce what the in-recording assistant said, closing the loop between the "live" assistant and the batch pipeline.

## Run

```bash
python phase4-assistant/src/main.py
```

Writes `output/recording.wav` (3 voices), `output/transcript.txt`, and `output/summary.txt` (5 sections, same shape as phase2-checklist). Pass `--regenerate` for a fresh recording — unlike Phases 1-3/5, this phase does synthesize its own audio, since `audio-generation/` has no assistant voice to layer onto.

## Notes

- See [phase1-baseline](../phase1-baseline/README.md) for setup/model notes — unchanged here.
- See [phase2-checklist](../phase2-checklist/README.md) for why checklist coverage is a deterministic keyword check rather than another LLM call.
