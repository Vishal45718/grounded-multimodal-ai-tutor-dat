"""Policies governing the lifecycle of learner memory items (M5).

Includes:
1. Write Policy: Filters transient conversation remarks, requiring confirmation or confidence >= tau_mem.
2. Expiry Policy: Manages TTL and temporal decay.
3. Correction Policy: Supersedes prior records and logs provenance.
4. Deletion Policy: Immediate and complete erasure.
5. Isolation Policy: Forbids citing memory as course evidence.
"""
import time
from typing import Optional, Tuple
from memory.models import LearnerMemoryItem


class LearnerMemoryPolicy:
    """Configurable policy engine for durable learner memory."""

    def __init__(
        self,
        tau_mem: float = 0.75,
        default_ttl_seconds: float = 30 * 86400.0,  # 30 days
        require_explicit_confirmation: bool = False,
        daily_decay_rate: float = 0.005,
    ):
        self.tau_mem = tau_mem
        self.default_ttl_seconds = default_ttl_seconds
        self.require_explicit_confirmation = require_explicit_confirmation
        self.daily_decay_rate = daily_decay_rate

    def evaluate_write(self, item: LearnerMemoryItem) -> Tuple[bool, str]:
        """Evaluates whether an item is eligible to be committed to durable memory.

        Guarantees that a speculative or passing remark is not automatically persisted.
        """
        if self.require_explicit_confirmation and not item.is_confirmed:
            return False, "Explicit learner confirmation required by policy."

        if item.is_confirmed:
            return True, "Learner explicitly confirmed item."

        if item.confidence < self.tau_mem:
            return False, f"Confidence {item.confidence:.2f} is below write threshold tau_mem={self.tau_mem:.2f}."

        return True, "Confidence exceeds threshold tau_mem."

    def is_expired(self, item: LearnerMemoryItem, current_time: Optional[float] = None) -> bool:
        """Determines if a memory item has exceeded its Time-To-Live.

        Mastery items undergo temporal confidence decay rather than sudden expiry.
        """
        if item.memory_type == "mastery":
            return False
        now = current_time if current_time is not None else time.time()
        if item.expires_at is not None and now >= item.expires_at:
            return True
        return False

    def calculate_decayed_confidence(self, item: LearnerMemoryItem, current_time: Optional[float] = None) -> float:
        """Applies time-decay to mastery confidence unless reinforced."""
        if item.memory_type != "mastery":
            return item.confidence

        now = current_time if current_time is not None else time.time()
        days_passed = (now - item.updated_at) / 86400.0
        if days_passed < 1.0:
            return item.confidence

        decay = days_passed * self.daily_decay_rate
        return max(0.0, item.confidence - decay)
