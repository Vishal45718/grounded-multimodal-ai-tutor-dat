"""Foundational data models for selective learner memory (M5.1).

Defines strongly typed, validated dataclasses for:
1. LearnerProfile: Persistent learner profile with preferences and metadata.
2. MemoryEntry: Individual memory items (goals, mastery, misconceptions, preferences, etc.)
   with deterministic SHA-256 IDs and confidence scoring.
3. MasteryState: Topic mastery tracking across discrete progress stages.
4. LearnerCorrection: Attributable corrections supplied by learners to supersede or update memories.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Union


class MemoryType(str, Enum):
    """Supported categories of learner memory records."""
    LEARNING_GOAL = "learning_goal"
    TOPIC_MASTERY = "topic_mastery"
    MISCONCEPTION = "misconception"
    LEARNING_PREFERENCE = "learning_preference"
    STUDENT_CORRECTION = "student_correction"
    STRUGGLED_CONCEPT = "struggled_concept"


class MasteryStatus(str, Enum):
    """Discrete progression stages for a learner's topic mastery."""
    NOT_STARTED = "not_started"
    LEARNING = "learning"
    STRUGGLING = "struggling"
    IMPROVING = "improving"
    MASTERED = "mastered"


_MEMORY_TYPE_ALIASES: Dict[str, MemoryType] = {
    "learning_goal": MemoryType.LEARNING_GOAL,
    "learning_goals": MemoryType.LEARNING_GOAL,
    "goal": MemoryType.LEARNING_GOAL,
    "goals": MemoryType.LEARNING_GOAL,
    "topic_mastery": MemoryType.TOPIC_MASTERY,
    "mastery": MemoryType.TOPIC_MASTERY,
    "misconception": MemoryType.MISCONCEPTION,
    "misconceptions": MemoryType.MISCONCEPTION,
    "learning_preference": MemoryType.LEARNING_PREFERENCE,
    "learning_preferences": MemoryType.LEARNING_PREFERENCE,
    "preference": MemoryType.LEARNING_PREFERENCE,
    "preferences": MemoryType.LEARNING_PREFERENCE,
    "student_correction": MemoryType.STUDENT_CORRECTION,
    "student_corrections": MemoryType.STUDENT_CORRECTION,
    "correction": MemoryType.STUDENT_CORRECTION,
    "corrections": MemoryType.STUDENT_CORRECTION,
    "struggled_concept": MemoryType.STRUGGLED_CONCEPT,
    "struggled_concepts": MemoryType.STRUGGLED_CONCEPT,
    "struggling_concept": MemoryType.STRUGGLED_CONCEPT,
}

_MASTERY_STATUS_ALIASES: Dict[str, MasteryStatus] = {
    "not_started": MasteryStatus.NOT_STARTED,
    "learning": MasteryStatus.LEARNING,
    "struggling": MasteryStatus.STRUGGLING,
    "improving": MasteryStatus.IMPROVING,
    "masterED": MasteryStatus.MASTERED,
    "mastered": MasteryStatus.MASTERED,
}


