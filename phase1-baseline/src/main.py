import argparse
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from eval_scoring import evaluate_variant
from pipeline_status import write_status
from run_history import append_run
from summarize import summarize
from transcribe import transcribe

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
AUDIO_GENERATION_DIR = os.path.join(REPO_ROOT, "audio-generation")


def _load_meetings():
    # audio-generation/ isn't a valid Python package name (hyphen), so it's
    # loaded by file path — same technique eval/extraction_efficiency.py
    # already uses for the same reason.
    spec = importlib.util.spec_from_file_location(
        "_audio_generation_dialogues", os.path.join(AUDIO_GENERATION_DIR, "src", "dialogues.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MEETINGS


def run_pipeline(regenerate=False, provider=None, judge_provider=None, on_stage=None):
    """All 15 recordings come from audio-generation/output/<slug>/ (see its
    README) — this phase only transcribes and summarizes them, it doesn't
    generate its own audio.  `regenerate`, if set, forces re-transcription of
    every meeting (clears cached transcript.txt files); it can't regenerate
    the recordings themselves, which are audio-generation/'s to own.
    Stages: per meeting (detail = "<label> (N/15)"): 'transcribing',
    'summarizing', plus 'judging' when judge_provider is given (skipped by
    default).  'done' at the very end."""
    on_stage = on_stage or (lambda stage, detail=None: None)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    meetings = _load_meetings()

    if regenerate:
        for meeting in meetings:
            transcript_path = os.path.join(OUTPUT_DIR, meeting["slug"], "transcript.txt")
            if os.path.exists(transcript_path):
                os.remove(transcript_path)

    for i, meeting in enumerate(meetings, start=1):
        slug = meeting["slug"]
        meeting_dir = os.path.join(OUTPUT_DIR, slug)
        os.makedirs(meeting_dir, exist_ok=True)
        detail = f"{meeting['label']} ({i}/{len(meetings)})"
        recording_path = os.path.join(AUDIO_GENERATION_DIR, "output", slug, "recording.wav")

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

        summary_path = os.path.join(meeting_dir, "summary.txt")
        on_stage("summarizing", detail)
        print("Summarizing...")
        summary = summarize(transcript, provider=provider)
        with open(summary_path, "w") as f:
            f.write(summary)

        if judge_provider is not None:
            on_stage("judging", detail)
            print("Judging...")
            evaluation = evaluate_variant(transcript, summary, provider=judge_provider)
            append_run("phase1-baseline", "baseline", provider, judge_provider, transcript, summary,
                       evaluation, meeting=slug)

    print(f"\nDone. All {len(meetings)} meetings written under {OUTPUT_DIR}")
    on_stage("done")


def main():
    parser = argparse.ArgumentParser(
        description="15-meeting baseline pipeline: transcribe and summarize all meetings"
    )
    parser.add_argument(
        "--regenerate", action="store_true",
        help="Force re-transcription of every meeting (recordings themselves "
        "come from audio-generation/ and aren't regenerated here)",
    )
    parser.add_argument(
        "--provider", choices=["local", "mistral", "claude"], default=None,
        help="Summarization backend: local Qwen2.5 (default) or the Claude API. "
        "Falls back to the SUMMARY_PROVIDER env var, then 'local'.",
    )
    parser.add_argument(
        "--judge-provider", choices=["local", "mistral", "claude"], default=None,
        help="If set, score every meeting's summary and append it to "
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
