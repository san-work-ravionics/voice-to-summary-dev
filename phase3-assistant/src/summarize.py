import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from llm_provider import build_generator, generate as llm_generate
from redaction import redact_names as _redact_names

from checklist import CHECKLIST
from context import MEETING_CONTEXT
from generate_dummy_audio import SPEAKER_NAMES

BRIEF_SYSTEM_PROMPT = (
    "You summarize meeting transcripts into a structured, anonymized brief. "
    "You are given background context about the meeting before the "
    "transcript. Use that context only to correctly interpret what's being "
    "discussed (e.g. what project this is, what 'the review' refers to, "
    "what workstreams exist) — never state something as having happened or "
    "been decided unless it's actually in the transcript. "
    "The transcript has exactly two meeting participants, Person A and "
    "Person B, plus a third voice: an AI meeting assistant that periodically "
    "repeats back notes and gives a closing summary. The assistant's own "
    "remarks are not meeting content — never generate a Key Point, "
    "Decision, or Action from something only the assistant said; only "
    "Person A's and Person B's own statements count. Never use personal "
    "names, even if one appears in the transcript — refer to the two "
    "participants only as 'Person A' and 'Person B'. "
    "Respond in Markdown with exactly these four sections:\n"
    "## Topic\n(one line)\n"
    "## Key Points\n(bullet points)\n"
    "## Decisions\n(bullet points)\n"
    "## Actions\n(bullet points)\n"
    "For the Actions section: only list things Person A or Person B "
    "personally committed to do (phrases like 'I will', 'I'll', 'let me'). "
    "Every single bullet in Actions MUST start with either 'Person A: ' or "
    "'Person B: ' followed by what they committed to do — no exceptions, "
    "and no other prefix is allowed. Never attribute an action to a third "
    "party who is merely mentioned in conversation (e.g. legal, another "
    "team, another engineer, or the assistant itself); if a speaker says "
    "they'll contact or involve a third party, the bullet still starts "
    "with that speaker's label. "
    "Keep it concise. If a section has nothing to report, write a single "
    "bullet saying so."
)

# Checklist coverage is deliberately NOT another LLM call — see
# phase3-checklist's summarize.py for why (a small local model was unreliable at judging
# coverage across three different prompt framings). A plain keyword match
# against the transcript, quoting the matched sentence as evidence, is
# correct by construction for this known content.
def _split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


# A sentence that names a topic while saying it WASN'T discussed (e.g. the
# assistant recapping "budget wasn't discussed") must not itself count as
# coverage — the keyword is present, but only inside a denial of coverage.
# This matters more here than in phase3-checklist: the assistant explicitly names any
# missed checklist topic while explaining that it's missing.
NEGATION_PHRASES = [
    "wasn't discussed", "was not discussed", "isn't discussed", "is not discussed",
    "wasn't covered", "was not covered", "isn't covered", "is not covered",
    "wasn't mentioned", "was not mentioned", "isn't mentioned", "is not mentioned",
    "didn't come up", "did not come up", "doesn't come up", "does not come up",
    "not discussed", "not covered", "not mentioned",
]


def _check_checklist(transcript, checklist):
    sentences = _split_sentences(transcript)
    lines = []
    for topic, keywords in checklist:
        match = next(
            (
                s for s in sentences
                if any(kw in s.lower() for kw in keywords)
                and not any(neg in s.lower() for neg in NEGATION_PHRASES)
            ),
            None,
        )
        if match:
            lines.append(f'- Covered: {topic} — "{match}"')
        else:
            lines.append(f"- Not covered: {topic} — not mentioned in the transcript")
    return "\n".join(lines)


def redact_names(text, labels=None):
    return _redact_names(text, speaker_names=SPEAKER_NAMES, labels=labels)


def _generate(generator, system_prompt, user_content, max_new_tokens):
    reply = llm_generate(generator, system_prompt, user_content, max_new_tokens=max_new_tokens)
    return redact_names(reply)


def summarize(text, context=MEETING_CONTEXT, checklist=CHECKLIST, provider=None, model_name=None):
    redacted_transcript = redact_names(text)

    generator = build_generator(provider, model_name)

    brief = _generate(
        generator,
        BRIEF_SYSTEM_PROMPT,
        f"Meeting context:\n{context}\n\nTranscript:\n\n{redacted_transcript}",
        max_new_tokens=350,
    )

    checklist_coverage = _check_checklist(redacted_transcript, checklist)

    return f"{brief}\n\n## Checklist Coverage\n{checklist_coverage}"


def main():
    transcript_path = sys.argv[1] if len(sys.argv) > 1 else "output/transcript.txt"
    summary_path = "output/summary.txt"

    with open(transcript_path) as f:
        text = f.read()

    summary = summarize(text)

    os.makedirs(os.path.dirname(summary_path) or ".", exist_ok=True)
    with open(summary_path, "w") as f:
        f.write(summary)

    print(f"Summary written to {summary_path}")
    print(summary)


if __name__ == "__main__":
    main()
