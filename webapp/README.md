# Web UI

A framework-free HTML/CSS/JS page for browsing the scenarios, triggering and monitoring any pipeline run (with a choice of summarization/judge provider), running the pipeline on new audio, and comparing quality and cost across local/Mistral/Claude.

## Run

```bash
python webapp/server.py        # serves on :8743 by default; pass a port to override
```

Open `http://localhost:8743/webapp/index.html`. A plain `python -m http.server` also works for the Scenarios/Evaluation pages, but **Custom Audio and Pipeline need `server.py`** — they add the `/api/*` endpoints a static server can't provide.

## Pages

- **Scenarios** — v1-v4, each showing the recording, transcript, and summary (Key Points + full output; v2 shows baseline vs. context-aware side by side), plus a Technology summary reused from `../app-documentation.md` and a plain-language **Evaluation Summary** table for anyone who wants the verdict without the technical detail on the Evaluation page. One row per (scenario, provider) that's actually been run — Model, Last Run, Transcription Accuracy, Summary Trustworthiness, Format Compliance, Checklist Coverage, Cost, and Does Context Help, all in simple terms.
- **Story** — the 5-meeting baseline-vs-context comparison (see [../story/README.md](../story/README.md)): recording/transcript per week, summaries side by side, and per-meeting "Targeted checks" (noise leakage, deterministic conflation/stale-action checks, LLM probes).
- **Custom Audio** — lists any audio file dropped into `custom/audio/` (polls every few seconds, so a newly copied-in file shows up on its own). Pick a provider and click "Run pipeline" to transcribe + summarize it. This always runs **v1's plain baseline pipeline** — v2's meeting context and v3/v4's checklist are hardcoded to the scripted "Mobile App Redesign" dummy dialogue and wouldn't mean anything applied to a real recording. Output lands in `custom/output/<filename-without-extension>/`.
- **Pipeline** — trigger any of v1-v4 or story directly, with live per-stage progress (Recording → Transcribing → Summarizing → Judging → Done, or the baseline/context-split version for v2 and story). Each panel has independent "Summarize with" and "Judge with" pickers (local/Mistral/Claude) and a "Regenerate recording" toggle. Runs execute as a subprocess of that scenario's own `main.py` — the same script you'd run by hand — so behavior is identical to the CLI, just monitored over HTTP. Judging is **on by default** here (unlike the CLI, where `--judge-provider` is opt-in), so every webapp-triggered run feeds the Evaluation page's run history.
- **Evaluation** — four sections: **(A) Speech Recognition & Transcription Quality** (WER + noise-robustness from `eval/transcription_quality.py`), **(B) Summarization Quality** (extraction efficiency from `eval/extraction_efficiency.py`, plus the bulk faithfulness/structure/format snapshot from `eval/judge.py`), and **(C) Provider Comparison — Local vs Claude vs Mistral, Across Runs**: a live comparison table plus small-multiple trend charts (faithfulness over run sequence) built from every judged run in `eval/output/run_history.jsonl`, not just the latest. Section C updates automatically as you run things from the Pipeline page — no script to re-run. Sections A/B still need their underlying script re-run after a pipeline change, or they show stale scores.

## Files

- `server.py` — stdlib-only `http.server` subclass: serves the project as static files, plus:
  - `/api/custom-audio` (list), `/api/run-pipeline` (POST), `/api/run-status` (poll) — Custom Audio.
  - `/api/pipeline/run` (POST), `/api/pipeline/status` (poll) — Pipeline page. Runs each scenario's `main.py` as a subprocess (not imported in-process — v1-v4/story all define sibling modules with the same names, e.g. `summarize`, and Python's module cache is keyed by name, not directory, so importing more than one version into the same process would silently alias them) and cross-process progress reports through `../pipeline_status.py`'s JSON status file.
  - `/api/eval/history` (GET, optional `?scenario=` filter) — reads `eval/output/run_history.jsonl` via `../run_history.py`.
  - Custom Audio job state is in-memory (resets on restart, harmless — re-derives "done" from disk); Pipeline page state is a mix of in-memory (live stage) and on-disk (`last_run_at` from file mtime, provider from run history) so it survives a server restart.
- `index.html`, `style.css`, `app.js` — no build step, no dependencies. `app.js`'s SVG trend charts are hand-rolled (no charting library) following this project's categorical color convention: local = blue, Claude = green, Mistral = magenta, in that fixed order everywhere.
