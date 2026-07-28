import importlib.util
import json
import os
import re
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "extraction_efficiency.json")

# Same heuristic every summarizer's system prompt is instructed to use for
# what counts as a commitment worth an Actions bullet — applied here to the
# SCRIPT instead of the transcript, to get a ground-truth commitment list
# independent of anything Whisper or the LLM produced.
# "let me know"/"let me see" are requests FOR information, not commitments
# TO do something — excluded so a line like small-talk's "let me know how
# the first episode is" doesn't get counted as a ground-truth action.
COMMITMENT_PATTERN = re.compile(r"\bi'll\b|\bi will\b|\blet me\b(?!\s+(know|see))", re.IGNORECASE)

VERSION_SCENARIOS = [
    {
        "id": "phase4-assistant", "dialogue_module": "phase4-assistant/src/generate_dummy_audio.py",
        "variants": [{"key": "context_checklist_assistant", "summary": "phase4-assistant/output/summary.txt"}],
    },
]

# phase1-baseline/phase2-checklist/phase3-context all summarize the exact
# same shared transcript (audio-generation/output/01-kickoff/) — one
# ground-truth commitment list computed once, reused for all three variants.
SHARED_KICKOFF_SCENARIOS = [
    {"id": "phase1-baseline", "variants": [{"key": "baseline", "summary": "phase1-baseline/output/summary.txt"}]},
    {"id": "phase2-checklist", "variants": [{"key": "context_checklist", "summary": "phase2-checklist/output/summary.txt"}]},
    {"id": "phase3-context", "variants": [
        {"key": "baseline", "summary": "phase3-context/output/summary_baseline.txt"},
        {"key": "with_context", "summary": "phase3-context/output/summary_with_context.txt"},
    ]},
]


