# Roadmap alignment — Phases 1-8

Maps the built pipeline (`phase1-baseline`, `phase2-checklist`, `phase3-context`, `phase4-assistant`, `phase5-office-agent`, `phase6-history`, `phase7-reference-rag`, `phase8-voice-query`, `eval/`) to this project's 8-phase build-out — each phase adds one technique on top of the last. `audio-generation/` is the shared raw-input folder every phase transcribes from (see its README).

Live metrics for these phases are also visualized in the webapp's **Roadmap** page (`python webapp/server.py`, then the "Roadmap" nav item) — this doc is the narrative version of the same mapping.

## Voice-to-Transcript (foundation, not a numbered phase)

**Goal:** convert raw spoken audio into a clean transcript. **Built by:** the shared Whisper step (`transcription.py`), used identically by every scenario folder.

| Metric | Status | Source |
|---|---|---|
| Word Error Rate | **Measured.** Clean + two noise tiers (`light_noise` ~20dB below speech, `heavy_noise` ~8dB below speech + 3kHz low-pass) across the shared kickoff recording, phase4-assistant's own 3-voice recording, and all 15 `phase6-history` meetings. | `eval/transcription_quality.py` → `eval/output/transcription_quality.json` |
| Real-Time Factor | **Not measured.** No wall-clock timing is captured around the Whisper call anywhere in the pipeline today. | Gap — would need timing instrumentation added to `transcription.py` |

Ground truth is the exact TTS script text, so any WER here is genuine ASR error or transcript-formatting divergence (e.g. Whisper renders "kickoff" as "Kikov" or misreads "sprints" as "sinks" — real ASR noise, not information loss for a human reader). Speaker diarization and accent resilience are explicitly not implemented/tested — see `eval/README.md`.

## Phase 1 — Basic Summary

**Goal:** a meaningful paragraph + bullet summary, no extra grounding. **Built by:** [`phase1-baseline/`](phase1-baseline/README.md) — `summarize()`, zero-shot against the transcript of `audio-generation/output/01-kickoff/`.

| Metric | Status | Source |
|---|---|---|
| Factuality (% derived from content vs. fabricated) | **Measured as a proxy:** LLM-judge "faithfulness" score (1-5) plus an explicit unsupported-claims list. | `eval/judge.py` → `eval/output/results.json`, scenario `phase1-baseline`, `layer2.faithfulness` / `layer2.unsupported_claims` |
| Key Point Recall | **Measured as a proxy, not a literal count:** LLM-judge "completeness" score (1-5) — there's no separate ground-truth key-point list to compute a numeric recall against. | `results.json`, `layer2.completeness` |

Known limitation carried over from `eval/README.md`: most local-model summaries are judged by that same local model (self-preference bias). `eval/rejudge.py --judge-provider claude` re-scores everything under one neutral judge.

## Phase 2 — Checklist Coverage & Task Extraction

**Goal:** structured, schema-conformant capture of tasks/topics. **Built by:** [`phase2-checklist/`](phase2-checklist/README.md)'s `## Checklist Coverage` section (deterministic keyword match, not another LLM call — see its README for why three different LLM framings were tried and rejected), and the Actions-bullet schema (`Person A:` / `Person B:` prefix) enforced since Phase 1.

| Metric | Status | Source |
|---|---|---|
| Adherence to schema | **Measured.** Markdown section presence + heading-level compliance, and Actions-bullet prefix compliance. | `eval/judge.py` layer 1 → `results.json`, `layer1.schema` / `layer1.actions` |
| % of correctly mapped data fields | **Measured two ways:** (1) checklist tp/fp/fn/tn → precision/recall/accuracy against a hand-labeled ground truth. (2) Actions-bullet recall/precision against scripted ground-truth commitments (auto-derived from `audio-generation/src/dialogues.py`, not hand-labeled). | `results.json`, `layer1.checklist` · `eval/extraction_efficiency.py` → `eval/output/extraction_efficiency.json` |

