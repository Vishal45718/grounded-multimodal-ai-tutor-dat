"""Unit tests for Learner Memory data models (M5.1).

Covers all 14 test requirements:
1. LearnerProfile creation
2. MemoryEntry creation
3. MasteryState creation
4. LearnerCorrection creation
5. Invalid confidence rejection
6. Invalid mastery rejection
7. Empty identifier rejection
8. Invalid expiration timestamps
9. Deterministic memory IDs
10. Different learner IDs produce different memory IDs (learner isolation)
11. Timezone-aware timestamps
12. Default metadata isolation
13. Enum validation
14. Serialization and deserialization round-trip
"""
from datetime import datetime, timedelta, timezone

import pytest

from memory.models import (
    LearnerCorrection,
    LearnerProfile,
    MasteryState,
    MasteryStatus,
    MemoryEntry,
    MemoryType,
    compute_correction_id,
    compute_memory_id,
    now_utc,
)


# ---------------------------------------------------------------------------
# 1. LearnerProfile creation
# ---------------------------------------------------------------------------
def test_learner_profile_creation_minimal():
    profile = LearnerProfile(learner_id="learner_001")
    assert profile.learner_id == "learner_001"
    assert profile.created_at is not None
    assert profile.created_at.tzinfo == timezone.utc
    assert profile.updated_at == profile.created_at
    assert profile.preferred_learning_level is None
    assert profile.learning_preferences == {}
    assert profile.metadata == {}


def test_learner_profile_creation_full():
    t0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    profile = LearnerProfile(
        learner_id="learner_42",
        created_at=t0,
        updated_at=t1,
        preferred_learning_level="intermediate",
        learning_preferences={"visual": True, "pace": "slow"},
        metadata={"cohort": "fall_2026"},
    )
    assert profile.learner_id == "learner_42"
    assert profile.created_at == t0
    assert profile.updated_at == t1
    assert profile.preferred_learning_level == "intermediate"
    assert profile.learning_preferences["visual"] is True
    assert profile.metadata["cohort"] == "fall_2026"


# ---------------------------------------------------------------------------
# 2. MemoryEntry creation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "m_type",
    [
        MemoryType.LEARNING_GOAL,
        MemoryType.TOPIC_MASTERY,
        MemoryType.MISCONCEPTION,
        MemoryType.LEARNING_PREFERENCE,
        MemoryType.STUDENT_CORRECTION,
        MemoryType.STRUGGLED_CONCEPT,
    ],
)
def test_memory_entry_creation_all_enum_types(m_type):
    entry = MemoryEntry(
        learner_id="learner_001",
        memory_type=m_type,
        topic="pointers",
        content="Understands null pointer dereference",
        confidence=0.85,
    )
    assert entry.learner_id == "learner_001"
    assert entry.memory_type == m_type
    assert entry.topic == "pointers"
    assert entry.content == "Understands null pointer dereference"
    assert entry.confidence == 0.85
    assert len(entry.memory_id) == 64  # SHA-256 hex digest
    assert entry.is_active is True
    assert entry.created_at.tzinfo == timezone.utc


def test_memory_entry_with_explicit_id_and_source():
    entry = MemoryEntry(
        memory_id="custom_mem_999",
        learner_id="learner_002",
        memory_type="learning_goal",
        topic="recursion",
        content="Master base case termination",
        confidence=0.9,
        source={"turn_id": "turn_12", "chunk_id": "chunk_abc"},
    )
    assert entry.memory_id == "custom_mem_999"
    assert entry.memory_type == MemoryType.LEARNING_GOAL
    assert entry.source == {"turn_id": "turn_12", "chunk_id": "chunk_abc"}


