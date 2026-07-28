"""Indexes every transcript/summary this project has already produced into
retrievable chunks, for phase8-voice-query's voice Q&A.

Two retrieval backends, selected via `method`:
  - "tfidf" (default): pure-Python TF-IDF scoring, no vector DB, consistent
    with this project's original preference for deterministic,
    dependency-light mechanisms over heavier ML infra.
  - "faiss": real sentence embeddings + a FAISS index, via the shared
    ../../faiss_retrieval.py — kept as a second, comparable option rather
    than a replacement (see phase7-reference-rag/README.md for a worked
    example of where the two backends actually disagree).
"""
import glob
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import faiss_retrieval

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (glob pattern relative to PROJECT_ROOT, source label — "{basename}" is
# filled in from the matched path's parent directory name, for patterns
# with a wildcard directory component).
SOURCE_GLOBS = [
    ("phase1-baseline/output/transcript.txt", "phase1-baseline transcript"),
    ("phase1-baseline/output/summary.txt", "phase1-baseline summary"),
    ("phase2-checklist/output/transcript.txt", "phase2-checklist transcript"),
    ("phase2-checklist/output/summary.txt", "phase2-checklist summary"),
    ("phase3-context/output/transcript.txt", "phase3-context transcript"),
    ("phase3-context/output/summary_baseline.txt", "phase3-context summary (no context)"),
    ("phase3-context/output/summary_with_context.txt", "phase3-context summary (with context)"),
    ("phase4-assistant/output/transcript.txt", "phase4-assistant transcript"),
    ("phase4-assistant/output/summary.txt", "phase4-assistant summary"),
    ("phase5-office-agent/output/transcript.txt", "phase5-office-agent transcript"),
    ("phase5-office-agent/output/baseline_summary.txt", "phase5-office-agent baseline summary"),
    ("phase5-office-agent/output/*/agent_reply.txt", "phase5-office-agent {basename} agent reply"),
    ("phase6-history/output/*/transcript.txt", "phase6-history {basename} transcript"),
    ("phase6-history/output/*/summary_baseline.txt", "phase6-history {basename} summary (no history)"),
    ("phase6-history/output/*/summary_with_context.txt", "phase6-history {basename} summary (with history)"),
    ("phase7-reference-rag/output/transcript.txt", "phase7-reference-rag transcript"),
    ("phase7-reference-rag/output/summary_baseline.txt", "phase7-reference-rag summary (no references)"),
    ("phase7-reference-rag/output/summary_with_references.txt", "phase7-reference-rag summary (with references)"),
    ("custom/output/*/transcript.txt", "custom audio {basename} transcript"),
    ("custom/output/*/summary.txt", "custom audio {basename} summary"),
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "been", "being", "with", "that", "this", "it", "as",
    "at", "by", "we", "i", "you", "he", "she", "they", "will", "would", "can",
    "could", "so", "but", "if", "not", "do", "does", "did", "have", "has",
    "had", "our", "your", "their", "about", "just", "get", "got",
}
_WORD_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _iter_source_files():
    for pattern, label_template in SOURCE_GLOBS:
        abs_pattern = os.path.join(PROJECT_ROOT, pattern)
        for path in sorted(glob.glob(abs_pattern)):
            if "{basename}" in label_template:
                label = label_template.format(basename=os.path.basename(os.path.dirname(path)))
            else:
                label = label_template
            yield path, label


def _sentences(text):
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def _chunk_transcript(text, sentences_per_chunk=4):
    sents = _sentences(text)
    return [" ".join(sents[i:i + sentences_per_chunk]) for i in range(0, len(sents), sentences_per_chunk)]


def _chunk_markdown(text):
    """Splits a '## Heading' summary into one chunk per section, so
    retrieval can point at e.g. just the Actions of one meeting rather than
    the whole brief."""
    parts = re.split(r"(?m)^(#{1,6}\s+.+)$", text)
    chunks = []
    if parts[0].strip():
        chunks.append(parts[0].strip())
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        combined = f"{heading}\n{body}".strip()
        if combined:
            chunks.append(combined)
    return chunks or ([text.strip()] if text.strip() else [])


def build_corpus():
    """Returns a list of {"id", "source", "path", "text"} chunks over every
    transcript/summary file currently on disk — missing files (a phase that
    hasn't been run yet) are silently skipped, not an error."""
    chunks = []
    for path, source in _iter_source_files():
        try:
            with open(path) as f:
                text = f.read()
        except OSError:
            continue
        if not text.strip():
            continue
        is_summary = "summary" in os.path.basename(path) or "reply" in os.path.basename(path)
        pieces = _chunk_markdown(text) if is_summary else _chunk_transcript(text)
        for i, piece in enumerate(pieces):
            chunks.append({
                "id": f"{source}#{i}",
                "source": source,
                "path": os.path.relpath(path, PROJECT_ROOT),
                "text": piece,
            })
    return chunks


def _tokenize(text):
    return [t for t in _WORD_RE.findall(text.lower()) if len(t) > 1 and t not in STOPWORDS]


def build_index_tfidf(chunks):
    """Precomputes per-chunk token counts and corpus-wide IDF weights so
    query() is cheap to call repeatedly."""
    token_lists = [_tokenize(c["text"]) for c in chunks]
    doc_freq = Counter()
    for tokens in token_lists:
        doc_freq.update(set(tokens))

    n_docs = max(len(chunks), 1)
    idf = {term: math.log((n_docs + 1) / (freq + 1)) + 1 for term, freq in doc_freq.items()}

    indexed = []
    for chunk, tokens in zip(chunks, token_lists):
        indexed.append({**chunk, "_term_counts": Counter(tokens), "_length": len(tokens)})
    return {"chunks": indexed, "idf": idf}


def query_tfidf(index, question, top_k=5):
    """TF-IDF-ish scoring: sum of (term count in chunk * corpus IDF) over
    the question's terms, length-normalized so short, on-point chunks don't
    lose to long ones that merely happen to contain a query word once."""
    q_terms = _tokenize(question)
    scored = []
    for chunk in index["chunks"]:
        score = sum(chunk["_term_counts"].get(t, 0) * index["idf"].get(t, 0) for t in q_terms)
        if score <= 0:
            continue
        norm = math.sqrt(chunk["_length"] + 1)
        scored.append((score / norm, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {"id": c["id"], "source": c["source"], "path": c["path"], "text": c["text"], "score": s}
        for s, c in scored[:top_k]
    ]


def build_index(chunks, method="tfidf"):
    if method == "faiss":
        return faiss_retrieval.build_index(chunks)
    return build_index_tfidf(chunks)


def query(index, question, top_k=5, method="tfidf"):
    if method == "faiss":
        return faiss_retrieval.query(index, question, top_k=top_k)
    return query_tfidf(index, question, top_k=top_k)
