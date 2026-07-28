import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from llm_provider import build_generator, generate as llm_generate
from redaction import redact_names as _redact_names

from context import MEETING_CONTEXT

# Matches audio-generation/src/dialogues.py's SPEAKER_NAMES — the source
# recording every phase 1/2/3/5 transcribes is synthesized with these two
# voices (see ../../audio-generation/README.md).
SPEAKER_NAMES = {"A": "Jordan", "B": "Priya"}

FORMAT_INSTRUCTIONS = (
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

BASELINE_SYSTEM_PROMPT = (
    "You summarize meeting transcripts into a structured, anonymized brief. "
    + FORMAT_INSTRUCTIONS
)

CONTEXT_SYSTEM_PROMPT = (
    "You summarize meeting transcripts into a structured, anonymized brief. "
    "You are given background context about the meeting before the "
    "transcript. Use that context only to correctly interpret what's being "
    "discussed (e.g. what project this is, what 'the review' refers to, "
    "what workstreams exist) — never state something as having happened or "
    "been decided unless it's actually in the transcript. "
    + FORMAT_INSTRUCTIONS
)


def redact_names(text, labels=None):
    return _redact_names(text, speaker_names=SPEAKER_NAMES, labels=labels)


def _generate(system_prompt, user_content, provider, model_name):
    generator = build_generator(provider, model_name)
    reply = llm_generate(generator, system_prompt, user_content, max_new_tokens=350)
    return redact_names(reply)


def summarize_baseline(text, provider=None, model_name=None):
    redacted_transcript = redact_names(text)
    return _generate(
        BASELINE_SYSTEM_PROMPT,
        f"Transcript:\n\n{redacted_transcript}",
        provider,
        model_name,
    )


def summarize_with_context(text, context=MEETING_CONTEXT, provider=None, model_name=None):
    redacted_transcript = redact_names(text)
    return _generate(
        CONTEXT_SYSTEM_PROMPT,
        f"Meeting context:\n{context}\n\nTranscript:\n\n{redacted_transcript}",
        provider,
        model_name,
    )


def main():
    transcript_path = sys.argv[1] if len(sys.argv) > 1 else "output/transcript.txt"
    output_dir = "output"

    with open(transcript_path) as f:
        text = f.read()

    baseline = summarize_baseline(text)
    with_context = summarize_with_context(text)

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "summary_baseline.txt"), "w") as f:
        f.write(baseline)
    with open(os.path.join(output_dir, "summary_with_context.txt"), "w") as f:
        f.write(with_context)

    print("--- Baseline summary (no context) ---")
    print(baseline)
    print("\n--- Context-aware summary ---")
    print(with_context)


if __name__ == "__main__":
    main()
