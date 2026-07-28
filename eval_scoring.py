"""Shared summary-quality scoring, used by eval/judge.py (bulk offline scoring)
and by each scenario's main.py's run_pipeline() (automatic per-run scoring for
the webapp's Pipeline/Evaluation pages).

Two layers:
  - Layer 1 (deterministic): Markdown schema compliance, Actions-bullet
    prefix compliance, and checklist coverage precision/recall
    (phase2-checklist/phase4-assistant only).
  - Layer 2 (LLM-as-judge): faithfulness/completeness/conciseness, routed
    through llm_provider so the judge itself is local-or-Claude swappable.
"""
import json
import re

from llm_provider import build_generator, generate as llm_generate

# Ground truth for the shared kickoff dialogue used by phase1-baseline
# through phase4-assistant (see phase2-checklist/README.md): every checklist
# topic is actually discussed except budget/cost impact, which is left out
# on purpose so the "Not covered" path is exercised.
CHECKLIST_GROUND_TRUTH = {
    "Onboarding flow status": True,
    "Payments integration status": True,
    "Design updates (e.g. dark mode)": True,
    "Legal / privacy approval": True,
    "Analytics instrumentation": True,
    "Budget or cost impact": False,
    "Next meeting / follow-up schedule": True,
}

REQUIRED_HEADINGS = ["Topic", "Key Points", "Decisions", "Actions"]

# Deliberately does NOT judge checklist coverage — that's the deterministic
# layer-1 check below, kept separate because phase2-checklist's README already
# found a small model unreliable at that specific judgment.
JUDGE_SYSTEM_PROMPT = (
    "You are an evaluator grading a meeting summary against the transcript "
    "it was generated from. Score the summary on three dimensions, each on "
    "a 1 (very poor) to 5 (excellent) scale:\n"
    "- faithfulness: every claim in the summary is actually supported by "
    "the transcript, with no invented facts, numbers, or names.\n"
    "- completeness: the substantive points, decisions, and commitments "
    "actually present in the transcript are reflected in the summary.\n"
    "- conciseness: the summary avoids redundancy and irrelevant filler "
    "while still covering the substance.\n"
    "Respond with ONLY a single JSON object, no other text, in exactly "
    "this shape:\n"
    '{"faithfulness": <1-5>, "faithfulness_notes": "<one sentence>", '
    '"completeness": <1-5>, "completeness_notes": "<one sentence>", '
    '"conciseness": <1-5>, "conciseness_notes": "<one sentence>", '
    '"unsupported_claims": ["<quote from the summary not backed by the '
    'transcript>", ...]}'
)


def split_brief_and_checklist(summary_text):
    marker = re.search(r"^#{1,6}\s*Checklist Coverage\s*$", summary_text, re.MULTILINE)
    if not marker:
        return summary_text.strip(), None
    return summary_text[: marker.start()].strip(), summary_text[marker.end():].strip()


def check_schema(brief_text):
    lines = brief_text.splitlines()
    sections = {}
    for heading in REQUIRED_HEADINGS:
        pattern = re.compile(rf"^(#{{1,6}})\s*{re.escape(heading)}\s*$", re.IGNORECASE)
        found = next((pattern.match(l.strip()) for l in lines if pattern.match(l.strip())), None)
        sections[heading] = {
            "present": bool(found),
            "heading_level": len(found.group(1)) if found else None,
        }
    all_present = all(s["present"] for s in sections.values())
    heading_level_matches_spec = all(
        s["heading_level"] == 2 for s in sections.values() if s["present"]
    )
    return {
        "sections": sections,
        "all_sections_present": all_present,
        # The system prompt in every version specifies "## Topic" etc.
        # (heading level 2) exactly — flags summaries that drifted to "###".
        "heading_level_matches_spec": heading_level_matches_spec,
    }


def check_actions_prefix(brief_text):
    heading_match = re.search(r"^#{1,6}\s*Actions\s*$", brief_text, re.MULTILINE | re.IGNORECASE)
    if not heading_match:
        return {"checked": False, "compliant": None, "violations": []}

    rest = brief_text[heading_match.end():]
    next_heading = re.search(r"^#{1,6}\s+\S", rest, re.MULTILINE)
    section = rest[: next_heading.start()] if next_heading else rest

    bullets = [l.strip("-* ").strip() for l in section.splitlines() if l.strip().startswith(("-", "*"))]
    violations = []
    for bullet in bullets:
        lowered = bullet.lower()
        if lowered.startswith("person a:") or lowered.startswith("person b:"):
            continue
        if "no action" in lowered or "nothing to report" in lowered:
            continue
        violations.append(bullet)

    return {"checked": True, "bullets": bullets, "violations": violations, "compliant": len(violations) == 0}


def parse_checklist_section(checklist_text):
    items = {}
    for line in checklist_text.splitlines():
        m = re.match(r"-\s*(Covered|Not covered):\s*(.+?)\s*—\s*(.+)", line.strip())
        if m:
            status, topic, evidence = m.groups()
            items[topic.strip()] = {"covered": status == "Covered", "evidence": evidence.strip()}
    return items


def score_checklist(parsed_items):
    tp = fp = fn = tn = 0
    mismatches = []
    for topic, truth in CHECKLIST_GROUND_TRUTH.items():
        entry = parsed_items.get(topic)
        predicted = entry["covered"] if entry else None
        if predicted is None:
            mismatches.append({"topic": topic, "truth": truth, "predicted": None, "note": "topic missing from output"})
            continue
        if truth and predicted:
            tp += 1
        elif not truth and not predicted:
            tn += 1
        else:
            if predicted:
                fp += 1
            else:
                fn += 1
            mismatches.append({
                "topic": topic, "truth": truth, "predicted": predicted,
                "evidence": entry["evidence"],
            })
    total = tp + fp + fn + tn
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": (tp / (tp + fp)) if (tp + fp) else None,
        "recall": (tp / (tp + fn)) if (tp + fn) else None,
        "accuracy": ((tp + tn) / total) if total else None,
        "mismatches": mismatches,
    }


def _parse_judge_json(reply):
    try:
        return {**json.loads(reply), "raw": reply, "parse_error": False}
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if match:
        try:
            return {**json.loads(match.group(0)), "raw": reply, "parse_error": False}
        except json.JSONDecodeError:
            pass
    return {"raw": reply, "parse_error": True}


def judge_summary(transcript, brief_text, provider=None, model_name=None):
    generator = build_generator(provider, model_name)
    reply = llm_generate(
        generator,
        JUDGE_SYSTEM_PROMPT,
        f"Transcript:\n{transcript}\n\nSummary:\n{brief_text}",
        max_new_tokens=300,
    )
    return _parse_judge_json(reply)


def evaluate_variant(transcript, summary_text, provider=None, model_name=None):
    """provider/model_name select the JUDGE model — independent of whichever
    provider generated summary_text in the first place."""
    brief_text, checklist_text = split_brief_and_checklist(summary_text)

    result = {
        "layer1": {
            "schema": check_schema(brief_text),
            "actions": check_actions_prefix(brief_text),
        },
        "layer2": judge_summary(transcript, brief_text, provider=provider, model_name=model_name),
        "checklist": None,
    }

    if checklist_text:
        parsed = parse_checklist_section(checklist_text)
        result["checklist"] = score_checklist(parsed)

    return result
