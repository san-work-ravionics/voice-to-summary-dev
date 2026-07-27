# phase4-history — 5 meetings, baseline vs. context-aware summarization over time (Phase 4)

Part of the [voice-to-summary](../README.md) project. phase2-context already showed that giving the summarizer *static* project background produces a sharper single-meeting summary. This asks a harder question: across a **series** of meetings, does giving the summarizer a **running history of what happened in prior meetings** produce a better summary than treating each meeting in isolation?

## The story

Five weekly Monday status syncs about the same Mobile App Redesign project (same premise as phase2-baseline through phase3-assistant), in the weeks leading up to a stakeholder review. Unlike those scenarios' single snapshot, this is a real arc — each week's dialogue references earlier weeks by name:

| Week | Payments sandbox | Dark mode | Legal/privacy | Analytics |
|---|---|---|---|---|
| 1 | Flagged as "a little flaky" | Not started | Kickoff requested | Scoping requested |
| 2 | Worse — blocking QA | Picked up as bonus | Review started | Chased again, no answer |
| 3 | Still unresolved (3rd week running) | Shipped | Still reviewing | Extra engineer requested |
| 4 | Vendor fixes it, QA passes | (done) | Approved | Engineer wired it up, validating |
| 5 | Fully resolved, retro'd | (done) | (done) | Validated |

Budget/cost impact is never discussed on any of the 5 calls — called out explicitly in week 5, echoing the same deliberate checklist gap from [phase3-checklist](../phase3-checklist/README.md)/[phase3-assistant](../phase3-assistant/README.md).

Each meeting also opens with a few lines of clearly non-project small talk — distinct per week (weather, a TV series, a game, coffee, pre-review nerves), using words chosen not to collide with any real project vocabulary elsewhere in these scripts. This tests something separate from context: whether the summarizer reliably keeps small talk out of Topic/Key Points/Decisions/Actions. It does, consistently, across all 5 weeks and both summarizer variants — see `eval/story_probes.py`'s noise-leakage check.

## Two summarizers per meeting

- **`summarize_baseline`** — the current transcript only, no memory of prior meetings. This is what every meeting would get if summarized in total isolation.
- **`summarize_with_context`** — the project's static background (like phase2-context) **plus a running history** built from the Decisions + Actions of every previous meeting's own context-aware summary. Meeting 4's context literally depends on what meeting 1-3 actually produced, not a hand-written script — the same way a person catching up from real meeting notes would.

The system prompt is explicit that history is for *interpreting* the current transcript (recognizing a callback as a continuation of a known issue), never a source of facts to state as having happened in the current meeting.

## Run

```bash
python phase4-history/src/main.py
```

Writes `output/meeting-{1..5}/{recording.wav, transcript.txt, summary_baseline.txt, summary_with_context.txt}`. Pass `--regenerate` to re-synthesize all 5 recordings (this also re-transcribes — a regenerated recording invalidates the old transcript, so `main.py` clears both together).

```bash
python eval/story_judge.py     # holistic faithfulness/completeness/conciseness/continuity scores
python eval/story_probes.py    # noise-leakage check + the deterministic/probe checks below
```

## Where to look for the difference

Two real, verified findings — one for context, one against it, found by manually reading the actual generated text (not from any automated score):

- **Week 3: context wins.** Baseline conflates two unrelated workstreams — it writes things like "Legal review for dark mode needs attention," mixing up dark mode (a design workstream, already shipped) with the separate legal/privacy review. The context-aware summary keeps them correctly distinct.
- **Week 5: context loses.** The context-aware summary lists Week 4's already-completed actions ("finish validating analytics by Friday", "start preparing the stakeholder deck") as if still pending in Week 5 — stale history leaking into current-meeting content, exactly what the system prompt was written to prevent.

Neither finding showed up in the holistic 1-5 "continuity" score in `eval/story_judge.py` — nor in a targeted LLM-judge yes/no probe built specifically to catch each one; both scored a pass. Only a deterministic check (keyword co-occurrence for the conflation, word-overlap against the accumulated history for the stale actions — see `eval/story_probes.py`) catches them reliably, reproduced independently across two separate regenerations. See the Story page in `webapp/` for the full evidence, side by side.
