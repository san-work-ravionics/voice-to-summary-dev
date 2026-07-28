# Voice to Summary

A progressive demo of a local, offline voice → transcript → summary pipeline, organized around an 8-phase build-out — each phase adds one technique on top of the last, so the improvement from each layer is visible on its own. [`audio-generation/`](audio-generation/README.md) is the shared **input**: 15 scripted, synthesized recordings covering a fictional Mobile App Redesign project's full lifecycle (kickoff through launch retro, ~5 months) — every phase below transcribes and summarizes recordings from that folder rather than generating its own throwaway audio.

| Scenario | Phase | Adds | Input | Summary output |
|---|---|---|---|---|
| [phase1-baseline](phase1-baseline/README.md) | Phase 1 | Baseline pipeline | `audio-generation/output/01-kickoff/` | `summary.txt` — Topic / Key Points / Decisions / Actions |
| [phase2-checklist](phase2-checklist/README.md) | Phase 2 | **Checklist** coverage check | same kickoff recording | `summary.txt` — adds a "Checklist Coverage" section (Covered / Not covered, with evidence quotes) |
| [phase3-context](phase3-context/README.md) | Phase 3 | Meeting **context** injected into the prompt | same kickoff recording | `summary_baseline.txt` **and** `summary_with_context.txt`, for comparison |
| [phase4-assistant](phase4-assistant/README.md) | Phase 4 | A third voice, **AI Assistant**, in the recording itself | kickoff dialogue + assistant lines, synthesized locally | `summary.txt` — same 5 sections, produced independently of what the in-recording assistant says |

Each scenario folder is fully self-contained: its own `src/` (transcribe with Whisper → summarize with a local LLM) and its own `output/`. There's deliberate duplication across scenarios so each one can be read and run on its own — see each scenario's README for what specifically changed from the one before it.