The checklist ground truth deliberately omits one topic (budget/cost impact) from the kickoff dialogue so the "Not covered" path is demonstrably exercised, not just theoretical.

## Phase 3 — Context-Aware Summarization

**Goal:** does giving the summarizer meeting background sharpen the summary? **Built by:** [`phase3-context/`](phase3-context/README.md) — `summarize_baseline` (zero-shot) vs `summarize_with_context` (project background injected into the prompt), same kickoff transcript, same run.

| Metric | Status | Source |
|---|---|---|
| Comparison: zero-shot vs. context-grounded | **Measured directly**, both scored by the same judge. | `results.json` — compare `phase3-context`/`baseline` vs `phase3-context`/`with_context` rows |
| Factuality / Key Point Recall | Same proxy metrics as Phase 1, for both variants. | `results.json`, `layer2.faithfulness` / `layer2.completeness` |

## Phase 4 — AI Assistant as Third Actor

**Goal:** a third voice (an AI meeting assistant) joins the recording itself — does the summarizer correctly exclude the assistant's own remarks from actual meeting content? **Built by:** [`phase4-assistant/`](phase4-assistant/README.md) — same checklist + context-aware summarizer as Phases 2-3, applied to a re-synthesized version of the kickoff dialogue with assistant note-taking/closing-summary lines interleaved.

| Metric | Status | Source |
|---|---|---|
| Adherence to schema + checklist accuracy | **Measured**, same layer-1/checklist checks as Phase 2. | `results.json`, scenario `phase4-assistant` |
| Assistant-content exclusion | **Measured**: Actions-bullet prefix compliance only allows `Person A:`/`Person B:`, never an assistant attribution; action-item extraction ground truth still only counts Person A/B commitments. | `results.json`, `layer1.actions` · `extraction_efficiency.json`, scenario `phase4-assistant` |

## Phase 5 — On-Device / Office Tool Processing

**Goal:** use Copilot Enterprise features to build agents and validate performance in low-network areas. **Built by:** [`phase5-office-agent/`](phase5-office-agent/README.md) — this repo has no Microsoft 365 Copilot Enterprise license or Copilot Studio/Graph API access, so **a Claude tool-use agent substitutes for the Copilot agent** ([`office_agent.py`](office_agent.py)), per explicit direction. See the scenario's README for exactly what that substitution does and doesn't validate — treat every number below as "what an agentic, tool-using approach looks like," not "what Copilot Enterprise looks like."

