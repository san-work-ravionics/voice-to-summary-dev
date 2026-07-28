import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from eval_scoring import evaluate_variant
from pipeline_status import write_status
from run_history import append_run
from summarize import summarize_baseline, summarize_with_context
from transcribe import transcribe

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
# See phase1-baseline/src/main.py — same shared kickoff recording.
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
SOURCE_RECORDING = os.path.join(REPO_ROOT, "audio-generation", "output", "01-kickoff", "recording.wav")
TRANSCRIPT_PATH = os.path.join(OUTPUT_DIR, "transcript.txt")
BASELINE_SUMMARY_PATH = os.path.join(OUTPUT_DIR, "summary_baseline.txt")
CONTEXT_SUMMARY_PATH = os.path.join(OUTPUT_DIR, "summary_with_context.txt")


def run_pipeline(regenerate=False, provider=None, judge_provider=None, on_stage=None):
    """`regenerate` is accepted for CLI/webapp parity but has no effect —
    see phase1-baseline/src/main.py. Stages: 'transcribing',
    'summarizing_baseline', 'summarizing_context', plus
    'judging_baseline'/'judging_context' when judge_provider is given
    (skipped by default), 'done'."""
    on_stage = on_stage or (lambda stage, detail=None: None)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    on_stage("transcribing")
    print("\nTranscribing...")
    transcript = transcribe(SOURCE_RECORDING)
    with open(TRANSCRIPT_PATH, "w") as f:
        f.write(transcript)
    print("\n--- Transcript ---")
    print(transcript)

    on_stage("summarizing_baseline")
    print("\nSummarizing (baseline, no context)...")
    baseline = summarize_baseline(transcript, provider=provider)
    with open(BASELINE_SUMMARY_PATH, "w") as f:
        f.write(baseline)

    if judge_provider is not None:
        on_stage("judging_baseline")
        print("Judging (baseline)...")
        evaluation = evaluate_variant(transcript, baseline, provider=judge_provider)
        append_run("phase3-context", "baseline", provider, judge_provider, transcript, baseline, evaluation)

    on_stage("summarizing_context")
    print("Summarizing (with meeting context)...")
    with_context = summarize_with_context(transcript, provider=provider)
    with open(CONTEXT_SUMMARY_PATH, "w") as f:
        f.write(with_context)

    if judge_provider is not None:
        on_stage("judging_context")
        print("Judging (with context)...")
        evaluation = evaluate_variant(transcript, with_context, provider=judge_provider)
        append_run("phase3-context", "with_context", provider, judge_provider, transcript, with_context, evaluation)

    print("\n--- Baseline summary (no context) ---")
    print(baseline)
    print("\n--- Context-aware summary ---")
    print(with_context)

    on_stage("done")


def main():
    parser = argparse.ArgumentParser(description="Voice -> transcript -> summary demo pipeline (context comparison)")
    parser.add_argument(
        "--regenerate", action="store_true",
        help=argparse.SUPPRESS,  # no-op here, kept for CLI/webapp parity with other phases
    )
    parser.add_argument(
        "--provider", choices=["local", "mistral", "claude"], default=None,
        help="Summarization backend: local Qwen2.5 (default) or the Claude API. "
        "Falls back to the SUMMARY_PROVIDER env var, then 'local'.",
    )
    parser.add_argument(
        "--judge-provider", choices=["local", "mistral", "claude"], default=None,
        help="If set, score both summaries and append them to "
        "eval/output/run_history.jsonl. Skipped by default.",
    )
    parser.add_argument(
        "--status-file", default=None,
        help=argparse.SUPPRESS,  # used by webapp/server.py to poll stage progress
    )
    args = parser.parse_args()

    on_stage = None
    if args.status_file:
        on_stage = lambda stage, detail=None: write_status(args.status_file, stage, detail)  # noqa: E731

    run_pipeline(
        regenerate=args.regenerate, provider=args.provider,
        judge_provider=args.judge_provider, on_stage=on_stage,
    )


if __name__ == "__main__":
    main()
