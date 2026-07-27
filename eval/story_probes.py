import json
import os
import re
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# judge.py used to expose build_judge_generator/_parse_judge_json directly;
# it was refactored to delegate to eval_scoring.py. Probes reuse one
# generator across every week/probe to avoid reloading the local model
# repeatedly, so this calls llm_provider/eval_scoring directly.
from llm_provider import build_generator, generate as llm_generate  # noqa: E402
from eval_scoring import _parse_judge_json  # noqa: E402

STORY_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "phase4-history", "output")
RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "story_probes.json")

WEEKS = [1, 2, 3, 4, 5]

# Distinct per-week small-talk words (see phase4-history/src/dialogues.py) that never
# appear in the real project content — a plain substring check is exact here,
# unlike the holistic 1-5 rubric that couldn't reliably tell variants apart.
NOISE_KEYWORDS = [
    "weather", "rainy", "series", "episode", "game last night", "coffee",
    "traffic", "weekend",
]

# Specific, verifiable yes/no questions rather than a holistic quality score.
# These are "control" probes both variants are expected to pass (the fact is
# stated plainly in the current transcript) — used as a sanity check that
# the judge isn't just rubber-stamping everything "yes".
#
# The two probes originally here for week 3 (dark-mode/legal conflation) and
# week 5 (stale-action carryover) were REMOVED after this same small judge
# model got both wrong on manual verification — it answered "pass" for both
# known, reproduced defects, even reading the exact same text a human could
# see was wrong. See check_conflation()/check_stale_actions() below: the same
# checks, done deterministically instead, the way v3's checklist coverage
# already does for the identical reason.
PROBES = {
    2: [
        {
            "id": "w2_escalation",
            "question": (
                "Does the summary correctly convey that the payments sandbox "
                "instability got WORSE this week (an escalation), rather than "
                "just describing a generic ongoing issue?"
            ),
            "expected": "yes",
        },
    ],
    4: [
        {
            "id": "w4_resolution",
            "question": (
                "Does the summary correctly convey that the payments sandbox "
                "instability, previously an ongoing problem, is now RESOLVED "
                "(not still ongoing)?"
            ),
            "expected": "yes",
        },
    ],
    5: [
        {
            "id": "w5_budget_gap",
            "question": (
                "Does the summary correctly reflect that budget/cost impact "
                "was raised as something that still needs to be addressed "
                "separately, rather than already resolved or not mentioned "
                "at all?"
            ),
            "expected": "yes",
        },
    ],
}

DARK_MODE_KEYWORD = "dark mode"
LEGAL_KEYWORDS = ("legal", "privacy")


def check_conflation(summary_text):
    """Week 3 check: flag any single bullet/line that mentions dark mode and
    legal/privacy together — the exact shape of the reproduced defect (e.g.
    "Legal review for dark mode needs attention"), which is otherwise two
    unrelated workstreams."""
    hits = []
    for line in summary_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        lowered = line.lower()
        if DARK_MODE_KEYWORD in lowered and any(kw in lowered for kw in LEGAL_KEYWORDS):
            hits.append(line)
    return {"conflated": bool(hits), "offending_lines": hits}


def extract_section(text, heading_name):
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


def _extract_decisions_and_actions(summary_text):
    decisions = extract_section(summary_text, "Decisions")
    actions = extract_section(summary_text, "Actions")
    parts = []
    if decisions:
        parts.append("Decisions: " + " ".join(decisions))
    if actions:
        parts.append("Actions: " + " ".join(actions))
    return " ".join(parts) if parts else "Nothing notable decided or committed to."


_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "with",
    "this", "by", "will", "person", "we", "our", "get", "provide", "start",
    "finish", "still", "already", "week",
}


