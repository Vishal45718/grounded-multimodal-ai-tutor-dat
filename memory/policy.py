"""Configurable learner-memory policy (M5.2).

Decides whether a memory is accepted, retained, expired, or removed.
This policy is not a retrieval ranker and does not treat learner memory
as corpus-grounded evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Dict, Mapping, Optional, Tuple, Union

from memory.models import MemoryEntry, MemoryType, _normalize_memory_type, now_utc


Clock = Callable[[], datetime]


class MemoryDecision(str, Enum):
    """Policy action for a memory entry."""

    ACCEPT = "accept"
    REJECT = "reject"
    EXPIRE = "expire"
    REMOVE = "remove"


class MemoryPolicyError(ValueError):
    """Raised when policy configuration or clock values are invalid."""


@dataclass(frozen=True)
class PolicyEvaluation:
    """Result of evaluating one memory against the policy."""

    action: MemoryDecision
    reason: str
    treat_as_corpus_evidence: bool = False


_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I),
    re.compile(r"disregard\s+all\s+(prior|previous)\s+(rules|instructions)", re.I),
    re.compile(r"you\s+are\s+now\s+(the\s+)?system", re.I),
    re.compile(r"<\|im_start\|>", re.I),
    re.compile(r"reveal\s+the\s+system\s+prompt", re.I),
)


def _validate_unit_interval(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MemoryPolicyError(f"{field_name} threshold must be numeric")
    fval = float(value)
    if not 0.0 <= fval <= 1.0:
        raise MemoryPolicyError(f"{field_name} threshold must be between 0.0 and 1.0")
    return fval


@dataclass
class MemoryPolicy:
    """Rules for confidence, expiration, retention, mastery, and safety.

    Confidence: a memory is accepted only when its score is at or above the
    threshold for its type. Uncertain values are never rewritten upward.

    Expiration: timezone-aware UTC comparisons against ``expires_at``, or
    against ``created_at + default_ttl`` when no explicit expiry is set.
    Memories with neither expiry nor a default TTL are retained until deleted.

    Isolation and evidence: learner memories stay learner-scoped and are never
    labeled as verified corpus evidence.
    """

    default_min_confidence: float = 0.5
    type_thresholds: Mapping[Union[MemoryType, str], float] = field(default_factory=dict)
    default_ttl: Optional[timedelta] = None
    min_mastery_evidence_count: int = 2
    min_mastery_confidence: float = 0.7
    min_mastery_level: float = 0.8
    max_context_entries: int = 20
    clock: Clock = now_utc

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "default_min_confidence",
            _validate_unit_interval(self.default_min_confidence, "default_min_confidence"),
        )
        object.__setattr__(
            self,
            "min_mastery_confidence",
            _validate_unit_interval(self.min_mastery_confidence, "min_mastery_confidence"),
        )
        object.__setattr__(
            self,
            "min_mastery_level",
            _validate_unit_interval(self.min_mastery_level, "mastery"),
        )
        if (
            isinstance(self.min_mastery_evidence_count, bool)
            or not isinstance(self.min_mastery_evidence_count, int)
            or self.min_mastery_evidence_count < 1
        ):
            raise MemoryPolicyError("min_mastery_evidence_count evidence must be >= 1")
        if (
            isinstance(self.max_context_entries, bool)
            or not isinstance(self.max_context_entries, int)
            or self.max_context_entries < 1
        ):
            raise MemoryPolicyError("max_context_entries context limit must be >= 1")
        if self.default_ttl is not None and not isinstance(self.default_ttl, timedelta):
            raise MemoryPolicyError("default_ttl must be a timedelta or None")
        if self.default_ttl is not None and self.default_ttl.total_seconds() < 0:
            raise MemoryPolicyError("default_ttl cannot be negative")

        normalized: Dict[MemoryType, float] = {}
        for key, raw in dict(self.type_thresholds).items():
            try:
                memory_type = key if isinstance(key, MemoryType) else _normalize_memory_type(key)
            except ValueError as exc:
                raise MemoryPolicyError(f"unknown memory type in type_thresholds: {key}") from exc
            normalized[memory_type] = _validate_unit_interval(
                raw, f"type_thresholds[{memory_type.value}]"
            )
        object.__setattr__(self, "type_thresholds", normalized)

    def now(self) -> datetime:
        """Return the policy clock as timezone-aware UTC."""
        current = self.clock()
        if not isinstance(current, datetime):
            raise MemoryPolicyError("clock must return a datetime")
        if current.tzinfo is None or current.tzinfo.utcoffset(current) is None:
            raise MemoryPolicyError("clock must return a timezone-aware UTC datetime")
        return current.astimezone(timezone.utc)

    def threshold_for(self, memory_type: Union[MemoryType, str]) -> float:
        """Minimum confidence required to accept a memory of this type."""
        resolved = memory_type if isinstance(memory_type, MemoryType) else _normalize_memory_type(memory_type)
        return self.type_thresholds.get(resolved, self.default_min_confidence)

    def looks_like_prompt_injection(self, text: str) -> bool:
        """Detect raw instruction-override attempts in learner-supplied text."""
        return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)

    def effective_expiry(self, entry: MemoryEntry) -> Optional[datetime]:
        """Return the expiry instant, applying default TTL when unset."""
        if entry.expires_at is not None:
            return entry.expires_at
        if self.default_ttl is None:
            return None
        return entry.created_at + self.default_ttl

    def is_expired(self, entry: MemoryEntry, at: Optional[datetime] = None) -> bool:
        """True when the entry's expiry instant is at or before ``at``."""
        moment = at.astimezone(timezone.utc) if at is not None else self.now()
        expiry = self.effective_expiry(entry)
        if expiry is None:
            return False
        return moment >= expiry

    def is_retrievable(self, entry: MemoryEntry, at: Optional[datetime] = None) -> bool:
        """Active, non-expired memories may be returned to callers."""
        return bool(entry.is_active) and not self.is_expired(entry, at=at)

    def evaluate(self, entry: MemoryEntry, at: Optional[datetime] = None) -> PolicyEvaluation:
        """Decide accept / reject / expire / remove for one entry.

        Source attribution and confidence are left unchanged. Learner text is
        never marked as corpus evidence.
        """
        if not entry.is_active:
            return PolicyEvaluation(MemoryDecision.REMOVE, "inactive memory is not retrievable")
        if self.is_expired(entry, at=at):
            return PolicyEvaluation(MemoryDecision.EXPIRE, "memory has expired")
        if (
            entry.memory_type is MemoryType.LEARNING_PREFERENCE
            and self.looks_like_prompt_injection(entry.content)
        ):
            return PolicyEvaluation(
                MemoryDecision.REJECT,
                "prompt injection must not be stored as a trusted learner preference or system instruction",
            )
        threshold = self.threshold_for(entry.memory_type)
        if entry.confidence < threshold:
            return PolicyEvaluation(
                MemoryDecision.REJECT,
                f"confidence {entry.confidence} is below threshold {threshold}",
            )
        return PolicyEvaluation(
            MemoryDecision.ACCEPT,
            "accepted",
            treat_as_corpus_evidence=False,
        )

    def allows_mastered_status(
        self,
        *,
        evidence_count: int,
        confidence: float,
        mastery_level: float,
    ) -> Tuple[bool, str]:
        """MASTERED requires repeated strong evidence, not one weak observation."""
        if evidence_count < self.min_mastery_evidence_count:
            return False, "insufficient evidence to mark mastered"
        if confidence < self.min_mastery_confidence:
            return False, "confidence too low to mark mastered"
        if mastery_level < self.min_mastery_level:
            return False, "mastery_level too low to mark mastered"
        return True, ""
