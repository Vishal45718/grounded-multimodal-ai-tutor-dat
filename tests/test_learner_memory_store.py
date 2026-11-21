"""Persistent unit and integration tests for SQLite LearnerMemoryStore (M5).

Verifies:
1. Schema initialization and PRAGMA integrity_check on file-backed and :memory: stores.
2. Persistent :memory: operation across sequential calls and clean close().
3. PRAGMA foreign_keys = ON active, allowing memory creation before LearnerProfile.
4. Field-by-field round trips (to_dict() equality) for all 4 canonical models.
5. Strict _serialize_source() validation (accepted types vs SourceSerializationError on invalid types).
6. Expiry and inactive filtering in get_memories() with explicit flags and as_of determinism.
7. apply_correction() original deactivation, replacement insertion, and audit trail.
8. purge_learner() complete multi-table erasure with strict learner isolation.
9. Transaction rollback on mid-operation failure.
10. build_pedagogical_context() formatting and evidence isolation.
11. Backwards-compatibility methods (write_memory, get_active_memories, correct_memory).
"""
from __future__ import annotations

import math
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest

from memory.models import (
    LearnerCorrection,
    LearnerProfile,
    MasteryState,
    MasteryStatus,
    MemoryEntry,
    MemoryType,
    compute_memory_id,
    now_utc,
)
from memory.store import LearnerMemoryStore, SourceSerializationError


@pytest.fixture
def mem_store():
    """In-memory SQLite store fixture."""
    store = LearnerMemoryStore(":memory:")
    yield store
    store.close()


@pytest.fixture
def file_store(tmp_path):
    """File-backed SQLite store fixture."""
    db_file = tmp_path / "test_learner_memory.db"
    store = LearnerMemoryStore(str(db_file))
    yield store
    store.close()


# -----------------------------------------------------------------------------
# 1. Schema initialization & PRAGMA integrity_check
# -----------------------------------------------------------------------------


def test_schema_initialization_and_integrity(file_store, mem_store):
    for store in (file_store, mem_store):
        with store._connect() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            assert integrity == "ok"

            # Check that all 4 tables exist
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {r["name"] for r in tables}
            assert {
                "learner_profiles",
                "memory_entries",
                "mastery_states",
                "learner_corrections",
            }.issubset(table_names)


# -----------------------------------------------------------------------------
# 2. Persistent :memory: operation across calls & clean close()
# -----------------------------------------------------------------------------


def test_persistent_in_memory_store_across_calls():
    store = LearnerMemoryStore(":memory:")
    p = LearnerProfile(
        learner_id="learner_seq",
        created_at=now_utc(),
        updated_at=now_utc(),
        preferred_learning_level="introductory",
    )
    store.upsert_profile(p)

    # Next call on same instance should see profile
    fetched_p = store.get_profile("learner_seq")
    assert fetched_p is not None
    assert fetched_p.preferred_learning_level == "introductory"

    # Add memory in subsequent call
    m = MemoryEntry(
        learner_id="learner_seq",
        memory_type=MemoryType.LEARNING_PREFERENCE,
        topic="graphs",
        content="visual learner",
    )
    store.add_memory(m)

    fetched_m = store.get_memory("learner_seq", m.memory_id)
    assert fetched_m is not None
    assert fetched_m.content == "visual learner"

    # Test clean close()
    store.close()
    assert store._shared_conn is None
    with pytest.raises(RuntimeError, match="connection is already closed"):
        with store._connect():
            pass


# -----------------------------------------------------------------------------
# 3. Foreign keys enabled & memory creation without profile
# -----------------------------------------------------------------------------


def test_foreign_keys_and_profile_independence(file_store, mem_store):
    for store in (file_store, mem_store):
        with store._connect() as conn:
            fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk_on == 1

        # Memory entry can be created even if no learner_profile exists
        m = MemoryEntry(
            learner_id="unregistered_learner",
            memory_type=MemoryType.MISCONCEPTION,
            topic="recursion",
            content="recursion has no base case",
        )
        stored_m = store.add_memory(m)
        assert stored_m.memory_id == m.memory_id

        fetched = store.get_memory("unregistered_learner", m.memory_id)
        assert fetched is not None
        assert fetched.content == "recursion has no base case"
        assert store.get_profile("unregistered_learner") is None


# -----------------------------------------------------------------------------
# 4. Canonical model round trips (to_dict() equality, timezone & enums)
# -----------------------------------------------------------------------------


