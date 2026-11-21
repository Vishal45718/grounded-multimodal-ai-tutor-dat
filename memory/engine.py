"""In-memory or SQLite-backed learner memory engine (M5.2).

Deterministic storage. When ``store`` is provided, profile and memory
records are persisted across restarts in SQLite. Learner records are isolated
by ``learner_id`` and are never corpus evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Union, TYPE_CHECKING

from memory.models import (
    LearnerCorrection,
    LearnerProfile,
    MasteryState,
    MasteryStatus,
    MemoryEntry,
    MemoryType,
    _normalize_mastery_status,
    _normalize_memory_type,
    now_utc,
)
from memory.policy import MemoryDecision, MemoryPolicy

if TYPE_CHECKING:
    from memory.store import LearnerMemoryStore


Clock = Callable[[], datetime]


class MemoryRejected(ValueError):
    """Raised when policy refuses to store a memory."""


class MemoryNotFound(KeyError):
    """Raised when a correction targets a missing or foreign memory."""


@dataclass(frozen=True)
class LearnerContext:
    """Compact learner-side context. This is not verified source evidence."""

    learner_id: str
    memories: List[MemoryEntry]
    mastery: List[MasteryState]
    kind: str = "learner_context"
    label: str = "Learner context (not verified corpus evidence)"
    is_corpus_evidence: bool = False


def _topic_key(topic: str) -> str:
    return topic.strip().lower()


class LearnerMemoryEngine:
    """Create, retrieve, correct, and delete learner memories in memory or SQLite store.

    Public operations:
    - ``upsert_profile`` / ``get_profile``
    - ``add_memory`` / ``get_memories`` / ``get_memory``
    - ``update_mastery``
    - ``track_misconception``
    - ``apply_correction`` / ``get_corrections``
    - ``delete_memory``
    - ``build_learner_context``

    Isolation: every lookup is keyed by ``learner_id``. A memory ID from one
    learner cannot be read, corrected, or deleted as another learner.

    Corrections deactivate the original entry and insert a replacement so the
    original content remains auditable. Deletion removes the entry from the
    store; missing IDs return False and do not affect other learners.

    Mastery: ``MASTERED`` requires the policy's evidence, confidence, and
    level floors. One weak observation stays at LEARNING.
    """

    def __init__(
        self,
        policy: Optional[MemoryPolicy] = None,
        clock: Optional[Clock] = None,
        store: Optional[LearnerMemoryStore] = None,
    ) -> None:
        shared_clock = clock or now_utc
        self.policy = policy or MemoryPolicy(clock=shared_clock)
        if clock is not None:
            self.policy.clock = clock
        self.store = store
        self._profiles: Dict[str, LearnerProfile] = {}
        self._memories: Dict[str, Dict[str, MemoryEntry]] = {}
        self._mastery: Dict[str, Dict[str, MasteryState]] = {}
        self._corrections: Dict[str, List[LearnerCorrection]] = {}

    def now(self) -> datetime:
        return self.policy.now()

    def upsert_profile(
        self,
        learner_id: str,
        *,
        preferred_learning_level: Optional[str] = None,
        learning_preferences: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> LearnerProfile:
        """Create a profile or update allowed preference fields.

        ``created_at`` is preserved on updates; ``updated_at`` follows the clock.
        """
        existing = (
            self.store.get_profile(learner_id)
            if self.store is not None
            else self._profiles.get(learner_id)
        )
        moment = self.now()
        if existing is None:
            profile = LearnerProfile(
                learner_id=learner_id,
                created_at=moment,
                updated_at=moment,
                preferred_learning_level=preferred_learning_level,
                learning_preferences=dict(learning_preferences or {}),
                metadata=dict(metadata or {}),
            )
        else:
            merged_prefs = dict(existing.learning_preferences)
            if learning_preferences:
                merged_prefs.update(learning_preferences)
            merged_meta = dict(existing.metadata)
            if metadata:
                merged_meta.update(metadata)
            profile = LearnerProfile(
                learner_id=existing.learner_id,
                created_at=existing.created_at,
                updated_at=moment,
                preferred_learning_level=(
                    preferred_learning_level
                    if preferred_learning_level is not None
                    else existing.preferred_learning_level
                ),
                learning_preferences=merged_prefs,
                metadata=merged_meta,
            )

        if self.store is not None:
            self.store.upsert_profile(profile)
        self._profiles[profile.learner_id] = profile
        return profile

    def get_profile(self, learner_id: str) -> Optional[LearnerProfile]:
        if self.store is not None:
            profile = self.store.get_profile(learner_id)
            if profile is not None:
                self._profiles[learner_id] = profile
                return profile
        return self._profiles.get(learner_id)

    def add_memory(self, entry: MemoryEntry) -> MemoryEntry:
        """Validate, apply policy, and store a memory isolated by learner.

        Duplicate deterministic IDs update in place and keep ``created_at``.
        Inactive entries may be stored for audit but are excluded from retrieval.
        """
        decision = self.policy.evaluate(entry)
        if decision.action is MemoryDecision.REJECT:
            raise MemoryRejected(decision.reason)
        if decision.action is MemoryDecision.EXPIRE:
            raise MemoryRejected(decision.reason)

        existing = (
            self.store.get_memory(entry.learner_id, entry.memory_id, include_inactive=True)
            if self.store is not None
            else self._memories.get(entry.learner_id, {}).get(entry.memory_id)
        )

        if existing is not None:
            stored = MemoryEntry(
                memory_id=existing.memory_id,
                learner_id=existing.learner_id,
                memory_type=entry.memory_type,
                topic=entry.topic,
                content=entry.content,
                confidence=entry.confidence,
                source=entry.source,
                created_at=existing.created_at,
                updated_at=self.now(),
                expires_at=entry.expires_at if entry.expires_at is not None else existing.expires_at,
                is_active=entry.is_active,
                metadata={**existing.metadata, **entry.metadata},
            )
        else:
            stored = entry

        if self.store is not None:
            self.store.add_memory(stored)

        bucket = self._memories.setdefault(stored.learner_id, {})
        bucket[stored.memory_id] = stored
        return stored

    def _owned(self, learner_id: str, memory_id: str) -> Optional[MemoryEntry]:
        if self.store is not None:
            entry = self.store.get_memory(learner_id, memory_id, include_inactive=True)
            if entry is not None:
                self._memories.setdefault(learner_id, {})[memory_id] = entry
                return entry
        return self._memories.get(learner_id, {}).get(memory_id)

    def get_memory(
        self,
        learner_id: str,
        memory_id: str,
        *,
        include_inactive: bool = False,
    ) -> Optional[MemoryEntry]:
        entry = self._owned(learner_id, memory_id)
        if entry is None:
            return None
        if include_inactive:
            return entry
        if not self.policy.is_retrievable(entry):
            return None
        return entry

    def get_memories(
        self,
        learner_id: str,
        memory_type: Optional[Union[MemoryType, str]] = None,
        topic: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """Active, non-expired memories for one learner, ordered deterministically."""
        resolved_type = (
            _normalize_memory_type(memory_type) if memory_type is not None else None
        )
        topic_filter = _topic_key(topic) if topic else None

        if self.store is not None:
            # Query from store, respecting policy retrievability and ordering
            store_entries = self.store.get_memories(
                learner_id,
                memory_type=resolved_type,
                topic=topic,
                include_inactive=False,
                as_of=self.now(),
            )
            items = [m for m in store_entries if self.policy.is_retrievable(m)]
        else:
            items = []
            for entry in self._memories.get(learner_id, {}).values():
                if not self.policy.is_retrievable(entry):
                    continue
                if resolved_type is not None and entry.memory_type is not resolved_type:
                    continue
                if topic_filter is not None and _topic_key(entry.topic) != topic_filter:
                    continue
                items.append(entry)

        items.sort(key=lambda m: (m.created_at, m.memory_id, m.topic))
        return items

    def update_mastery(
        self,
        learner_id: str,
        topic: str,
        *,
        mastery_level: float,
        confidence: float,
        status: Optional[Union[MasteryStatus, str]] = None,
        evidence_increment: int = 1,
    ) -> MasteryState:
        """Create or update topic mastery. Weak evidence cannot yield MASTERED."""
        if evidence_increment < 1:
            raise ValueError("evidence_increment must be >= 1")

        key = _topic_key(topic)
        previous = None
        if self.store is not None:
            existing_states = self.store.get_mastery(learner_id, topic=topic)
            previous = existing_states[0] if existing_states else None
        if previous is None:
            by_topic = self._mastery.setdefault(learner_id, {})
            previous = by_topic.get(key)

        evidence_count = (previous.evidence_count if previous else 0) + evidence_increment
        requested_status = _normalize_mastery_status(
            status if status is not None else (
                previous.status if previous else MasteryStatus.LEARNING
            )
        )
        if requested_status is MasteryStatus.MASTERED:
            allowed, _reason = self.policy.allows_mastered_status(
                evidence_count=evidence_count,
                confidence=confidence,
                mastery_level=mastery_level,
            )
            if not allowed:
                requested_status = (
                    MasteryStatus.IMPROVING if evidence_count >= 2 else MasteryStatus.LEARNING
                )
        state = MasteryState(
            learner_id=learner_id,
            topic=previous.topic if previous else topic,
            mastery_level=mastery_level,
            confidence=confidence,
            evidence_count=evidence_count,
            last_updated=self.now(),
            status=requested_status,
            metadata=dict(previous.metadata) if previous else {},
        )

        if self.store is not None:
            self.store.update_mastery(state)

        by_topic = self._mastery.setdefault(learner_id, {})
        by_topic[key] = state
        return state

    def get_mastery(self, learner_id: str, topic: Optional[str] = None) -> List[MasteryState]:
        if self.store is not None:
            states = self.store.get_mastery(learner_id, topic=topic)
        else:
            states = list(self._mastery.get(learner_id, {}).values())
            if topic is not None:
                key = _topic_key(topic)
                states = [s for s in states if _topic_key(s.topic) == key]
        states.sort(key=lambda s: (s.topic.lower(), s.learner_id))
        return states

    def track_misconception(
        self,
        learner_id: str,
        topic: str,
        content: str,
        *,
        confidence: float = 1.0,
        source=None,
    ) -> MemoryEntry:
        """Create or update a misconception memory, preserving source."""
        entry = MemoryEntry(
            learner_id=learner_id,
            memory_type=MemoryType.MISCONCEPTION,
            topic=topic,
            content=content,
            confidence=confidence,
            source=source,
            created_at=self.now(),
        )
        return self.add_memory(entry)

    def apply_correction(self, correction: LearnerCorrection) -> MemoryEntry:
        """Record a correction, deactivate the original, and store a replacement.

        The original content is kept on the inactive entry and in correction
        history. The original is never overwritten in place.
        """
        original = self._owned(correction.learner_id, correction.target_memory_id)
        if original is None or not correction.matches_memory(original):
            raise MemoryNotFound(
                f"memory {correction.target_memory_id!r} not found for learner "
                f"{correction.learner_id!r}"
            )

        replacement = MemoryEntry(
            learner_id=original.learner_id,
            memory_type=original.memory_type,
            topic=original.topic,
            content=correction.corrected_content,
            confidence=1.0,
            source={"kind": "learner_correction", "correction_id": correction.correction_id},
            created_at=self.now(),
            metadata={
                "supersedes": original.memory_id,
                "correction_id": correction.correction_id,
            },
        )
        deactivated = MemoryEntry(
            memory_id=original.memory_id,
            learner_id=original.learner_id,
            memory_type=original.memory_type,
            topic=original.topic,
            content=original.content,
            confidence=original.confidence,
            source=original.source,
            created_at=original.created_at,
            updated_at=self.now(),
            expires_at=original.expires_at,
            is_active=False,
            metadata={
                **original.metadata,
                "correction_id": correction.correction_id,
                "superseded_by": replacement.memory_id,
            },
        )

        if self.store is not None:
            self.store.apply_correction(correction)

        self._corrections.setdefault(correction.learner_id, []).append(correction)
        self._memories.setdefault(original.learner_id, {})[deactivated.memory_id] = deactivated
        self._memories.setdefault(replacement.learner_id, {})[replacement.memory_id] = replacement
        return replacement

    def get_corrections(self, learner_id: str) -> List[LearnerCorrection]:
        if self.store is not None:
            items = self.store.get_corrections(learner_id)
        else:
            items = list(self._corrections.get(learner_id, []))
        items.sort(key=lambda c: (c.created_at, c.correction_id))
        return items

    def delete_memory(self, learner_id: str, memory_id: str) -> bool:
        """Delete one memory owned by ``learner_id``. Missing IDs return False.

        A caller cannot delete another learner's memory by ID.
        """
        deleted_in_store = False
        if self.store is not None:
            deleted_in_store = self.store.delete_memory(learner_id, memory_id)

        bucket = self._memories.get(learner_id)
        deleted_in_mem = False
        if bucket and memory_id in bucket:
            del bucket[memory_id]
            deleted_in_mem = True

        return deleted_in_store or deleted_in_mem

    def build_learner_context(
        self,
        learner_id: str,
        *,
        max_entries: Optional[int] = None,
    ) -> LearnerContext:
        """Compact active memories for prompting. Not corpus-grounded evidence."""
        limit = max_entries if max_entries is not None else self.policy.max_context_entries
        if limit < 1:
            raise ValueError("max_entries must be >= 1")
        memories = self.get_memories(learner_id)[:limit]
        mastery = self.get_mastery(learner_id)
        return LearnerContext(
            learner_id=learner_id,
            memories=memories,
            mastery=mastery,
        )
