# Roadmap alignment — Phases 1-4

Maps the built pipeline (`phase2-baseline`, `phase2-context`, `phase3-checklist`, `phase3-assistant`, `phase4-history`, `eval/`) to the 6-phase product roadmap, scoped here to **Phases 1-4** (the phases with code and measured results today). Phases 5 (On-Device / Office Tool Processing) and 6 (Voice interface for querying) are future work and out of scope for this doc.

Live metrics for these phases are also visualized in the webapp's **Roadmap** page (`python webapp/server.py`, then the "Roadmap" nav item) — this doc is the narrative version of the same mapping.

## Phase 1 — Core Voice-to-Transcript

**Goal:** convert raw spoken audio into a clean transcript. **Built by:** the shared Whisper step (`transcription.py`), used identically by every scenario folder.

| Metric (roadmap) | Status | Source |
|---|---|---|
| Word Error Rate | **Measured.** Clean + two noise tiers (`light_noise` ~20dB below speech, `heavy_noise` ~8dB below speech + 3kHz low-pass) across all 9 recordings (phase2-baseline, phase2-context, phase3-checklist, phase3-assistant + 5 phase4-history weeks). | `eval/transcription_quality.py` → `eval/output/transcription_quality.json` |
| Real-Time Factor | **Not measured.** No wall-clock timing is captured around the Whisper call anywhere in the pipeline today. | Gap — would need timing instrumentation added to `transcription.py` |

Ground truth is the exact TTS script text, so any WER here is genuine ASR error or transcript-formatting divergence (e.g. Whisper renders "eighty-eight percent" as "88%", which scores as a substitution under strict WER despite no information loss). Speaker diarization and accent resilience are explicitly not implemented/tested — see `eval/README.md`.

## Phase 2 — Transcript Summary

**Goal:** a meaningful paragraph + bullet summary. **Built by:** phase2-baseline (`summarize_baseline` — zero-shot, transcript only) vs phase2-context (`summarize_with_context` — meeting background injected into the prompt, closer to a few-shot/grounded prompt than the bare zero-shot).

| Metric (roadmap) | Status | Source |
|---|---|---|
| Factuality (% derived from content vs. fabricated) | **Measured as a proxy:** LLM-judge "faithfulness" score (1-5) plus an explicit unsupported-claims list per summary. | `eval/judge.py` → `eval/output/results.json`, `layer2.faithfulness` / `layer2.unsupported_claims` |
| Key Point Recall | **Measured as a proxy, not a literal count:** LLM-judge "completeness" score (1-5) — there's no separate ground-truth key-point list to compute a numeric recall against; the Actions-specific recall/precision below is the one place a real ground-truth comparison exists. | `eval/judge.py` → `results.json`, `layer2.completeness` |
| Comparison: no-prompt vs zero-shot vs few-shot | **Partially covered.** phase2-baseline (zero-shot) vs phase2-context (context-grounded) is compared directly, both scored by the same judge. There's no "no-prompt" baseline in this pipeline — every variant uses a structured system prompt by design. | `results.json` — compare `phase2-baseline`/baseline vs `phase2-context`/with_context rows |

Known limitation carried over from `eval/README.md`: most local-model summaries are judged by that same local model (self-preference bias). `eval/rejudge.py --judge-provider claude` re-scores everything under one neutral judge.

## Phase 3 — Actionable Checklists & Task Extraction

**Goal:** structured, schema-conformant capture of tasks/data. **Built by:** phase3-checklist's `## Checklist Coverage` section (deterministic keyword match, not another LLM call — see `phase3-checklist/README.md` for why three different LLM framings were tried and rejected), extended in phase3-assistant with a third recorded voice, and the Actions-bullet schema (`Person A:` / `Person B:` prefix) enforced since phase2-baseline.

| Metric (roadmap) | Status | Source |
|---|---|---|
| Adherence to schema | **Measured.** Markdown section presence + heading-level compliance, and Actions-bullet prefix compliance. | `eval/judge.py` layer 1 → `results.json`, `layer1.schema` / `layer1.actions` |
| % of correctly mapped data fields | **Measured two ways:** (1) checklist tp/fp/fn/tn → precision/recall/accuracy against a hand-labeled ground truth (phase3-checklist/phase3-assistant only). (2) Actions-bullet recall/precision against scripted ground-truth commitments (all scenarios). | `results.json`, `layer1.checklist` (precision/recall/accuracy) · `eval/extraction_efficiency.py` → `eval/output/extraction_efficiency.json` |

The checklist ground truth deliberately omits one topic (budget/cost impact) from the dummy dialogue so the "Not covered" path is demonstrably exercised, not just theoretical.

## Phase 4 — Contextual & Domain-Specific Summaries

**Goal:** meeting-type-aware summaries using history/RAG over past notes. **Built by:** `phase4-history/` — 5 weekly syncs about the same project, comparing a summarizer with no memory of prior meetings against one given a running history built from each prior week's own generated summary (Decisions + Actions), not a hand-written script.

| Metric (roadmap) | Status | Source |
|---|---|---|
| Comparison with Phase 2 baseline; was the improvement significant? | **Measured, with a real (non-obvious) answer: no on holistic scores, yes on targeted checks.** The 1-5 judge scores are nearly identical between baseline and context+history across all 5 weeks. Two deterministic checks (not caught by the holistic score or a purpose-built LLM probe) show a real difference: baseline conflates two workstreams in Week 3 that context keeps separate; context leaks Week 4's completed actions into Week 5 as still-pending, which baseline (no history to leak) doesn't do. | `eval/story_judge.py` → `eval/output/story_results.json` · `eval/story_probes.py` → `eval/output/story_probes.json` |
| RAG Faithfulness (accurate capture of past notes without hallucinating) | **Measured as a proxy:** the same faithfulness score as Phase 2, plus a "continuity" judge score specific to the story, plus the deterministic stale-action-carryover check above (word-overlap against accumulated history) — the more trustworthy of the two per `phase4-history/README.md`, since the LLM continuity probe missed the same case the deterministic check caught. | `story_results.json` (`layer2.faithfulness`, `continuity`) · `story_probes.py`'s deterministic checks |

Also verified: unrelated small talk at the start of each meeting (weather, a show, a game, coffee, traffic) never leaks into Topic/Key Points/Decisions/Actions, across all 5 weeks and both summarizer variants — `eval/story_probes.py`'s noise-leakage check.

## What Phase 4 does *not* cover yet

The roadmap's Phase 4 also calls for **meeting-type-specific** templates (project status vs. blocker discussion, etc.) and **domain terminology handling**. `phase4-history/` only demonstrates the history/RAG half of Phase 4 — every meeting is still the same "project status sync" type with the same `MEETING_CONTEXT` shape from phase2-context. Meeting-type-specific prompt templates aren't built.

## Gaps to close before calling Phases 1-4 "done"

1. Real-Time Factor isn't measured (Phase 1).
2. Key Point Recall has no ground-truth-backed numeric metric, only a judge's subjective completeness score (Phase 2).
3. Meeting-type-specific templates and domain terminology handling aren't built (Phase 4).
