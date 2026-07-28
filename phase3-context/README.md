# phase3-context — Context-aware summarization (Phase 3)

Part of the [voice-to-summary](../README.md) progression. Builds on [phase1-baseline](../phase1-baseline/README.md) by giving the summarizer meeting **context** before it reads the transcript, and produces both a baseline and a context-aware summary so the difference is visible in one run.

Same shared kickoff recording/transcript as phase1-baseline/phase2-checklist — only the summarization step changes.

## What's new

`src/context.py` holds a `MEETING_CONTEXT` block describing things the bare transcript doesn't spell out: the project name, that the two speakers are "Person A" / "Person B", that this is the project kickoff (the first meeting in a roughly five-month timeline), and the five workstreams scoped at kickoff (onboarding, payments, design/dark mode, legal/privacy, analytics).

`src/summarize.py` exposes two functions:
- `summarize_baseline(text)` — same prompt/logic as phase1-baseline.
- `summarize_with_context(text, context)` — same 4-section format, but the system prompt is given `MEETING_CONTEXT` first, with an explicit instruction to use it only for grounding/interpretation, not to invent facts absent from the transcript.

Expect the context-aware summary to be more specific: a sharper Topic line (naming the actual project and occasion instead of a generic "status update"), and less hedging around what "the redesign" or a given workstream refers to. In practice, the context-aware version has also been observed to correctly attribute all of Person A's commitments to Person A, where the baseline (no context) misattributed one to Person B.

## Run

```bash
python phase3-context/src/main.py
```

Writes:
- `output/transcript.txt` — same shared kickoff transcript as phase1-baseline/phase2-checklist
- `output/summary_baseline.txt` — no context, for comparison
- `output/summary_with_context.txt` — the context-aware version

`--regenerate` is a no-op (see phase1-baseline's README) — the shared kickoff recording belongs to `audio-generation/`.

## Notes

- See [phase1-baseline](../phase1-baseline/README.md) for setup/model notes — unchanged here.
- See [phase2-checklist](../phase2-checklist/README.md) for adding a checklist-based coverage check on top of this.
