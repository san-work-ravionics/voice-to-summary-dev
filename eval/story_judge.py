import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge  # reuse build_judge_generator, run_judge, _parse_judge_json, split_brief_and_checklist

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "story", "output")
RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "story_results.json")

WEEKS = [1, 2, 3, 4, 5]

# Layer 2 (faithfulness/completeness/conciseness) reused unchanged from
# judge.py grades a summary against its own transcript in isolation — it
# can't tell whether a summary correctly used history, since it's never
# shown any. This "continuity" dimension is the story-specific addition:
# it's given the actual history alongside the transcript and summary, and
# grades whether cross-meeting callbacks were handled correctly.
CONTINUITY_JUDGE_PROMPT = (
    "You are evaluating whether a meeting summary correctly handles "
    "references to EARLIER meetings. You will be given: (1) a short history "
    "of what actually happened in prior meetings, (2) the transcript of the "
    "CURRENT meeting (which may reference the past, e.g. 'the issue from "
    "last week'), and (3) a summary of the current meeting to grade.\n"
    "Score continuity 1 (very poor) to 5 (excellent): a high score means the "
    "summary correctly reflects that something is a continuation, "
    "escalation, or resolution of a specific prior event when the "
    "transcript signals that, using only facts consistent with the provided "
    "history — not vague hand-waving, and not inventing specifics absent "
    "from both the transcript and the history. A summary that ignores an "
    "available, relevant piece of history where the transcript clearly "
    "calls back to it should score low.\n"
    "Respond with ONLY a single JSON object, no other text: "
    '{"continuity": <1-5>, "continuity_notes": "<one sentence>"}'
)


def _read(path):
    with open(path) as f:
        return f.read()


def _meeting_dir(week):
    return os.path.join(STORY_OUTPUT_DIR, f"meeting-{week}")


def _extract_decisions_and_actions(summary_text):
    decisions = judge_extract_section(summary_text, "Decisions")
    actions = judge_extract_section(summary_text, "Actions")
    parts = []
    if decisions:
        parts.append("Decisions: " + " ".join(decisions))
    if actions:
        parts.append("Actions: " + " ".join(actions))
    return " ".join(parts) if parts else "Nothing notable decided or committed to."


def judge_extract_section(text, heading_name):
    # Mirrors story/src/summarize.py's extract_section — reimplemented here
    # (rather than imported) so this eval script only depends on eval/judge.py,
    # not on story/src, keeping the two independently runnable.
    import re
    lines = text.split("\n")
    heading_re = re.compile(rf"^#{{1,6}}\s*{heading_name}\s*$", re.IGNORECASE)
    any_heading_re = re.compile(r"^#{1,6}\s+\S")
    start = None
    for i, line in enumerate(lines):
        if heading_re.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return []
    collected = []
    for line in lines[start:]:
        if any_heading_re.match(line.strip()):
            break
        collected.append(line.strip())
    return [l for l in collected if l]


def run_continuity_judge(generator, history_text, transcript, summary_text):
    messages = [
        {"role": "system", "content": CONTINUITY_JUDGE_PROMPT},
        {"role": "user", "content": (
            f"Prior history:\n{history_text}\n\n"
            f"Current transcript:\n{transcript}\n\n"
            f"Summary to grade:\n{summary_text}"
        )},
    ]
    output = generator(messages, max_new_tokens=200, do_sample=False)
    reply = output[0]["generated_text"][-1]["content"].strip()
    return judge._parse_judge_json(reply)


def score_layer2(generator, transcript, summary_text):
    brief_text, _ = judge.split_brief_and_checklist(summary_text)
    return judge.run_judge(generator, transcript, brief_text)


def score_layer1(summary_text):
    # Story summaries have no checklist section, so the whole file is brief
    # text — same deterministic schema/Actions-prefix checks judge.py already
    # runs for v1-v4, added here for "Structure & Format Control" parity
    # across every scenario in the project, not just v1-v4.
    return {
        "schema": judge.check_schema(summary_text),
        "actions": judge.check_actions_prefix(summary_text),
    }


def main():
    generator = judge.build_judge_generator()

    meetings_out = []
    # Built from each week's own actual context-aware summary, in order —
    # the same construction main.py used when generating, so the "ground
    # truth" history handed to the continuity judge matches what the
    # context-aware summarizer itself was actually given.
    history_entries = []

    for week in WEEKS:
        meeting_dir = _meeting_dir(week)
        label = f"Week {week}"
        transcript = _read(os.path.join(meeting_dir, "transcript.txt"))
        baseline_text = _read(os.path.join(meeting_dir, "summary_baseline.txt"))
        context_text = _read(os.path.join(meeting_dir, "summary_with_context.txt"))

        print(f"Judging {label}...")

        history_text = (
            "No prior meetings yet — this is the first one."
            if not history_entries
            else "\n".join(history_entries)
        )

        baseline_layer2 = score_layer2(generator, transcript, baseline_text)
        context_layer2 = score_layer2(generator, transcript, context_text)

        if history_entries:
            baseline_continuity = run_continuity_judge(generator, history_text, transcript, baseline_text)
            context_continuity = run_continuity_judge(generator, history_text, transcript, context_text)
        else:
            baseline_continuity = None
            context_continuity = None

        meetings_out.append({
            "week": week,
            "label": label,
            "baseline": {
                "layer1": score_layer1(baseline_text),
                "layer2": baseline_layer2,
                "continuity": baseline_continuity,
            },
            "with_context": {
                "layer1": score_layer1(context_text),
                "layer2": context_layer2,
                "continuity": context_continuity,
            },
        })

        history_entries.append(f"{label}: " + _extract_decisions_and_actions(context_text))

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": judge.DEFAULT_MODEL,
        "meetings": meetings_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
