import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from llm_provider import build_generator, generate as llm_generate
from redaction import redact_names as _redact_names

# Matches audio-generation/src/dialogues.py's SPEAKER_NAMES.
SPEAKER_NAMES = {"A": "Jordan", "B": "Priya"}

SYSTEM_PROMPT = (
    "You summarize meeting transcripts into a structured, anonymized brief. "
    "There are exactly two speakers in the transcript. Never use personal "
    "names, even if one appears in the transcript — refer to the two "
    "speakers only as 'Person A' and 'Person B'. "
    "Respond in Markdown with exactly these four sections:\n"
    "## Topic\n(one line)\n"
    "## Key Points\n(bullet points)\n"
    "## Decisions\n(bullet points)\n"
    "## Actions\n(bullet points)\n"
    "For the Actions section: only list things one of the two speakers "
    "personally committed to do (phrases like 'I will', 'I'll', 'let me'). "
    "Every single bullet in Actions MUST start with either 'Person A: ' or "
    "'Person B: ' followed by what they committed to do — no exceptions, "
    "and no other prefix is allowed. Never attribute an action to a third "
    "party who is merely mentioned in conversation (e.g. legal, another "
    "team, another engineer); if a speaker says they'll contact or involve "
    "a third party, the bullet still starts with that speaker's label. "
    "Keep it concise. If a section has nothing to report, write a single "
    "bullet saying so."
)


def redact_names(text, labels=None):
    return _redact_names(text, speaker_names=SPEAKER_NAMES, labels=labels)


def summarize(text, provider=None, model_name=None):
    redacted_transcript = redact_names(text)

    generator = build_generator(provider, model_name)
    reply = llm_generate(
        generator,
        SYSTEM_PROMPT,
        f"Transcript:\n\n{redacted_transcript}",
        max_new_tokens=350,
    )

    # Belt-and-suspenders: redact again in case a name slipped into the output.
    return redact_names(reply)


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
