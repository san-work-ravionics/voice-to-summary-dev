"""Append-only log of every scored (scenario, variant) run — local or
Claude, summarizer or judge — so the webapp's Evaluation page can compare
providers and show quality over time instead of only the latest run.

One JSON object per line (JSONL), append-only, never rewritten in place —
safe to append from multiple processes (each pipeline run is its own
subprocess) without a lock, since a single os.write of a line under 4KB is
atomic on POSIX for O_APPEND-opened files. The one exception is
backfill_costs(), a one-time migration that rewrites the whole file — run
it offline, not while pipelines are actively appending.
"""
import json
import os
import time
import uuid

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(PROJECT_ROOT, "eval", "output", "run_history.jsonl")


def _compute_costs(summarizer_provider, judge_provider, transcript, summary, layer2):
    from cost_estimate import estimate_cost_usd
    from llm_provider import CLAUDE_MODEL

    summarizer_cost = estimate_cost_usd(summarizer_provider or "local", CLAUDE_MODEL, transcript, summary)
    judge_raw = (layer2 or {}).get("raw", "")
    judge_cost = estimate_cost_usd(
        judge_provider or "local", CLAUDE_MODEL, transcript + "\n\n" + summary, judge_raw,
    )
    total = None
    if summarizer_cost["cost_usd"] is not None and judge_cost["cost_usd"] is not None:
        total = summarizer_cost["cost_usd"] + judge_cost["cost_usd"]
    return {
        "summarizer_cost_usd": summarizer_cost["cost_usd"],
        "judge_cost_usd": judge_cost["cost_usd"],
        "total_cost_usd": total,
    }


def append_run(scenario_id, variant, summarizer_provider, judge_provider,
                transcript, summary, evaluation, meeting=None):
    costs = _compute_costs(
        summarizer_provider, judge_provider, transcript, summary, evaluation.get("layer2"),
    )
    record = {
        "run_id": uuid.uuid4().hex[:12],
        "timestamp": time.time(),
        "scenario_id": scenario_id,
        "variant": variant,
        "meeting": meeting,  # meeting slug for phase6-history/, else None
        "summarizer_provider": summarizer_provider or "local",
        "judge_provider": judge_provider or "local",
        "transcript": transcript,
        "summary": summary,
        **costs,
        **evaluation,  # layer1, layer2, checklist
    }
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    line = json.dumps(record) + "\n"
    with open(HISTORY_PATH, "a") as f:
        f.write(line)
    return record


def read_history(scenario_id=None):
    if not os.path.exists(HISTORY_PATH):
        return []
    records = []
    with open(HISTORY_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if scenario_id is None or record.get("scenario_id") == scenario_id:
                records.append(record)
    return records


def backfill_costs():
    """One-time migration: add cost fields to records written before cost
    tracking existed. Safe to re-run — skips records that already have
    'total_cost_usd'. Returns the number of records updated."""
    records = read_history()
    changed = 0
    for r in records:
        if "total_cost_usd" in r:
            continue
        r.update(_compute_costs(
            r.get("summarizer_provider"), r.get("judge_provider"),
            r["transcript"], r["summary"], r.get("layer2"),
        ))
        changed += 1
    if changed:
        with open(HISTORY_PATH, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
    return changed


if __name__ == "__main__":
    n = backfill_costs()
    print(f"Backfilled cost estimates for {n} record(s).")
