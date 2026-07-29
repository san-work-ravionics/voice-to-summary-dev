# Evaluation harness

Scores the existing `<scenario>/output/summary*.txt` files against their transcripts. Scoring logic lives in `../eval_scoring.py` (shared with every pipeline's optional `--judge-provider` step, so a webapp-triggered run and a bulk `eval/judge.py` run score identically). Two layers:

- **Layer 1 (deterministic):** Markdown schema compliance (all 4 sections present, `##` heading level as specified in every summarizer's system prompt), Actions-bullet prefix compliance (`Person A:` / `Person B:`), and — for phase2-checklist/phase4-assistant — checklist coverage precision/recall against a hand-labeled ground truth (every topic is actually discussed in the kickoff dialogue except budget/cost impact, on purpose — see [phase2-checklist/README.md](../phase2-checklist/README.md)).
- **Layer 2 (LLM-as-judge):** a judge model scores each brief (Topic/Key Points/Decisions/Actions only, not the checklist section) on faithfulness, completeness, and conciseness (1-5 each), plus any unsupported claims it can spot. The judge is **provider-swappable** (`--provider local|mistral|claude`, default `local`) via `../llm_provider.py`, independent of whichever provider generated the summary being judged.

Judging with the same model that generated the summary is a real limitation (self-preference bias, and the same reliability ceiling noted in phase2-checklist's README for LLM-based checklist judging) — treat layer 2 scores as a rough signal to spot-check, not ground truth. This matters most for `local`, since most of this project's local-model summaries were also judged by the local model. `eval/rejudge.py --judge-provider claude` re-scores everything under one neutral judge without re-running summarization. Layer 1 is exact for what it checks, but only checks what it was told to check.

## Run

```bash
python eval/judge.py                        # local judge (default)
python eval/judge.py --provider claude       # judge with Claude instead
```

Writes `eval/output/results.json` (a single bulk snapshot, consumed by `webapp/`'s scenario-level fallback display) and appends one record per scored variant to `eval/output/run_history.jsonl` (summarizer attribution `"unknown"`, since this scores whatever's currently on disk without knowing which provider wrote it — see `eval/rejudge.py` below for provider-attributed re-scoring).

## Re-judging without re-summarizing (`eval/rejudge.py`)

Every pipeline run with `--judge-provider` set (or any webapp Pipeline run — judging is on by default there) appends a provider-attributed record to `eval/output/run_history.jsonl` via `../run_history.py`. To compare providers under one *neutral* judge without paying for new summarization calls, re-score the latest stored summary for every (scenario, variant, provider) combo already in that history:

```bash
python eval/rejudge.py --judge-provider claude    # default judge is claude
```

Each run also gets a cost estimate (`../cost_estimate.py` — free for local/Mistral, token-counted for Claude; see the root README's cost caveat) stored alongside the scores.

## Transcription quality (`eval/transcription_quality.py`)

Word Error Rate against the exact scripted dialogue text (the TTS ground truth), for the shared kickoff recording (transcribed identically by phase1-baseline/phase2-checklist/phase3-context/phase5-office-agent), phase4-assistant's own 3-voice recording, and all 15 phase6-history meetings — this project's first measurement of the ASR step itself, everything above only ever evaluated summarization against Whisper's output as if it were ground truth. Word-level Levenshtein distance (no new dependency), reporting substitutions/deletions/insertions separately.

Also generates two degraded variants per recording with `pydub` (already a dependency) — `light_noise` (white noise ~20dB below speech) and `heavy_noise` (~8dB below speech + a 3kHz low-pass filter simulating a poor mic) — and re-transcribes each, so WER-vs-noise-severity is an actual measured trend rather than a documented gap.

**Speaker diarization is not implemented and not measurable here** — Whisper's `transcribe()` as used everywhere in this project returns one undifferentiated text stream with no speaker labels; the closest proxy is the Actions-prefix compliance check below (does the summarizer's *own* speaker attribution stay internally consistent), which is a downstream LLM behavior, not an ASR capability.

**Accent resilience is not tested** — every recording uses the same one or two macOS system TTS voices.

```bash
python eval/transcription_quality.py                      # whisper only (default, fast)
python eval/transcription_quality.py --engines whisper,voxtral   # add the Voxtral comparison
```

Transcription runs through the shared engine layer (`transcription.py`), so this benchmarks the exact code path the pipelines use. By default it measures Whisper only; `--engines whisper,voxtral` also benchmarks Mistral Voxtral Mini 3B over the same recordings (much slower on CPU — opt in). When more than one engine is present, each scenario carries per-engine tiers under `engines`, and the webapp's Foundation scorecard renders a Whisper-vs-Voxtral WER + speed table. Writes `eval/output/transcription_quality.json`.

## Information extraction efficiency (`eval/extraction_efficiency.py`)

Ground truth: lines in the scripted dialogue matching the same commitment heuristic ("I'll"/"I will"/"let me [do]") every summarizer's own prompt is instructed to use for Actions bullets. Matched against generated Actions bullets via word-containment (deterministic, not another LLM call) — recall/precision per scenario/variant, for phase1-baseline through phase4-assistant and all 15 phase6-history meetings.

```bash
python eval/extraction_efficiency.py
```

Writes `eval/output/extraction_efficiency.json`.
