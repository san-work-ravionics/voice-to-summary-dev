import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from eval_scoring import evaluate_variant
from generate_dummy_audio import generate as generate_audio
from pipeline_status import write_status
from run_history import append_run
from summarize import summarize
from transcribe import transcribe

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
RECORDING_PATH = os.path.join(OUTPUT_DIR, "recording.wav")
TRANSCRIPT_PATH = os.path.join(OUTPUT_DIR, "transcript.txt")
SUMMARY_PATH = os.path.join(OUTPUT_DIR, "summary.txt")


def run_pipeline(regenerate=False, provider=None, judge_provider=None, on_stage=None):
    """Stages: 'recording', 'transcribing', 'summarizing', 'judging' (only
    when judge_provider is given — skipped by default), 'done'."""
    on_stage = on_stage or (lambda stage, detail=None: None)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    on_stage("recording")
    if regenerate or not os.path.exists(RECORDING_PATH):
        print("Generating dummy recording...")
        generate_audio(RECORDING_PATH)
    else:
        print(f"Using existing recording at {RECORDING_PATH}")

    on_stage("transcribing")
    print("\nTranscribing...")
    transcript = transcribe(RECORDING_PATH)
    with open(TRANSCRIPT_PATH, "w") as f:
        f.write(transcript)
    print("\n--- Transcript ---")
    print(transcript)

    on_stage("summarizing")
    print("\nSummarizing (context + checklist, 3-actor transcript)...")
    summary = summarize(transcript, provider=provider)
    with open(SUMMARY_PATH, "w") as f:
        f.write(summary)
    print("\n--- Summary ---")
    print(summary)

    if judge_provider is not None:
        on_stage("judging")
        print("\nJudging...")
        evaluation = evaluate_variant(transcript, summary, provider=judge_provider)
        append_run("phase3-assistant", "context_checklist_assistant", provider, judge_provider, transcript, summary, evaluation)

    on_stage("done")


def main():
    parser = argparse.ArgumentParser(description="Voice (3-actor, incl. AI assistant) -> transcript -> checklist-aware summary demo pipeline")
    parser.add_argument(
        "--regenerate", action="store_true",
        help="Regenerate the dummy recording even if one already exists",
    )
    parser.add_argument(
        "--provider", choices=["local", "mistral", "claude"], default=None,
        help="Summarization backend: local Qwen2.5 (default) or the Claude API. "
        "Falls back to the SUMMARY_PROVIDER env var, then 'local'.",
    )
    parser.add_argument(
        "--judge-provider", choices=["local", "mistral", "claude"], default=None,
        help="If set, score the resulting summary and append it to "
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
