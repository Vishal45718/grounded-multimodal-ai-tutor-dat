"""Data models for selective learner memory (M5).

Differentiates:
1. Durable profile items: goals, mastery, misconceptions.
2. Ephemeral session state: short-lived conversational turns that are discarded upon session close.
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LearnerMemoryItem:
    """A durable item in a learner's persistent profile."""
    item_id: str
    learner_id: str
    memory_type: str  # "goal" | "mastery" | "misconception"
    topic: str
    content: str
    confidence: float  # 0.0 to 1.0
    provenance_turn_id: str
    is_confirmed: bool = False
    status: str = "active"  # "active" | "corrected" | "expired" | "deleted"
    provenance_evidence_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        valid_types = {"goal", "mastery", "misconception"}
        if self.memory_type not in valid_types:
            raise ValueError(f"Invalid memory_type '{self.memory_type}'. Must be one of {valid_types}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence {self.confidence} must be between 0.0 and 1.0")
        if not self.learner_id.strip():
            raise ValueError("learner_id cannot be empty")


def compute_memory_id(learner_id: str, memory_type: str, topic: str, content: str) -> str:
    """Computes a deterministic identifier for a memory item."""
    ident = f"{learner_id.strip()}:{memory_type}:{topic.strip().lower()}:{content.strip().lower()}"
    return hashlib.sha256(ident.encode("utf-8")).hexdigest()[:16]


@dataclass
class EphemeralSession:
    """Ephemeral conversation working memory. Discarded at session end."""
    session_id: str
    learner_id: str
    turns: List[Dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    is_active: bool = True

    def add_turn(self, user_msg: str, tutor_msg: str, turn_id: Optional[str] = None) -> str:
        tid = turn_id or f"turn_{len(self.turns)+1}_{int(time.time())}"
        self.turns.append({
            "turn_id": tid,
            "user": user_msg,
            "tutor": tutor_msg,
            "timestamp": time.time(),
        })
        return tid

    def close(self):
        """Discards working memory upon session termination."""
        self.is_active = False
        self.turns.clear()
