"""
eval/run_eval.py
---------------------
A measurement harness, not a toy: it answers two separate questions.

  1. RETRIEVAL: for each of the four search modes (vector / keyword / hybrid /
     hybrid_rerank), what fraction of questions found a chunk from the right
     document in the top 5? This isolates the retrieval half of the system
     from the LLM, and is exactly the comparison Stage 5 set up.

  2. END TO END: using the real pipeline (hybrid_rerank, with query rewriting
     and a groundedness check), how often does the final ANSWER contain the
     expected phrase, how often is it marked grounded, and how fast is it?

Fill in eval_dataset.json with real questions from YOUR documents, then:

    python run_eval.py

Keep this simple: the point of an eval harness is that you are MEASURING
quality at all, not the sophistication of the metric. Phrase-containment is
a rough proxy for "correct", not a guarantee — always read a few answers
yourself before trusting the number.
"""

import json
import sys
import time
from pathlib import Path
from statistics import mean
import requests

BACKEND_URL = "http://localhost:8000"
DATASET_PATH = Path(__file__).parent / "eval_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results" / "latest_run.json"
RETRIEVAL_MODES = ["vector", "keyword", "hybrid", "hybrid_rerank"]
TOP_K = 5

def load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        dataset = json.load(f)
    if any(v.startswith("REPLACE ME") for item in dataset for v in item.values()):
        sys.exit(
            f"{DATASET_PATH} still has its placeholder rows. Replace them with real "
            "questions from your own documents before running the eval."
        )
    return dataset

def check_backend() -> None:
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        sys.exit(f"Could not reach the backend at {BACKEND_URL} ({exc}). Is `uvicorn` running?")

def eval_retrieval(dataset: list[dict]) -> dict:
    """For each mode, what fraction of questions retrieved a chunk from the expected file?"""
    recall = {mode: [] for mode in RETRIEVAL_MODES}
    for item in dataset:
        expected_file = item.get("expected_source_filename", "")
        if not expected_file or expected_file.startswith("REPLACE ME"):
            continue   # this question can't be scored for retrieval without a known source
        for mode in RETRIEVAL_MODES:
            resp = requests.post(
                f"{BACKEND_URL}/search",
                json={"query": item["question"], "top_k": TOP_K, "mode": mode},
                timeout=60,
            )
            hits = resp.json() if resp.status_code == 200 else []
            found = any(h["filename"] == expected_file for h in hits)
            recall[mode].append(found)
    return {mode: round(mean(hits), 3) if hits else None for mode, hits in recall.items()}

def eval_pipeline(dataset: list[dict]) -> dict:
    """Run the real, full /query pipeline and score the final answer."""
    results = []
    for item in dataset:
        question = item["question"]
        expected_phrase = item["expected_answer_contains"].lower()

        resp = requests.post(f"{BACKEND_URL}/query", json={"question": question}, timeout=60)
        if resp.status_code != 200:
            results.append({"question": question, "error": resp.text, "correct": False, "grounded": False})
            continue

        data = resp.json()
        answer = data.get("answer", "")
        results.append({
            "question": question,
            "answer": answer,
            "expected_phrase": item["expected_answer_contains"],
            "correct": expected_phrase in answer.lower(),
            "grounded": data.get("is_grounded"),
            "retrieval_degraded": data.get("retrieval_degraded", False),
            "latency_ms": data.get("trace", {}).get("total_ms", 0),
            "stage_ms": data.get("trace", {}).get("stages_ms", {}),
        })

    n = len(results)
    scored = [r for r in results if "error" not in r]
    return {
        "total_questions": n,
        "errors": n - len(scored),
        "accuracy_proxy": round(mean(r["correct"] for r in scored), 3) if scored else 0,
        "grounded_rate": round(mean(bool(r["grounded"]) for r in scored), 3) if scored else 0,
        "avg_latency_ms": round(mean(r["latency_ms"] for r in scored), 1) if scored else 0,
        "avg_stage_ms": {
            stage: round(mean(r["stage_ms"].get(stage, 0) for r in scored), 1)
            for stage in ["rewrite_query", "retrieve", "generate_answer", "check_groundedness"]
        } if scored else {},
        "results": results,
    }

def print_report(retrieval: dict, pipeline: dict) -> None:
    print("\n=== Retrieval comparison (Recall@%d: right document found in top %d?) ===" % (TOP_K, TOP_K))
    for mode in RETRIEVAL_MODES:
        value = retrieval[mode]
        label = f"{value * 100:5.1f}%" if value is not None else "  n/a"
        print(f"  {mode:<15s} {label}")
    if all(v is None for v in retrieval.values()):
        print("  (no questions had an expected_source_filename filled in - retrieval was not scored)")

    print("\n=== End-to-end pipeline (hybrid_rerank + query rewrite + groundedness check) ===")
    print(f"  Questions run       : {pipeline['total_questions']}  ({pipeline['errors']} errored)")
    print(f"  Accuracy (proxy)    : {pipeline['accuracy_proxy'] * 100:.1f}%")
    print(f"  Grounded rate       : {pipeline['grounded_rate'] * 100:.1f}%")
    print(f"  Avg total latency   : {pipeline['avg_latency_ms']:.0f} ms")
    if pipeline["avg_stage_ms"]:
        print("  Avg time per stage  :")
        for stage, ms in pipeline["avg_stage_ms"].items():
            print(f"    {stage:<20s} {ms:7.1f} ms")

    failures = [r for r in pipeline["results"] if not r.get("correct")]
    if failures:
        print(f"\n  {len(failures)} question(s) did not contain the expected phrase - see {RESULTS_PATH} for details:")
        for r in failures[:5]:
            print(f"    - {r['question']!r}")

    print(f"\nFull results written to {RESULTS_PATH}")

def run() -> None:
    check_backend()
    dataset = load_dataset()

    print(f"Running {len(dataset)} questions against {BACKEND_URL} ...")
    retrieval = eval_retrieval(dataset)
    pipeline = eval_pipeline(dataset)

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump({"retrieval_recall_at_5": retrieval, "pipeline": pipeline}, f, indent=2)

    print_report(retrieval, pipeline)

if __name__ == "__main__":
    run()