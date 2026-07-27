# Voice to Summary

A progressive demo of a local, offline voice → transcript → summary pipeline. Each version below adds one technique on top of the last, so the improvement from each layer is visible on its own:

| Version | Adds | Recording | Summary output |
|---|---|---|---|
| [v1](v1/README.md) | Baseline pipeline | 2-person dialogue + narrator intro | `summary.txt` — Topic / Key Points / Decisions / Actions |
| [v2](v2/README.md) | Meeting **context** injected into the prompt | same as v1 | `summary_baseline.txt` **and** `summary_with_context.txt`, for comparison |
| [v3](v3/README.md) | **Checklist** coverage check | same as v1 | `summary.txt` — adds a "Checklist Coverage" section (Covered / Not covered, with evidence quotes) |
| [v4](v4/README.md) | A third voice, **AI Assistant**, in the recording itself | 3-person dialogue: 2 participants + assistant | `summary.txt` — same 5 sections, produced independently of what the in-recording assistant says |

Each `vN/` folder is fully self-contained: its own `src/` (generate dummy audio → transcribe with Whisper → summarize with a local LLM) and its own `output/`. There's deliberate duplication across versions so each one can be read and run on its own — see each version's README for what specifically changed from the one before it.

[`story/`](story/README.md) goes a step further than any single `vN/`: 5 weekly status syncs about the same project, told as one continuous arc, comparing a summarizer with no memory of prior meetings against one given a running history built from each prior week's own summary — a harder, more realistic test of whether "context" actually helps than a single snapshot meeting can show.

## Setup

Shared by all versions (installed once at the project root):

```bash
brew install ffmpeg   # required by both pydub and whisper

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python v1/src/main.py
python v2/src/main.py
python v3/src/main.py
python v4/src/main.py
```

Each writes into its own `vN/output/` on first run (recording, transcript, summary). Pass `--regenerate` to force a fresh recording instead of reusing an existing one.

```bash
python story/src/main.py       # 5-meeting story: baseline vs. context+history
```

Writes `story/output/meeting-{1..5}/`. Pass `--regenerate` to re-synthesize all 5 recordings (also re-transcribes, since a new recording invalidates the old transcript).

## Run with Docker

```bash
cp .env.example .env        # optional — fill in ANTHROPIC_API_KEY etc. if needed
docker compose up --build
```

Open `http://localhost:8743/webapp/index.html`. First start downloads the local models (~3GB) into a `model_cache` volume, so later restarts are fast. Each scenario's output, `custom/`, and `eval/output/` are also named volumes — `docker compose down` keeps them; add `-v` to actually discard them. Runs entirely on CPU inside the container (no GPU/MPS passthrough), so local/Mistral summarization is slower than on bare metal — `--provider claude` avoids that if you have an API key.

### Choosing a summarization provider

Transcription always runs locally (Whisper) — none of these providers take audio input. Summarization can run against any of three, via `llm_provider.py` (shared by all versions):

