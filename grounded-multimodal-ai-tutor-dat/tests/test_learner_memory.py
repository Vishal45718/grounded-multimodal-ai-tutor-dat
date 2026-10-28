"""Automated unit test suite for Milestone M5: Selective Learner Memory.

Guarantees tested:
1. Ephemeral session state is discarded at session end and not persisted.
2. Low-confidence/casual remarks (< tau_mem) without confirmation are rejected.
3. High-confidence (>= tau_mem) or confirmed memories are persisted.
4. Provenance (turn ID, timestamp, confidence, evidence ID) is strictly maintained.
5. Expiry policy: memories past TTL are excluded from active retrieval.
6. Temporal decay: unreinforced mastery confidence decays over time.
7. Correction policy: corrections supersede older values and preserve audit history.
8. Deletion policy: deletion is immediate and absent from subsequent queries.
9. Learner isolation: memories for learner A never leak into learner B's queries.
10. Pedagogical isolation: profile context explicitly forbids citing memory as evidence.
11. Purge capability: hard erasure removes all learner data.
"""
import time
import pytest
from memory.models import LearnerMemoryItem, EphemeralSession, compute_memory_id
from memory.policy import LearnerMemoryPolicy
from memory.store import LearnerMemoryStore


@pytest.fixture
def memory_store(tmp_path):
    db_file = tmp_path / "test_memory.db"
    policy = LearnerMemoryPolicy(tau_mem=0.75, default_ttl_seconds=3600.0)
    return LearnerMemoryStore(db_path=str(db_file), policy=policy)


def test_ephemeral_session_working_memory_discarded():
    session = EphemeralSession(session_id="sess_101", learner_id="learner_alice")
    t1 = session.add_turn("I find recursion tricky.", "Recursion is when a function calls itself.")
    assert len(session.turns) == 1
    assert session.turns[0]["turn_id"] == t1

    # Session ends
    session.close()
    assert session.is_active is False
    assert len(session.turns) == 0


def test_write_policy_rejects_low_confidence_unconfirmed(memory_store):
    item = LearnerMemoryItem(
        item_id=compute_memory_id("learner_alice", "misconception", "binary_search", "O(n) complexity"),
        learner_id="learner_alice",
        memory_type="misconception",
        topic="binary_search",
        content="Believes binary search is O(n)",
        confidence=0.45,  # below tau_mem (0.75)
        provenance_turn_id="turn_5",
        is_confirmed=False,
    )
    success, res_item, reason = memory_store.write_memory(item)
    assert success is False
    assert res_item is None
    assert "below write threshold" in reason

    # Active memories should be empty
    active = memory_store.get_active_memories("learner_alice")
    assert len(active) == 0


def test_write_policy_accepts_high_confidence_or_confirmed(memory_store):
    # High confidence write
    item1 = LearnerMemoryItem(
        item_id=compute_memory_id("learner_alice", "goal", "cs50", "Prepare for Week 2 Arrays"),
        learner_id="learner_alice",
        memory_type="goal",
        topic="cs50",
        content="Prepare for Week 2 Arrays",
        confidence=0.90,
        provenance_turn_id="turn_1",
        is_confirmed=False,
    )
    ok1, res1, _ = memory_store.write_memory(item1)
    assert ok1 is True
    assert res1.item_id == item1.item_id

    # Confirmed write even with moderate confidence
    item2 = LearnerMemoryItem(
        item_id=compute_memory_id("learner_alice", "misconception", "pointers", "confusing NULL with 0"),
        learner_id="learner_alice",
        memory_type="misconception",
        topic="pointers",
        content="Confusing NULL pointer with integer zero",
        confidence=0.60,
        provenance_turn_id="turn_2",
        is_confirmed=True,  # explicitly confirmed by learner
    )
    ok2, res2, _ = memory_store.write_memory(item2)
    assert ok2 is True

    active = memory_store.get_active_memories("learner_alice")
    assert len(active) == 2


def test_provenance_fields_preserved(memory_store):
    item = LearnerMemoryItem(
        item_id=compute_memory_id("learner_alice", "mastery", "compilation", "clang and make"),
        learner_id="learner_alice",
        memory_type="mastery",
        topic="compilation",
        content="Understands clang command line flags",
        confidence=0.85,
        provenance_turn_id="turn_42",
        provenance_evidence_id="ev_clang_flags_12",
        is_confirmed=True,
    )
    memory_store.write_memory(item)
    active = memory_store.get_active_memories("learner_alice", memory_type="mastery")
    assert len(active) == 1
    m = active[0]
    assert m.provenance_turn_id == "turn_42"
    assert m.provenance_evidence_id == "ev_clang_flags_12"
    assert m.confidence == 0.85
    assert m.is_confirmed is True


