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


def upsert_source(version: SourceVersion) -> bool:
    """Returns False (no-op) if this exact content_hash is already indexed
    for this source_id -- keeps re-ingestion idempotent. If the source_id
    exists with a *different* hash, the old chunks are marked stale before
    the new version is written, so retrieval never mixes evidence from two
    versions of the same lecture."""
    with _connect() as conn:
        existing = conn.execute(
            "SELECT content_hash FROM sources WHERE source_id = ?", (version.source_id,)
        ).fetchone()
        if existing and existing[0] == version.content_hash:
            return False
        if existing:
            conn.execute("UPDATE chunks SET is_stale = 1 WHERE source_id = ?", (version.source_id,))
        conn.execute(
            "INSERT OR REPLACE INTO sources VALUES (?, ?, ?, ?, ?, ?)",
            (
                version.source_id, version.content_hash, version.course_edition,
                version.title, version.ingested_at, int(version.is_deprecated),
            ),
        )
        return True


def insert_chunks(chunks: List[EvidenceChunk]):
    with _connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO chunks "
            "(chunk_id, source_id, content_hash, modality, start_sec, end_sec, text, image_path, is_stale) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
            [
                (c.chunk_id, c.source_id, c.content_hash, c.modality, c.start_sec, c.end_sec, c.text, c.image_path)
                for c in chunks
            ],
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
    """What M2's retriever is allowed to search: not stale, not deprecated."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        q = (
            "SELECT c.* FROM chunks c JOIN sources s ON c.source_id = s.source_id "
            "WHERE c.is_stale = 0 AND s.is_deprecated = 0"
        )
        params: tuple = ()
        if modality:
            q += " AND c.modality = ?"
            params = (modality,)
        return [dict(r) for r in conn.execute(q, params).fetchall()]