# ---------------------------------------------------------------------------
# 3. MasteryState creation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "status",
    [
        MasteryStatus.NOT_STARTED,
        MasteryStatus.LEARNING,
        MasteryStatus.STRUGGLING,
        MasteryStatus.IMPROVING,
        MasteryStatus.MASTERED,
    ],
)
def test_mastery_state_creation(status):
    state = MasteryState(
        learner_id="learner_003",
        topic="binary_search",
        mastery_level=0.75,
        confidence=0.9,
        evidence_count=3,
        status=status,
    )
    assert state.learner_id == "learner_003"
    assert state.topic == "binary_search"
    assert state.mastery_level == 0.75
    assert state.confidence == 0.9
    assert state.evidence_count == 3
    assert state.status == status
    assert state.last_updated.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# 4. LearnerCorrection creation and attribution
# ---------------------------------------------------------------------------
def test_learner_correction_creation_and_attribution():
    corr = LearnerCorrection(
        learner_id="learner_004",
        target_memory_id="mem_target_123",
        original_content="Arrays are dynamic in C",
        corrected_content="Arrays have fixed size in C, malloc is needed for dynamic memory",
        reason="Clarified after lecture 4",
    )
    assert corr.learner_id == "learner_004"
    assert corr.target_memory_id == "mem_target_123"
    assert corr.reason == "Clarified after lecture 4"
    assert len(corr.correction_id) == 64
    assert corr.created_at.tzinfo == timezone.utc

    # Attribution checking
    assert corr.is_attributable_to("learner_004") is True
    assert corr.is_attributable_to("learner_other") is False
    assert corr.is_attributable_to("") is False

    matching_entry = MemoryEntry(
        memory_id="mem_target_123",
        learner_id="learner_004",
        memory_type=MemoryType.MISCONCEPTION,
        topic="c_arrays",
        content="Arrays are dynamic in C",
    )
    mismatched_entry = MemoryEntry(
        memory_id="mem_target_123",
        learner_id="learner_imposter",
        memory_type=MemoryType.MISCONCEPTION,
        topic="c_arrays",
        content="Arrays are dynamic in C",
    )
    assert corr.matches_memory(matching_entry) is True
    assert corr.matches_memory(mismatched_entry) is False


# ---------------------------------------------------------------------------
# 5. Invalid confidence rejection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("invalid_conf", [-0.01, -1.0, 1.01, 2.0, 100.0])
def test_invalid_confidence_rejection_memory_entry(invalid_conf):
    with pytest.raises(ValueError, match="confidence .* must be between 0.0 and 1.0"):
        MemoryEntry(
            learner_id="l1",
            memory_type=MemoryType.LEARNING_GOAL,
            topic="test",
            content="test",
            confidence=invalid_conf,
        )


@pytest.mark.parametrize("invalid_conf", [-0.5, 1.5])
def test_invalid_confidence_rejection_mastery_state(invalid_conf):
    with pytest.raises(ValueError, match="confidence .* must be between 0.0 and 1.0"):
        MasteryState(
            learner_id="l1",
            topic="test",
            mastery_level=0.5,
            confidence=invalid_conf,
        )


@pytest.mark.parametrize("bad_type_conf", ["0.5", None, True, False, []])
def test_non_numeric_confidence_rejected(bad_type_conf):
    with pytest.raises(TypeError):
        MemoryEntry(
            learner_id="l1",
            memory_type=MemoryType.LEARNING_GOAL,
            topic="test",
            content="test",
            confidence=bad_type_conf,
        )


# ---------------------------------------------------------------------------
# 6. Invalid mastery rejection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("invalid_mastery", [-0.01, -1.0, 1.01, 5.0, 100.0])
def test_invalid_mastery_level_rejected(invalid_mastery):
    with pytest.raises(ValueError, match="mastery_level .* must be between 0.0 and 1.0"):
        MasteryState(
            learner_id="l1",
            topic="test",
            mastery_level=invalid_mastery,
            confidence=0.8,
        )


@pytest.mark.parametrize("bad_type_mastery", ["0.8", None, True, {}])
def test_non_numeric_mastery_level_rejected(bad_type_mastery):
    with pytest.raises(TypeError):
        MasteryState(
            learner_id="l1",
            topic="test",
            mastery_level=bad_type_mastery,
            confidence=0.8,
        )