def test_expiry_policy(memory_store):
    current_time = time.time()
    # Create item with TTL of 10 seconds
    item = LearnerMemoryItem(
        item_id="temp_goal_01",
        learner_id="learner_alice",
        memory_type="goal",
        topic="problem_set",
        content="Finish pset 1 by tonight",
        confidence=0.95,
        provenance_turn_id="turn_1",
        created_at=current_time,
        expires_at=current_time + 10.0,
    )
    memory_store.write_memory(item, force=True)

    # Before expiry
    active = memory_store.get_active_memories("learner_alice", current_time=current_time + 5.0)
    assert len(active) == 1

    # After expiry (15 seconds later)
    expired = memory_store.get_active_memories("learner_alice", current_time=current_time + 15.0)
    assert len(expired) == 0


def test_temporal_decay_on_mastery(memory_store):
    current_time = time.time()
    item = LearnerMemoryItem(
        item_id="mastery_decay_01",
        learner_id="learner_alice",
        memory_type="mastery",
        topic="pointers",
        content="Confident with pointer arithmetic",
        confidence=1.0,
        provenance_turn_id="turn_1",
        created_at=current_time,
        updated_at=current_time,
    )
    memory_store.write_memory(item, force=True)

    # 10 days later: decay = 10 * 0.005 = 0.05 -> confidence should be 0.95
    active = memory_store.get_active_memories("learner_alice", current_time=current_time + 10 * 86400)
    assert len(active) == 1
    assert round(active[0].confidence, 2) == 0.95


def test_correction_policy_preserves_history(memory_store):
    item = LearnerMemoryItem(
        item_id="misconception_01",
        learner_id="learner_alice",
        memory_type="misconception",
        topic="arrays",
        content="Believes arrays in C are 1-indexed",
        confidence=0.88,
        provenance_turn_id="turn_3",
    )
    memory_store.write_memory(item)

    # Learner corrects misconception
    corrected = memory_store.correct_memory(
        item_id="misconception_01",
        new_content="Understands arrays in C are 0-indexed",
        reason="Corrected after lecture slide review",
    )
    assert corrected is not None
    assert corrected.content == "Understands arrays in C are 0-indexed"
    assert len(corrected.history) == 1
    assert corrected.history[0]["previous_content"] == "Believes arrays in C are 1-indexed"

    active = memory_store.get_active_memories("learner_alice")
    assert len(active) == 1
    assert active[0].content == "Understands arrays in C are 0-indexed"


def test_deletion_policy_immediate_erasure(memory_store):
    item = LearnerMemoryItem(
        item_id="goal_delete_01",
        learner_id="learner_alice",
        memory_type="goal",
        topic="exam",
        content="Study for midterm",
        confidence=0.90,
        provenance_turn_id="turn_9",
    )
    memory_store.write_memory(item)
    assert len(memory_store.get_active_memories("learner_alice")) == 1

    # Delete within 1 query cycle
    deleted = memory_store.delete_memory("goal_delete_01")
    assert deleted is True

    # Immediate query must be absent
    assert len(memory_store.get_active_memories("learner_alice")) == 0


def test_learner_isolation(memory_store):
    item_a = LearnerMemoryItem(
        item_id="goal_a",
        learner_id="learner_A",
        memory_type="goal",
        topic="algorithms",
        content="Master Merge Sort",
        confidence=0.9,
        provenance_turn_id="turn_1",
    )
    item_b = LearnerMemoryItem(
        item_id="goal_b",
        learner_id="learner_B",
        memory_type="goal",
        topic="memory",
        content="Understand malloc and free",
        confidence=0.9,
        provenance_turn_id="turn_1",
    )
    memory_store.write_memory(item_a)
    memory_store.write_memory(item_b)

    mems_a = memory_store.get_active_memories("learner_A")
    mems_b = memory_store.get_active_memories("learner_B")

    assert len(mems_a) == 1 and mems_a[0].topic == "algorithms"
    assert len(mems_b) == 1 and mems_b[0].topic == "memory"


def test_pedagogical_context_isolation(memory_store):
    item = LearnerMemoryItem(
        item_id="goal_iso_01",
        learner_id="learner_alice",
        memory_type="goal",
        topic="c_programming",
        content="Prepare for problem set 1",
        confidence=0.85,
        provenance_turn_id="turn_1",
    )
    memory_store.write_memory(item)
    context = memory_store.build_pedagogical_context("learner_alice")

    assert "[LEARNER PROFILE - PEDAGOGICAL STYLING ONLY - DO NOT CITE AS EVIDENCE]" in context
    assert "MUST NEVER cite these profile notes as instructional course evidence" in context


def test_purge_learner(memory_store):
    item = LearnerMemoryItem(
        item_id="goal_purge_01",
        learner_id="learner_purge",
        memory_type="goal",
        topic="test",
        content="Temporary goal",
        confidence=0.9,
        provenance_turn_id="t1",
    )
    memory_store.write_memory(item)
    count = memory_store.purge_learner("learner_purge")
    assert count == 1
    assert len(memory_store.get_active_memories("learner_purge")) == 0
