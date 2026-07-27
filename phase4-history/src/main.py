import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dialogues import MEETINGS
from eval_scoring import evaluate_variant
from generate_audio import generate_all
from llm_provider import build_generator
from pipeline_status import write_status
from run_history import append_run
from summarize import (
    extract_decisions_and_actions,
    summarize_baseline,
    summarize_with_context,
)
from transcribe import transcribe

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")


def run_pipeline(regenerate=False, provider=None, judge_provider=None, on_stage=None):
    """Stages: 'recording', then per meeting (detail = "Week N/5"):
    'transcribing', 'summarizing_baseline', 'summarizing_context', plus
    'judging_baseline'/'judging_context' when judge_provider is given
    (skipped by default). 'done' at the very end."""
    on_stage = on_stage or (lambda stage, detail=None: None)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if regenerate:
        for meeting in MEETINGS:
            meeting_dir = os.path.join(OUTPUT_DIR, f"meeting-{meeting['week']}")
            # Invalidate the transcript too — otherwise a regenerated
            # recording gets summarized from the previous (now stale)
            # transcript, since transcribing is skipped whenever a
            # transcript.txt already exists (see the loop below).
            for filename in ("recording.wav", "transcript.txt"):
                path = os.path.join(meeting_dir, filename)
                if os.path.exists(path):
                    os.remove(path)

    on_stage("recording")
    template = os.path.join(OUTPUT_DIR, "meeting-{week}", "recording.wav")
    print("Generating recordings...")
    recording_paths = generate_all(output_dir_template=template)

    generator = build_generator(provider)

    # Built up meeting by meeting, in order — meeting N's context-aware
    # summary is only ever given what meetings 1..N-1 actually produced, the
    # same way a person catching up from real meeting notes would be.
    history_entries = []

    for meeting, recording_path in zip(MEETINGS, recording_paths):
        week = meeting["week"]
        meeting_dir = os.path.join(OUTPUT_DIR, f"meeting-{week}")
        os.makedirs(meeting_dir, exist_ok=True)
        detail = f"{meeting['label']} ({week}/{len(MEETINGS)})"

        print(f"\n=== {meeting['label']} ===")

        transcript_path = os.path.join(meeting_dir, "transcript.txt")
        on_stage("transcribing", detail)
        if os.path.exists(transcript_path):
            print("Using existing transcript")
            with open(transcript_path) as f:
                transcript = f.read()
        else:
            print("Transcribing...")
            transcript = transcribe(recording_path)
            with open(transcript_path, "w") as f:
                f.write(transcript)

        on_stage("summarizing_baseline", detail)
        print("Summarizing (baseline, isolated)...")
        baseline_summary = summarize_baseline(transcript, generator)
        with open(os.path.join(meeting_dir, "summary_baseline.txt"), "w") as f:
            f.write(baseline_summary)

        if judge_provider is not None:
            on_stage("judging_baseline", detail)
            print("Judging (baseline)...")
            evaluation = evaluate_variant(transcript, baseline_summary, provider=judge_provider)
            append_run("phase4-history", "baseline", provider, judge_provider, transcript, baseline_summary,
                       evaluation, meeting=week)

        on_stage("summarizing_context", detail)
        print("Summarizing (with static context + running history)...")
        context_summary = summarize_with_context(transcript, history_entries, generator)
        with open(os.path.join(meeting_dir, "summary_with_context.txt"), "w") as f:
            f.write(context_summary)

        if judge_provider is not None:
            on_stage("judging_context", detail)
            print("Judging (with context)...")
            evaluation = evaluate_variant(transcript, context_summary, provider=judge_provider)
            append_run("phase4-history", "with_context", provider, judge_provider, transcript, context_summary,
                       evaluation, meeting=week)

        history_entries.append(f"{meeting['label']}: " + extract_decisions_and_actions(context_summary))

    print(f"\nDone. All 5 meetings written under {OUTPUT_DIR}")
    on_stage("done")


def main():
    parser = argparse.ArgumentParser(
        description="5-meeting story pipeline: baseline vs context+history-aware summarization"
    )
    parser.add_argument(
        "--regenerate", action="store_true",
        help="Regenerate all 5 recordings even if they already exist",
    )
    parser.add_argument(
        "--provider", choices=["local", "mistral", "claude"], default=None,
        help="Summarization backend: local Qwen2.5 (default) or the Claude API. "
        "Falls back to the SUMMARY_PROVIDER env var, then 'local'.",
    )
    parser.add_argument(
        "--judge-provider", choices=["local", "mistral", "claude"], default=None,
        help="If set, score every meeting's summaries and append them to "
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
