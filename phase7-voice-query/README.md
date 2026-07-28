# phase7-voice-query — voice interface for querying stored content (Phase 7)

Part of the [voice-to-summary](../README.md) project: **Voice interface for querying the content**. Ask a spoken question, get a text answer grounded in every transcript and summary this project has already produced.

## How it works

1. **Transcribe** the question audio with the same shared Whisper wrapper (`../transcription.py`) every other scenario uses.
2. **Retrieve** the most relevant chunks from a corpus built over everything currently on disk under `phase1-baseline/`, `phase2-checklist/`, `phase3-context/`, `phase4-assistant/`, `phase5-office-agent/`, all 15 `phase6-history/` meetings, and `custom/output/` ([`src/corpus.py`](src/corpus.py)). Transcripts are chunked into ~4-sentence windows; Markdown summaries are chunked per `##` section, so a query can land on e.g. just one meeting's Actions instead of a whole brief.
3. **Answer**, grounded only in the retrieved excerpts ([`src/answer.py`](src/answer.py)) — provider-swappable (`local`/`mistral`/`claude`) via the same `llm_provider.py` every other scenario uses.

Because the corpus is built from files already on disk, **run the phases you want to be able to ask about first** — an empty `phase6-history/output/` means Phase 7 has nothing from that story to answer from.

## Retrieval: TF-IDF, not a vector DB

No new dependency (no `sentence-transformers`, no vector database) — retrieval is a pure-Python term-frequency / inverse-document-frequency scorer over the corpus built at query time. This follows this project's existing preference for deterministic, dependency-light mechanisms (see the root README's notes on `eval/story_probes.py`'s word-overlap checks) over adding heavier ML infrastructure for something a small local computation already answers adequately at this project's scale (a few dozen short documents, not a production knowledge base).

## Grounding Score

Measured deterministically, not by an LLM judge: the % of the answer's content words that also appear in the retrieved excerpts actually used to generate it — the same word-overlap technique `eval/story_probes.py` uses to catch stale-action leakage in Phase 6. An abstention ("I couldn't find that in the stored content.") legitimately scores low without being a grounding *failure* — `grounding.json`'s `abstained` flag distinguishes the two cases; don't read a low score as bad grounding without checking it first.

## Run

```bash
python phase7-voice-query/src/main.py path/to/question.wav
python phase7-voice-query/src/main.py path/to/question.wav --provider claude
```

Writes `output/query-N/{question_transcript.txt, answer.txt, retrieved_chunks.json, timing.json, grounding.json}`.

## Metrics

| Metric | How it's measured here |
|---|---|
| Response to user query | `answer.txt` — grounded text answer (no spoken reply in this pass; see below). |
| End-to-end latency | `timing.json`: `transcribe_s`, `retrieve_s`, `answer_s`, `total_s`. |
| Grounding Score | `grounding.json`: `score` (0-1), `matched`/`total` word counts, `abstained` flag — see above. |
| Appropriate content in response | Not separately scored here — inspect `answer.txt` against `retrieved_chunks.json` for the specific query; the grounding score is the closest automated proxy but is a groundedness check, not a correctness check. |

## Web UI

The webapp's **Voice Query** page (`python webapp/server.py`) records a question with the browser's microphone, uploads it, and displays the answer with the same latency/grounding breakdown — see [`../webapp/README.md`](../webapp/README.md).

## What isn't built here

A spoken (TTS) reply isn't implemented — the stated output ("Response to user query") is satisfied by text, and neither of its two metrics (latency, grounding) requires audio out. `pyttsx3` is already a dependency (used to generate every scripted recording elsewhere in this project) and would be a small, deliberately-deferred follow-up if a spoken reply is wanted later.
