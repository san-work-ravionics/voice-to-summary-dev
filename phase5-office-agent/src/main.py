import argparse
import importlib.util
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
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
AUDIO_GENERATION_DIR = os.path.join(REPO_ROOT, "audio-generation")

# Matches audio-generation/src/dialogues.py's SPEAKER_NAMES.
SPEAKER_NAMES = {"A": "Jordan", "B": "Priya"}


def _load_meetings():
    """Load the MEETINGS list from audio-generation/src/dialogues.py.

    audio-generation/ isn't a valid Python package name (hyphen), so it's
    loaded by file path -- same technique eval/extraction_efficiency.py
    already uses for the same reason."""
    spec = importlib.util.spec_from_file_location(
        "_audio_generation_dialogues", os.path.join(AUDIO_GENERATION_DIR, "src", "dialogues.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MEETINGS


def redact(text):
    return _redact_names(text, speaker_names=SPEAKER_NAMES)


def _ensure_transcript(recording_path, transcript_path, regenerate, on_stage, detail=None):
    """Transcribe `recording_path` into `transcript_path` (cached unless
    `regenerate` is set).  Returns the transcript text."""
    on_stage("transcribing", detail)
    if regenerate or not os.path.exists(transcript_path):
        print("Transcribing...")
        text = transcribe(recording_path)
        with open(transcript_path, "w") as f:
            f.write(text)
    else:
        print("Using existing transcript")
    with open(transcript_path) as f:
        return f.read()


def run_agent_arm(transcript, condition, judge_provider, meeting_dir, slug):
    """Runs the office agent under a simulated network `condition`
    ('good'/'degraded'/'offline'), scores the resulting brief the same way
    every other scenario's summary is scored, and appends it to
    run_history.jsonl so it shows up next to Phases 2-4."""
    condition_dir = os.path.join(meeting_dir, condition)
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
            transcript, reply, evaluation, meeting=slug,
        )
        return record
    return None


def run_baseline_arm(transcript, judge_provider, meeting_dir, slug):
    """The existing single-shot phase1-baseline-style summarizer, run once
    with the same provider (claude) as the agent's 'good' condition, as the
    non-agentic point of comparison."""
    reply = summarize_baseline(transcript, provider="claude")
    with open(os.path.join(meeting_dir, "baseline_summary.txt"), "w") as f:
        f.write(reply)

    if judge_provider is not None:
        evaluation = evaluate_variant(transcript, reply, provider=judge_provider)
        record = append_run(
            "phase5-office-agent", "baseline", "claude", judge_provider,
            transcript, reply, evaluation, meeting=slug,
        )
        return record
    return None


def run_pipeline(conditions, regenerate=False, judge_provider="local",
                  skip_baseline=False, on_stage=None):
    """All 15 recordings come from audio-generation/output/<slug>/ -- this
    phase only transcribes and summarizes them, it doesn't generate its own
    audio.  For each meeting, baseline and agent arms run under every
    requested network condition ('good'/'degraded'/'offline').

    `regenerate`, if set, deletes cached transcript.txt files and
    re-transcribes every meeting; it can't regenerate the recordings
    themselves, which are audio-generation/'s to own.

    Stages (per meeting, detail = "<label> (N/15)"): 'transcribing',
    'baseline', 'agent_<condition>'; 'done' at the very end."""
    on_stage = on_stage or (lambda stage, detail=None: None)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    meetings = _load_meetings()

    # When regenerating, delete all cached transcripts up front so that
    # _ensure_transcript will re-transcribe each one.
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

        transcript = _ensure_transcript(recording_path, os.path.join(meeting_dir, "transcript.txt"),
                                        regenerate, on_stage, detail)

        if not skip_baseline:
            on_stage("baseline", detail)
            run_baseline_arm(transcript, judge_provider, meeting_dir, slug)

        for condition in conditions:
            on_stage(f"agent_{condition}", detail)
            run_agent_arm(transcript, condition, judge_provider, meeting_dir, slug)

    print(f"\nDone. All {len(meetings)} meetings written under {OUTPUT_DIR}")
    on_stage("done")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 5 -- office agent (Claude tool-use, standing in for "
        "Copilot Enterprise) vs. the single-shot baseline, across simulated "
        "network conditions.  All 15 meetings from audio-generation are "
        "processed.  Needs ANTHROPIC_API_KEY.",
    )
    parser.add_argument(
        "--network", choices=list(network_sim.CONDITIONS) + ["all"], default="all",
        help="Which simulated network condition(s) to run the agent under (default: all three).",
    )
    parser.add_argument(
        "--regenerate", action="store_true",
        help="Force re-transcription of every meeting (recordings themselves "
        "come from audio-generation/ and aren't regenerated here)",
    )
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