def test_invalid_evidence_count_rejected():
    with pytest.raises(ValueError, match="evidence_count .* must be >= 0"):
        MasteryState(
            learner_id="l1",
            topic="test",
            mastery_level=0.5,
            confidence=0.8,
            evidence_count=-1,
        )


# ---------------------------------------------------------------------------
# 7. Empty identifier rejection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("empty_id", ["", "   ", "\t\n"])
def test_empty_learner_id_rejected_across_models(empty_id):
    with pytest.raises(ValueError, match="learner_id cannot be empty"):
        LearnerProfile(learner_id=empty_id)

    with pytest.raises(ValueError, match="learner_id cannot be empty"):
        MemoryEntry(
            learner_id=empty_id,
            memory_type=MemoryType.LEARNING_GOAL,
            topic="loops",
            content="for loops",
        )

    with pytest.raises(ValueError, match="learner_id cannot be empty"):
        MasteryState(learner_id=empty_id, topic="loops")

    with pytest.raises(ValueError, match="learner_id cannot be empty"):
        LearnerCorrection(
            learner_id=empty_id,
            target_memory_id="mem1",
            original_content="c1",
            corrected_content="c2",
        )


@pytest.mark.parametrize("empty_str", ["", "   "])
def test_empty_topic_rejected(empty_str):
    with pytest.raises(ValueError, match="topic cannot be empty"):
        MemoryEntry(
            learner_id="l1",
            memory_type=MemoryType.LEARNING_GOAL,
            topic=empty_str,
            content="content",
        )

    with pytest.raises(ValueError, match="topic cannot be empty"):
        MasteryState(learner_id="l1", topic=empty_str)


@pytest.mark.parametrize("empty_str", ["", "   "])
def test_empty_content_rejected(empty_str):
    with pytest.raises(ValueError, match="content cannot be empty"):
        MemoryEntry(
            learner_id="l1",
            memory_type=MemoryType.LEARNING_GOAL,
            topic="topic",
            content=empty_str,
        )


@pytest.mark.parametrize("empty_str", ["", "   "])
def test_empty_memory_id_rejected_when_explicitly_passed(empty_str):
    with pytest.raises(ValueError, match="memory_id cannot be empty"):
        MemoryEntry(
            memory_id=empty_str,
            learner_id="l1",
            memory_type=MemoryType.LEARNING_GOAL,
            topic="topic",
            content="content",
        )


@pytest.mark.parametrize("empty_str", ["", "   "])
def test_empty_correction_fields_rejected(empty_str):
    with pytest.raises(ValueError, match="target_memory_id cannot be empty"):
        LearnerCorrection(
            learner_id="l1",
            target_memory_id=empty_str,
            original_content="orig",
            corrected_content="corr",
        )

    with pytest.raises(ValueError, match="original_content cannot be empty"):
        LearnerCorrection(
            learner_id="l1",
            target_memory_id="mem1",
            original_content=empty_str,
            corrected_content="corr",
        )

    with pytest.raises(ValueError, match="corrected_content cannot be empty"):
        LearnerCorrection(
            learner_id="l1",
            target_memory_id="mem1",
            original_content="orig",
            corrected_content=empty_str,
        )

    with pytest.raises(ValueError, match="correction_id cannot be empty"):
        LearnerCorrection(
            correction_id=empty_str,
            learner_id="l1",
            target_memory_id="mem1",
            original_content="orig",
            corrected_content="corr",
        )


# ---------------------------------------------------------------------------
# 8. Invalid expiration timestamps
# ---------------------------------------------------------------------------
def test_expires_at_cannot_precede_created_at():
    t_create = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    t_expired = datetime(2026, 11, 2, 11, 59, 59, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="expires_at cannot precede created_at"):
        MemoryEntry(
            learner_id="l1",
            memory_type=MemoryType.LEARNING_GOAL,
            topic="recursion",
            content="understanding stack frames",
            created_at=t_create,
            expires_at=t_expired,
        )


