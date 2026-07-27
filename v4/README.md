# v4 — AI Assistant as a third actor in the recording

Part of the [voice-to-summary](../README.md) progression. Unlike v1-v3 (where only the summarization step changed), the **recording itself** changes here: a third voice, "Assistant," joins the two-person meeting.

## What's new

`src/generate_dummy_audio.py` has a new `DIALOGUE` with three speaker tags (`A`, `B`, `ASSISTANT`), synthesized in three distinct system voices (Assistant gets a different accent from the two participants so it's audibly distinguishable). The script arc:

1. Person A announces the assistant's role up front: *"Assistant will be taking notes for us today and will summarize the meeting once we're done."*
2. The assistant briefly acknowledges.
3. The meeting proceeds through the same content as v1-v3 (onboarding, payments, dark mode, legal/analytics asks, next sync) — after each major point, A or B calls out to the assistant ("Assistant, can you make a note of that?") and the assistant confirms/paraphrases (3 note-taking call-outs).
4. Near the end, the assistant is asked whether the checklist was fully covered, and correctly flags the one gap: budget/cost impact.
5. The assistant is asked to summarize, and gives a short spoken closing summary.

No personal names are used — "Assistant" is a role label, not personal data, consistent with the anonymization requirement from v1.

`src/summarize.py` reuses v3's context + keyword-based checklist pipeline, with one added instruction: the assistant's own spoken remarks are not meeting content and must never generate a Key Point, Decision, or Action — only what Person A / Person B actually said counts.

`output/summary.txt` is still produced independently by the offline transcribe→summarize pipeline (not copied from the assistant's spoken words) — running it should closely reproduce what the in-recording assistant said, closing the loop between the "live" assistant and the batch pipeline.

## Run

```bash
python v4/src/main.py
```

Writes `output/recording.wav` (3 voices), `output/transcript.txt`, and `output/summary.txt` (5 sections, same shape as v3). Pass `--regenerate` for a fresh recording.

## Notes

- See [v1](../v1/README.md) for setup/model notes — unchanged here.
- See [v3](../v3/README.md) for why checklist coverage is a deterministic keyword check rather than another LLM call.
