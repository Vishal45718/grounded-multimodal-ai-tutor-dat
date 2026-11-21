"""Persistent, policy-controlled SQLite storage for durable learner memory (M5).

Provides:
- SQLite persistence separate from course evidence corpus.
- Complete round-trip persistence of canonical root models (LearnerProfile,
  MemoryEntry, MasteryState, LearnerCorrection).
- Expiry, decay, correction, deletion and learner isolation enforcement.
- Hard delete / purge within one query cycle.
- Formatting of isolated pedagogical styling context.
- Backwards compatibility with nested LearnerMemoryStore API methods.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from memory.models import (
    LearnerCorrection,
    LearnerProfile,
    MasteryState,
    MasteryStatus,
    MemoryEntry,
    MemoryType,
    _normalize_mastery_status,
    _normalize_memory_type,
    compute_memory_id,
    now_utc,
)
from memory.policy import MemoryPolicy


class SourceSerializationError(TypeError):
    """Raised when an unsupported Python object is passed as a source in MemoryEntry."""


def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    """Serialize datetime to ISO-8601 string, ensuring timezone info is preserved."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _iso_to_dt(val: Optional[str]) -> Optional[datetime]:
    """Parse ISO-8601 string back to datetime, ensuring timezone info is present."""
    if val is None:
        return None
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _serialize_source(val: Any) -> Optional[str]:
    """Serialize source field to JSON strictly preserving JSON-compatible values.

    Raises SourceSerializationError if val contains unsupported Python objects.
    """
    if val is None:
        return None
    try:
        return json.dumps(val)
    except (TypeError, ValueError) as err:
        raise SourceSerializationError(
            f"Cannot serialize source of type {type(val).__name__!r} to JSON: {err}"
        ) from err


def _serialize_json(val: Any) -> str:
    """Serialize internal metadata/preferences dictionaries to JSON."""
    return json.dumps(val)


