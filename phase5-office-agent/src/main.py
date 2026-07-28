import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import network_sim
from eval_scoring import evaluate_variant
from office_agent import run_agent
from pipeline_status import write_status
from redaction import redact_names as _redact_names
from run_history import append_run
from summarize import summarize as summarize_baseline
from transcribe import transcribe

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
# See phase1-baseline/src/main.py — same shared kickoff recording.
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
SOURCE_RECORDING = os.path.join(REPO_ROOT, "audio-generation", "output", "01-kickoff", "recording.wav")
TRANSCRIPT_PATH = os.path.join(OUTPUT_DIR, "transcript.txt")

# Matches audio-generation/src/dialogues.py's SPEAKER_NAMES.
SPEAKER_NAMES = {"A": "Jordan", "B": "Priya"}


def redact(text):
    return _redact_names(text, speaker_names=SPEAKER_NAMES)


def _ensure_transcript(regenerate, on_stage):
    """`regenerate` is accepted for CLI/webapp parity but has no effect —
    see phase1-baseline/src/main.py."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    on_stage("transcribing")
    if regenerate or not os.path.exists(TRANSCRIPT_PATH):
        print("Transcribing...")
        text = transcribe(SOURCE_RECORDING)
        with open(TRANSCRIPT_PATH, "w") as f:
            f.write(text)
    with open(TRANSCRIPT_PATH) as f:
        return f.read()


def run_agent_arm(transcript, condition, judge_provider):
    """Runs the office agent under a simulated network `condition`
    ('good'/'degraded'/'offline'), scores the resulting brief the same way
    every other scenario's summary is scored, and appends it to
    run_history.jsonl so it shows up next to Phases 2-4."""
    condition_dir = os.path.join(OUTPUT_DIR, condition)
    os.makedirs(condition_dir, exist_ok=True)

    redacted_transcript = redact(transcript)

    start = time.time()
    fallback_note = None
    try:
        result = run_agent(redacted_transcript, condition_dir, network_call=network_sim.wrap(condition))
        provider_used = "claude"
    except network_sim.Offline as exc:
        fallback_note = str(exc)
        print(f"[{condition}] {fallback_note}")
        reply = summarize_baseline(transcript, provider="local")
        result = {"reply": reply, "tool_calls": [], "turns": 0, "fell_back_to_local": True}
        provider_used = "local"
    elapsed = time.time() - start

    reply = redact(result["reply"])
    with open(os.path.join(condition_dir, "agent_reply.txt"), "w") as f:
        f.write(reply)

    meta = {
        "condition": condition,
        "elapsed_s": elapsed,
        "turns": result["turns"],
        "tool_calls": [tc["name"] for tc in result["tool_calls"]],
        "fell_back_to_local": result.get("fell_back_to_local", False),
        "fallback_note": fallback_note,
    }
    with open(os.path.join(condition_dir, "run_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"[{condition}] agent reply in {elapsed:.1f}s "
          f"({result['turns']} turn(s), tools called: {meta['tool_calls']})")

    if judge_provider is not None and reply:
        evaluation = evaluate_variant(transcript, reply, provider=judge_provider)
        record = append_run(
            "phase5-office-agent", f"agent_{condition}", provider_used, judge_provider,
            transcript, reply, evaluation,
        )
        return record
    return None


def run_baseline_arm(transcript, judge_provider):
    """The existing single-shot phase1-baseline-style summarizer, run once
    with the same provider (claude) as the agent's 'good' condition, as the
    non-agentic point of comparison."""
    reply = summarize_baseline(transcript, provider="claude")
    with open(os.path.join(OUTPUT_DIR, "baseline_summary.txt"), "w") as f:
        f.write(reply)

    if judge_provider is not None:
        evaluation = evaluate_variant(transcript, reply, provider=judge_provider)
        record = append_run(
            "phase5-office-agent", "baseline", "claude", judge_provider,
            transcript, reply, evaluation,
        )
        return record
    return None


def run_pipeline(conditions, regenerate=False, judge_provider="local",
                  skip_baseline=False, on_stage=None):
    on_stage = on_stage or (lambda stage, detail=None: None)

    transcript = _ensure_transcript(regenerate, on_stage)

    if not skip_baseline:
        on_stage("baseline")
        run_baseline_arm(transcript, judge_provider)

    for condition in conditions:
        on_stage(f"agent_{condition}")
        run_agent_arm(transcript, condition, judge_provider)

    on_stage("done")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 5 — office agent (Claude tool-use, standing in for "
        "Copilot Enterprise) vs. the single-shot baseline, across simulated "
        "network conditions. Needs ANTHROPIC_API_KEY.",
    )
    parser.add_argument(
        "--network", choices=list(network_sim.CONDITIONS) + ["all"], default="all",
        help="Which simulated network condition(s) to run the agent under (default: all three).",
    )
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument(
        "--judge-provider", choices=["local", "mistral", "claude"], default="local",
        help="Scores every arm and appends to eval/output/run_history.jsonl (default: local).",
    )
    parser.add_argument(
        "--skip-baseline", action="store_true",
        help="Skip the non-agentic comparison arm (useful when re-running just one network condition).",
    )
    parser.add_argument("--status-file", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    on_stage = None
    if args.status_file:
        on_stage = lambda stage, detail=None: write_status(args.status_file, stage, detail)  # noqa: E731

    conditions = list(network_sim.CONDITIONS) if args.network == "all" else [args.network]
    run_pipeline(
        conditions, regenerate=args.regenerate, judge_provider=args.judge_provider,
        skip_baseline=args.skip_baseline, on_stage=on_stage,
    )


if __name__ == "__main__":
    main()
