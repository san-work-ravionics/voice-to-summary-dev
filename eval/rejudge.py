"""Re-score already-generated summaries with a different judge, without
re-running summarization. For each (scenario, variant, summarizer_provider[,
meeting]) combo already in run_history.jsonl, takes the latest stored
transcript+summary and appends a new record scored by --judge-provider —
so you can compare all providers under one neutral judge without paying for
new summarization calls.
"""
import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from eval_scoring import evaluate_variant  # noqa: E402
from run_history import append_run, read_history  # noqa: E402

VALID_PROVIDERS = ("local", "mistral", "claude")


def latest_per_key(records):
    latest = {}
    for r in records:
        if r["summarizer_provider"] not in VALID_PROVIDERS:
            continue  # skip "unknown" — pre-tracking bulk eval/judge.py runs
        key = (r["scenario_id"], r["variant"], r["summarizer_provider"], r.get("meeting"))
        if key not in latest or r["timestamp"] > latest[key]["timestamp"]:
            latest[key] = r
    return latest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge-provider", choices=VALID_PROVIDERS, default="claude")
    args = parser.parse_args()

    latest = latest_per_key(read_history())
    print(f"Re-judging {len(latest)} (scenario, variant, provider) combos with judge={args.judge_provider}...")

    for (scenario_id, variant, provider, meeting), r in sorted(latest.items(), key=lambda kv: kv[0]):
        label = f"{scenario_id}/{variant}" + (f" week {meeting}" if meeting else "") + f" [{provider}]"
        print(f"  {label}...")
        evaluation = evaluate_variant(r["transcript"], r["summary"], provider=args.judge_provider)
        append_run(
            scenario_id, variant, provider, args.judge_provider,
            r["transcript"], r["summary"], evaluation, meeting=meeting,
        )

    print("Done.")


if __name__ == "__main__":
    main()