class LearnerMemoryStore:
    """Manages persistent learner records with strict isolation and lifecycle policies.

    Supports both canonical root models (LearnerProfile, MemoryEntry, MasteryState,
    LearnerCorrection) and compatibility methods for nested benchmark/guardrail tests.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        policy: Optional[Any] = None,
    ):
        self.db_path = db_path
        self._is_memory = (db_path == ":memory:")
        self._shared_conn: Optional[sqlite3.Connection] = None
        if self._is_memory:
            self._shared_conn = sqlite3.connect(":memory:")
            self._shared_conn.row_factory = sqlite3.Row
            self._shared_conn.execute("PRAGMA foreign_keys = ON;")

        if policy is None:
            self.policy = MemoryPolicy()
        else:
            self.policy = policy
        self._init_db()

    def close(self):
        """Safely close underlying persistent connection if open."""
        if self._shared_conn is not None:
            try:
                self._shared_conn.close()
            except Exception:
                pass
            self._shared_conn = None

    def __del__(self):
        self.close()

    @contextmanager
    def _connect(self):
        if self._is_memory:
            conn = self._shared_conn
            if conn is None:
                raise RuntimeError("In-memory SQLite store connection is already closed.")
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        else:
            import os

            parent_dir = os.path.dirname(self.db_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learner_profiles (
                    learner_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    preferred_learning_level TEXT,
                    learning_preferences TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    memory_id TEXT PRIMARY KEY,
                    learner_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    is_active INTEGER NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mastery_states (
                    learner_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    mastery_level REAL NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    last_updated TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    PRIMARY KEY (learner_id, topic)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learner_corrections (
                    correction_id TEXT PRIMARY KEY,
                    learner_id TEXT NOT NULL,
                    target_memory_id TEXT NOT NULL,
                    original_content TEXT NOT NULL,
                    corrected_content TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_learner ON memory_entries(learner_id, is_active)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_expiry ON memory_entries(learner_id, is_active, expires_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mastery_learner ON mastery_states(learner_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_corrections_learner ON learner_corrections(learner_id)"
            )

    # -------------------------------------------------------------------------
    # Canonical Root API: LearnerProfile
    # -------------------------------------------------------------------------

    def upsert_profile(
        self,
        profile_or_id: Union[LearnerProfile, str],
        *,
        preferred_learning_level: Optional[str] = None,
        learning_preferences: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> LearnerProfile:
        """Upsert a learner profile using a LearnerProfile instance or keyword arguments."""
        if isinstance(profile_or_id, LearnerProfile):
            profile = profile_or_id
        else:
            learner_id = profile_or_id
            existing = self.get_profile(learner_id)
            now = now_utc()
            if existing is None:
                profile = LearnerProfile(
                    learner_id=learner_id,
                    created_at=now,
                    updated_at=now,
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
                    updated_at=now,
                    preferred_learning_level=(
                        preferred_learning_level
                        if preferred_learning_level is not None
                        else existing.preferred_learning_level
                    ),
                    learning_preferences=merged_prefs,
                    metadata=merged_meta,
                )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO learner_profiles (
                    learner_id, created_at, updated_at, preferred_learning_level,
                    learning_preferences, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(learner_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    preferred_learning_level = excluded.preferred_learning_level,
                    learning_preferences = excluded.learning_preferences,
                    metadata = excluded.metadata
                """,
                (
                    profile.learner_id,
                    _dt_to_iso(profile.created_at),
                    _dt_to_iso(profile.updated_at),
                    profile.preferred_learning_level,
                    _serialize_json(profile.learning_preferences),
                    _serialize_json(profile.metadata),
                ),
            )
        return profile

    def get_profile(self, learner_id: str) -> Optional[LearnerProfile]:
        """Retrieve a LearnerProfile by learner_id."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM learner_profiles WHERE learner_id = ?", (learner_id,)
            ).fetchone()
            if not row:
                return None
            return LearnerProfile(
                learner_id=row["learner_id"],
                created_at=_iso_to_dt(row["created_at"]),
                updated_at=_iso_to_dt(row["updated_at"]),
                preferred_learning_level=row["preferred_learning_level"],
                learning_preferences=json.loads(row["learning_preferences"] or "{}"),
                metadata=json.loads(row["metadata"] or "{}"),
            )

    # -------------------------------------------------------------------------
    # Canonical Root API: MemoryEntry
    # -------------------------------------------------------------------------

    def add_memory(self, entry: MemoryEntry) -> MemoryEntry:
        """Persist a canonical root MemoryEntry. Keeps created_at if entry exists."""
        existing = self.get_memory(entry.learner_id, entry.memory_id, include_inactive=True)
        now = now_utc()
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
                updated_at=now,
                expires_at=entry.expires_at if entry.expires_at is not None else existing.expires_at,
                is_active=entry.is_active,
                metadata={**existing.metadata, **entry.metadata},
            )
        else:
            stored = entry

        serialized_source = _serialize_source(stored.source)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_entries (
                    memory_id, learner_id, memory_type, topic, content, confidence,
                    source, created_at, updated_at, expires_at, is_active, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    memory_type = excluded.memory_type,
                    topic = excluded.topic,
                    content = excluded.content,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at,
                    is_active = excluded.is_active,
                    metadata = excluded.metadata
                """,
                (
                    stored.memory_id,
                    stored.learner_id,
                    stored.memory_type.value
                    if isinstance(stored.memory_type, MemoryType)
                    else str(stored.memory_type),
                    stored.topic,
                    stored.content,
                    stored.confidence,
                    serialized_source,
                    _dt_to_iso(stored.created_at),
                    _dt_to_iso(stored.updated_at),
                    _dt_to_iso(stored.expires_at),
                    int(stored.is_active),
                    _serialize_json(stored.metadata),
                ),
            )
        return stored

    def get_memory(
        self,
        learner_id: str,
        memory_id: str,
        *,
        include_inactive: bool = False,
    ) -> Optional[MemoryEntry]:
        """Fetch a specific memory entry owned by learner_id."""
        with self._connect() as conn:
            query = "SELECT * FROM memory_entries WHERE learner_id = ? AND memory_id = ?"
            if not include_inactive:
                query += " AND is_active = 1"
            row = conn.execute(query, (learner_id, memory_id)).fetchone()
            if not row:
                return None
            return self._row_to_memory_entry(row)

    def get_memories(
        self,
        learner_id: str,
        memory_type: Optional[Union[MemoryType, str]] = None,
        topic: Optional[str] = None,
        *,
        include_inactive: bool = False,
        include_expired: bool = False,
        as_of: Optional[datetime] = None,
    ) -> List[MemoryEntry]:
        """Return memories for learner_id matching type/topic filters.

        By default, excludes inactive and expired memories.
        """
        query = "SELECT * FROM memory_entries WHERE learner_id = ?"
        params: List[Any] = [learner_id]

        if not include_inactive:
            query += " AND is_active = 1"

        if not include_expired:
            current_moment = as_of or now_utc()
            iso_now = _dt_to_iso(current_moment)
            query += " AND (expires_at IS NULL OR expires_at > ?)"
            params.append(iso_now)

        if memory_type is not None:
            norm_type = (
                memory_type.value
                if isinstance(memory_type, MemoryType)
                else _normalize_memory_type(memory_type).value
            )
            query += " AND memory_type = ?"
            params.append(norm_type)

        if topic is not None:
            query += " AND LOWER(TRIM(topic)) = LOWER(TRIM(?))"
            params.append(topic)

        query += " ORDER BY created_at ASC, memory_id ASC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_memory_entry(r) for r in rows]

    def _row_to_memory_entry(self, row: sqlite3.Row) -> MemoryEntry:
        source_val = json.loads(row["source"]) if row["source"] is not None else None
        return MemoryEntry(
            memory_id=row["memory_id"],
            learner_id=row["learner_id"],
            memory_type=MemoryType(row["memory_type"]),
            topic=row["topic"],
            content=row["content"],
            confidence=float(row["confidence"]),
            source=source_val,
            created_at=_iso_to_dt(row["created_at"]),
            updated_at=_iso_to_dt(row["updated_at"]),
            expires_at=_iso_to_dt(row["expires_at"]),
            is_active=bool(row["is_active"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    # -------------------------------------------------------------------------
    # Canonical Root API: MasteryState
    # -------------------------------------------------------------------------

    def update_mastery(
        self,
        learner_id_or_state: Union[MasteryState, str],
        topic: Optional[str] = None,
        *,
        mastery_level: Optional[float] = None,
        confidence: Optional[float] = None,
        status: Optional[Union[MasteryStatus, str]] = None,
        evidence_increment: int = 1,
    ) -> MasteryState:
        """Upsert a topic mastery state for a learner."""
        if isinstance(learner_id_or_state, MasteryState):
            state = learner_id_or_state
        else:
            learner_id = learner_id_or_state
            if topic is None or mastery_level is None or confidence is None:
                raise ValueError("topic, mastery_level, and confidence are required when passing learner_id")
            if evidence_increment < 1:
                raise ValueError("evidence_increment must be >= 1")

            existing_list = self.get_mastery(learner_id, topic=topic)
            previous = existing_list[0] if existing_list else None
            evidence_count = (previous.evidence_count if previous else 0) + evidence_increment
            requested_status = _normalize_mastery_status(
                status if status is not None else (
                    previous.status if previous else MasteryStatus.LEARNING
                )
            )

            # Check policy constraint on MASTERED
            if requested_status is MasteryStatus.MASTERED:
                if hasattr(self.policy, "allows_mastered_status"):
                    allowed, _ = self.policy.allows_mastered_status(
                        evidence_count=evidence_count,
                        confidence=confidence,
                        mastery_level=mastery_level,
                    )
                    if not allowed:
                        requested_status = (
                            MasteryStatus.IMPROVING if evidence_count >= 2 else MasteryStatus.LEARNING
                        )
                elif hasattr(self.policy, "min_mastered_evidence"):
                    if evidence_count < self.policy.min_mastered_evidence or confidence < self.policy.min_mastered_confidence:
                        requested_status = (
                            MasteryStatus.IMPROVING if evidence_count >= 2 else MasteryStatus.LEARNING
                        )

            state = MasteryState(
                learner_id=learner_id,
                topic=previous.topic if previous else topic,
                mastery_level=mastery_level,
                confidence=confidence,
                evidence_count=evidence_count,
                last_updated=now_utc(),
                status=requested_status,
                metadata=dict(previous.metadata) if previous else {},
            )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mastery_states (
                    learner_id, topic, mastery_level, confidence,
                    evidence_count, last_updated, status, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(learner_id, topic) DO UPDATE SET
                    mastery_level = excluded.mastery_level,
                    confidence = excluded.confidence,
                    evidence_count = excluded.evidence_count,
                    last_updated = excluded.last_updated,
                    status = excluded.status,
                    metadata = excluded.metadata
                """,
                (
                    state.learner_id,
                    state.topic,
                    state.mastery_level,
                    state.confidence,
                    state.evidence_count,
                    _dt_to_iso(state.last_updated),
                    state.status.value
                    if isinstance(state.status, MasteryStatus)
                    else str(state.status),
                    _serialize_json(state.metadata),
                ),
            )
        return state

    def get_mastery(
        self, learner_id: str, topic: Optional[str] = None
    ) -> List[MasteryState]:
        """Fetch mastery states for learner_id, optionally filtered by topic."""
        query = "SELECT * FROM mastery_states WHERE learner_id = ?"
        params: List[Any] = [learner_id]
        if topic is not None:
            query += " AND LOWER(TRIM(topic)) = LOWER(TRIM(?))"
            params.append(topic)
        query += " ORDER BY LOWER(topic) ASC, learner_id ASC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                MasteryState(
                    learner_id=r["learner_id"],
                    topic=r["topic"],
                    mastery_level=float(r["mastery_level"]),
                    confidence=float(r["confidence"]),
                    evidence_count=int(r["evidence_count"]),
                    last_updated=_iso_to_dt(r["last_updated"]),
                    status=MasteryStatus(r["status"]),
                    metadata=json.loads(r["metadata"] or "{}"),
                )
                for r in rows
            ]

    # -------------------------------------------------------------------------
    # Canonical Root API: LearnerCorrection
    # -------------------------------------------------------------------------

    def apply_correction(self, correction: LearnerCorrection) -> MemoryEntry:
        """Apply a correction: deactivates original memory entry, inserts replacement entry,

        and records the audit log in learner_corrections.
        """
        original = self.get_memory(
            correction.learner_id, correction.target_memory_id, include_inactive=True
        )
        if original is None or not correction.matches_memory(original):
            raise KeyError(
                f"memory {correction.target_memory_id!r} not found for learner {correction.learner_id!r}"
            )

        replacement = MemoryEntry(
            learner_id=original.learner_id,
            memory_type=original.memory_type,
            topic=original.topic,
            content=correction.corrected_content,
            confidence=1.0,
            source={"kind": "learner_correction", "correction_id": correction.correction_id},
            created_at=now_utc(),
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
            updated_at=now_utc(),
            expires_at=original.expires_at,
            is_active=False,
            metadata={
                **original.metadata,
                "correction_id": correction.correction_id,
                "superseded_by": replacement.memory_id,
            },
        )

        serialized_replacement_source = _serialize_source(replacement.source)

        with self._connect() as conn:
            # 1. Record correction
            conn.execute(
                """
                INSERT INTO learner_corrections (
                    correction_id, learner_id, target_memory_id,
                    original_content, corrected_content, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(correction_id) DO UPDATE SET
                    corrected_content = excluded.corrected_content,
                    reason = excluded.reason
                """,
                (
                    correction.correction_id,
                    correction.learner_id,
                    correction.target_memory_id,
                    correction.original_content,
                    correction.corrected_content,
                    correction.reason,
                    _dt_to_iso(correction.created_at),
                ),
            )
            # 2. Deactivate original
            conn.execute(
                """
                UPDATE memory_entries
                SET is_active = 0, updated_at = ?, metadata = ?
                WHERE memory_id = ?
                """,
                (
                    _dt_to_iso(deactivated.updated_at),
                    _serialize_json(deactivated.metadata),
                    deactivated.memory_id,
                ),
            )
            # 3. Insert replacement
            conn.execute(
                """
                INSERT INTO memory_entries (
                    memory_id, learner_id, memory_type, topic, content, confidence,
                    source, created_at, updated_at, expires_at, is_active, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    replacement.memory_id,
                    replacement.learner_id,
                    replacement.memory_type.value,
                    replacement.topic,
                    replacement.content,
                    replacement.confidence,
                    serialized_replacement_source,
                    _dt_to_iso(replacement.created_at),
                    _dt_to_iso(replacement.updated_at),
                    _dt_to_iso(replacement.expires_at),
                    int(replacement.is_active),
                    _serialize_json(replacement.metadata),
                ),
            )

        return replacement

    def get_corrections(self, learner_id: str) -> List[LearnerCorrection]:
        """Fetch audit log of corrections for learner_id."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM learner_corrections WHERE learner_id = ? ORDER BY created_at ASC, correction_id ASC",
                (learner_id,),
            ).fetchall()
            return [
                LearnerCorrection(
                    correction_id=r["correction_id"],
                    learner_id=r["learner_id"],
                    target_memory_id=r["target_memory_id"],
                    original_content=r["original_content"],
                    corrected_content=r["corrected_content"],
                    reason=r["reason"] or "",
                    created_at=_iso_to_dt(r["created_at"]),
                )
                for r in rows
            ]

    # -------------------------------------------------------------------------
    # Deletion & Hard Purge (GDPR / Isolation)
    # -------------------------------------------------------------------------

    def delete_memory(self, learner_id: str, memory_id: str) -> bool:
        """Deletes one memory owned by learner_id. Returns True if deleted."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM memory_entries WHERE learner_id = ? AND memory_id = ?",
                (learner_id, memory_id),
            )
            return cur.rowcount > 0

    def purge_learner(self, learner_id: str) -> int:
        """Permanently purges all data across all tables for a learner."""
        total_deleted = 0
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM learner_profiles WHERE learner_id = ?", (learner_id,))
            total_deleted += cur.rowcount
            cur.execute("DELETE FROM memory_entries WHERE learner_id = ?", (learner_id,))
            total_deleted += cur.rowcount
            cur.execute("DELETE FROM mastery_states WHERE learner_id = ?", (learner_id,))
            total_deleted += cur.rowcount
            cur.execute("DELETE FROM learner_corrections WHERE learner_id = ?", (learner_id,))
            total_deleted += cur.rowcount
        return total_deleted

    # -------------------------------------------------------------------------
    # Pedagogical Context Prefix
    # -------------------------------------------------------------------------

    def build_pedagogical_context(self, learner_id: str) -> str:
        """Constructs an isolated prompt prefix strictly for personalization.

        Guaranteed never to be cited as course evidence. Excludes expired or inactive items.
        """
        memories = self.get_memories(learner_id)
        if not memories:
            return ""

        lines = [
            "=== [LEARNER PROFILE - PEDAGOGICAL STYLING ONLY - DO NOT CITE AS EVIDENCE] ===",
            f"Learner ID: {learner_id}",
        ]
        for m in memories:
            m_type = m.memory_type.value.upper() if isinstance(m.memory_type, MemoryType) else str(m.memory_type).upper()
            lines.append(f"- [{m_type}] Topic: {m.topic} | {m.content} (Confidence: {m.confidence:.2f})")
        lines.append(
            "Instructions: Use this profile ONLY to adjust your tone and explanation depth. "
            "You MUST NEVER cite these profile notes as instructional course evidence."
        )
        lines.append("==========================================================================")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Backwards Compatibility API for Nested Test Cases
    # -------------------------------------------------------------------------

    def write_memory(
        self,
        item: Any,
        force: bool = False,
    ) -> Tuple[bool, Optional[Any], str]:
        """Backwards-compatible write method for nested LearnerMemoryItem instances."""
        if not force and hasattr(self.policy, "evaluate_write"):
            allowed, reason = self.policy.evaluate_write(item)
            if not allowed:
                return False, None, reason

        default_ttl = getattr(self.policy, "default_ttl_seconds", 0)
        if getattr(item, "expires_at", None) is None and default_ttl > 0:
            created_at = getattr(item, "created_at", time.time())
            item.expires_at = created_at + default_ttl

        # Convert timestamp created_at / updated_at / expires_at if float
        def _to_dt(val):
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val, tz=timezone.utc)
            if isinstance(val, datetime):
                return val
            return _iso_to_dt(val)

        source_dict = {
            "provenance_turn_id": getattr(item, "provenance_turn_id", ""),
            "provenance_evidence_id": getattr(item, "provenance_evidence_id", None),
            "is_confirmed": getattr(item, "is_confirmed", False),
        }
        meta_dict = {
            "history": getattr(item, "history", []),
            "status": getattr(item, "status", "active"),
        }

        # Normalize memory_type
        m_type_str = str(getattr(item, "memory_type", "preference")).lower()
        try:
            m_type = _normalize_memory_type(m_type_str)
        except Exception:
            m_type = MemoryType.LEARNING_PREFERENCE

        memory_id = getattr(item, "item_id", None) or compute_memory_id(
            getattr(item, "learner_id"), getattr(item, "topic"), getattr(item, "content")
        )

        entry = MemoryEntry(
            memory_id=memory_id,
            learner_id=getattr(item, "learner_id"),
            memory_type=m_type,
            topic=getattr(item, "topic"),
            content=getattr(item, "content"),
            confidence=float(getattr(item, "confidence", 1.0)),
            source=source_dict,
            created_at=_to_dt(getattr(item, "created_at", None)) or now_utc(),
            updated_at=_to_dt(getattr(item, "updated_at", None)) or now_utc(),
            expires_at=_to_dt(getattr(item, "expires_at", None)),
            is_active=(getattr(item, "status", "active") == "active"),
            metadata=meta_dict,
        )

        stored = self.add_memory(entry)
        return True, item, "Successfully committed to durable memory."

    def get_active_memories(
        self,
        learner_id: str,
        memory_type: Optional[str] = None,
        current_time: Optional[float] = None,
    ) -> List[Any]:
        """Backwards-compatible retrieval method returning active memories."""
        try:
            from memory.models import LearnerMemoryItem
        except ImportError:
            # Fallback definition if running against root models where LearnerMemoryItem is not exported
            from dataclasses import dataclass, field

            @dataclass
            class LearnerMemoryItem:
                item_id: str
                learner_id: str
                memory_type: str
                topic: str
                content: str
                confidence: float
                provenance_turn_id: str
                is_confirmed: bool = False
                status: str = "active"
                provenance_evidence_id: Optional[str] = None
                created_at: float = field(default_factory=time.time)
                updated_at: float = field(default_factory=time.time)
                expires_at: Optional[float] = None
                history: List[dict] = field(default_factory=list)

        now_sec = current_time if current_time is not None else time.time()
        # Retrieve non-inactive memories
        memories = self.get_memories(
            learner_id,
            memory_type=memory_type,
            include_inactive=False,
            include_expired=True,  # let backwards policy evaluate expiry
        )
        items: List[LearnerMemoryItem] = []
        expired_ids: List[str] = []

        for m in memories:
            history = m.metadata.get("history", [])
            is_confirmed = False
            prov_turn = ""
            prov_ev = None
            if isinstance(m.source, dict):
                is_confirmed = m.source.get("is_confirmed", False)
                prov_turn = m.source.get("provenance_turn_id", "")
                prov_ev = m.source.get("provenance_evidence_id")

            created_sec = m.created_at.timestamp()
            updated_sec = m.updated_at.timestamp()
            expires_sec = m.expires_at.timestamp() if m.expires_at else None

            item = LearnerMemoryItem(
                item_id=m.memory_id,
                learner_id=m.learner_id,
                memory_type=m.memory_type.value,
                topic=m.topic,
                content=m.content,
                confidence=m.confidence,
                provenance_turn_id=prov_turn,
                is_confirmed=is_confirmed,
                status="active" if m.is_active else "inactive",
                provenance_evidence_id=prov_ev,
                created_at=created_sec,
                updated_at=updated_sec,
                expires_at=expires_sec,
                history=history,
            )

            # Check expiry policy
            expired = False
            if hasattr(self.policy, "is_expired"):
                try:
                    expired = self.policy.is_expired(item, now_sec)
                except TypeError:
                    expired = self.policy.is_expired(m, datetime.fromtimestamp(now_sec, tz=timezone.utc))
                except AttributeError:
                    expired = self.policy.is_expired(m, datetime.fromtimestamp(now_sec, tz=timezone.utc))
            elif m.expires_at and m.expires_at.timestamp() <= now_sec:
                expired = True

            if expired:
                expired_ids.append(m.memory_id)
            else:
                if hasattr(self.policy, "calculate_decayed_confidence"):
                    item.confidence = self.policy.calculate_decayed_confidence(item, now_sec)
                items.append(item)

        if expired_ids:
            with self._connect() as conn:
                placeholders = ",".join("?" for _ in expired_ids)
                conn.execute(
                    f"UPDATE memory_entries SET is_active = 0 WHERE memory_id IN ({placeholders})",
                    expired_ids,
                )

        return items

    def correct_memory(
        self,
        item_id: str,
        new_content: str,
        reason: str = "Learner correction",
    ) -> Optional[Any]:
        """Backwards-compatible memory correction method returning LearnerMemoryItem."""
        try:
            from memory.models import LearnerMemoryItem
        except ImportError:
            from dataclasses import dataclass, field

            @dataclass
            class LearnerMemoryItem:
                item_id: str
                learner_id: str
                memory_type: str
                topic: str
                content: str
                confidence: float
                provenance_turn_id: str
                is_confirmed: bool = False
                status: str = "active"
                provenance_evidence_id: Optional[str] = None
                created_at: float = field(default_factory=time.time)
                updated_at: float = field(default_factory=time.time)
                expires_at: Optional[float] = None
                history: List[dict] = field(default_factory=list)

        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memory_entries WHERE memory_id = ?", (item_id,)).fetchone()
            if not row:
                return None
            m = self._row_to_memory_entry(row)

            history = m.metadata.get("history", [])
            history.append({
                "previous_content": m.content,
                "superseded_at": time.time(),
                "reason": reason,
            })
            new_meta = {**m.metadata, "history": history, "status": "active"}
            now = now_utc()

            conn.execute(
                """
                UPDATE memory_entries
                SET content = ?, updated_at = ?, metadata = ?, is_active = 1
                WHERE memory_id = ?
                """,
                (new_content, _dt_to_iso(now), _serialize_json(new_meta), item_id),
            )

            prov_turn = ""
            prov_ev = None
            if isinstance(m.source, dict):
                prov_turn = m.source.get("provenance_turn_id", "")
                prov_ev = m.source.get("provenance_evidence_id")

            return LearnerMemoryItem(
                item_id=item_id,
                learner_id=m.learner_id,
                memory_type=m.memory_type.value,
                topic=m.topic,
                content=new_content,
                confidence=m.confidence,
                provenance_turn_id=prov_turn,
                is_confirmed=True,
                status="active",
                provenance_evidence_id=prov_ev,
                created_at=m.created_at.timestamp(),
                updated_at=now.timestamp(),
                expires_at=m.expires_at.timestamp() if m.expires_at else None,
                history=history,
            )