def _load_module(path, unique_name):
    spec = importlib.util.spec_from_file_location(unique_name, os.path.join(PROJECT_ROOT, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTEXT_LOOKBACK_LINES = 4


def ground_truth_commitments(dialogue, exclude_speakers=("ASSISTANT",), lookback=CONTEXT_LOOKBACK_LINES):
    """A commitment line like "I'll ping legal today" is often the reply to
    a question that actually carries the substance ("could you confirm with
    legal whether the updated privacy language is approved?") — and the
    referent of a pronoun ("I'll ping THEM") can sit more than one turn back
    (e.g. "Where's legal on the privacy review?" / "Still reviewing." / "I'll
    ping them today."). Matching on too narrow a window under-counts real
    matches against a summary that (correctly) folds in that substance — so
    match_text includes up to `lookback` preceding lines, while `line` stays
    the literal commitment sentence for display."""
    commitments = []
    for idx, (speaker, line) in enumerate(dialogue):
        if speaker in exclude_speakers:
            continue
        if COMMITMENT_PATTERN.search(line):
            start = max(0, idx - lookback)
            context_text = " ".join(l for _, l in dialogue[start:idx])
            commitments.append({
                "speaker": speaker,
                "line": line,
                "match_text": f"{context_text} {line}".strip(),
            })
    return commitments


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
    return [l for l in collected if l and l.startswith(("-", "*"))]


_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "with",
    "this", "by", "will", "person", "we", "our", "let", "me",
}


def _normalize_words(text):
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _containment_ratio(bullet, gt_text):
    """Fraction of the (short, compressed) bullet's substantive words that
    are grounded somewhere in the (longer) ground-truth text — a plain
    symmetric overlap ratio unfairly penalizes summarization's compression,
    since the union grows with the ground truth's length while the bullet
    stays short."""
    wb, wg = _normalize_words(bullet), _normalize_words(gt_text)
    if not wb or not wg:
        return 0.0
    return len(wb & wg) / len(wb)


def match_commitments(ground_truth, generated_bullets, threshold=0.5):
    matched_gt = set()
    matched_bullets = set()
    matches = []

    for gi, gt in enumerate(ground_truth):
        best_bi, best_ratio = None, 0.0
        for bi, bullet in enumerate(generated_bullets):
            if bi in matched_bullets:
                continue
            ratio = _containment_ratio(bullet, gt["match_text"])
            if ratio > best_ratio:
                best_ratio = ratio
                best_bi = bi
        if best_bi is not None and best_ratio >= threshold:
            matched_gt.add(gi)
            matched_bullets.add(best_bi)
            matches.append({
                "ground_truth": ground_truth[gi]["line"],
                "ground_truth_speaker": ground_truth[gi]["speaker"],
                "generated_bullet": generated_bullets[best_bi],
                "overlap_ratio": round(best_ratio, 2),
            })

    recall = (len(matched_gt) / len(ground_truth)) if ground_truth else None
    precision = (len(matched_bullets) / len(generated_bullets)) if generated_bullets else None

    return {
        "recall": recall,
        "precision": precision,
        "ground_truth_count": len(ground_truth),
        "generated_count": len(generated_bullets),
        "matches": matches,
        "missed": [ground_truth[i] for i in range(len(ground_truth)) if i not in matched_gt],
        "extra": [generated_bullets[i] for i in range(len(generated_bullets)) if i not in matched_bullets],
    }


def _read(relative_path):
    with open(os.path.join(PROJECT_ROOT, relative_path)) as f:
        return f.read()


def main():
    scenarios_out = []
    dialogues_module = _load_module("audio-generation/src/dialogues.py", "_ee_audio_generation_dialogues")

    kickoff = next(m for m in dialogues_module.MEETINGS if m["slug"] == "01-kickoff")
    kickoff_ground_truth = ground_truth_commitments(kickoff["dialogue"])
    for scenario in SHARED_KICKOFF_SCENARIOS:
        variants_out = []
        for variant in scenario["variants"]:
            summary_text = _read(variant["summary"])
            bullets = extract_section(summary_text, "Actions")
            result = match_commitments(kickoff_ground_truth, bullets)
            variants_out.append({"variant": variant["key"], **result})
        scenarios_out.append({"id": scenario["id"], "variants": variants_out})

    for scenario in VERSION_SCENARIOS:
        mod = _load_module(scenario["dialogue_module"], f"_ee_{scenario['id']}")
        ground_truth = ground_truth_commitments(mod.DIALOGUE)
        variants_out = []
        for variant in scenario["variants"]:
            summary_text = _read(variant["summary"])
            bullets = extract_section(summary_text, "Actions")
            result = match_commitments(ground_truth, bullets)
            variants_out.append({"variant": variant["key"], **result})
        scenarios_out.append({"id": scenario["id"], "variants": variants_out})

    for meeting in dialogues_module.MEETINGS:
        slug = meeting["slug"]
        ground_truth = ground_truth_commitments(meeting["dialogue"])
        meeting_dir = os.path.join("phase6-history", "output", slug)
        variants_out = []
        for key, filename in (("baseline", "summary_baseline.txt"), ("with_context", "summary_with_context.txt")):
            summary_text = _read(os.path.join(meeting_dir, filename))
            bullets = extract_section(summary_text, "Actions")
            result = match_commitments(ground_truth, bullets)
            variants_out.append({"variant": key, **result})
        scenarios_out.append({"id": f"phase6-history-{slug}", "variants": variants_out})

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method_note": (
            "Ground truth: lines in the scripted dialogue matching the same "
            "commitment heuristic (\"I'll\"/\"I will\"/\"let me\") every "
            "summarizer's own system prompt is instructed to use for Actions "
            "bullets, excluding the AI Assistant's own lines in v4. Each "
            "commitment is matched against generated bullets using the "
            f"commitment line PLUS up to {CONTEXT_LOOKBACK_LINES} preceding "
            "lines as context (a commitment like \"I'll ping them\" often "
            "depends on a pronoun referent or question raised a turn or two "
            "earlier), via containment of the bullet's words in that context "
            "(>=0.5) — a deterministic heuristic, not another LLM judgment "
            "call. Known limitation: a referent raised even further back "
            "than the lookback window will still be missed."
        ),
        "scenarios": scenarios_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
