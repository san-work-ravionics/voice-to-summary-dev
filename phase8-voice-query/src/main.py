import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from answer import answer_question, grounding_score
from corpus import build_corpus, build_index, query as query_index
from cost_estimate import estimate_cost_usd
from llm_provider import build_generator
from pipeline_status import write_status
from query_history import append_query
from transcription import transcribe

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")


def _next_query_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    nums = [
        int(name.split("-", 1)[1]) for name in os.listdir(OUTPUT_DIR)
        if name.startswith("query-") and name.split("-", 1)[1].isdigit()
    ]
    query_dir = os.path.join(OUTPUT_DIR, f"query-{max(nums, default=0) + 1}")
    os.makedirs(query_dir)
    return query_dir


def run_query(audio_path, provider=None, top_k=5, retrieval="tfidf", on_stage=None):
    """Transcribes the question audio, retrieves the most relevant chunks
    from everything this project has already produced (see corpus.py), and
    answers grounded in those chunks. `retrieval` selects "tfidf" (default)
    or "faiss" (real sentence embeddings + a vector index, see
    ../../faiss_retrieval.py) — a comparable option, not a replacement.
    Returns a dict with the answer, retrieved sources, per-stage timing, and
    a deterministic grounding score; also writes all of it to
    output/query-N/."""
    on_stage = on_stage or (lambda stage, detail=None: None)
    timings = {}
    t_total = time.time()

    on_stage("transcribing")
    t0 = time.time()
    question_text = transcribe(audio_path)
    timings["transcribe_s"] = time.time() - t0

    on_stage("retrieving")
    t0 = time.time()
    index = build_index(build_corpus(), method=retrieval)
    retrieved = query_index(index, question_text, top_k=top_k, method=retrieval)
    timings["retrieve_s"] = time.time() - t0

    # Resolved once here (rather than left to answer_question's own internal
    # build_generator call) so the exact provider/model that produced this
    # answer is known for logging — otherwise a "local" run and a "claude"
    # run would be indistinguishable in the saved output.
    generator = build_generator(provider)

    on_stage("answering")
    t0 = time.time()
    answer_text = answer_question(question_text, retrieved, provider=generator.provider, model_name=generator.model_name)
    timings["answer_s"] = time.time() - t0

    grounding = grounding_score(answer_text, retrieved)
    timings["total_s"] = time.time() - t_total
    cost = estimate_cost_usd(generator.provider, generator.model_name, question_text, answer_text)

    query_dir = _next_query_dir()
    query_id = os.path.basename(query_dir)
    with open(os.path.join(query_dir, "question_transcript.txt"), "w") as f:
        f.write(question_text)
    with open(os.path.join(query_dir, "answer.txt"), "w") as f:
        f.write(answer_text)
    with open(os.path.join(query_dir, "retrieved_chunks.json"), "w") as f:
        json.dump(retrieved, f, indent=2)
    with open(os.path.join(query_dir, "timing.json"), "w") as f:
        json.dump(timings, f, indent=2)
    with open(os.path.join(query_dir, "grounding.json"), "w") as f:
        json.dump(grounding, f, indent=2)
    with open(os.path.join(query_dir, "provider.json"), "w") as f:
        json.dump({
            "provider": generator.provider, "model_name": generator.model_name,
            "retrieval_method": retrieval, **cost,
        }, f, indent=2)

    append_query(
        query_id, generator.provider, generator.model_name, question_text, answer_text,
        top_k, timings, grounding, cost["cost_usd"], retrieval_method=retrieval,
    )

    on_stage("done")
    return {
        "query_dir": query_dir,
        "provider": generator.provider,
        "model_name": generator.model_name,
        "retrieval_method": retrieval,
        "question": question_text,
        "answer": answer_text,
        "retrieved": retrieved,
        "timing": timings,
        "grounding": grounding,
        "cost_usd": cost["cost_usd"],
    }


def main():
    parser = argparse.ArgumentParser(description="Phase 8 — ask a spoken question, get a grounded text answer")
    parser.add_argument("audio_path", help="Path to the question audio file (.wav/.mp3/.m4a/.ogg/.flac)")
    parser.add_argument("--provider", choices=["local", "mistral", "claude"], default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--retrieval", choices=["tfidf", "faiss"], default="tfidf",
        help="Retrieval backend: pure-Python TF-IDF (default) or a real "
        "FAISS vector index over sentence-transformers embeddings.",
    )
    parser.add_argument("--status-file", default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--result-file", default=None,
        help=argparse.SUPPRESS,  # used by webapp/server.py to read back the full result as JSON
    )
    args = parser.parse_args()

    on_stage = None
    if args.status_file:
        on_stage = lambda stage, detail=None: write_status(args.status_file, stage, detail)  # noqa: E731

    result = run_query(
        args.audio_path, provider=args.provider, top_k=args.top_k,
        retrieval=args.retrieval, on_stage=on_stage,
    )

    if args.result_file:
        with open(args.result_file, "w") as f:
            json.dump(result, f)

    print(f"\n--- Provider ---\n{result['provider']} ({result['model_name']}, retrieval={result['retrieval_method']})")
    print(f"\n--- Question ---\n{result['question']}")
    print(f"\n--- Answer ---\n{result['answer']}")
    print("\n--- Retrieved sources ---")
    for c in result["retrieved"]:
        print(f"  [{c['score']:.2f}] {c['source']}")
    print(f"\n--- Timing ---\n{json.dumps(result['timing'], indent=2)}")
    print(f"\n--- Grounding ---\n{json.dumps(result['grounding'], indent=2)}")
    print(f"\nWritten to {result['query_dir']}")


if __name__ == "__main__":
    main()
