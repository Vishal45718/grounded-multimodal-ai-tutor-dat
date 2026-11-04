"""Learner Memory package for Grounded Multimodal AI Tutor (M5).

Public API:
- Models (M5.1): profiles, entries, mastery, corrections, deterministic IDs.
- Policy (M5.2): confidence, expiration, retention, and safety decisions.
- Engine (M5.2): in-memory, learner-isolated operations. Not durable and not
  corpus-grounded evidence.

Example::

    from memory import LearnerMemoryEngine, MemoryEntry, MemoryType

    engine = LearnerMemoryEngine()
    engine.upsert_profile("learner_a", preferred_learning_level="beginner")
    engine.add_memory(MemoryEntry(
        learner_id="learner_a",
        memory_type=MemoryType.LEARNING_GOAL,
        topic="pointers",
        content="Learn malloc and free",
        confidence=0.9,
        source={"kind": "learner_statement"},
    ))
    ctx = engine.build_learner_context("learner_a")
    # ctx.kind == "learner_context"; do not treat as retrieved evidence
"""

from memory.engine import (
    LearnerContext,
    LearnerMemoryEngine,
    MemoryNotFound,
    MemoryRejected,
)
from memory.models import (
    LearnerCorrection,
    LearnerProfile,
    MasteryState,
    MasteryStatus,
    MemoryEntry,
    MemoryType,
    compute_correction_id,
    compute_memory_id,
)
from memory.policy import MemoryDecision, MemoryPolicy, MemoryPolicyError

__all__ = [
    "LearnerProfile",
    "MemoryEntry",
    "MasteryState",
    "LearnerCorrection",
    "MemoryType",
    "MasteryStatus",
    "compute_memory_id",
    "compute_correction_id",
    "MemoryPolicy",
    "MemoryPolicyError",
    "MemoryDecision",
    "LearnerMemoryEngine",
    "LearnerContext",
    "MemoryRejected",
    "MemoryNotFound",
]
