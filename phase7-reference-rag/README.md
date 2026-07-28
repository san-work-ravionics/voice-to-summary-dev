# phase7-reference-rag — reference-document RAG (Phase 7)

Part of the [voice-to-summary](../README.md) progression. Introduces the project's own **reference documents** — a PRD, a design spec, a payments vendor integration doc — and retrieves the excerpts most relevant to the meeting being summarized, so the summary can be grounded in authoritative project facts, not just what's said aloud.

Same shared kickoff recording/transcript as phase1-baseline/phase2-checklist/phase3-context — only the summarization step changes.

## Why this is useful

The kickoff meeting discusses topics only in general terms: "a new payments provider," "dark mode," "legal and privacy review." It never names the vendor, states a numeric onboarding target, or names the compliance tier — because that's not how people talk in a kickoff meeting; those specifics live in planning documents instead. A transcript-only summary structurally cannot surface them. This phase does, without inventing anything: retrieval finds the reference sections relevant to what's actually discussed, and the summarizer is instructed to attribute any added specific to the reference material, never to imply a speaker said it themselves.

## How it works

1. **Transcribe** the shared kickoff recording, same as every other phase ([`../transcription.py`](../transcription.py)).
2. **Retrieve** the most relevant chunks from `reference-docs/*.md` using the transcript itself as the query ([`src/retrieve.py`](src/retrieve.py)). Each doc is chunked per `##` section. Same TF-IDF, no-vector-DB approach as [`phase8-voice-query`](../phase8-voice-query/README.md)'s corpus retrieval — re-implemented here rather than shared, since the two phases retrieve over different, differently-shaped corpora.
3. **Summarize** twice ([`src/summarize.py`](src/summarize.py)):
   - `summarize_baseline` — transcript only, same prompt shape as phase1-baseline.
   - `summarize_with_references` — transcript plus the retrieved reference excerpts. The system prompt allows adding a specific fact from the excerpts when the transcript raises that same topic generally (e.g. "Per the PRD, the target is 85%+") — but never claims a speaker said or decided something the transcript doesn't actually support, and never pulls in a topic the transcript doesn't raise at all.

## Reference documents

`reference-docs/`: three fictional but internally-consistent documents for the same Mobile App Redesign project used everywhere else in this repo:
- `product-requirements.md` — goals, workstreams, success metrics (onboarding target, vendor name, design system, analytics platform).
- `design-spec.md` — dark mode implementation approach, onboarding flow redesign, accessibility requirement.
- `payments-vendor-integration.md` — vendor selection rationale, integration approach, security/compliance tier.

These ship with the phase — nothing needs to be generated first, unlike the transcript/summary corpus `phase8-voice-query` depends on.

## Run

```bash
python phase7-reference-rag/src/main.py
python phase7-reference-rag/src/main.py --provider claude
```

Writes:
- `output/transcript.txt` — same shared kickoff transcript as phase1-baseline/phase2-checklist/phase3-context
- `output/retrieved_references.json` — which reference chunks were retrieved and their scores
- `output/summary_baseline.txt` — transcript only, for comparison
- `output/summary_with_references.txt` — enriched with retrieved reference excerpts
- `output/reference_grounding.json` — the Reference Grounding Score (see below); written unconditionally, no `--judge-provider` needed

`--regenerate` is a no-op (see phase1-baseline's README) — the shared kickoff recording belongs to `audio-generation/`. `--judge-provider` scores both summaries (faithfulness/completeness/conciseness) and appends to `eval/output/run_history.jsonl`, same as every other phase; the `with_references` record also carries the Reference Grounding Score.

## Reference Grounding Score

Measured deterministically, not by an LLM judge, and computed on every run regardless of `--judge-provider`: take the words present in the reference-grounded summary but *not* in the baseline summary — the specifics the reference material is supposed to be adding — and check what fraction of them also appear somewhere in the retrieved excerpts actually used. Same word-overlap technique as [`phase8-voice-query`](../phase8-voice-query/README.md)'s Grounding Score and Phase 6's stale-action check, applied to a diff between two summaries instead of a single answer.

This is a proxy for "did the added content come from the reference docs," not a semantic fact-check — it can't catch a hallucination that happens to reuse a word already present in the baseline summary, and a score of `None` (with `total: 0`) means the reference-grounded summary added no new words at all, not that grounding failed.

## What isn't measured here

Retrieval relevance — are the *right* reference sections actually being surfaced for the topic, as opposed to *some* excerpt the added content happens to overlap with — isn't separately scored. The Reference Grounding Score above checks the latter, not the former. See [`../ROADMAP.md`](../ROADMAP.md)'s Phase 7 section for the honest gap list.

## Notes

- See [phase1-baseline](../phase1-baseline/README.md) for setup/model notes — unchanged here.
- See [phase3-context](../phase3-context/README.md) for the closest sibling comparison (baseline vs. enhanced summary, same kickoff recording) — the difference is *what* enhances the summary: fixed meeting context there, retrieved reference-document excerpts here.
- See [phase8-voice-query](../phase8-voice-query/README.md) for the sibling retrieval implementation this phase's `retrieve.py` mirrors, applied to Q&A instead of summarization.
