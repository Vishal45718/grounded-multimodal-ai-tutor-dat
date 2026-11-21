"""Unit tests for M6: Abstention policy, version safety, cache invalidation, and stale leakage."""
import os
import pytest
from guardrails.abstention_policy import (
    AbstentionPolicy,
    DecisionType,
    ABSTAIN_UNSUPPORTED,
    QUALIFY_PREFIX,
)
from guardrails.version_safety import (
    VersionSafeCache,
    filter_stale_chunks,
    compute_stale_leakage,
)
from generation.answer import generate_grounded_answer


class MockNode:
    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata

    def get_content(self) -> str:
        return self.text


class SimpleRetriever:
    def __init__(self, nodes):
        self.nodes = nodes

    def retrieve(self, query: str, fusion: bool = True):
        return self.nodes


# ----------------------------------------------------------------------
# 1. Abstention Policy Tests
# ----------------------------------------------------------------------

def test_abstention_policy_high_similarity_answers():
    policy = AbstentionPolicy(sim_threshold_answer=0.20, sim_threshold_qualify=0.10)
    query = "What is a variable in C?"
    node = MockNode("A variable in C is a named storage location in memory for values.", {
        "source_id": "cs50-lec01",
        "chunk_id": "c1",
        "modality": "text",
    })
    decision, score, coverage, reason = policy.evaluate(query, [node])
    assert decision == DecisionType.ANSWER
    assert score >= 0.20
    assert "tau_ans" in reason


def test_abstention_policy_medium_similarity_qualifies():
    policy = AbstentionPolicy(tau_ans=0.80, tau_qual=0.20, tau_cov=0.70)
    query = "Explain variable storage and memory allocation"
    node = MockNode("A variable storage location holds integer values.", {
        "source_id": "cs50-lec01",
        "chunk_id": "c1",
        "modality": "text",
    })
    decision, score, coverage, reason = policy.evaluate(query, [node])
    assert decision == DecisionType.QUALIFY
    assert "tau_ans" in reason or "Partial evidence" in reason


def test_abstention_policy_low_similarity_abstains():
    policy = AbstentionPolicy(sim_threshold_answer=0.30, sim_threshold_qualify=0.15)
    query = "How to bake chocolate chip cookies with sourdough?"
    node = MockNode("A variable in C is an integer.", {
        "source_id": "cs50-lec01",
        "chunk_id": "c1",
        "modality": "text",
    })
    decision, score, coverage, reason = policy.evaluate(query, [node])
    assert decision == DecisionType.ABSTAIN
    assert "tau_qual" in reason


def test_abstention_policy_empty_nodes_abstains():
    policy = AbstentionPolicy()
    decision, score, coverage, reason = policy.evaluate("Any query", [])
    assert decision == DecisionType.ABSTAIN
    assert score == 0.0
    assert coverage == 0.0


def test_format_qualification():
    policy = AbstentionPolicy()
    raw = "Variables store memory addresses [Evidence 1]."
    qualified = policy.format_qualification(raw)
    assert qualified.startswith(QUALIFY_PREFIX)
    assert "[Evidence 1]" in qualified


# ----------------------------------------------------------------------
# 2. Version-Safe Cache Tests
# ----------------------------------------------------------------------

def test_version_safe_cache_set_and_get():
    cache = VersionSafeCache()
    citations = [{"citation_label": "[Evidence 1]", "chunk_id": "c1"}]
    cache.set(
        source_id="cs50-lec01",
        content_hash="hash_v1",
        course_edition="2024",
        query="What is printf?",
        answer="printf prints formatted strings [Evidence 1].",
        citations=citations,
    )
    assert cache.size == 1

    # Exact match hit
    hit = cache.get("cs50-lec01", "hash_v1", "What is printf?")
    assert hit is not None
    ans, cits = hit
    assert "printf prints formatted strings" in ans
    assert len(cits) == 1

    # Miss on different query
    assert cache.get("cs50-lec01", "hash_v1", "What is scanf?") is None

    # Miss on updated content hash (source updated)
    assert cache.get("cs50-lec01", "hash_v2_updated", "What is printf?") is None


def test_version_safe_cache_invalidate_source():
    cache = VersionSafeCache()
    cache.set("cs50-lec01", "h1", "2024", "query 1", "answer 1", [])
    cache.set("cs50-lec01", "h1", "2024", "query 2", "answer 2", [])
    cache.set("cs50-lec02", "h2", "2024", "query 3", "answer 3", [])
    assert cache.size == 3

    # Invalidate source cs50-lec01
    removed = cache.invalidate_source("cs50-lec01")
    assert removed == 2
    assert cache.size == 1
    assert cache.get("cs50-lec02", "h2", "query 3") is not None
    assert cache.get("cs50-lec01", "h1", "query 1") is None


