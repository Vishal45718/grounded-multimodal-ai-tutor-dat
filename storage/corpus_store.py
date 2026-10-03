"""Versioned evidence-corpus store (M1) with the invalidation hooks M6
needs when a lecture is re-recorded or a course edition is superseded."""
import os
import sqlite3
from contextlib import contextmanager
from typing import List, Optional

from config import CONFIG
from ingestion.chunker import EvidenceChunk
from ingestion.versioning import SourceVersion

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


@contextmanager
def _connect():
    os.makedirs(os.path.dirname(CONFIG.corpus_db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(CONFIG.corpus_db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _connect() as conn, open(_SCHEMA_PATH) as f:
        conn.executescript(f.read())


def is_source_active(source_id: str, content_hash: str) -> bool:
    """Check if a source is currently active at this exact content_hash."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT content_hash, is_deprecated FROM sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        return bool(row and row[0] == content_hash and row[1] == 0)


def upsert_source(version: SourceVersion) -> bool:
    """Activates the given source version.
    Marks older version chunks as stale and ensures new version chunks are active.
    Returns False (no-op) if this exact content_hash is already indexed and active."""
    with _connect() as conn:
        existing = conn.execute(
            "SELECT content_hash, ingested_at, is_deprecated FROM sources WHERE source_id = ?",
            (version.source_id,)
        ).fetchone()
        if existing:
            if existing[0] == version.content_hash and bool(existing[2]) == bool(version.is_deprecated):
                return False
            if existing[1] > version.ingested_at:
                # A newer version is already active; delayed superseded version must never activate
                return False

        # Mark chunks from previous versions as stale
        conn.execute(
            "UPDATE chunks SET is_stale = 1 WHERE source_id = ? AND content_hash != ?",
            (version.source_id, version.content_hash),
        )

        conn.execute(
            "INSERT OR REPLACE INTO sources (source_id, content_hash, course_edition, title, ingested_at, is_deprecated) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                version.source_id, version.content_hash, version.course_edition,
                version.title, version.ingested_at, int(version.is_deprecated),
            ),
        )

        if not version.is_deprecated:
            conn.execute(
                "UPDATE chunks SET is_stale = 0 WHERE source_id = ? AND content_hash = ?",
                (version.source_id, version.content_hash),
            )
        else:
            conn.execute(
                "UPDATE chunks SET is_stale = 1 WHERE source_id = ? AND content_hash = ?",
                (version.source_id, version.content_hash),
            )
        return True


def insert_chunks(chunks: List[EvidenceChunk]):
    """Inserts evidence chunks. If a chunk does not match the active source version
    or belongs to a deprecated source, it is persisted as stale (is_stale = 1) so it
    cannot become active."""
    if not chunks:
        return
    with _connect() as conn:
        source_ids = list({c.source_id for c in chunks})
        placeholders = ",".join("?" for _ in source_ids)
        rows = conn.execute(
            f"SELECT source_id, content_hash, is_deprecated FROM sources WHERE source_id IN ({placeholders})",
            source_ids,
        ).fetchall()
        active_map = {row[0]: (row[1], bool(row[2])) for row in rows}

        to_insert = []
        for c in chunks:
            is_active = (
                c.source_id in active_map
                and active_map[c.source_id][0] == c.content_hash
                and not active_map[c.source_id][1]
            )
            is_stale = 0 if is_active else 1
            to_insert.append((
                c.chunk_id, c.source_id, c.content_hash, c.modality,
                c.start_sec, c.end_sec, c.text, c.image_path, is_stale
            ))

        conn.executemany(
            "INSERT OR REPLACE INTO chunks "
            "(chunk_id, source_id, content_hash, modality, start_sec, end_sec, text, image_path, is_stale) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            to_insert,
        )


def deprecate_edition(course_edition: str):
    """M6: invalidate a whole superseded course edition in one call."""
    with _connect() as conn:
        conn.execute("UPDATE sources SET is_deprecated = 1 WHERE course_edition = ?", (course_edition,))
        conn.execute(
            "UPDATE chunks SET is_stale = 1 WHERE source_id IN "
            "(SELECT source_id FROM sources WHERE course_edition = ?)",
            (course_edition,),
        )


def active_chunks(modality: Optional[str] = None) -> List[dict]:
    """What M2's retriever is allowed to search: not stale, not deprecated, and strictly matching active source version."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        q = (
            "SELECT c.* FROM chunks c "
            "JOIN sources s ON c.source_id = s.source_id AND c.content_hash = s.content_hash "
            "WHERE c.is_stale = 0 AND s.is_deprecated = 0"
        )
        params: tuple = ()
        if modality:
            q += " AND c.modality = ?"
            params = (modality,)
        return [dict(r) for r in conn.execute(q, params).fetchall()]
