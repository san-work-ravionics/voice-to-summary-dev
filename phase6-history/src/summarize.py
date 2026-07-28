import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from llm_provider import build_generator, generate as llm_generate
from redaction import redact_names as _redact_names

from context import STATIC_CONTEXT, build_history_block

# Matches audio-generation/src/dialogues.py's SPEAKER_NAMES — every meeting
# this phase transcribes comes from audio-generation/output/<slug>/.
SPEAKER_NAMES = {"A": "Jordan", "B": "Priya"}

BASELINE_SYSTEM_PROMPT = (
    "You summarize meeting transcripts into a structured, anonymized brief. "
    "You are only given this one transcript in isolation — you have no "
    "information about any other meeting. There are exactly two speakers in "
    "the transcript. Never use personal names, even if one appears in the "
    "transcript — refer to the two speakers only as 'Person A' and "
    "'Person B'. "
    "Respond in Markdown with exactly these four sections:\n"
    "## Topic\n(one line)\n"
    "## Key Points\n(bullet points)\n"
    "## Decisions\n(bullet points)\n"
    "## Actions\n(bullet points)\n"
    "For the Actions section: only list things one of the two speakers "
    "personally committed to do (phrases like 'I will', 'I'll', 'let me'). "
    "Every single bullet in Actions MUST start with either 'Person A: ' or "
    "'Person B: ' followed by what they committed to do — no exceptions. "
    "Keep it concise. If a section has nothing to report, write a single "
    "bullet saying so."
)

# Unlike the baseline prompt, this one is given the project's static
# background AND a running history of prior meetings, specifically so it can
# correctly interpret callbacks ("the sandbox issue from week one") as
# continuations of something already known, rather than either ignoring them
# or treating them as new unexplained information.
CONTEXT_SYSTEM_PROMPT = (
    "You summarize meeting transcripts into a structured, anonymized brief. "
    "You are given background context about the overall project, and a "
    "history of what happened in prior weekly meetings, before the current "
    "transcript. Use both only to correctly interpret what's being discussed "
    "in THIS transcript — e.g. recognizing that something mentioned here is "
    "a continuation, escalation, or resolution of an issue from an earlier "
    "week. Never state that something happened, was decided, or was "
    "resolved in THIS meeting unless the current transcript actually says "
    "so — the history is for interpretation only, not a source of new facts "
    "to add. There are exactly two speakers in the transcript. Never use "
    "personal names, even if one appears in the transcript — refer to the "
    "two speakers only as 'Person A' and 'Person B'. "
    "Respond in Markdown with exactly these four sections:\n"
    "## Topic\n(one line)\n"
    "## Key Points\n(bullet points)\n"
    "## Decisions\n(bullet points)\n"
    "## Actions\n(bullet points)\n"
    "For the Actions section: only list things one of the two speakers "
    "personally committed to do (phrases like 'I will', 'I'll', 'let me'). "
    "Every single bullet in Actions MUST start with either 'Person A: ' or "
    "'Person B: ' followed by what they committed to do — no exceptions. "
    "Keep it concise. If a section has nothing to report, write a single "
    "bullet saying so."
)


def redact_names(text, labels=None):
    return _redact_names(text, speaker_names=SPEAKER_NAMES, labels=labels)


def _generate(generator, system_prompt, user_content, max_new_tokens=350):
    reply = llm_generate(generator, system_prompt, user_content, max_new_tokens=max_new_tokens)
    return redact_names(reply)


def summarize_baseline(text, generator):
    redacted_transcript = redact_names(text)
    return _generate(generator, BASELINE_SYSTEM_PROMPT, f"Transcript:\n\n{redacted_transcript}")


def summarize_with_context(text, history_entries, generator, context=STATIC_CONTEXT):
    redacted_transcript = redact_names(text)
    history_block = build_history_block(history_entries)
    user_content = (
        f"Project background:\n{context}\n\n"
        f"{history_block}\n\n"
        f"Current meeting transcript:\n\n{redacted_transcript}"
    )
    return _generate(generator, CONTEXT_SYSTEM_PROMPT, user_content)


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


def extract_decisions_and_actions(summary_text):
    """Pulls just the Decisions + Actions bullets out of a context-aware
    summary, to fold into the next meeting's history. Deliberately excludes
    Key Points/Topic — the running history is meant to be a record of what
    was decided/committed to, not a re-statement of everything discussed."""
    decisions = extract_section(summary_text, "Decisions")
    actions = extract_section(summary_text, "Actions")
    parts = []
    if decisions:
        parts.append("Decisions: " + " ".join(decisions))
    if actions:
        parts.append("Actions: " + " ".join(actions))
    return " ".join(parts) if parts else "Nothing notable decided or committed to."
