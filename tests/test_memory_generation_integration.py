"""Integration tests for persistent memory engine and pedagogical context generation.

Verifies:
1. Engine restart persistence across two LearnerMemoryEngine instances sharing an SQLite file.
2. Pedagogical context injection into generate_grounded_answer() with zero citation leakage.
3. Safe abstention triggers when corpus evidence is absent, even if learner memory is present.
4. Profile context is strictly isolated from <untrusted_evidence_data> corpus tags.
"""
from __future__ import annotations

import tempfile
from datetime import timedelta

import pytest

from generation.answer import ABSTAIN_UNSUPPORTED, generate_grounded_answer
from memory.engine import LearnerMemoryEngine
from memory.models import (
    LearnerCorrection,
    LearnerProfile,
    MasteryState,
    MasteryStatus,
    MemoryEntry,
    MemoryType,
    now_utc,
)
from memory.store import LearnerMemoryStore


class MockNode:
    """Mock retrieved evidence node."""

    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata

    def get_content(self) -> str:
        return self.text


class MockRetriever:
    """Mock retriever returning fixed nodes."""

    def __init__(self, nodes: list):
        self.nodes = nodes

    def retrieve(self, query: str, fusion: bool = False, top_k: int = 5):
        return self.nodes


# -----------------------------------------------------------------------------
# 1. Engine Persistence Across Restarts
# -----------------------------------------------------------------------------


def test_engine_persistence_across_restarts(tmp_path):
    db_file = str(tmp_path / "persistent_engine.db")

    # Instance 1: Create state
    store1 = LearnerMemoryStore(db_file)
    engine1 = LearnerMemoryEngine(store=store1)

    p = engine1.upsert_profile(
        "learner_restart",
        preferred_learning_level="intermediate",
        learning_preferences={"style": "concise"},
        metadata={"cohort": "2026-Fall"},
    )
    m = engine1.add_memory(
        MemoryEntry(
            learner_id="learner_restart",
            memory_type=MemoryType.LEARNING_PREFERENCE,
            topic="algorithms",
            content="prefers step-by-step walkthroughs",
            confidence=0.95,
        )
    )
    mastery = engine1.update_mastery(
        "learner_restart",
        "algorithms",
        mastery_level=0.7,
        confidence=0.85,
        status=MasteryStatus.LEARNING,
        evidence_increment=2,
    )
    corr = engine1.apply_correction(
        LearnerCorrection(
            learner_id="learner_restart",
            target_memory_id=m.memory_id,
            original_content=m.content,
            corrected_content="prefers interactive code demos over text walkthroughs",
            reason="learner feedback",
        )
    )

    store1.close()

    # Instance 2: Brand new store and engine pointing to same database
    store2 = LearnerMemoryStore(db_file)
    engine2 = LearnerMemoryEngine(store=store2)

    # 1. Profile survived
    p_fetched = engine2.get_profile("learner_restart")
    assert p_fetched is not None
    assert p_fetched.preferred_learning_level == "intermediate"
    assert p_fetched.learning_preferences["style"] == "concise"

    # 2. Memories survived & correction active
    memories = engine2.get_memories("learner_restart")
    assert len(memories) == 1
    assert memories[0].content == "prefers interactive code demos over text walkthroughs"
    assert memories[0].confidence == 1.0

    # 3. Inactive original preserved for audit
    orig_deactivated = engine2.get_memory("learner_restart", m.memory_id, include_inactive=True)
    assert orig_deactivated is not None
    assert orig_deactivated.is_active is False

    # 4. Mastery survived
    m_list = engine2.get_mastery("learner_restart", topic="algorithms")
    assert len(m_list) == 1
    assert m_list[0].mastery_level == 0.7
    assert m_list[0].evidence_count == 2

    # 5. Corrections audit survived
    corrs = engine2.get_corrections("learner_restart")
    assert len(corrs) == 1
    assert corrs[0].reason == "learner feedback"

    store2.close()


# -----------------------------------------------------------------------------
# 2. Pedagogical Context Injection with Zero Citation Leakage
# -----------------------------------------------------------------------------


def test_pedagogical_context_injection_zero_citation_leakage(tmp_path):
    db_file = str(tmp_path / "pedagogical_test.db")
    store = LearnerMemoryStore(db_file)
    store.add_memory(
        MemoryEntry(
            learner_id="ped_alice",
            memory_type=MemoryType.LEARNING_PREFERENCE,
            topic="C Programming",
            content="Focus on pointer arithmetic analogies",
            confidence=0.9,
        )
    )

    recorded_prompts = []

    def mock_llm_capture(prompt: str):
        recorded_prompts.append(prompt)

        class _R:
            text = "Pointers store addresses in memory [Evidence 1]."

        return _R()

    node = MockNode(
        text="A pointer is a variable that stores the memory address of another variable.",
        metadata={
            "chunk_id": "chunk_ptr_01",
            "source_id": "cs50-lec04",
            "modality": "audio",
            "start_sec": 100.0,
            "end_sec": 120.0,
        },
    )
    retriever = MockRetriever([node])

    answer, citations = generate_grounded_answer(
        query="What is a pointer?",
        retriever=retriever,
        llm=mock_llm_capture,
        learner_id="ped_alice",
        memory_store=store,
    )

    # 1. Prompt contained pedagogical styling header
    assert len(recorded_prompts) == 1
    full_prompt = recorded_prompts[0]
    assert "=== [LEARNER PROFILE - PEDAGOGICAL STYLING ONLY - DO NOT CITE AS EVIDENCE] ===" in full_prompt
    assert "Learner ID: ped_alice" in full_prompt
    assert "Focus on pointer arithmetic analogies" in full_prompt

    # 2. Pedagogical note is OUTSIDE untrusted evidence tags
    assert full_prompt.index("=== [LEARNER PROFILE") < full_prompt.index("<untrusted_evidence_data")

    # 3. Zero citation leakage: learner memory is never included in citations
    assert len(citations) == 1
    assert citations[0]["citation_label"] == "[Evidence 1]"
    assert citations[0]["chunk_id"] == "chunk_ptr_01"
    assert "Focus on pointer arithmetic analogies" not in str(citations)

    store.close()


# -----------------------------------------------------------------------------
# 3. Absence of Corpus Evidence Still Abstains Despite Learner Memory
# -----------------------------------------------------------------------------


def test_abstention_triggers_when_corpus_evidence_absent_despite_memory(tmp_path):
    db_file = str(tmp_path / "abstain_test.db")
    store = LearnerMemoryStore(db_file)
    store.add_memory(
        MemoryEntry(
            learner_id="ped_bob",
            memory_type=MemoryType.LEARNING_PREFERENCE,
            topic="General",
            content="Prefers detailed answers",
            confidence=1.0,
        )
    )

    # Empty retrieval: no evidence retrieved
    empty_retriever = MockRetriever([])

    answer, citations = generate_grounded_answer(
        query="Explain quantum computing in detail.",
        retriever=empty_retriever,
        learner_id="ped_bob",
        memory_store=store,
    )

    # Must abstain because there is zero corpus evidence, despite learner memory presence
    assert answer.startswith("I abstain") or answer == ABSTAIN_UNSUPPORTED
    assert citations == []

    store.close()