def test_canonical_model_round_trips(file_store):
    t_now = now_utc()
    t_exp = t_now + timedelta(days=7)

    # 1. LearnerProfile
    profile = LearnerProfile(
        learner_id="alice",
        created_at=t_now,
        updated_at=t_now,
        preferred_learning_level="advanced",
        learning_preferences={"pace": "fast", "multimodal": True},
        metadata={"track": "cs_core", "mentor_id": "prof_oak"},
    )
    file_store.upsert_profile(profile)
    fetched_p = file_store.get_profile("alice")
    assert fetched_p is not None
    assert fetched_p.to_dict() == profile.to_dict()
    assert fetched_p.created_at.tzinfo == timezone.utc

    # 2. MemoryEntry
    entry = MemoryEntry(
        learner_id="alice",
        memory_type=MemoryType.MISCONCEPTION,
        topic="Sorting",
        content="QuickSort is always O(n log n)",
        confidence=0.88,
        source={"turn": 5, "agent": "evaluator", "confirmed": False},
        created_at=t_now,
        updated_at=t_now,
        expires_at=t_exp,
        is_active=True,
        metadata={"revisit": True, "depth": 2},
    )
    file_store.add_memory(entry)
    fetched_e = file_store.get_memory("alice", entry.memory_id)
    assert fetched_e is not None
    assert fetched_e.to_dict() == entry.to_dict()
    assert isinstance(fetched_e.memory_type, MemoryType)
    assert fetched_e.memory_type is MemoryType.MISCONCEPTION
    assert fetched_e.created_at.tzinfo == timezone.utc
    assert fetched_e.expires_at.tzinfo == timezone.utc

    # 3. MasteryState
    mastery = MasteryState(
        learner_id="alice",
        topic="Sorting",
        mastery_level=0.82,
        confidence=0.91,
        evidence_count=5,
        last_updated=t_now,
        status=MasteryStatus.LEARNING,
        metadata={"last_quiz": "sorting_quiz_v2"},
    )
    file_store.update_mastery(mastery)
    fetched_m = file_store.get_mastery("alice", topic="Sorting")
    assert len(fetched_m) == 1
    assert fetched_m[0].to_dict() == mastery.to_dict()
    assert isinstance(fetched_m[0].status, MasteryStatus)
    assert fetched_m[0].status is MasteryStatus.LEARNING
    assert fetched_m[0].last_updated.tzinfo == timezone.utc

    # 4. LearnerCorrection
    correction = LearnerCorrection(
        learner_id="alice",
        target_memory_id=entry.memory_id,
        original_content=entry.content,
        corrected_content="QuickSort worst-case is O(n^2) on sorted input",
        reason="Learner self-corrected in reflection",
        created_at=t_now,
    )
    file_store.apply_correction(correction)
    corrs = file_store.get_corrections("alice")
    assert len(corrs) == 1
    assert corrs[0].to_dict() == correction.to_dict()
    assert corrs[0].created_at.tzinfo == timezone.utc


# -----------------------------------------------------------------------------
# 5. Strict _serialize_source() validation
# -----------------------------------------------------------------------------


def test_strict_source_serialization_accepted_types(mem_store):
    accepted_sources = [
        None,
        "simple_string",
        "",
        True,
        False,
        0,
        -42,
        3.14159,
        -0.0001,
        [],
        [1, "text", 2.5, True, False, None],
        {},
        {"key": "value"},
        {"nested": {"list": [1, 2, {"k": None}], "bool": True}},
    ]

    for idx, src in enumerate(accepted_sources):
        m = MemoryEntry(
            learner_id="source_learner",
            memory_type=MemoryType.LEARNING_PREFERENCE,
            topic=f"topic_{idx}",
            content=f"content_{idx}",
            source=src,
        )
        mem_store.add_memory(m)
        fetched = mem_store.get_memory("source_learner", m.memory_id)
        assert fetched is not None
        assert fetched.source == src


def test_strict_source_serialization_rejected_types(mem_store):
    class CustomPayload:
        def __init__(self, val):
            self.val = val

    rejected_sources = [
        (1, 2),  # tuple
        [1, (2, 3)],  # nested tuple
        {"key": (1, 2)},  # tuple value in dict
        {1, 2, 3},  # set
        {"set_val": {1, 2}},  # nested set
        float("nan"),  # NaN
        float("inf"),  # Infinity
        float("-inf"),  # -Infinity
        [1, float("nan")],  # nested NaN
        {"val": float("inf")},  # nested Infinity
        {1: "numeric_key"},  # non-string key
        {(1, 2): "tuple_key"},  # non-string key
        CustomPayload("test"),  # custom object
        {"custom": CustomPayload("test")},  # nested custom object
    ]

    for bad_src in rejected_sources:
        m = MemoryEntry(
            learner_id="bad_source_learner",
            memory_type=MemoryType.LEARNING_PREFERENCE,
            topic="test",
            content="test",
            source=bad_src,
        )
        with pytest.raises(SourceSerializationError):
            mem_store.add_memory(m)