def now_utc() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _validate_utc_datetime(
    dt: Any,
    field_name: str,
    allow_none: bool = False,
) -> Optional[datetime]:
    """Validate that a datetime is a timezone-aware UTC datetime."""
    if dt is None:
        if allow_none:
            return None
        raise ValueError(f"{field_name} cannot be None")
    if not isinstance(dt, datetime):
        raise TypeError(f"{field_name} must be a datetime instance, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f"{field_name} must be a timezone-aware UTC datetime")
    # Normalize to UTC
    return dt.astimezone(timezone.utc)


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    """Validate that a string value is non-empty and non-whitespace."""
    if not isinstance(val, str) or not val.strip():
        raise ValueError(f"{field_name} cannot be empty")
    return val.strip()


def _validate_confidence(val: Any, field_name: str = "confidence") -> float:
    """Validate that confidence is a float in [0.0, 1.0]."""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise TypeError(f"{field_name} must be a numeric float or int, got {type(val).__name__}")
    fval = float(val)
    if not (0.0 <= fval <= 1.0):
        raise ValueError(f"{field_name} ({fval}) must be between 0.0 and 1.0")
    return fval


def _validate_mastery_level(val: Any, field_name: str = "mastery_level") -> float:
    """Validate that mastery_level is a float in [0.0, 1.0]."""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise TypeError(f"{field_name} must be a numeric float or int, got {type(val).__name__}")
    fval = float(val)
    if not (0.0 <= fval <= 1.0):
        raise ValueError(f"{field_name} ({fval}) must be between 0.0 and 1.0 (documented range)")
    return fval


def _normalize_memory_type(val: Union[MemoryType, str]) -> MemoryType:
    """Normalize a memory type value or alias to a valid MemoryType enum."""
    if isinstance(val, MemoryType):
        return val
    if isinstance(val, str):
        cleaned = val.strip().lower()
        if cleaned in _MEMORY_TYPE_ALIASES:
            return _MEMORY_TYPE_ALIASES[cleaned]
    raise ValueError(
        f"Invalid memory_type '{val}'. Must be one of {[t.value for t in MemoryType]}"
    )


def _normalize_mastery_status(val: Union[MasteryStatus, str]) -> MasteryStatus:
    """Normalize a mastery status value or alias to a valid MasteryStatus enum."""
    if isinstance(val, MasteryStatus):
        return val
    if isinstance(val, str):
        cleaned = val.strip().lower()
        if cleaned in _MASTERY_STATUS_ALIASES:
            return _MASTERY_STATUS_ALIASES[cleaned]
    raise ValueError(
        f"Invalid mastery status '{val}'. Must be one of {[s.value for s in MasteryStatus]}"
    )


def compute_memory_id(
    learner_id: str,
    memory_type: Union[MemoryType, str],
    topic: str,
    content: str,
) -> str:
    """Compute a deterministic, collision-resistant SHA-256 memory ID.

    Normalizes inputs consistently (strips whitespace, lowercases topic and memory type)
    and binds the learner_id to guarantee learner isolation.
    """
    lid = _validate_non_empty_str(learner_id, "learner_id")
    top = _validate_non_empty_str(topic, "topic").lower()
    cnt = _validate_non_empty_str(content, "content")
    m_type = _normalize_memory_type(memory_type)

    identity = f"{lid}:{m_type.value}:{top}:{cnt}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def compute_correction_id(
    learner_id: str,
    target_memory_id: str,
    corrected_content: str,
) -> str:
    """Compute a deterministic SHA-256 identifier for a learner correction."""
    lid = _validate_non_empty_str(learner_id, "learner_id")
    mid = _validate_non_empty_str(target_memory_id, "target_memory_id")
    cnt = _validate_non_empty_str(corrected_content, "corrected_content")

    identity = f"{lid}:{mid}:{cnt}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


