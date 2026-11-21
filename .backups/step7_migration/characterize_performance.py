"""Performance Characterization Benchmark Harness for Milestone M8.

Compares retrieval quality and latency trade-offs across 4 distinct configurations:
1. Config 1: Sparse-Only (Okapi BM25)
2. Config 2: Dense-Only (Vector Cosine Sim)
3. Config 3: Hybrid Fusion (BM25 + Dense RRF)
4. Config 4: Hybrid Fusion + Tutor Reranker

Computes:
- Latency: p50 (median), p95, p99, mean latency in milliseconds.
- Retrieval Quality: Recall@1, Recall@3, Recall@5, MRR.
- Outputs structured JSON report to benchmark/results/performance_characterization.json.
"""
import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Tuple

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmark.run_eval import evaluate_retrieval
from retrieval.retriever import TutorRetriever


def compute_percentiles(latencies: List[float]) -> Dict[str, float]:
    """Computes p50, p95, p99, and mean latency in milliseconds."""
    if not latencies:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "mean_ms": 0.0}

    s = sorted(latencies)
    n = len(s)

    def _idx(pct: float) -> int:
        return min(n - 1, max(0, int(round((pct / 100.0) * n)) - 1))

    return {
        "p50_ms": round(s[_idx(50)] * 1000.0, 2),
        "p95_ms": round(s[_idx(95)] * 1000.0, 2),
        "p99_ms": round(s[_idx(99)] * 1000.0, 2),
        "mean_ms": round((sum(s) / n) * 1000.0, 2),
    }


def evaluate_configuration(
    retriever: TutorRetriever,
    cases: List[Dict[str, Any]],
    top_k: int = 5,
    warmup_runs: int = 5,
) -> Dict[str, Any]:
    """Measures latency percentiles and retrieval recall/MRR for a specific retriever setup."""
    # Warmup runs to initialize caches
    for i in range(min(warmup_runs, len(cases))):
        retriever.retrieve(cases[i]["question"], top_k=top_k)

    latencies: List[float] = []
    total_r1, total_r3, total_r5, total_mrr = 0.0, 0.0, 0.0, 0.0
    evaluated_queries = 0

    for case in cases:
        q = case["question"]
        gold_ids = case.get("expected_evidence_ids", [])
        ans = case.get("answerability", "answerable")

        # Time the retrieval operation with high precision
        t0 = time.perf_counter()
        nodes = retriever.retrieve(q, top_k=top_k)
        t1 = time.perf_counter()
        latencies.append(t1 - t0)

        retrieved_ids = [getattr(n, "metadata", {}).get("chunk_id", "") for n in nodes]

        if gold_ids and ans == "answerable":
            r1, r3, r5, rr = evaluate_retrieval(retrieved_ids, gold_ids)
            total_r1 += r1
            total_r3 += r3
            total_r5 += r5
            total_mrr += rr
            evaluated_queries += 1

    latency_metrics = compute_percentiles(latencies)

    n_eval = max(1, evaluated_queries)
    return {
        "evaluated_queries": evaluated_queries,
        "total_queries_timed": len(latencies),
        "latency": latency_metrics,
        "retrieval_quality": {
            "recall_at_1": round(total_r1 / n_eval, 4),
            "recall_at_3": round(total_r3 / n_eval, 4),
            "recall_at_5": round(total_r5 / n_eval, 4),
            "mrr": round(total_mrr / n_eval, 4),
        },
    }


def run_characterization(
    cases_path: str = "benchmark/cases_60.jsonl",
    output_path: str = "benchmark/results/performance_characterization.json",
    top_k: int = 5,
) -> Dict[str, Any]:
    """Runs performance characterization across all 4 retriever configurations."""
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    configs = [
        {
            "name": "Config 1: Sparse-Only (BM25)",
            "use_dense": False,
            "use_sparse": True,
            "use_reranker": False,
            "description": "Pure Okapi BM25 inverted index retrieval with IDF weighting",
        },
        {
            "name": "Config 2: Dense-Only (Cosine Sim)",
            "use_dense": True,
            "use_sparse": False,
            "use_reranker": False,
            "description": "Dense normalized vector cosine similarity retrieval",
        },
        {
            "name": "Config 3: Hybrid Fusion (BM25 + Dense RRF)",
            "use_dense": True,
            "use_sparse": True,
            "use_reranker": False,
            "description": "Reciprocal Rank Fusion (k=60) combining BM25 and Dense rankings",
        },
        {
            "name": "Config 4: Hybrid Fusion + Tutor Reranker",
            "use_dense": True,
            "use_sparse": True,
            "use_reranker": True,
            "description": "Hybrid RRF candidate expansion followed by exact code and token reranking",
        },
    ]

    report: Dict[str, Any] = {
        "benchmark_file": cases_path,
        "candidate_top_k": top_k,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configurations": {},
    }

    print("\n" + "=" * 80)
    print("      M8 PERFORMANCE CHARACTERIZATION: RETRIEVAL & LATENCY TRADE-OFFS")
    print("=" * 80)
    print(f"{'Configuration':<38} | {'p50 (ms)':<9} | {'p95 (ms)':<9} | {'R@1':<7} | {'R@5':<7} | {'MRR':<7}")
    print("-" * 80)

    for cfg in configs:
        retriever = TutorRetriever(
            use_dense=cfg["use_dense"],
            use_sparse=cfg["use_sparse"],
            use_reranker=cfg["use_reranker"],
        )
        res = evaluate_configuration(retriever, cases, top_k=top_k)

        p50 = res["latency"]["p50_ms"]
        p95 = res["latency"]["p95_ms"]
        r1 = res["retrieval_quality"]["recall_at_1"]
        r5 = res["retrieval_quality"]["recall_at_5"]
        mrr = res["retrieval_quality"]["mrr"]

        print(f"{cfg['name']:<38} | {p50:<9.2f} | {p95:<9.2f} | {r1 * 100:<6.1f}% | {r5 * 100:<6.1f}% | {mrr:<7.4f}")

        report["configurations"][cfg["name"]] = {
            "description": cfg["description"],
            "settings": {
                "use_dense": cfg["use_dense"],
                "use_sparse": cfg["use_sparse"],
                "use_reranker": cfg["use_reranker"],
            },
            "metrics": res,
        }

    print("=" * 80 + "\n")

    # Save to disk
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="M8 Performance Characterization Harness")
    parser.add_argument("--cases", default="benchmark/cases_60.jsonl", help="Benchmark cases file")
    parser.add_argument("--output", default="benchmark/results/performance_characterization.json", help="Output path")
    parser.add_argument("--top-k", type=int, default=5, help="Retrieval candidate top-k")
    args = parser.parse_args()

    run_characterization(
        cases_path=args.cases,
        output_path=args.output,
        top_k=args.top_k,
    )