# -----------------------------------------------------------------------------
# 6. Expiry and inactive filtering in get_memories()
# -----------------------------------------------------------------------------


def test_expiry_and_inactive_filtering(mem_store):
    t_now = now_utc()
    t_past_created = t_now - timedelta(days=5)
    t_past_expired = t_now - timedelta(days=1)
    t_future_expired = t_now + timedelta(days=2)

    # 1. Normal active memory
    m_active = MemoryEntry(
        learner_id="learner_filters",
        memory_type=MemoryType.LEARNING_PREFERENCE,
        topic="t",
        content="active_content",
        created_at=t_now,
        expires_at=t_future_expired,
        is_active=True,
    )
    # 2. Inactive memory
    m_inactive = MemoryEntry(
        learner_id="learner_filters",
        memory_type=MemoryType.LEARNING_PREFERENCE,
        topic="t",
        content="inactive_content",
        created_at=t_now,
        expires_at=t_future_expired,
        is_active=False,
    )
    # 3. Expired memory
    m_expired = MemoryEntry(
        learner_id="learner_filters",
        memory_type=MemoryType.LEARNING_PREFERENCE,
        topic="t",
        content="expired_content",
        created_at=t_past_created,
        expires_at=t_past_expired,
        is_active=True,
    )

    mem_store.add_memory(m_active)
    mem_store.add_memory(m_inactive)
    mem_store.add_memory(m_expired)

    # Default: excludes inactive AND excludes expired
    default_results = mem_store.get_memories("learner_filters")
    assert len(default_results) == 1
    assert default_results[0].content == "active_content"

    # include_inactive=True: includes active + inactive, excludes expired
    inactive_results = mem_store.get_memories("learner_filters", include_inactive=True)
    assert len(inactive_results) == 2
    assert {m.content for m in inactive_results} == {"active_content", "inactive_content"}

    # include_expired=True: includes active + expired, excludes inactive
    expired_results = mem_store.get_memories("learner_filters", include_expired=True)
    assert len(expired_results) == 2
    assert {m.content for m in expired_results} == {"active_content", "expired_content"}

    # Both include_inactive and include_expired: all 3
    all_results = mem_store.get_memories(
        "learner_filters", include_inactive=True, include_expired=True
    )
    assert len(all_results) == 3

    # as_of determinism: query as_of past (before m_expired expired)
    as_of_past = t_past_created + timedelta(days=1)
    as_of_results = mem_store.get_memories("learner_filters", as_of=as_of_past)
    assert len(as_of_results) == 2
    assert {m.content for m in as_of_results} == {"active_content", "expired_content"}


# -----------------------------------------------------------------------------
# 7. apply_correction() audit trail and deactivation
# -----------------------------------------------------------------------------


def test_apply_correction_semantics(mem_store):
    orig = MemoryEntry(
        learner_id="bob",
        memory_type=MemoryType.MISCONCEPTION,
        topic="DP",
        content="Memoization requires recursion.",
    )
    mem_store.add_memory(orig)

    correction = LearnerCorrection(
        learner_id="bob",
        target_memory_id=orig.memory_id,
        original_content=orig.content,
        corrected_content="Memoization can be top-down, tabulation is bottom-up.",
        reason="Reviewed lecture 4 notes.",
    )
    replacement = mem_store.apply_correction(correction)

    assert replacement.content == correction.corrected_content
    assert replacement.confidence == 1.0
    assert replacement.metadata["supersedes"] == orig.memory_id
    assert replacement.metadata["correction_id"] == correction.correction_id

    # Original must now be inactive
    deactivated = mem_store.get_memory("bob", orig.memory_id, include_inactive=True)
    assert deactivated is not None
    assert deactivated.is_active is False
    assert deactivated.metadata["superseded_by"] == replacement.memory_id

    # Active memories return replacement only
    active = mem_store.get_memories("bob")
    assert len(active) == 1
    assert active[0].content == correction.corrected_content

    # Corrections audit table recorded entry
    corrs = mem_store.get_corrections("bob")
    assert len(corrs) == 1
    assert corrs[0].correction_id == correction.correction_id


# -----------------------------------------------------------------------------
# 8. purge_learner() multi-table erasure and learner isolation
# -----------------------------------------------------------------------------