def _normalize_words(text):
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _overlap_ratio(a, b):
    wa, wb = _normalize_words(a), _normalize_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def check_stale_actions(summary_text, history_entries, threshold=0.35):
    """Week 5 check: flag any current-meeting Actions bullet that closely
    repeats a phrase already recorded as an action in a PRIOR meeting's
    history — a verbatim/near-verbatim carryover suggests already-resolved
    work is being presented as newly pending, rather than the history being
    used only to interpret the current transcript."""
    history_action_phrases = []
    for entry in history_entries:
        m = re.search(r"Actions:\s*(.+)$", entry)
        if m:
            history_action_phrases.append(m.group(1).strip())

    current_bullets = extract_section(summary_text, "Actions")
    matches = []
    for bullet in current_bullets:
        for hist_phrase in history_action_phrases:
            ratio = _overlap_ratio(bullet, hist_phrase)
            if ratio >= threshold:
                matches.append({
                    "current_bullet": bullet,
                    "matched_history_phrase": hist_phrase,
                    "overlap_ratio": round(ratio, 2),
                })
    return {"stale": bool(matches), "matches": matches}

PROBE_JUDGE_PROMPT = (
    "You are fact-checking a meeting summary against the transcript it was "
    "generated from. You will be given the transcript, a summary, and a "
    "yes/no question about that summary. Answer strictly based on what the "
    "summary actually says (use the transcript only to check whether the "
    "summary's claims are accurate) — do not answer based on what you think "
    "would be ideal.\n"
    "Respond with ONLY a single JSON object, no other text: "
    '{"answer": "yes" or "no", "rationale": "<one sentence>"}'
)


def _read(path):
    with open(path) as f:
        return f.read()


def _meeting_dir(week):
    return os.path.join(STORY_OUTPUT_DIR, f"meeting-{week}")


def check_noise_leakage(summary_text):
    lowered = summary_text.lower()
    hits = [kw for kw in NOISE_KEYWORDS if kw in lowered]
    return {"leaked": bool(hits), "keywords_found": hits}


def run_probe(generator, transcript, summary_text, question):
    reply = llm_generate(
        generator, PROBE_JUDGE_PROMPT,
        f"Transcript:\n{transcript}\n\nSummary:\n{summary_text}\n\nQuestion: {question}",
        max_new_tokens=150,
    )
    return _parse_judge_json(reply)


def _answer_is_yes(parsed):
    return str(parsed.get("answer", "")).strip().lower().startswith("y")


def main():
    generator = build_generator()

    weeks_out = []
    history_entries = []  # built the same way phase4-history/src/main.py does, week by week

    for week in WEEKS:
        meeting_dir = _meeting_dir(week)
        transcript = _read(os.path.join(meeting_dir, "transcript.txt"))
        baseline_text = _read(os.path.join(meeting_dir, "summary_baseline.txt"))
        context_text = _read(os.path.join(meeting_dir, "summary_with_context.txt"))

        print(f"Week {week}: checking noise leakage...")
        noise = {
            "baseline": check_noise_leakage(baseline_text),
            "with_context": check_noise_leakage(context_text),
        }

        deterministic_checks = {}
        if week == 3:
            print(f"Week {week}: checking dark-mode/legal conflation (deterministic)...")
            deterministic_checks["conflation"] = {
                "baseline": check_conflation(baseline_text),
                "with_context": check_conflation(context_text),
            }
        if week == 5:
            print(f"Week {week}: checking stale-action carryover (deterministic)...")
            deterministic_checks["stale_actions"] = {
                "baseline": check_stale_actions(baseline_text, history_entries),
                "with_context": check_stale_actions(context_text, history_entries),
            }

        probes_out = []
        for probe in PROBES.get(week, []):
            print(f"Week {week}: probe {probe['id']}...")
            baseline_answer = run_probe(generator, transcript, baseline_text, probe["question"])
            context_answer = run_probe(generator, transcript, context_text, probe["question"])

            expected_yes = probe["expected"] == "yes"
            baseline_pass = _answer_is_yes(baseline_answer) == expected_yes
            context_pass = _answer_is_yes(context_answer) == expected_yes

            probes_out.append({
                "id": probe["id"],
                "question": probe["question"],
                "expected": probe["expected"],
                "baseline": {**baseline_answer, "pass": baseline_pass},
                "with_context": {**context_answer, "pass": context_pass},
            })

        weeks_out.append({
            "week": week,
            "label": f"Week {week}",
            "noise": noise,
            "deterministic_checks": deterministic_checks,
            "probes": probes_out,
        })

        history_entries.append(f"Week {week}: " + _extract_decisions_and_actions(context_text))

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": generator.model_name,
        "noise_keywords": NOISE_KEYWORDS,
        "weeks": weeks_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