The agent acts on real Office documents via tool calls (`write_minutes_docx` via `python-docx`, `write_action_tracker_xlsx` via `openpyxl`) rather than only replying with text, then gives a final Markdown brief scored identically to Phases 1-4. Three simulated network conditions (`good`/`degraded`/`offline` — see `phase5-office-agent/src/network_sim.py`; there's no real network-shaping tool in this repo, so this is documented simulation, not a real network test) stand in for "low network areas," with `offline` falling back to the local on-device model.

| Metric | Status | Source |
|---|---|---|
| Summary metrics, comparison across approaches | **Measured** — the agent's final brief (`agent_good`) vs. the single-shot baseline, same judge (faithfulness/completeness/conciseness) as Phases 1-4. | `eval/output/run_history.jsonl`, `scenario_id="phase5-office-agent"`, `variant` = `"baseline"` vs `"agent_good"` |
| Was the summary improvement significant? | Compare the two variants above for the same run — see `phase5-office-agent/README.md`'s results table once run against a live API key. | Same as above |
| Ease of integration | **Qualitative**, documented in the scenario README: the agent is a bounded tool-use loop over two well-established libraries, versus what a real Copilot Enterprise integration would additionally require (Azure AD app registration, Graph API permissions, Copilot Studio configuration). | `phase5-office-agent/README.md` |
| Performance in low-network areas | **Measured (simulated).** `agent_degraded` vs. `agent_good` elapsed time; whether `agent_offline` falls back cleanly to the local model with a valid brief still produced. | `run_history.jsonl` `variant="agent_degraded"`/`"agent_offline"` · `<condition>/run_meta.json` |

Claude-only limitation, reported as a real finding rather than hidden: `llm_provider.py`'s local/Mistral path has no tool-calling support, so agentic Office-document actions require a cloud model here — on-device models in this project remain comprehension-only (single-shot summarization), not agentic.

## Phase 6 — RAG over Meeting History

**Goal:** meeting-history-aware summaries using RAG over past notes, across a realistic multi-meeting project lifecycle. **Built by:** [`phase6-history/`](phase6-history/README.md) — all 15 `audio-generation/` meetings (kickoff through launch retro), comparing a summarizer with no memory of prior meetings against one given a running history built from each prior meeting's own generated summary (Decisions + Actions), not a hand-written script.

| Metric | Status | Source |
|---|---|---|
| Comparison with baseline; was the improvement significant? | **Measured, with a real answer: a modest edge to context on holistic scores, a clearer and more decisive edge on targeted checks.** Average faithfulness 4.0/5 (context) vs. 3.9/5 (baseline), completeness 3.5/5 vs. 3.3/5; continuity is identical (4.6/5 both — doesn't distinguish them). Deterministic checks are more decisive: baseline leaks small talk into the summary in 3 of 15 meetings, context-aware in 0 of 15 (clean win for context); context-aware also correctly conveys the payments vendor issue is fully resolved by meeting 9, where baseline's phrasing is ambiguous. But context-aware carries stale, already-resolved actions forward as still-pending in 2 of 15 meetings (04-sprint-status-1, 12-uat-kickoff) — a real cost, and the one place baseline (no history to leak) never fails this way. | `eval/story_judge.py` → `eval/output/story_results.json` · `eval/story_probes.py` → `eval/output/story_probes.json` |
| RAG Faithfulness (accurate capture of past notes without hallucinating) | **Measured as a proxy:** the same faithfulness score as Phase 1, plus a "continuity" judge score specific to the story, plus the deterministic stale-action-carryover check above (word-overlap against accumulated history) — the more trustworthy of the two per `phase6-history/README.md`, since the holistic continuity score doesn't catch either finding above. | `story_results.json` (`layer2.faithfulness`, `continuity`) · `story_probes.py`'s deterministic checks |

Also checked but not a clean generalization: a deterministic "dark mode / legal-privacy conflation" check (ported from an earlier 5-meeting version of this story) flags 2 of 15 meetings, but manual review shows these are compact status bullets that legitimately mention every workstream together (several genuinely converge/complete around the same sprints in this richer narrative) — not the semantic conflation the check was designed to catch. No genuine cross-workstream conflation was found in this run.

## What Phase 6 does *not* cover yet

**Meeting-type-specific** templates (project status vs. blocker discussion, etc.) and **domain terminology handling** beyond this project's own vocabulary aren't built — every meeting uses the same `STATIC_CONTEXT` shape regardless of its actual type (kickoff, design review, UAT triage, ...).

## Phase 7 — Reference-Document RAG

**Goal:** improve summary accuracy by retrieving relevant excerpts from the project's own reference documents and grounding the summary in them, in addition to the transcript. **Built by:** [`phase7-reference-rag/`](phase7-reference-rag/README.md) — three fictional but internally-consistent reference documents (a PRD, a design spec, a payments vendor integration doc, at `reference-docs/*.md`) covering the same Mobile App Redesign project, retrieved against the shared kickoff transcript and compared: a transcript-only baseline summary vs. one enriched with retrieved reference excerpts.

Retrieval is the same TF-IDF, no-vector-DB approach as Phase 8's voice query (`phase7-reference-rag/src/retrieve.py`), scoped to a small fixed corpus (the reference docs) instead of everything on disk. The kickoff transcript only gestures at topics generally (e.g. "a new payments vendor," "dark mode") — the reference docs carry the specifics (vendor name, numeric targets, compliance tier) a transcript-only summary structurally cannot know.

| Metric | Status | Source |
|---|---|---|
| Comparison with baseline (faithfulness/completeness/conciseness) | **Measured** — same LLM-judge infrastructure as Phase 3's baseline-vs-context comparison, via `--judge-provider`. | `eval/output/run_history.jsonl` (`scenario_id: "phase7-reference-rag"`) |
| Retrieval relevance (are the right reference sections surfaced for the topic) | **Not separately measured** — inspect `retrieved_references.json` against the transcript for a given run; no deterministic or judged relevance score is computed. | — |
| Reference Grounding (does every word added by the reference-grounded summary, vs. the baseline, trace back to a retrieved excerpt) | **Measured deterministically**, not by an LLM judge — same word-overlap technique as Phase 8's Grounding Score and Phase 6's stale-action check, applied to the diff between the two summaries rather than a single answer. It's a proxy for "did the addition come from the reference docs," not a semantic fact-check — it can't catch a hallucination that happens to reuse a word already present in the baseline. | `output/reference_grounding.json`; also folded into the judged run's `reference_grounding` field in `run_history.jsonl` |

## Phase 8 — Voice Interface for Querying the Content

**Goal:** use a voice channel to query and retrieve from stored content. **Built by:** [`phase8-voice-query/`](phase8-voice-query/README.md) — ask a spoken question, get a text answer grounded in everything the project has already produced (Phases 1-7 transcripts/summaries plus any Custom Audio), via the webapp's **Voice Query** page (browser mic recording) or the CLI.

Retrieval is a pure-Python TF-IDF scorer over paragraph/section-level chunks (`phase8-voice-query/src/corpus.py`) — no vector DB, no new dependency, consistent with this project's existing preference for deterministic, dependency-light mechanisms.

| Metric | Status | Source |
|---|---|---|
| Response to user query | **Measured** — text answer only in this pass (no spoken reply; see the scenario README for why that's a deliberate, easy-to-add-later scope cut, not a gap). | `phase8-voice-query/output/query-N/answer.txt` |
| End-to-end latency | **Measured** — per-stage (transcribe/retrieve/answer) and total wall-clock time. | `output/query-N/timing.json` |
| Grounding Score (% of response backed by content) | **Measured deterministically**, not by an LLM judge — % of the answer's content words that appear in the retrieved excerpts actually used, the same word-overlap technique as Phase 6's stale-action-carryover check above. An `abstained` flag distinguishes "the model correctly said it couldn't find an answer" (legitimately low score) from an actual grounding failure. | `output/query-N/grounding.json` |
| Appropriate content in response | **Not separately scored** — the Grounding Score is the closest automated proxy (it's a groundedness check, not a correctness check); spot-check `answer.txt` against `retrieved_chunks.json` for a given query. | — |
| Comparing providers/iterations over time | **Measured** — every run appends to `output/query_history.jsonl` (provider, model, timing, grounding, cost); `python phase8-voice-query/src/history.py` or the webapp's "Progress across providers" table summarizes it. | `output/query_history.jsonl` |

## Gaps to close before calling Phases 1-8 "done"

1. Real-Time Factor isn't measured (Voice-to-Transcript).
2. Key Point Recall has no ground-truth-backed numeric metric, only a judge's subjective completeness score (Phase 1/3).
3. Meeting-type-specific templates and domain terminology handling aren't built (Phase 6).
4. Phase 5 evaluates a Claude tool-use agent, not Microsoft Copilot Enterprise — nothing here speaks to Copilot's actual UX, real network resilience, or pricing (see `phase5-office-agent/README.md`). Network conditions are simulated, not real network-shaped.
5. Phase 7 has no retrieval-relevance metric (are the *right* reference sections being surfaced) — Reference Grounding checks whether added content traces back to *some* retrieved excerpt, not whether the excerpts retrieved were the best ones for the topic.
6. Phase 8 has no spoken (TTS) reply and no automated correctness scoring, only groundedness (see table above).