def test_purge_learner_isolation(file_store):
    # Setup Alice
    file_store.upsert_profile(LearnerProfile(learner_id="alice", created_at=now_utc(), updated_at=now_utc()))
    m_alice = MemoryEntry(learner_id="alice", memory_type=MemoryType.LEARNING_PREFERENCE, topic="a", content="ca")
    file_store.add_memory(m_alice)
    file_store.update_mastery(MasteryState(learner_id="alice", topic="a", mastery_level=0.5, confidence=0.5, evidence_count=1, last_updated=now_utc(), status=MasteryStatus.LEARNING))
    file_store.apply_correction(LearnerCorrection(learner_id="alice", target_memory_id=m_alice.memory_id, original_content="ca", corrected_content="ca_new", reason="r"))

    # Setup Bob
    file_store.upsert_profile(LearnerProfile(learner_id="bob", created_at=now_utc(), updated_at=now_utc()))
    m_bob = MemoryEntry(learner_id="bob", memory_type=MemoryType.LEARNING_PREFERENCE, topic="b", content="cb")
    file_store.add_memory(m_bob)

    # Purge Alice
    deleted = file_store.purge_learner("alice")
    assert deleted >= 4

    # Alice records should be completely gone
    assert file_store.get_profile("alice") is None
    assert len(file_store.get_memories("alice", include_inactive=True, include_expired=True)) == 0
    assert len(file_store.get_mastery("alice")) == 0
    assert len(file_store.get_corrections("alice")) == 0

    # Bob records must remain intact
    assert file_store.get_profile("bob") is not None
    assert len(file_store.get_memories("bob")) == 1


# -----------------------------------------------------------------------------
# 9. Transaction rollback on error
# -----------------------------------------------------------------------------


def test_transaction_rollback(file_store):
    with pytest.raises(RuntimeError, match="simulated failure"):
        with file_store._connect() as conn:
            conn.execute(
                """
                INSERT INTO learner_profiles (
                    learner_id, created_at, updated_at, preferred_learning_level,
                    learning_preferences, metadata
                ) VALUES ('fail_learner', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', NULL, '{}', '{}')
                """
            )
            raise RuntimeError("simulated failure")

    assert file_store.get_profile("fail_learner") is None


# -----------------------------------------------------------------------------
# 10. build_pedagogical_context() isolation banner & formatting
# -----------------------------------------------------------------------------


def test_build_pedagogical_context(mem_store):
    # Empty case
    assert mem_store.build_pedagogical_context("empty_learner") == ""

    t_now = now_utc()
    mem_store.add_memory(
        MemoryEntry(
            learner_id="charlie",
            memory_type=MemoryType.LEARNING_PREFERENCE,
            topic="Geometry",
            content="Likes visual proofs",
            confidence=0.95,
        )
    )
    # Add an inactive memory that should NOT appear in pedagogical context
    mem_store.add_memory(
        MemoryEntry(
            learner_id="charlie",
            memory_type=MemoryType.LEARNING_PREFERENCE,
            topic="History",
            content="Outdated note",
            confidence=0.5,
            is_active=False,
        )
    )

    context = mem_store.build_pedagogical_context("charlie")
    assert "=== [LEARNER PROFILE - PEDAGOGICAL STYLING ONLY - DO NOT CITE AS EVIDENCE] ===" in context
    assert "Learner ID: charlie" in context
    assert "Topic: Geometry | Likes visual proofs (Confidence: 0.95)" in context
    assert "Outdated note" not in context
    assert "You MUST NEVER cite these profile notes as instructional course evidence." in context


# -----------------------------------------------------------------------------
# 11. Backwards-compatibility adapter methods
# -----------------------------------------------------------------------------


def test_backwards_compatibility_adapter_methods(mem_store):
    class LegacyItem:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    now_sec = time.time()
    legacy_item = LegacyItem(
        item_id="legacy_1",
        learner_id="dave",
        memory_type="misconception",
        topic="Binary Trees",
        content="Binary trees have at most 3 children",
        confidence=0.9,
        provenance_turn_id="turn_12",
        is_confirmed=True,
        created_at=now_sec,
        updated_at=now_sec,
        expires_at=None,
        history=[],
    )

    ok, item, msg = mem_store.write_memory(legacy_item, force=True)
    assert ok is True
    assert "Successfully committed" in msg

    active = mem_store.get_active_memories("dave")
    assert len(active) == 1
    assert active[0].content == "Binary trees have at most 3 children"

    # Test legacy correct_memory
    corrected = mem_store.correct_memory(
        "legacy_1",
        "Binary trees have at most 2 children",
        reason="Corrected in quiz review",
    )
    assert corrected is not None
    assert corrected.content == "Binary trees have at most 2 children"
    assert corrected.is_confirmed is True

    # Test delete_memory
    deleted = mem_store.delete_memory("dave", "legacy_1")
    assert deleted is True
    assert len(mem_store.get_active_memories("dave")) == 0