| Provider | Model | Notes |
|---|---|---|
| `local` (default) | `Qwen/Qwen2.5-1.5B-Instruct` | ~3GB, fast, runs comfortably on a laptop |
| `mistral` | `mistralai/Mistral-7B-Instruct-v0.3` | ~14GB, slower, also fully local |
| `claude` | `claude-haiku-4-5` | Anthropic API — needs `ANTHROPIC_API_KEY` or `ant auth login` |

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or `ant auth login` — only needed for --provider claude
python v1/src/main.py --provider claude
python v1/src/main.py --provider mistral
```

Every `main.py` (v1-v4, story) takes `--provider local|mistral|claude`; omitting it falls back to the `SUMMARY_PROVIDER` env var, then `local`. Override the specific model with `CLAUDE_MODEL` / `MISTRAL_MODEL`. `eval/judge.py --provider ...` selects the same three options for the *judge* model, independent of whichever provider generated the summary being judged — every `--judge-provider` flag on the pipelines works the same way.

## Web UI and evaluation

- [`webapp/`](webapp/README.md) — a framework-free web page: browse all 4 scenarios and the 5-meeting Story, run any pipeline (v1-v4, story) end-to-end from a **Pipeline** page with live per-stage progress and a provider picker for both summarizing and judging, and compare local/Mistral/Claude quality (and estimated Claude cost) on an **Evaluation** page that updates as you run things. Run with `python webapp/server.py`.
- [`eval/`](eval/README.md) — the evaluation suite: summarization quality (schema compliance, checklist precision/recall, LLM-judged faithfulness/completeness/conciseness — judge model is provider-swappable, `--provider local|mistral|claude`), speech-recognition quality (Word Error Rate + noise-robustness testing), and information extraction efficiency (recall/precision on action items against the scripted ground truth). Run `python eval/judge.py`, `python eval/transcription_quality.py`, and `python eval/extraction_efficiency.py`; `eval/story_judge.py` / `eval/story_probes.py` cover the 5-meeting story specifically. `eval/rejudge.py --judge-provider claude` re-scores every already-generated summary (all providers, all scenarios) under one neutral judge, without re-running summarization.
- Every judged run (CLI with `--judge-provider`, or any webapp Pipeline run — judging is on by default there) is appended to `eval/output/run_history.jsonl`, an append-only log the webapp's Evaluation page reads to compare providers over time — see "Shared modules" below.

## Shared modules (project root)

Cross-cutting pieces used by every `vN/`, `story/`, and `webapp/` — factored out because they're infrastructure, not part of what each scenario is teaching (see `v1/src/summarize.py` etc. for the actual per-scenario logic, which is deliberately duplicated — see the note in the intro above):

| Module | What it does |
|---|---|
| `llm_provider.py` | The local/mistral/claude summarization+judging backend (see above) |
| `transcription.py` | Shared Whisper wrapper (transcription is always local, regardless of summarization provider) |
| `redaction.py` | The name-anonymization logic (Sam/Priya/etc. → Person A/Person B) |
| `eval_scoring.py` | Layer-1 deterministic checks + layer-2 LLM-judge scoring, used by both `eval/judge.py` and every pipeline's optional `--judge-provider` step |
| `run_history.py` | Appends/reads `eval/output/run_history.jsonl`; also estimates and backfills per-run Claude cost (`python run_history.py` re-runs the backfill) |
| `cost_estimate.py` | USD cost estimate for a Claude call, via Anthropic's free token-counting endpoint — local/Mistral are always free |
| `pipeline_status.py` | Cross-process stage-progress reporting between a running pipeline subprocess and `webapp/server.py`'s polling endpoint |

## Notes

- First run downloads models locally: Whisper `base` (~140MB) and `Qwen/Qwen2.5-1.5B-Instruct` (~3GB) — shared across all four versions since they use the same `requirements.txt`/`.venv`. Mistral (`--provider mistral`) is a separate, larger download (~14GB) the first time it's used. Expect the first run of each to take a few minutes; later runs are much faster since models are cached.
- No personal names appear anywhere in any recording, transcript, or summary — speakers are always "Person A" / "Person B" (plus "Assistant" as a role label in v4), never real names. See each version's README for the specific redaction/anonymization mechanism.
- v3's checklist coverage check is a deterministic keyword match against the transcript, not another LLM call — a small local model turned out to be unreliable at that specific judgment across several prompt designs. Details in [v3/README.md](v3/README.md).
- `custom/audio/` is a drop folder for real (non-scripted) recordings: copy a `.wav`/`.mp3`/`.m4a`/`.ogg`/`.flac` file in, and the webapp's Custom Audio page (needs `python webapp/server.py`, not a plain static server) detects it and can run the plain v1 baseline pipeline on it — v2's context and v3/v4's checklist are hardcoded to the scripted "Mobile App Redesign" dialogue and don't apply to arbitrary audio.
- Wherever this project measures something with a small local LLM as judge (checklist coverage, faithfulness scores, continuity, yes/no probes), treat it as a rough signal, not ground truth — every one of those approaches has been caught giving a wrong answer at some point in this project's own testing. Where a deterministic check was possible instead (keyword matching, word-overlap, Word Error Rate), it was used, and is the more trustworthy number.
- Judging a model's own output with itself is a known bias risk (self-preference) — most of this project's local-model runs were judged by the same local model that summarized them. `eval/rejudge.py --judge-provider claude` re-scores everything under one neutral judge for a cleaner comparison.
- The "Cost" figures shown for Claude runs are **estimates**, not read back from an actual bill — the project never captured real API usage at call time, so cost is re-derived by token-counting the stored transcript/summary via Anthropic's (free) count-tokens endpoint. It excludes the system prompt and any injected context text, undercounting slightly (well under $0.001/call at current Haiku pricing). Local and Mistral are always exactly free — no API involved.
