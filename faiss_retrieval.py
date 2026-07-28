"""Shared FAISS + sentence-embedding retrieval backend, used by
phase7-reference-rag/src/retrieve.py and phase8-voice-query/src/corpus.py as
an alternative to their own TF-IDF scoring (see those files) — a real
embedding model + vector index, not a new dependency-light default. Kept
here, not duplicated per-phase, because loading the embedding model has real
cost (unlike TF-IDF's plain word counts) and both phases need the exact same
model/index-building logic, just over different, differently-shaped chunk
lists.

Both retrieval backends return chunks in the same shape
({"id", "source", ["path",] "text", "score"}), so callers can swap between
`--retrieval tfidf` and `--retrieval faiss` without touching anything
downstream of retrieval.
"""
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def build_index(chunks):
    """Embeds every chunk's text and builds a FAISS flat index over the
    normalized vectors (inner product on unit vectors = cosine similarity).
    Rebuilt fresh on every call, same as the TF-IDF index — no persisted
    index file, consistent with this project's "index at query time" design
    (the corpus is a few dozen short documents, not a production-scale
    knowledge base that would need incremental indexing)."""
    import faiss
    import numpy as np

    if not chunks:
        return {"index": None, "chunks": []}

    embedder = _get_embedder()
    vectors = embedder.encode([c["text"] for c in chunks], normalize_embeddings=True)
    vectors = np.asarray(vectors, dtype="float32")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return {"index": index, "chunks": chunks}


def query(index_data, text, top_k=5):
    import numpy as np

    chunks = index_data["chunks"]
    if not chunks or index_data["index"] is None:
        return []

    embedder = _get_embedder()
    query_vector = embedder.encode([text], normalize_embeddings=True)
    query_vector = np.asarray(query_vector, dtype="float32")

    k = min(top_k, len(chunks))
    scores, indices = index_data["index"].search(query_vector, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        chunk = chunks[idx]
        results.append({
            "id": chunk["id"], "source": chunk["source"],
            **({"path": chunk["path"]} if "path" in chunk else {}),
            "text": chunk["text"], "score": float(score),
        })
    return results
