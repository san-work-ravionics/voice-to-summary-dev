import argparse
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
# See phase1-baseline/src/main.py — same shared kickoff recording, so this
# phase's baseline-vs-references comparison is directly comparable to the
# other single-meeting phases rather than needing its own recording.
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
SOURCE_RECORDING = os.path.join(REPO_ROOT, "audio-generation", "output", "01-kickoff", "recording.wav")
TRANSCRIPT_PATH = os.path.join(OUTPUT_DIR, "transcript.txt")
BASELINE_SUMMARY_PATH = os.path.join(OUTPUT_DIR, "summary_baseline.txt")
REFERENCES_SUMMARY_PATH = os.path.join(OUTPUT_DIR, "summary_with_references.txt")
RETRIEVED_REFERENCES_PATH = os.path.join(OUTPUT_DIR, "retrieved_references.json")
REFERENCE_GROUNDING_PATH = os.path.join(OUTPUT_DIR, "reference_grounding.json")


def run_pipeline(regenerate=False, provider=None, judge_provider=None, retrieval="tfidf", on_stage=None):
    """`regenerate` is accepted for CLI/webapp parity but has no effect —
    see phase1-baseline/src/main.py. `retrieval` selects "tfidf" (default)
    or "faiss" (real sentence embeddings + a vector index, see
    ../../faiss_retrieval.py) — kept as a comparable option, not a
    replacement. Stages: 'transcribing', 'retrieving',
    'summarizing_baseline', 'judging_baseline', 'summarizing_with_references',
    'judging_with_references' (judging stages only when judge_provider is
    given, skipped by default), 'done'."""
    on_stage = on_stage or (lambda stage, detail=None: None)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    on_stage("transcribing")
    print("\nTranscribing...")
    transcript = transcribe(SOURCE_RECORDING)
    with open(TRANSCRIPT_PATH, "w") as f:
        f.write(transcript)
    print("\n--- Transcript ---")
    print(transcript)

    on_stage("retrieving")
    print(f"\nRetrieving relevant reference-document excerpts (method={retrieval})...")
    retrieved = retrieve_references(transcript, method=retrieval)
    with open(RETRIEVED_REFERENCES_PATH, "w") as f:
        json.dump(retrieved, f, indent=2)

    on_stage("summarizing_baseline")
    print("\nSummarizing (baseline, transcript only)...")
    baseline = summarize_baseline(transcript, provider=provider)
    with open(BASELINE_SUMMARY_PATH, "w") as f:
        f.write(baseline)

    if judge_provider is not None:
        on_stage("judging_baseline")
        print("Judging (baseline)...")
        evaluation = evaluate_variant(transcript, baseline, provider=judge_provider)
        append_run("phase7-reference-rag", "baseline", provider, judge_provider, transcript, baseline, evaluation)

    on_stage("summarizing_with_references")
    print("Summarizing (with retrieved reference excerpts)...")
    with_references = summarize_with_references(transcript, retrieved, provider=provider)
    with open(REFERENCES_SUMMARY_PATH, "w") as f:
        f.write(with_references)

    # Deterministic, not LLM-judged — computed unconditionally (cheap, no
    # generation call) unlike the faithfulness/completeness/conciseness
    # judge below, which only runs when --judge-provider is given.
    grounding = reference_grounding_score(baseline, with_references, retrieved)
    grounding["retrieval_method"] = retrieval
    with open(REFERENCE_GROUNDING_PATH, "w") as f:
        json.dump(grounding, f, indent=2)

    if judge_provider is not None:
        on_stage("judging_with_references")
        print("Judging (with references)...")
        evaluation = evaluate_variant(transcript, with_references, provider=judge_provider)
        evaluation["reference_grounding"] = grounding
        evaluation["retrieval_method"] = retrieval
        append_run("phase7-reference-rag", "with_references", provider, judge_provider,
                   transcript, with_references, evaluation)

    print("\n--- Baseline summary (transcript only) ---")
    print(baseline)
    print("\n--- Reference-grounded summary ---")
    print(with_references)
    print(f"\n--- Reference Grounding Score ---\n{json.dumps(grounding, indent=2)}")

    on_stage("done")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 7 — voice -> transcript -> summary demo pipeline (reference-document RAG comparison)"
    )
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
