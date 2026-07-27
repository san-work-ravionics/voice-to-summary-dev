import argparse
import json
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from eval_scoring import evaluate_variant  # noqa: E402
from llm_provider import CLAUDE_MODEL, LOCAL_MODEL, MISTRAL_MODEL  # noqa: E402
from run_history import append_run  # noqa: E402

RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "results.json")

SCENARIOS = [
    {
        "id": "v1",
        "label": "v1 — Baseline pipeline",
        "transcript": "v1/output/transcript.txt",
        "has_checklist": False,
        "variants": [
            {"variant": "baseline", "summary_path": "v1/output/summary.txt"},
        ],
    },
    {
        "id": "v2",
        "label": "v2 — Context-aware summarization",
        "transcript": "v2/output/transcript.txt",
        "has_checklist": False,
        "variants": [
            {"variant": "baseline", "summary_path": "v2/output/summary_baseline.txt"},
            {"variant": "with_context", "summary_path": "v2/output/summary_with_context.txt"},
        ],
    },
    {
        "id": "v3",
        "label": "v3 — Checklist coverage check",
        "transcript": "v3/output/transcript.txt",
        "has_checklist": True,
        "variants": [
            {"variant": "context_checklist", "summary_path": "v3/output/summary.txt"},
        ],
    },
    {
        "id": "v4",
        "label": "v4 — AI Assistant as third actor",
        "transcript": "v4/output/transcript.txt",
        "has_checklist": True,
        "variants": [
            {"variant": "context_checklist_assistant", "summary_path": "v4/output/summary.txt"},
        ],
    },
]


def _read(relative_path):
    with open(os.path.join(PROJECT_ROOT, relative_path)) as f:
        return f.read()


def main():
    parser = argparse.ArgumentParser(description="Score existing vN/output summaries against their transcripts")
    parser.add_argument(
        "--provider", choices=["local", "mistral", "claude"], default=None,
        help="Judge model backend: local Qwen2.5 (default) or the Claude API. "
        "This judges whichever summaries already exist on disk — it doesn't "
        "know or care what provider generated them.",
    )
    args = parser.parse_args()
    judge_model = {"claude": CLAUDE_MODEL, "mistral": MISTRAL_MODEL}.get(args.provider, LOCAL_MODEL)

    scenarios_out = []
    for scenario in SCENARIOS:
        transcript = _read(scenario["transcript"])
        variants_out = []
        for variant in scenario["variants"]:
            print(f"Judging {scenario['id']} / {variant['variant']}...")
            summary_text = _read(variant["summary_path"])
            evaluation = evaluate_variant(transcript, summary_text, provider=args.provider)
            variants_out.append({
                "variant": variant["variant"],
                "summary_path": variant["summary_path"],
                **evaluation,
            })
            append_run(
                scenario["id"], variant["variant"],
                summarizer_provider="unknown",  # bulk mode: whoever last wrote this file
                judge_provider=args.provider or "local",
                transcript=transcript, summary=summary_text, evaluation=evaluation,
            )
        scenarios_out.append({
            "id": scenario["id"],
            "label": scenario["label"],
            "has_checklist": scenario["has_checklist"],
            "variants": variants_out,
        })

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": judge_model,
        "scenarios": scenarios_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
