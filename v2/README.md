# v2 — Context-aware summarization

Part of the [voice-to-summary](../README.md) progression. Builds on [v1](../v1/README.md) by giving the summarizer meeting **context** before it reads the transcript, and produces both a baseline and a context-aware summary so the difference is visible in one run.

Same recording/transcript as v1 (identical `generate_dummy_audio.py` / `transcribe.py`) — only the summarization step changes.

## What's new

`src/context.py` holds a `MEETING_CONTEXT` block describing things the bare transcript doesn't spell out: the project name, that the two speakers are "Person A" / "Person B", the five workstreams in this release (onboarding, payments, design, legal/privacy, analytics), and that this is a pre-review sync ahead of Friday's stakeholder review.

`src/summarize.py` exposes two functions:
- `summarize_baseline(text)` — same prompt/logic as v1.
- `summarize_with_context(text, context)` — same 4-section format, but the system prompt is given `MEETING_CONTEXT` first, with an explicit instruction to use it only for grounding/interpretation, not to invent facts absent from the transcript.

Expect the context-aware summary to be more specific: a sharper Topic line (naming the actual project and occasion instead of a generic "status update"), and less hedging around what "the review" or "the redesign" refer to.

## Run

```bash
python v2/src/main.py
```

Writes, on first run:
- `output/recording.wav`, `output/transcript.txt` — same as v1
- `output/summary_baseline.txt` — no context, for comparison
- `output/summary_with_context.txt` — the context-aware version

Pass `--regenerate` to create a fresh recording.

## Notes

- See [v1](../v1/README.md) for setup/model notes — unchanged here.
- See [v3](../v3/README.md) for adding a checklist-based coverage check on top of this.
