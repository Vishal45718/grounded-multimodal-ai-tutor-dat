"""Unit tests for M8: Performance Characterization and Reranking Architecture."""
import json
import os
import pytest

from benchmark.characterize_performance import compute_percentiles, run_characterization
from retrieval.reranker import TutorReranker
from retrieval.retriever import FallbackNode, PurePythonBM25, TutorRetriever


# ----------------------------------------------------------------------
# 1. Percentile and Latency Computation Tests
# ----------------------------------------------------------------------

def test_compute_percentiles_known_values():
    latencies = [0.001 * i for i in range(1, 101)]  # 1ms to 100ms
    metrics = compute_percentiles(latencies)

    assert metrics["p50_ms"] == pytest.approx(50.0, abs=2.0)
    assert metrics["p95_ms"] == pytest.approx(95.0, abs=2.0)
    assert metrics["mean_ms"] == pytest.approx(50.5, abs=2.0)


def test_compute_percentiles_empty_list():
    metrics = compute_percentiles([])
    assert metrics["p50_ms"] == 0.0
    assert metrics["p95_ms"] == 0.0
    assert metrics["mean_ms"] == 0.0


# ----------------------------------------------------------------------
# 2. TutorReranker Scoring and Ordering Tests
# ----------------------------------------------------------------------

def test_reranker_promotes_exact_code_matches():
    reranker = TutorReranker(exact_boost=2.0)
    query = "How to print output with printf in C?"

    generic_node = FallbackNode("In computer programming, output can be displayed to a monitor.", {
        "chunk_id": "c_generic"
    })
    exact_code_node = FallbackNode("The function printf prints formatted text to the screen in C.", {
        "chunk_id": "c_exact"
    })

    score_generic = reranker.score_node(query, generic_node)
    score_exact = reranker.score_node(query, exact_code_node)

    assert score_exact > score_generic

    # Test rerank ordering
    reranked = reranker.rerank(query, [generic_node, exact_code_node], top_k=2)
    assert reranked[0].metadata["chunk_id"] == "c_exact"


def test_reranker_handles_empty_nodes():
    reranker = TutorReranker()
    assert reranker.rerank("any query", [], top_k=5) == []


def test_reranker_boosts_visual_query_for_visual_nodes():
    reranker = TutorReranker(code_boost=2.0)
    query = "Explain the slide diagram for compilation"

    text_node = FallbackNode("Compilation converts source code to machine code.", {
        "chunk_id": "c_text", "modality": "audio"
    })
    slide_node = FallbackNode("Slide diagram illustrating the compiler between source code and machine code.", {
        "chunk_id": "c_slide", "modality": "visual"
    })

    score_slide = reranker.score_node(query, slide_node)
    score_text = reranker.score_node(query, text_node)

    assert score_slide > score_text


# ----------------------------------------------------------------------
# 3. Retriever Configuration Switching Tests
# ----------------------------------------------------------------------

def test_retriever_sparse_only_mode():
    retriever = TutorRetriever(use_dense=False, use_sparse=True, use_reranker=False)
    assert retriever.use_sparse is True
    assert retriever.use_dense is False
    results = retriever.retrieve("compiler machine code", top_k=3)
    assert len(results) <= 3
    assert len(results) > 0


def test_retriever_dense_only_mode():
    retriever = TutorRetriever(use_dense=True, use_sparse=False, use_reranker=False)
    assert retriever.use_dense is True
    assert retriever.use_sparse is False
    results = retriever.retrieve("compiler machine code", top_k=3)
    assert len(results) <= 3
    assert len(results) > 0


def test_retriever_hybrid_fusion_mode():
    retriever = TutorRetriever(use_dense=True, use_sparse=True, use_reranker=False)
    assert retriever.use_dense is True
    assert retriever.use_sparse is True
    results = retriever.retrieve("printf hello world", top_k=5)
    assert len(results) == 5


def test_retriever_with_reranker_mode():
    retriever = TutorRetriever(use_dense=True, use_sparse=True, use_reranker=True)
    assert retriever.use_reranker is True
    assert retriever.reranker is not None
    results = retriever.retrieve("Boeing 787 integer overflow 248 days", top_k=3)
    assert len(results) <= 3
    assert len(results) > 0


# ----------------------------------------------------------------------
# 4. Performance Characterization Report Verification
# ----------------------------------------------------------------------

def test_performance_characterization_report_structure(tmp_path):
    output_file = str(tmp_path / "perf_test.json")
    cases_file = "benchmark/cases_60.jsonl"

    report = run_characterization(cases_path=cases_file, output_path=output_file, top_k=3)

    assert os.path.exists(output_file)
    assert "configurations" in report
    configs = report["configurations"]

    assert len(configs) == 4
    for name, data in configs.items():
        assert "latency" in data["metrics"]
        assert "retrieval_quality" in data["metrics"]
        lat = data["metrics"]["latency"]
        assert "p50_ms" in lat
        assert "p95_ms" in lat
        assert "mean_ms" in lat
        qual = data["metrics"]["retrieval_quality"]
        assert "recall_at_1" in qual
        assert "recall_at_5" in qual
        assert "mrr" in qual
