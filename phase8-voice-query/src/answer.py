"""Grounded voice-query answering: answers a question using only the corpus
chunks retrieved for it — mirrors phase6-history's system-prompt discipline
of treating supplied context as something to interpret, never a source of
facts to invent beyond it.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from llm_provider import build_generator, generate as llm_generate

SYSTEM_PROMPT = (
    "You answer questions about a set of recorded meetings using ONLY the "
    "excerpts provided below — never invent facts, names, numbers, or "
    "events not present in them. Each excerpt is labeled with its source. "
    "If the excerpts don't contain enough information to answer, say "
    "\"I couldn't find that in the stored content.\" instead of guessing. "
    "Keep the answer concise (2-4 sentences) and mention which meeting or "
    "source it came from where useful."
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _format_excerpts(chunks):
    if not chunks:
        return "(no matching excerpts found)"
    return "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)


def answer_question(question, retrieved_chunks, provider=None, model_name=None):
    generator = build_generator(provider, model_name)
    user_content = f"Excerpts:\n\n{_format_excerpts(retrieved_chunks)}\n\nQuestion: {question}"
    reply = llm_generate(generator, SYSTEM_PROMPT, user_content, max_new_tokens=300)
    return reply.strip()


def grounding_score(answer_text, retrieved_chunks):
    """% of the answer's content words that also appear somewhere in the
    retrieved chunks — the same word-overlap technique as
    eval/story_probes.py's stale-action check, used here as the primary
    (deterministic, not LLM-judged) Grounding Score metric the roadmap
    asks for. An abstention ("I couldn't find that...") legitimately scores
    low since it isn't drawing on the excerpts at all — check `abstained`
    before reading a low score as a grounding failure."""
    abstained = "couldn't find that" in answer_text.lower()
    answer_words = [w for w in _WORD_RE.findall(answer_text.lower()) if len(w) > 2]
    if not answer_words:
        return {"score": None, "matched": 0, "total": 0, "abstained": abstained}

    source_words = set()
    for chunk in retrieved_chunks:
        source_words.update(_WORD_RE.findall(chunk["text"].lower()))

    matched = sum(1 for w in answer_words if w in source_words)
    return {
        "score": matched / len(answer_words),
        "matched": matched,
        "total": len(answer_words),
        "abstained": abstained,
    }