def test_updated_at_cannot_precede_created_at():
    t_create = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    t_earlier = datetime(2026, 11, 2, 11, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="updated_at cannot precede created_at"):
        LearnerProfile(
            learner_id="l1",
            created_at=t_create,
            updated_at=t_earlier,
        )

    with pytest.raises(ValueError, match="updated_at cannot precede created_at"):
        MemoryEntry(
            learner_id="l1",
            memory_type=MemoryType.LEARNING_GOAL,
            topic="recursion",
            content="understanding stack frames",
            created_at=t_create,
            updated_at=t_earlier,
        )


def test_valid_expiration_timestamp_accepted():
    t_create = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    t_expire = t_create + timedelta(days=30)
    entry = MemoryEntry(
        learner_id="l1",
        memory_type=MemoryType.LEARNING_GOAL,
        topic="recursion",
        content="understanding stack frames",
        created_at=t_create,
        expires_at=t_expire,
    )
    assert entry.expires_at == t_expire


# ---------------------------------------------------------------------------
# 9. Deterministic memory IDs
# ---------------------------------------------------------------------------
def test_deterministic_memory_id_computation():
    id1 = compute_memory_id(
        learner_id="student_101",
        memory_type=MemoryType.MISCONCEPTION,
        topic="Pointers",
        content="Pointer arithmetic is in bytes not type size",
    )
    id2 = compute_memory_id(
        learner_id="student_101",
        memory_type="misconception",
        topic="  pointers  ",
        content="Pointer arithmetic is in bytes not type size",
    )
    assert id1 == id2
    assert len(id1) == 64

    # Entry auto-assigns the exact same deterministic ID
    entry = MemoryEntry(
        learner_id="student_101",
        memory_type=MemoryType.MISCONCEPTION,
        topic="pointers",
        content="Pointer arithmetic is in bytes not type size",
    )
    assert entry.memory_id == id1


def test_deterministic_correction_id_computation():
    c_id1 = compute_correction_id("l1", "m1", "corrected text")
    c_id2 = compute_correction_id(" l1 ", " m1 ", "corrected text")
    assert c_id1 == c_id2
    assert len(c_id1) == 64


# ---------------------------------------------------------------------------
# 10. Different learner IDs produce different memory IDs (Learner Isolation)
# ---------------------------------------------------------------------------
def test_different_learner_ids_produce_different_memory_ids():
    id_learner_a = compute_memory_id(
        learner_id="learner_alpha",
        memory_type=MemoryType.TOPIC_MASTERY,
        topic="binary_trees",
        content="Can traverse in-order and post-order",
    )
    id_learner_b = compute_memory_id(
        learner_id="learner_beta",
        memory_type=MemoryType.TOPIC_MASTERY,
        topic="binary_trees",
        content="Can traverse in-order and post-order",
    )
    assert id_learner_a != id_learner_b


def test_different_topics_or_types_produce_different_memory_ids():
    base_args = {
        "learner_id": "learner_same",
        "topic": "sorting",
        "content": "Merge sort has O(n log n) worst-case time complexity",
    }
    id_mastery = compute_memory_id(memory_type=MemoryType.TOPIC_MASTERY, **base_args)
    id_goal = compute_memory_id(memory_type=MemoryType.LEARNING_GOAL, **base_args)
    assert id_mastery != id_goal


