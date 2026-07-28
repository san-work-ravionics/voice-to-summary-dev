import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from llm_provider import build_generator, generate as llm_generate
from redaction import redact_names as _redact_names

from retrieve import retrieve_for_transcript

_WORD_RE = re.compile(r"[a-z0-9]+")

# Matches audio-generation/src/dialogues.py's SPEAKER_NAMES — the source
# recording this phase transcribes (the shared kickoff meeting) is
# synthesized with these two voices, same as phases 1/2/3/5.
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
    "'Person B: ' followed by what they committed to do — no exceptions. "
    "Keep it concise. If a section has nothing to report, write a single "
    "bullet saying so."
)

BASELINE_SYSTEM_PROMPT = (
    "You summarize meeting transcripts into a structured, anonymized brief. "
    "You are only given this one transcript — no other project material. "
    + FORMAT_INSTRUCTIONS
)

# Unlike phase6-history's prior-meeting history (interpretation aid only,
# never a source of new facts), these reference excerpts are the project's
# own authoritative planning documents — it's correct to pull a specific
# fact from them (a vendor name, a numeric target, a compliance tier) into
# Key Points when the transcript raises that topic only in general terms.
# The one guardrail: never claim the transcript speakers said, decided, or
# discussed a specific detail themselves unless the transcript backs that up
# — attribute added facts to the reference material, not to the meeting.
REFERENCES_SYSTEM_PROMPT = (
    "You summarize meeting transcripts into a structured, anonymized brief. "
    "You are also given excerpts from the project's own reference documents "
    "(PRD, design spec, vendor integration doc). When the transcript raises "
    "a topic only in general terms, and a reference excerpt gives a "
    "specific fact about that same topic (e.g. a vendor name, a numeric "
    "target, a compliance requirement), you should add that specific fact "
    "to Key Points — but phrase it as reference-material context (e.g. "
    "'Per the PRD, the target is...'), never as something a speaker said or "
    "decided in this meeting. Do not add facts about topics the transcript "
    "never raises at all, even if a reference excerpt mentions them. "
    + FORMAT_INSTRUCTIONS
)


def redact_names(text, labels=None):
    return _redact_names(text, speaker_names=SPEAKER_NAMES, labels=labels)


def _format_excerpts(chunks):
    if not chunks:
        return "(no matching reference excerpts found)"
    return "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)


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


def summarize_with_references(text, retrieved_chunks, provider=None, model_name=None):
    redacted_transcript = redact_names(text)
    user_content = (
        f"Reference excerpts:\n\n{_format_excerpts(retrieved_chunks)}\n\n"
        f"Transcript:\n\n{redacted_transcript}"
    )
    return _generate(REFERENCES_SYSTEM_PROMPT, user_content, provider, model_name)


def retrieve_references(text, top_k=5, method="tfidf"):
    return retrieve_for_transcript(text, top_k=top_k, method=method)


def _content_words(text):
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) > 2}


def reference_grounding_score(baseline_text, with_references_text, retrieved_chunks):
    """% of the words that appear in the reference-grounded summary but NOT
    in the baseline (transcript-only) summary — the specifics the reference
    material is supposed to be adding — that also appear somewhere in the
    retrieved excerpts actually used to generate it. Same word-overlap
    technique as phase8-voice-query's grounding_score() and Phase 6's
    stale-action check, applied to a diff instead of a single answer: it's
    a proxy for "did the added content come from the reference docs" not a
    semantic fact-check, and it can't catch a hallucination that happens to
    reuse a word already present in the baseline summary.
    """
    added_words = _content_words(with_references_text) - _content_words(baseline_text)
    if not added_words:
        return {"score": None, "matched": 0, "total": 0}

    retrieved_words = set()
    for chunk in retrieved_chunks:
        retrieved_words.update(_content_words(chunk["text"]))

    matched = len(added_words & retrieved_words)
    return {"score": matched / len(added_words), "matched": matched, "total": len(added_words)}