def test_version_safe_cache_invalidate_edition():
    cache = VersionSafeCache()
    cache.set("cs50-lec01", "h1", "2023", "query 1", "answer 1", [])
    cache.set("cs50-lec02", "h2", "2023", "query 2", "answer 2", [])
    cache.set("cs50-lec01", "h3", "2024", "query 3", "answer 3", [])
    assert cache.size == 3

    # Invalidate deprecated 2023 edition
    removed = cache.invalidate_edition("2023")
    assert removed == 2
    assert cache.size == 1
    assert cache.get("cs50-lec01", "h3", "query 3") is not None
    assert cache.get("cs50-lec01", "h1", "query 1") is None


def test_version_safe_cache_clear():
    cache = VersionSafeCache()
    cache.set("cs50-lec01", "h1", "2024", "q1", "a1", [])
    cache.clear()
    assert cache.size == 0


# ----------------------------------------------------------------------
# 3. Stale Evidence Filtering & Stale Leakage Metric Tests
# ----------------------------------------------------------------------

def test_filter_stale_chunks_removes_flagged_stale_nodes():
    fresh_node = MockNode("Active evidence", {"chunk_id": "c1", "is_stale": 0})
    stale_node = MockNode("Old deprecated evidence", {"chunk_id": "c2", "is_stale": 1})
    deprecated_node = MockNode("Old edition evidence", {"chunk_id": "c3", "is_deprecated": 1})

    filtered = filter_stale_chunks([fresh_node, stale_node, deprecated_node])
    assert len(filtered) == 1
    assert filtered[0].metadata["chunk_id"] == "c1"


def test_filter_stale_chunks_with_active_whitelist():
    node1 = MockNode("Evidence 1", {"chunk_id": "c1"})
    node2 = MockNode("Evidence 2", {"chunk_id": "c2"})
    node3 = MockNode("Evidence 3", {"chunk_id": "c3"})

    active_set = {"c1", "c3"}
    filtered = filter_stale_chunks([node1, node2, node3], active_chunk_ids=active_set)
    assert len(filtered) == 2
    ids = [n.metadata["chunk_id"] for n in filtered]
    assert ids == ["c1", "c3"]


def test_compute_stale_leakage_zero_for_clean_citations():
    citations = [
        {"chunk_id": "c1", "citation_label": "[Evidence 1]"},
        {"chunk_id": "c2", "citation_label": "[Evidence 2]"},
    ]
    active_set = {"c1", "c2", "c3"}
    leakage = compute_stale_leakage(citations, active_chunk_ids=active_set)
    assert leakage == 0.0


def test_compute_stale_leakage_positive_when_stale_leaks():
    citations = [
        {"chunk_id": "c1", "citation_label": "[Evidence 1]"},
        {"chunk_id": "c_stale_2", "citation_label": "[Evidence 2]"},
    ]
    active_set = {"c1", "c3"}
    leakage = compute_stale_leakage(citations, active_chunk_ids=active_set)
    assert leakage == 0.5


# ----------------------------------------------------------------------
# 4. End-to-End Abstention via generate_grounded_answer
# ----------------------------------------------------------------------

def test_unsupported_query_safely_abstains():
    node = MockNode("Introduction to C programming syntax and functions.", {
        "source_id": "cs50-lec01",
        "chunk_id": "c1",
        "modality": "audio",
        "start_sec": 10.0,
        "end_sec": 20.0,
    })
    retriever = SimpleRetriever([node])
    policy = AbstentionPolicy(sim_threshold_answer=0.25, sim_threshold_qualify=0.15)

    ans, citations = generate_grounded_answer(
        query="What is the capital of Australia and its kangaroo population?",
        retriever=retriever,
        policy=policy,
        use_cache=False,
    )
    assert ans == ABSTAIN_UNSUPPORTED
    assert citations == []


def test_supported_query_returns_answer_with_citations():
    node = MockNode("In C, printf is used to print output to the console terminal.", {
        "source_id": "cs50-lec01",
        "chunk_id": "c1",
        "modality": "audio",
        "start_sec": 10.0,
        "end_sec": 20.0,
    })
    retriever = SimpleRetriever([node])
    policy = AbstentionPolicy(sim_threshold_answer=0.15, sim_threshold_qualify=0.08)

    ans, citations = generate_grounded_answer(
        query="What function prints output in C?",
        retriever=retriever,
        policy=policy,
        use_cache=False,
    )
    assert ans != ABSTAIN_UNSUPPORTED
    assert len(citations) >= 1
    assert citations[0]["chunk_id"] == "c1"
