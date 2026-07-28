"""Prints every logged voice-query run (see query_history.py), grouped by
provider so results from Local Qwen / Mistral / Claude runs can be compared
side by side instead of only ever looking at the latest output/query-N/.

Run: python phase8-voice-query/src/history.py
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from query_history import read_history


def _fmt_pct(score):
    return f"{score * 100:.0f}%" if score is not None else "n/a"


def main():
    records = read_history()
    if not records:
        print("No voice-query runs logged yet — run main.py at least once.")
        return

    by_provider = defaultdict(list)
    for r in records:
        by_provider[r.get("provider", "unknown")].append(r)

    print(f"{len(records)} run(s) across {len(by_provider)} provider(s)\n")

    print(f"{'provider':<10} {'model':<38} {'runs':>4} {'avg grounding':>14} {'avg answer_s':>13} {'avg total':>10} {'total cost':>11}")
    for provider, runs in sorted(by_provider.items()):
        scores = [r["grounding"]["score"] for r in runs if r["grounding"].get("score") is not None and not r["grounding"].get("abstained")]
        avg_score = sum(scores) / len(scores) if scores else None
        avg_answer = sum(r["timing"].get("answer_s", 0) for r in runs) / len(runs)
        avg_latency = sum(r["timing"].get("total_s", 0) for r in runs) / len(runs)
        total_cost = sum(r.get("cost_usd") or 0 for r in runs)
        model_name = runs[-1].get("model_name", "")
        print(f"{provider:<10} {model_name:<38} {len(runs):>4} {_fmt_pct(avg_score):>14} {avg_answer:>12.2f}s {avg_latency:>9.2f}s ${total_cost:>10.4f}")

    print(f"\n{'query':<10} {'provider':<10} {'grounding':>10} {'total':>8} {'transcribe':>11} {'retrieve':>9} {'answer':>8} {'abstained':>10}  question")
    for r in records:
        g = r.get("grounding", {})
        t = r.get("timing", {})
        score = _fmt_pct(g.get("score"))
        abstained = "yes" if g.get("abstained") else ""
        question = r.get("question", "").strip().replace("\n", " ")
        if len(question) > 60:
            question = question[:57] + "..."
        print(
            f"{r.get('query_id', ''):<10} {r.get('provider', ''):<10} {score:>10} "
            f"{t.get('total_s', 0):>7.2f}s {t.get('transcribe_s', 0):>10.2f}s {t.get('retrieve_s', 0):>8.2f}s "
            f"{t.get('answer_s', 0):>7.2f}s {abstained:>10}  {question}"
        )


if __name__ == "__main__":
    main()