# ---------------------------------------------------------------------------
# 11. Timezone-aware timestamps
# ---------------------------------------------------------------------------
def test_naive_timestamps_rejected():
    naive_dt = datetime(2026, 11, 2, 12, 0, 0)  # No tzinfo

    with pytest.raises(ValueError, match="must be a timezone-aware UTC datetime"):
        LearnerProfile(learner_id="l1", created_at=naive_dt)

    with pytest.raises(ValueError, match="must be a timezone-aware UTC datetime"):
        MemoryEntry(
            learner_id="l1",
            memory_type=MemoryType.LEARNING_GOAL,
            topic="t",
            content="c",
            created_at=naive_dt,
        )

    with pytest.raises(ValueError, match="must be a timezone-aware UTC datetime"):
        MasteryState(learner_id="l1", topic="t", last_updated=naive_dt)

    with pytest.raises(ValueError, match="must be a timezone-aware UTC datetime"):
        LearnerCorrection(
            learner_id="l1",
            target_memory_id="m1",
            original_content="o",
            corrected_content="c",
            created_at=naive_dt,
        )


def test_non_utc_timezone_normalized_to_utc():
    # +05:30 offset
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    dt_ist = datetime(2026, 11, 2, 17, 30, 0, tzinfo=tz_ist)

    profile = LearnerProfile(learner_id="l1", created_at=dt_ist)
    assert profile.created_at.tzinfo == timezone.utc
    assert profile.created_at.hour == 12  # 17:30 - 5:30 = 12:00 UTC


# ---------------------------------------------------------------------------
# 12. Default metadata isolation
# ---------------------------------------------------------------------------
def test_default_metadata_and_preferences_isolated_between_instances():
    p1 = LearnerProfile(learner_id="l1")
    p2 = LearnerProfile(learner_id="l2")

    p1.metadata["theme"] = "dark"
    p1.learning_preferences["pace"] = "fast"
    assert "theme" not in p2.metadata
    assert "pace" not in p2.learning_preferences

    m1 = MemoryEntry(
        learner_id="l1",
        memory_type=MemoryType.LEARNING_GOAL,
        topic="t1",
        content="c1",
    )
    m2 = MemoryEntry(
        learner_id="l2",
        memory_type=MemoryType.LEARNING_GOAL,
        topic="t2",
        content="c2",
    )

    m1.metadata["flag"] = True
    assert "flag" not in m2.metadata


def test_caller_mutation_of_dict_does_not_mutate_model():
    incoming_meta = {"key": "original"}
    profile = LearnerProfile(learner_id="l1", metadata=incoming_meta)
    incoming_meta["key"] = "mutated"
    assert profile.metadata["key"] == "original"


# ---------------------------------------------------------------------------
# 13. Enum validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "alias,expected",
    [
        ("learning_goal", MemoryType.LEARNING_GOAL),
        ("goal", MemoryType.LEARNING_GOAL),
        ("goals", MemoryType.LEARNING_GOAL),
        ("topic_mastery", MemoryType.TOPIC_MASTERY),
        ("mastery", MemoryType.TOPIC_MASTERY),
        ("misconception", MemoryType.MISCONCEPTION),
        ("misconceptions", MemoryType.MISCONCEPTION),
        ("learning_preference", MemoryType.LEARNING_PREFERENCE),
        ("preferences", MemoryType.LEARNING_PREFERENCE),
        ("student_correction", MemoryType.STUDENT_CORRECTION),
        ("corrections", MemoryType.STUDENT_CORRECTION),
        ("struggled_concept", MemoryType.STRUGGLED_CONCEPT),
    ],
)
def test_valid_memory_type_aliases(alias, expected):
    entry = MemoryEntry(
        learner_id="l1",
        memory_type=alias,
        topic="topic",
        content="content",
    )
    assert entry.memory_type == expected


@pytest.mark.parametrize("invalid_type", ["random_type", "unsupported", "invalid", "123"])
def test_invalid_memory_type_rejected(invalid_type):
    with pytest.raises(ValueError, match="Invalid memory_type"):
        MemoryEntry(
            learner_id="l1",
            memory_type=invalid_type,
            topic="topic",
            content="content",
        )


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("not_started", MasteryStatus.NOT_STARTED),
        ("learning", MasteryStatus.LEARNING),
        ("struggling", MasteryStatus.STRUGGLING),
        ("improving", MasteryStatus.IMPROVING),
        ("mastered", MasteryStatus.MASTERED),
    ],
)
def test_valid_mastery_status_aliases(alias, expected):
    state = MasteryState(learner_id="l1", topic="topic", status=alias)
    assert state.status == expected


