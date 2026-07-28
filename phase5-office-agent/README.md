# phase5-office-agent — agentic Office processing vs. single-shot summarization (Phase 5)

Part of the [voice-to-summary](../README.md) project, mapping to the roadmap's Phase 5: **On-Device / Office Tool Processing**.

## The Copilot Enterprise substitution

The roadmap phrases Phase 5 as "use of Co-pilot Enterprise features to build agents and validate performance in low network areas." This repo has no Microsoft 365 Copilot Enterprise license, Copilot Studio access, or Graph API credentials — none of that can be built or run here. Per explicit direction, **a Claude tool-use agent substitutes for the Copilot agent** ([`office_agent.py`](../office_agent.py)), keeping the two questions the roadmap actually cares about intact:

1. Does an *agentic* approach — a model that acts on Office documents via tool calls, not just replies with text — produce a meaningfully better meeting brief than the existing single-shot summarizer?
2. How does a cloud-based agent hold up when the network is bad, versus falling back to an on-device model?

What this **does** validate: the general hypothesis (agentic vs. single-shot quality; cloud-vs-on-device behavior under network stress) using real, measurable pipeline runs. What it **doesn't** validate: anything about Copilot Enterprise's actual product — its UX, its real network resilience, its pricing, or its specific agent-builder tooling. Treat every number here as "what a tool-use agent looks like," not "what Copilot looks like."

## What the agent does

[`office_agent.py`](../office_agent.py) (root module, reused by this folder) runs a tool-use loop against the Anthropic Messages API with two tools:

- `write_minutes_docx` — a Word document (Topic / Key Points / Decisions / Actions), via `python-docx`
- `write_action_tracker_xlsx` — rows appended to a running Excel action tracker, via `openpyxl`

This models what a Copilot Enterprise agent does inside Word/Excel: act on documents through tool calls rather than a single text reply. After both tools are called, the agent also gives a short plain-text confirmation formatted as the same four-section Markdown brief every other scenario in this project produces — that reply is what gets scored, so it's directly comparable to Phase 1-4's summaries via the same judge (`eval_scoring.evaluate_variant`). It's given the same shared kickoff transcript Phases 1-3 transcribe (`audio-generation/output/01-kickoff/`).

**Claude-only.** `llm_provider.py`'s local/Mistral path is a plain `transformers` text-generation call with no tool-calling support, so the agent loop can't run on them. That's reported as a real Phase 5 finding — agentic tool use requires a cloud model; on-device models in this project are comprehension-only — not something worked around.

## Simulated network conditions

There's no real network-shaping tool in this repo (no Network Link Conditioner, no proxy). [`src/network_sim.py`](src/network_sim.py) simulates three conditions instead, explicitly documented as simulation, not real network testing:

| Condition | Behavior |
|---|---|
| `good` | Calls Claude directly, no injected delay. |
| `degraded` | ~4s latency injected before every Claude call, plus one simulated timeout+retry (another ~6s) if the call raises. |
| `offline` | Never calls Claude — raises immediately, and the pipeline falls back to the local on-device model (`--provider local`) for that arm, the same one-shot summarizer used as the baseline arm below. |

## Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # required — the agent arm is Claude-only
python phase5-office-agent/src/main.py                       # baseline + all 3 network conditions
python phase5-office-agent/src/main.py --network degraded    # just one condition
python phase5-office-agent/src/main.py --judge-provider claude
```

Writes `output/{transcript.txt, baseline_summary.txt}` and `output/<condition>/{minutes.docx, action_tracker.xlsx, agent_reply.txt, run_meta.json}` per network condition — no local `recording.wav`, since it transcribes the shared kickoff recording from `audio-generation/` directly. Every arm is scored with `eval_scoring.evaluate_variant` (default judge: `local`) and appended to `eval/output/run_history.jsonl` under `scenario_id="phase5-office-agent"`, `variant` = `"baseline"` or `"agent_<condition>"` — so it shows up in the webapp's Evaluation/Roadmap pages next to Phases 1-4.

## Metrics

| Roadmap metric | How it's measured here |
|---|---|
| Summary metrics, comparison across approaches | `agent_good` vs. `baseline` faithfulness/completeness/conciseness scores (same judge as every other phase), via `run_history.jsonl`. |
| Was the improvement significant? | Compare `agent_good` and `baseline` records for the same run — reported in a results table below once run against a live API key. |
| Ease of integration | Qualitative: `office_agent.py` is ~80 lines beyond a normal single-shot call (tool schema + a bounded loop), no new infra beyond two well-established libraries (`python-docx`, `openpyxl`) — a real Copilot Enterprise integration would additionally require Azure AD app registration, Graph API permissions, and Copilot Studio agent configuration, none of which this substitution needed. |
| Performance in low network areas | `agent_degraded`'s `run_meta.json.elapsed_s` vs. `agent_good`'s, and whether `agent_offline` falls back cleanly (`fell_back_to_local: true`, `fallback_note` set, and a valid brief still produced by the local model). |

Run the pipeline and check `eval/output/run_history.jsonl` / the webapp's Roadmap page for current numbers — this README doesn't hardcode results that would go stale the next time the pipeline runs with a different model version or provider mix.
