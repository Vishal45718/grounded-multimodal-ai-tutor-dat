"""Persistent, policy-controlled storage for durable learner memory (M5).

Provides:
- SQLite persistence separate from course evidence corpus.
- Expiry, decay, correction, deletion and isolation enforcement.
- Immediate purge within one query cycle.
- Formatting of isolated pedagogical styling context.
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

from memory.models import LearnerMemoryItem, compute_memory_id
from memory.policy import LearnerMemoryPolicy


class LearnerMemoryStore:
    """Manages persistent learner profile records with strict lifecycle policies."""

    def __init__(self, db_path: str = ":memory:", policy: Optional[LearnerMemoryPolicy] = None):
        self.db_path = db_path
        self.policy = policy or LearnerMemoryPolicy()
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
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
                CREATE TABLE IF NOT EXISTS learner_memories (
                    item_id TEXT PRIMARY KEY,
                    learner_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    is_confirmed INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    provenance_turn_id TEXT NOT NULL,
                    provenance_evidence_id TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    expires_at REAL,
                    history_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_learner ON learner_memories(learner_id, status)")

    def write_memory(
        self,
        item: LearnerMemoryItem,
        force: bool = False,
    ) -> Tuple[bool, Optional[LearnerMemoryItem], str]:
        """Validates and persists a learner memory item."""
        if not force:
            allowed, reason = self.policy.evaluate_write(item)
            if not allowed:
                return False, None, reason

        if item.expires_at is None and self.policy.default_ttl_seconds > 0:
            item.expires_at = item.created_at + self.policy.default_ttl_seconds

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO learner_memories (
                    item_id, learner_id, memory_type, topic, content, confidence,
                    is_confirmed, status, provenance_turn_id, provenance_evidence_id,
                    created_at, updated_at, expires_at, history_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    content = excluded.content,
                    confidence = excluded.confidence,
                    is_confirmed = excluded.is_confirmed,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at,
                    history_json = excluded.history_json
            """, (
                item.item_id, item.learner_id, item.memory_type, item.topic, item.content,
                item.confidence, int(item.is_confirmed), item.status, item.provenance_turn_id,
                item.provenance_evidence_id, item.created_at, item.updated_at, item.expires_at,
                json.dumps(item.history)
            ))

        return True, item, "Successfully committed to durable memory."

    def get_active_memories(
        self,
        learner_id: str,
        memory_type: Optional[str] = None,
        current_time: Optional[float] = None,
    ) -> List[LearnerMemoryItem]:
        """Returns all non-expired, active memories for a given learner."""
        now = current_time if current_time is not None else time.time()
        query = "SELECT * FROM learner_memories WHERE learner_id = ? AND status = 'active'"
        params: List[object] = [learner_id]

        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)

        items: List[LearnerMemoryItem] = []
        expired_ids: List[str] = []

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            for r in rows:
                item = LearnerMemoryItem(
                    item_id=r["item_id"],
                    learner_id=r["learner_id"],
                    memory_type=r["memory_type"],
                    topic=r["topic"],
                    content=r["content"],
                    confidence=r["confidence"],
                    provenance_turn_id=r["provenance_turn_id"],
                    is_confirmed=bool(r["is_confirmed"]),
                    status=r["status"],
                    provenance_evidence_id=r["provenance_evidence_id"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    expires_at=r["expires_at"],
                    history=json.loads(r["history_json"]),
                )

                if self.policy.is_expired(item, now):
                    expired_ids.append(item.item_id)
                else:
                    item.confidence = self.policy.calculate_decayed_confidence(item, now)
                    items.append(item)

            if expired_ids:
                placeholders = ",".join("?" for _ in expired_ids)
                conn.execute(
                    f"UPDATE learner_memories SET status = 'expired' WHERE item_id IN ({placeholders})",
                    expired_ids,
                )

        return items

    def correct_memory(
        self,
        item_id: str,
        new_content: str,
        reason: str = "Learner correction",
    ) -> Optional[LearnerMemoryItem]:
        """Corrects an existing memory item, archiving the prior value in history."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM learner_memories WHERE item_id = ?", (item_id,)).fetchone()
            if not row:
                return None

            history = json.loads(row["history_json"])
            history.append({
                "previous_content": row["content"],
                "superseded_at": time.time(),
                "reason": reason,
            })

            now = time.time()
            conn.execute("""
                UPDATE learner_memories
                SET content = ?, updated_at = ?, history_json = ?, status = 'active'
                WHERE item_id = ?
            """, (new_content, now, json.dumps(history), item_id))

            return LearnerMemoryItem(
                item_id=item_id,
                learner_id=row["learner_id"],
                memory_type=row["memory_type"],
                topic=row["topic"],
                content=new_content,
                confidence=row["confidence"],
                provenance_turn_id=row["provenance_turn_id"],
                is_confirmed=True,
                status="active",
                provenance_evidence_id=row["provenance_evidence_id"],
                created_at=row["created_at"],
                updated_at=now,
                expires_at=row["expires_at"],
                history=history,
            )

    def delete_memory(self, item_id: str, reason: str = "Learner requested deletion") -> bool:
        """Deletes a memory item immediately so it is absent within one query cycle."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE learner_memories
                SET status = 'deleted', updated_at = ?
                WHERE item_id = ?
            """, (time.time(), item_id))
            return cur.rowcount > 0

    def purge_learner(self, learner_id: str) -> int:
        """Permanently purges all data for a learner (hard delete)."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM learner_memories WHERE learner_id = ?", (learner_id,))
            return cur.rowcount

    def build_pedagogical_context(self, learner_id: str) -> str:
        """Constructs an isolated prompt prefix strictly for personalization.

        Guaranteed never to be cited as course evidence.
        """
        memories = self.get_active_memories(learner_id)
        if not memories:
            return ""

        lines = [
            "=== [LEARNER PROFILE - PEDAGOGICAL STYLING ONLY - DO NOT CITE AS EVIDENCE] ===",
            f"Learner ID: {learner_id}",
        ]
        for m in memories:
            lines.append(f"- [{m.memory_type.upper()}] Topic: {m.topic} | {m.content} (Confidence: {m.confidence:.2f})")
        lines.append(
            "Instructions: Use this profile ONLY to adjust your tone and explanation depth. "
            "You MUST NEVER cite these profile notes as instructional course evidence."
        )
        lines.append("==========================================================================")
        return "\n".join(lines)