@pytest.mark.parametrize("invalid_status", ["pro", "expert", "failed", "completed"])
def test_invalid_mastery_status_rejected(invalid_status):
    with pytest.raises(ValueError, match="Invalid mastery status"):
        MasteryState(learner_id="l1", topic="topic", status=invalid_status)


# ---------------------------------------------------------------------------
# 14. Serialization and deserialization round-trip
# ---------------------------------------------------------------------------
def test_learner_profile_serialization_round_trip():
    original = LearnerProfile(
        learner_id="learner_roundtrip",
        preferred_learning_level="advanced",
        learning_preferences={"code_examples": "C99", "verbosity": "high"},
        metadata={"created_via": "cli"},
    )
    serialized = original.to_dict()
    restored = LearnerProfile.from_dict(serialized)

    assert restored.learner_id == original.learner_id
    assert restored.preferred_learning_level == original.preferred_learning_level
    assert restored.learning_preferences == original.learning_preferences
    assert restored.metadata == original.metadata
    assert restored.created_at == original.created_at
    assert restored.updated_at == original.updated_at


def test_memory_entry_serialization_round_trip():
    t0 = now_utc()
    t_exp = t0 + timedelta(days=14)
    original = MemoryEntry(
        learner_id="learner_rt_mem",
        memory_type=MemoryType.STRUGGLED_CONCEPT,
        topic="hash_tables",
        content="Collision resolution with quadratic probing",
        confidence=0.72,
        source={"turn": 5, "session": "s_123"},
        created_at=t0,
        expires_at=t_exp,
        is_active=True,
        metadata={"attempts": 3},
    )
    serialized = original.to_dict()
    restored = MemoryEntry.from_dict(serialized)

    assert restored.memory_id == original.memory_id
    assert restored.learner_id == original.learner_id
    assert restored.memory_type == original.memory_type
    assert restored.topic == original.topic
    assert restored.content == original.content
    assert restored.confidence == original.confidence
    assert restored.source == original.source
    assert restored.created_at == original.created_at
    assert restored.expires_at == original.expires_at
    assert restored.is_active == original.is_active
    assert restored.metadata == original.metadata


def test_mastery_state_serialization_round_trip():
    original = MasteryState(
        learner_id="learner_rt_mastery",
        topic="graph_algorithms",
        mastery_level=0.88,
        confidence=0.95,
        evidence_count=7,
        status=MasteryStatus.IMPROVING,
        metadata={"last_quiz_score": 90},
    )
    serialized = original.to_dict()
    restored = MasteryState.from_dict(serialized)

    assert restored.learner_id == original.learner_id
    assert restored.topic == original.topic
    assert restored.mastery_level == original.mastery_level
    assert restored.confidence == original.confidence
    assert restored.evidence_count == original.evidence_count
    assert restored.status == original.status
    assert restored.last_updated == original.last_updated
    assert restored.metadata == original.metadata


def test_learner_correction_serialization_round_trip():
    original = LearnerCorrection(
        learner_id="learner_rt_corr",
        target_memory_id="mem_target_xyz",
        original_content="Big-O denotes lower bound",
        corrected_content="Big-O denotes asymptotic upper bound, Omega denotes lower bound",
        reason="Corrected terminology misconception",
        metadata={"verified_by_tutor": True},
    )
    serialized = original.to_dict()
    restored = LearnerCorrection.from_dict(serialized)

    assert restored.correction_id == original.correction_id
    assert restored.learner_id == original.learner_id
    assert restored.target_memory_id == original.target_memory_id
    assert restored.original_content == original.original_content
    assert restored.corrected_content == original.corrected_content
    assert restored.reason == original.reason
    assert restored.created_at == original.created_at
    assert restored.metadata == original.metadata