[`phase5-office-agent/`](phase5-office-agent/README.md) (Phase 5) tests an *agentic*, tool-using approach — a model that acts on real Word/Excel documents via tool calls, standing in for a Microsoft Copilot Enterprise agent this repo has no license for (see its README for the substitution and what it does/doesn't validate) — against the single-shot summarizer, across three simulated network conditions.

[`phase6-history/`](phase6-history/README.md) (Phase 6) goes a step further than any single Phase 1-4 scenario: all 15 `audio-generation/` meetings, told as one continuous arc, comparing a summarizer with no memory of prior meetings against one given a running history built from each prior meeting's own summary — a harder, more realistic test of whether "context" actually helps than a single snapshot meeting can show.

[`phase7-reference-rag/`](phase7-reference-rag/README.md) (Phase 7) introduces the project's own reference documents (a PRD, a design spec, a payments vendor integration doc) and retrieves relevant excerpts from them via TF-IDF to enrich the summary with authoritative specifics — a vendor name, a numeric target, a compliance tier — that the shared kickoff meeting only gestures at in general terms, comparing a transcript-only baseline against a reference-grounded summary.

[`phase8-voice-query/`](phase8-voice-query/README.md) (Phase 8) is a voice interface over everything the project has already produced: ask a spoken question, get a text answer grounded in the stored transcripts/summaries, with end-to-end latency and a deterministic Grounding Score.

Voice-to-Transcript isn't a separate numbered phase — it's the shared Whisper step (`transcription.py`) used identically by every scenario above.

## Setup

Shared by all scenarios (installed once at the project root):

```bash
brew install ffmpeg   # required by both pydub and whisper

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python audio-generation/src/main.py     # generates all 15 input recordings (run this first)
```

```bash
python phase1-baseline/src/main.py
python phase2-checklist/src/main.py
python phase3-context/src/main.py
```

Each transcribes `audio-generation/output/01-kickoff/recording.wav` and writes into its own `output/` (transcript, summary). `--regenerate` is accepted for interface parity with other phases but is a no-op here — the input recording belongs to `audio-generation/`, not these phases.

```bash
python phase4-assistant/src/main.py     # 3-voice recording: kickoff dialogue + AI assistant
```

Writes `phase4-assistant/output/{recording.wav, transcript.txt, summary.txt}`. Pass `--regenerate` to re-synthesize its recording (this one does generate its own audio, since it adds a voice `audio-generation/` doesn't have).

```bash
export ANTHROPIC_API_KEY=sk-ant-...             # required — the agent arm is Claude-only
python phase5-office-agent/src/main.py          # office agent vs. baseline, across good/degraded/offline
```

Writes `phase5-office-agent/output/{baseline_summary.txt, <condition>/{minutes.docx, action_tracker.xlsx, agent_reply.txt}}`.

```bash
python phase6-history/src/main.py       # 15-meeting story: baseline vs. context+history
```

Writes `phase6-history/output/<slug>/` for each of the 15 meetings (e.g. `01-kickoff/`, `15-launch-retro/`). Recordings come from `audio-generation/`; pass `--regenerate` to force re-transcription of every meeting.

```bash
python phase7-reference-rag/src/main.py    # same kickoff recording: baseline vs. reference-doc-grounded summary
```

Writes `phase7-reference-rag/output/{transcript.txt, retrieved_references.json, summary_baseline.txt, summary_with_references.txt}`. Reference documents ship with the phase at `phase7-reference-rag/reference-docs/*.md` — nothing to generate first.

```bash
python phase8-voice-query/src/main.py path/to/question.wav
```

Writes `phase8-voice-query/output/query-N/`. Needs Phases 1-4 (and optionally 5/6/7/Custom Audio) to have been run at least once, since that's the corpus it answers from.

## Run with Docker

```bash
cp .env.example .env        # optional — fill in ANTHROPIC_API_KEY etc. if needed
docker compose up --build
```

Open `http://localhost:8743/webapp/index.html`. First start downloads the local models (~3GB) into a `model_cache` volume, so later restarts are fast. `audio-generation/output/`, each scenario's `output/`, `custom/`, `eval/output/`, and `logs/` are bind-mounted from the project directory (not named volumes) — the container reads/writes the exact same files a local `python <scenario>/src/main.py` run would, so history from either one shows up in both. Runs entirely on CPU inside the container (no GPU/MPS passthrough), so local/Mistral summarization is slower than on bare metal — `--provider claude` avoids that if you have an API key.

### Choosing a summarization provider

Transcription always runs locally (Whisper) — none of these providers take audio input. Summarization can run against any of three, via `llm_provider.py` (shared by every scenario):

| Provider | Model | Notes |
|---|---|---|
| `local` (default) | `Qwen/Qwen2.5-1.5B-Instruct` | ~3GB, fast, runs comfortably on a laptop |
| `mistral` | `mistralai/Mistral-7B-Instruct-v0.3` | ~14GB, slower, also fully local |
| `claude` | `claude-haiku-4-5` | Anthropic API — needs `ANTHROPIC_API_KEY` or `ant auth login` |

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or `ant auth login` — only needed for --provider claude
python phase1-baseline/src/main.py --provider claude
python phase1-baseline/src/main.py --provider mistral
```

Every `main.py` (phase1-baseline through phase4-assistant, phase6-history, phase7-reference-rag, and phase8-voice-query) takes `--provider local|mistral|claude`; omitting it falls back to the `SUMMARY_PROVIDER` env var, then `local`. Override the specific model with `CLAUDE_MODEL` / `MISTRAL_MODEL`. `eval/judge.py --provider ...` selects the same three options for the *judge* model, independent of whichever provider generated the summary being judged — every `--judge-provider` flag on the pipelines works the same way. `phase5-office-agent/src/main.py` is the one exception — its agent arm is always Claude (tool-use isn't supported by the local/Mistral path), so it takes `--network good|degraded|offline` instead; see its README.

## Web UI and evaluation

- [`webapp/`](webapp/README.md) — a framework-free web page: browse Phases 1-4 and 7 and the 15-meeting Story, run any pipeline end-to-end from a **Pipeline** page with live per-stage progress and a provider picker for both summarizing and judging, ask a spoken question on the **Voice Query** page (Phase 8) via the browser microphone, compare local/Mistral/Claude quality (and estimated Claude cost) on an **Evaluation** page that updates as you run things, and see everything regrouped by phase on a **Roadmap** page. Run with `python webapp/server.py`.
- [`eval/`](eval/README.md) — the evaluation suite: summarization quality (schema compliance, checklist precision/recall, LLM-judged faithfulness/completeness/conciseness — judge model is provider-swappable, `--provider local|mistral|claude`), speech-recognition quality (Word Error Rate + noise-robustness testing), and information extraction efficiency (recall/precision on action items against the scripted ground truth). Run `python eval/judge.py`, `python eval/transcription_quality.py`, and `python eval/extraction_efficiency.py`; `eval/story_judge.py` / `eval/story_probes.py` cover the 15-meeting story specifically. `eval/rejudge.py --judge-provider claude` re-scores every already-generated summary (all providers, all scenarios) under one neutral judge, without re-running summarization.
- Every judged run (CLI with `--judge-provider`, or any webapp Pipeline run — judging is on by default there) is appended to `eval/output/run_history.jsonl`, an append-only log the webapp's Evaluation page reads to compare providers over time — see "Shared modules" below.

## Shared modules (project root)

Cross-cutting pieces used by every scenario and `webapp/` — factored out because they're infrastructure, not part of what each scenario is teaching (see `phase1-baseline/src/summarize.py` etc. for the actual per-scenario logic, which is deliberately duplicated — see the note in the intro above):

| Module | What it does |
|---|---|
| `llm_provider.py` | The local/mistral/claude summarization+judging backend (see above) |
| `transcription.py` | Shared Whisper wrapper (transcription is always local, regardless of summarization provider) |
| `redaction.py` | The name-anonymization logic (Jordan/Priya/etc. → Person A/Person B) |
| `eval_scoring.py` | Layer-1 deterministic checks + layer-2 LLM-judge scoring, used by both `eval/judge.py` and every pipeline's optional `--judge-provider` step |
| `run_history.py` | Appends/reads `eval/output/run_history.jsonl`; also estimates and backfills per-run Claude cost (`python run_history.py` re-runs the backfill) |
| `cost_estimate.py` | USD cost estimate for a Claude call, via Anthropic's free token-counting endpoint — local/Mistral are always free |
| `pipeline_status.py` | Cross-process stage-progress reporting between a running pipeline subprocess and `webapp/server.py`'s polling endpoint |
| `app_logging.py` | `webapp/server.py`'s logger factory — writes to stdout (`docker compose logs`) and a rotating file under `logs/` (`LOG_DIR` env var to override) so log history survives a container restart |
| `office_agent.py` | Phase 5's tool-use agent loop (Claude only) — writes Word/Excel via `python-docx`/`openpyxl`, used by `phase5-office-agent/` |

## Notes

- First run downloads models locally: Whisper `base` (~140MB) and `Qwen/Qwen2.5-1.5B-Instruct` (~3GB) — shared across every scenario since they use the same `requirements.txt`/`.venv`. Mistral (`--provider mistral`) is a separate, larger download (~14GB) the first time it's used. Expect the first run of each to take a few minutes; later runs are much faster since models are cached.
- No personal names appear anywhere in any recording, transcript, or summary — speakers are always "Person A" / "Person B" (plus "Assistant" as a role label in phase4-assistant), never real names. See each scenario's README for the specific redaction/anonymization mechanism.
- phase2-checklist's checklist coverage check is a deterministic keyword match against the transcript, not another LLM call — a small local model turned out to be unreliable at that specific judgment across several prompt designs. Details in [phase2-checklist/README.md](phase2-checklist/README.md).
- `custom/audio/` is a drop folder for real (non-scripted) recordings: copy a `.wav`/`.mp3`/`.m4a`/`.ogg`/`.flac` file in, and the webapp's Custom Audio page (needs `python webapp/server.py`, not a plain static server) detects it and can run the plain phase1-baseline pipeline on it — phase3-context's meeting context and phase2-checklist/phase4-assistant's checklist are hardcoded to the scripted kickoff dialogue and don't apply to arbitrary audio.
- Wherever this project measures something with a small local LLM as judge (checklist coverage, faithfulness scores, continuity, yes/no probes), treat it as a rough signal, not ground truth — every one of those approaches has been caught giving a wrong answer at some point in this project's own testing. Where a deterministic check was possible instead (keyword matching, word-overlap, Word Error Rate), it was used, and is the more trustworthy number.
- Judging a model's own output with itself is a known bias risk (self-preference) — most of this project's local-model runs were judged by the same local model that summarized them. `eval/rejudge.py --judge-provider claude` re-scores everything under one neutral judge for a cleaner comparison.
- The "Cost" figures shown for Claude runs are **estimates**, not read back from an actual bill — the project never captured real API usage at call time, so cost is re-derived by token-counting the stored transcript/summary via Anthropic's (free) count-tokens endpoint. It excludes the system prompt and any injected context text, undercounting slightly (well under $0.001/call at current Haiku pricing). Local and Mistral are always exactly free — no API involved.
