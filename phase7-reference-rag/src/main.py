import argparse
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from eval_scoring import evaluate_variant
from pipeline_status import write_status
from run_history import append_run
from summarize import (
    reference_grounding_score,
    retrieve_references,
    summarize_baseline,
    summarize_with_references,
)
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


def run_pipeline(regenerate=False, provider=None, judge_provider=None, retrieval="tfidf", on_stage=None):
    """All 15 recordings come from audio-generation/output/<slug>/ — this
    phase only transcribes and summarizes them, it doesn't generate its own
    audio.  For each meeting a baseline summary (transcript only) is compared
    against a reference-grounded summary that incorporates excerpts retrieved
    from the project's reference documents.  `regenerate`, if set, forces
    re-transcription of every meeting (clears cached transcript.txt files);
    it can't regenerate the recordings themselves, which are
    audio-generation/'s to own.  `retrieval` selects "tfidf" (default) or
    "faiss" (real sentence embeddings + a vector index, see
    ../../faiss_retrieval.py) — kept as a comparable option, not a
    replacement.  Stages: per meeting (detail = "<label> (N/15)"):
    'transcribing', 'retrieving', 'summarizing_baseline',
    'summarizing_with_references', plus 'judging_baseline'/
    'judging_with_references' when judge_provider is given (skipped by
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

        # --- Transcribe (cached unless regenerate) ---
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

        # --- Retrieve reference-document excerpts ---
        on_stage("retrieving", detail)
        print(f"Retrieving relevant reference-document excerpts (method={retrieval})...")
        retrieved = retrieve_references(transcript, method=retrieval)
        with open(os.path.join(meeting_dir, "retrieved_references.json"), "w") as f:
            json.dump(retrieved, f, indent=2)

        # --- Baseline summary (transcript only) ---
        on_stage("summarizing_baseline", detail)
        print("Summarizing (baseline, transcript only)...")
        baseline = summarize_baseline(transcript, provider=provider)
        with open(os.path.join(meeting_dir, "summary_baseline.txt"), "w") as f:
            f.write(baseline)

        if judge_provider is not None:
            on_stage("judging_baseline", detail)
            print("Judging (baseline)...")
            evaluation = evaluate_variant(transcript, baseline, provider=judge_provider)
            append_run("phase7-reference-rag", "baseline", provider, judge_provider,
                       transcript, baseline, evaluation, meeting=slug)

        # --- Reference-grounded summary ---
        on_stage("summarizing_with_references", detail)
        print("Summarizing (with retrieved reference excerpts)...")
        with_references = summarize_with_references(transcript, retrieved, provider=provider)
        with open(os.path.join(meeting_dir, "summary_with_references.txt"), "w") as f:
            f.write(with_references)

        # Deterministic, not LLM-judged — computed unconditionally (cheap, no
        # generation call) unlike the faithfulness/completeness/conciseness
        # judge below, which only runs when --judge-provider is given.
        grounding = reference_grounding_score(baseline, with_references, retrieved)
        grounding["retrieval_method"] = retrieval
        with open(os.path.join(meeting_dir, "reference_grounding.json"), "w") as f:
            json.dump(grounding, f, indent=2)

        if judge_provider is not None:
            on_stage("judging_with_references", detail)
            print("Judging (with references)...")
            evaluation = evaluate_variant(transcript, with_references, provider=judge_provider)
            evaluation["reference_grounding"] = grounding
            evaluation["retrieval_method"] = retrieval
            append_run("phase7-reference-rag", "with_references", provider, judge_provider,
                       transcript, with_references, evaluation, meeting=slug)

    print(f"\nDone. All {len(meetings)} meetings written under {OUTPUT_DIR}")
    on_stage("done")


def main():
    parser = argparse.ArgumentParser(
        description="15-meeting story pipeline: baseline vs reference-document RAG summarization"
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
        help="If set, score every meeting's summaries and append them to "
        "eval/output/run_history.jsonl. Skipped by default.",
    )
    parser.add_argument(
        "--retrieval", choices=["tfidf", "faiss"], default="tfidf",
        help="Retrieval backend: pure-Python TF-IDF (default) or a real "
        "FAISS vector index over sentence-transformers embeddings.",
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
        judge_provider=args.judge_provider, retrieval=args.retrieval, on_stage=on_stage,
    )


if __name__ == "__main__":
    main()