@dataclass
class LearnerProfile:
    """Represents an individual learner, their level, preferences, and metadata."""
    learner_id: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    preferred_learning_level: Optional[str] = None
    learning_preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.learner_id = _validate_non_empty_str(self.learner_id, "learner_id")

        if self.created_at is None:
            self.created_at = now_utc()
        else:
            self.created_at = _validate_utc_datetime(self.created_at, "created_at")

        if self.updated_at is None:
            self.updated_at = self.created_at
        else:
            self.updated_at = _validate_utc_datetime(self.updated_at, "updated_at")

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")

        if self.preferred_learning_level is not None:
            if not isinstance(self.preferred_learning_level, str):
                raise TypeError("preferred_learning_level must be a string or None")
            self.preferred_learning_level = self.preferred_learning_level.strip()

        # Defensively copy mutable containers to prevent leak across instances
        self.learning_preferences = (
            dict(self.learning_preferences) if self.learning_preferences is not None else {}
        )
        self.metadata = dict(self.metadata) if self.metadata is not None else {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile to a JSON-compatible dictionary."""
        return {
            "learner_id": self.learner_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "preferred_learning_level": self.preferred_learning_level,
            "learning_preferences": dict(self.learning_preferences),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LearnerProfile:
        """Deserialize profile from a dictionary."""
        created_at = (
            datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )
        updated_at = (
            datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
        )
        return cls(
            learner_id=data["learner_id"],
            created_at=created_at,
            updated_at=updated_at,
            preferred_learning_level=data.get("preferred_learning_level"),
            learning_preferences=data.get("learning_preferences") or {},
            metadata=data.get("metadata") or {},
        )


@dataclass
class MemoryEntry:
    """Represents an individual memory record for a learner."""
    memory_id: Optional[str] = None
    learner_id: str = ""
    memory_type: Union[MemoryType, str] = MemoryType.LEARNING_GOAL
    topic: str = ""
    content: str = ""
    confidence: float = 1.0
    source: Any = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.learner_id = _validate_non_empty_str(self.learner_id, "learner_id")
        self.topic = _validate_non_empty_str(self.topic, "topic")
        self.content = _validate_non_empty_str(self.content, "content")
        self.memory_type = _normalize_memory_type(self.memory_type)
        self.confidence = _validate_confidence(self.confidence, "confidence")

        if self.created_at is None:
            self.created_at = now_utc()
        else:
            self.created_at = _validate_utc_datetime(self.created_at, "created_at")

        if self.updated_at is None:
            self.updated_at = self.created_at
        else:
            self.updated_at = _validate_utc_datetime(self.updated_at, "updated_at")

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")

        if self.expires_at is not None:
            self.expires_at = _validate_utc_datetime(self.expires_at, "expires_at")
            if self.expires_at < self.created_at:
                raise ValueError("expires_at cannot precede created_at")

        if self.memory_id is not None:
            if not isinstance(self.memory_id, str) or not self.memory_id.strip():
                raise ValueError("memory_id cannot be empty")
            self.memory_id = self.memory_id.strip()
        else:
            self.memory_id = compute_memory_id(
                learner_id=self.learner_id,
                memory_type=self.memory_type,
                topic=self.topic,
                content=self.content,
            )

        if isinstance(self.source, dict):
            self.source = dict(self.source)

        self.metadata = dict(self.metadata) if self.metadata is not None else {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory entry to a JSON-compatible dictionary."""
        return {
            "memory_id": self.memory_id,
            "learner_id": self.learner_id,
            "memory_type": self.memory_type.value,
            "topic": self.topic,
            "content": self.content,
            "confidence": self.confidence,
            "source": dict(self.source) if isinstance(self.source, dict) else self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryEntry:
        """Deserialize memory entry from a dictionary."""
        created_at = (
            datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )
        updated_at = (
            datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
        )
        expires_at = (
            datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
        )
        return cls(
            memory_id=data.get("memory_id"),
            learner_id=data["learner_id"],
            memory_type=data["memory_type"],
            topic=data["topic"],
            content=data["content"],
            confidence=data.get("confidence", 1.0),
            source=data.get("source"),
            created_at=created_at,
            updated_at=updated_at,
            expires_at=expires_at,
            is_active=data.get("is_active", True),
            metadata=data.get("metadata") or {},
        )


@dataclass
class MasteryState:
    """Represents a learner's mastery level and progress status for a topic."""
    learner_id: str = ""
    topic: str = ""
    mastery_level: float = 0.0
    confidence: float = 1.0
    evidence_count: int = 0
    last_updated: Optional[datetime] = None
    status: Union[MasteryStatus, str] = MasteryStatus.NOT_STARTED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.learner_id = _validate_non_empty_str(self.learner_id, "learner_id")
        self.topic = _validate_non_empty_str(self.topic, "topic")
        self.mastery_level = _validate_mastery_level(self.mastery_level, "mastery_level")
        self.confidence = _validate_confidence(self.confidence, "confidence")

        if isinstance(self.evidence_count, bool) or not isinstance(self.evidence_count, int):
            raise TypeError("evidence_count must be an integer")
        if self.evidence_count < 0:
            raise ValueError(f"evidence_count ({self.evidence_count}) must be >= 0")

        self.status = _normalize_mastery_status(self.status)

        if self.last_updated is None:
            self.last_updated = now_utc()
        else:
            self.last_updated = _validate_utc_datetime(self.last_updated, "last_updated")

        self.metadata = dict(self.metadata) if self.metadata is not None else {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize mastery state to a JSON-compatible dictionary."""
        return {
            "learner_id": self.learner_id,
            "topic": self.topic,
            "mastery_level": self.mastery_level,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "status": self.status.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MasteryState:
        """Deserialize mastery state from a dictionary."""
        last_updated = (
            datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None
        )
        return cls(
            learner_id=data["learner_id"],
            topic=data["topic"],
            mastery_level=data.get("mastery_level", 0.0),
            confidence=data.get("confidence", 1.0),
            evidence_count=data.get("evidence_count", 0),
            last_updated=last_updated,
            status=data.get("status", MasteryStatus.NOT_STARTED),
            metadata=data.get("metadata") or {},
        )


@dataclass
class LearnerCorrection:
    """Represents an explicit correction supplied by a learner for a memory item."""
    correction_id: Optional[str] = None
    learner_id: str = ""
    target_memory_id: str = ""
    original_content: str = ""
    corrected_content: str = ""
    created_at: Optional[datetime] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.learner_id = _validate_non_empty_str(self.learner_id, "learner_id")
        self.target_memory_id = _validate_non_empty_str(self.target_memory_id, "target_memory_id")
        self.original_content = _validate_non_empty_str(self.original_content, "original_content")
        self.corrected_content = _validate_non_empty_str(self.corrected_content, "corrected_content")

        if self.correction_id is not None:
            if not isinstance(self.correction_id, str) or not self.correction_id.strip():
                raise ValueError("correction_id cannot be empty")
            self.correction_id = self.correction_id.strip()
        else:
            self.correction_id = compute_correction_id(
                learner_id=self.learner_id,
                target_memory_id=self.target_memory_id,
                corrected_content=self.corrected_content,
            )

        if self.created_at is None:
            self.created_at = now_utc()
        else:
            self.created_at = _validate_utc_datetime(self.created_at, "created_at")

        if self.reason is not None and not isinstance(self.reason, str):
            raise TypeError("reason must be a string or None")

        self.metadata = dict(self.metadata) if self.metadata is not None else {}

    def is_attributable_to(self, learner_id: str) -> bool:
        """Verify that this correction belongs to the specified learner."""
        return bool(learner_id and self.learner_id == learner_id.strip())

    def matches_memory(self, memory: MemoryEntry) -> bool:
        """Verify that this correction matches the target memory item's learner and ID."""
        return (
            self.learner_id == memory.learner_id
            and self.target_memory_id == memory.memory_id
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize correction to a JSON-compatible dictionary."""
        return {
            "correction_id": self.correction_id,
            "learner_id": self.learner_id,
            "target_memory_id": self.target_memory_id,
            "original_content": self.original_content,
            "corrected_content": self.corrected_content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LearnerCorrection:
        """Deserialize correction from a dictionary."""
        created_at = (
            datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )
        return cls(
            correction_id=data.get("correction_id"),
            learner_id=data["learner_id"],
            target_memory_id=data["target_memory_id"],
            original_content=data["original_content"],
            corrected_content=data["corrected_content"],
            created_at=created_at,
            reason=data.get("reason"),
            metadata=data.get("metadata") or {},
        )
