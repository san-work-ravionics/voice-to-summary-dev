"""Append-only log of every voice-query run (see ../README.md), one JSON
object per line — same append-only JSONL design as the root run_history.py,
kept separate because a query's shape (question/answer/grounding) doesn't
match a summarization run's (transcript/summary/layer1/layer2). This is what
lets the Voice Query page show progress across providers ("Local Qwen" vs
"mistral" vs "claude") instead of only ever showing the latest run.
"""
import json
import os
import time

PHASE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(PHASE_ROOT, "output", "query_history.jsonl")


def append_query(query_id, provider, model_name, question, answer, top_k, timing, grounding, cost_usd,
                  retrieval_method="tfidf"):
    record = {
        "query_id": query_id,
        "timestamp": time.time(),
        "provider": provider,
        "model_name": model_name,
        "retrieval_method": retrieval_method,
        "question": question,
        "answer": answer,
        "top_k": top_k,
        "timing": timing,
        "grounding": grounding,
        "cost_usd": cost_usd,
    }
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def read_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    records = []
    with open(HISTORY_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    records.sort(key=lambda r: r.get("timestamp", 0))
    return records
