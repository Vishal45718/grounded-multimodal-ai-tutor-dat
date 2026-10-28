
"""Version-aware SQLite store for multimodal tutor evidence.

Safety rules:
1. A failed extraction must not activate a new source version.
2. A chunk is active only when its content hash matches the active source.
3. Delayed writes from superseded versions remain stale.
4. A successful replacement activates its chunks and stales the previous ones.
5. Provenance is retained with each source and evidence chunk.
"""

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
    """Open a database connection and commit successful transactions."""
    db_path = CONFIG.corpus_db_path
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA busy_timeout = 30000")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(conn: sqlite3.Connection, table: str) -> set:
    """Return column names for an existing table."""
    return {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def init_db() -> None:
    """Create the schema and safely add provenance columns to older databases."""
    with _connect() as conn:
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
            conn.executescript(schema_file.read())

        source_columns = _columns(conn, "sources")
        source_migrations = {
            "asset_id": "TEXT",
            "source_url": "TEXT",
            "original_asset_url": "TEXT",
            "license": "TEXT",
            "license_url": "TEXT",
            "attribution": "TEXT",
            "modification_notice": "TEXT",
        }

        for name, definition in source_migrations.items():
            if name not in source_columns:
                conn.execute(
                    f"ALTER TABLE sources ADD COLUMN {name} {definition}"
                )

        chunk_columns = _columns(conn, "chunks")
        chunk_migrations = {
            "asset_id": "TEXT",
            "source_url": "TEXT",
            "original_asset_url": "TEXT",
            "edition_id": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'success'",
            "error_message": "TEXT",
            "page_number": "INTEGER",
            "extraction_method": "TEXT",
            "license": "TEXT",
            "license_url": "TEXT",
            "attribution": "TEXT",
            "modification_notice": "TEXT",
        }

        for name, definition in chunk_migrations.items():
            if name not in chunk_columns:
                conn.execute(
                    f"ALTER TABLE chunks ADD COLUMN {name} {definition}"
                )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_source_hash "
            "ON chunks(source_id, content_hash)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_active "
            "ON chunks(is_stale, source_id, content_hash)"
        )


def is_source_active(source_id: str, content_hash: str) -> bool:
    """Return True only if this exact source version is active."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM sources
            WHERE source_id = ?
              AND content_hash = ?
              AND is_deprecated = 0
            """,
            (source_id, content_hash),
        ).fetchone()

        return row is not None


def upsert_source(version: SourceVersion) -> bool:
    """Activate a successfully ingested source version.

    Call this only after extraction and chunk construction have succeeded.
    New chunks may be inserted first; they remain stale until this function
    activates their exact content hash.

    Returns:
        True if a source version was activated or its metadata was updated.
        False if the request was a no-op or an older delayed version.
    """
    if not version.source_id.strip():
        raise ValueError("source_id cannot be empty")
    if not version.course_edition.strip():
        raise ValueError("course_edition cannot be empty")
    if not version.content_hash:
        raise ValueError("content_hash cannot be empty")

    with _connect() as conn:
        # Serialize this read-modify-write sequence.
        conn.execute("BEGIN IMMEDIATE")

        existing = conn.execute(
            """
            SELECT content_hash, ingested_at, is_deprecated,
                   course_edition, title
            FROM sources
            WHERE source_id = ?
            """,
            (version.source_id,),
        ).fetchone()

        if existing is not None:
            old_hash = existing["content_hash"]
            old_ingested_at = existing["ingested_at"]
            old_deprecated = bool(existing["is_deprecated"])

            # A delayed worker must never replace a newer version.
            if (
                old_hash != version.content_hash
                and old_ingested_at > version.ingested_at
            ):
                return False

            # Repeating the same activation is a safe no-op.
            if (
                old_hash == version.content_hash
                and old_deprecated == bool(version.is_deprecated)
                and existing["course_edition"] == version.course_edition
                and existing["title"] == version.title
            ):
                # Repair stale flags only for this exact active version.
                if not version.is_deprecated:
                    conn.execute(
                        """
                        UPDATE chunks
                        SET is_stale = 0
                        WHERE source_id = ?
                          AND content_hash = ?
                        """,
                        (version.source_id, version.content_hash),
                    )
                return False

        # First invalidate chunks from other versions. The old version stays
        # active until this successful activation transaction commits.
        conn.execute(
            """
            UPDATE chunks
            SET is_stale = 1
            WHERE source_id = ?
              AND content_hash != ?
            """,
            (version.source_id, version.content_hash),
        )

        # Update in place rather than INSERT OR REPLACE, which can delete the
        # parent row and cause problems for databases with foreign keys.
        conn.execute(
            """
            INSERT INTO sources (
                source_id, content_hash, course_edition, title,
                ingested_at, is_deprecated, asset_id, source_url,
                original_asset_url, license, license_url, attribution,
                modification_notice
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                content_hash = excluded.content_hash,
                course_edition = excluded.course_edition,
                title = excluded.title,
                ingested_at = excluded.ingested_at,
                is_deprecated = excluded.is_deprecated,
                asset_id = excluded.asset_id,
                source_url = excluded.source_url,
                original_asset_url = excluded.original_asset_url,
                license = excluded.license,
                license_url = excluded.license_url,
                attribution = excluded.attribution,
                modification_notice = excluded.modification_notice
            """,
            (
                version.source_id,
                version.content_hash,
                version.course_edition,
                version.title,
                version.ingested_at,
                int(version.is_deprecated),
                getattr(version, "asset_id", None),
                getattr(version, "source_url", None),
                getattr(version, "original_asset_url", None),
                getattr(version, "license", None),
                getattr(version, "license_url", None),
                getattr(version, "attribution", None),
                getattr(version, "modification_notice", None),
            ),
        )

        # Activate only chunks matching the newly active source version.
        # Deprecated versions are never eligible for retrieval.
        conn.execute(
            """
            UPDATE chunks
            SET is_stale = ?
            WHERE source_id = ?
              AND content_hash = ?
            """,
            (
                int(version.is_deprecated),
                version.source_id,
                version.content_hash,
            ),
        )

        return True


def insert_chunks(chunks: List[EvidenceChunk]) -> None:
    """Insert evidence while preventing delayed old-version writes.

    If the source version is not currently active, inserted chunks are marked
    stale. This allows a pipeline to stage new chunks before calling
    upsert_source(), without exposing them to retrieval prematurely.
    """
    if not chunks:
        return

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        source_ids = sorted({chunk.source_id for chunk in chunks})
        placeholders = ",".join("?" for _ in source_ids)

        rows = conn.execute(
            f"""
            SELECT source_id, content_hash, is_deprecated
            FROM sources
            WHERE source_id IN ({placeholders})
            """,
            source_ids,
        ).fetchall()

        active_map = {
            row["source_id"]: (
                row["content_hash"],
                bool(row["is_deprecated"]),
            )
            for row in rows
        }

        values = []

        for chunk in chunks:
            current = active_map.get(chunk.source_id)

            is_current_version = (
                current is not None
                and current[0] == chunk.content_hash
                and not current[1]
            )

            # New chunks remain staged/stale until upsert_source activates
            # their version. Late writes from older versions stay stale.
            stale = 0 if is_current_version else 1

            values.append(
                (
                    chunk.chunk_id,
                    chunk.source_id,
                    chunk.content_hash,
                    chunk.modality,
                    chunk.start_sec,
                    chunk.end_sec,
                    chunk.text,
                    chunk.image_path,
                    stale,
                    getattr(chunk, "asset_id", None),
                    getattr(chunk, "source_url", None),
                    getattr(chunk, "original_asset_url", None),
                    getattr(chunk, "edition_id", None),
                    getattr(chunk, "status", "success"),
                    getattr(chunk, "error_message", None),
                    getattr(chunk, "page_number", None),
                    getattr(chunk, "extraction_method", None),
                    getattr(chunk, "license", None),
                    getattr(chunk, "license_url", None),
                    getattr(chunk, "attribution", None),
                    getattr(chunk, "modification_notice", None),
                )
            )

        conn.executemany(
            """
            INSERT INTO chunks (
                chunk_id, source_id, content_hash, modality,
                start_sec, end_sec, text, image_path, is_stale,
                asset_id, source_url, original_asset_url, edition_id,
                status, error_message, page_number, extraction_method,
                license, license_url, attribution, modification_notice
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(chunk_id) DO UPDATE SET
                source_id = excluded.source_id,
                content_hash = excluded.content_hash,
                modality = excluded.modality,
                start_sec = excluded.start_sec,
                end_sec = excluded.end_sec,
                text = excluded.text,
                image_path = excluded.image_path,
                is_stale = excluded.is_stale,
                asset_id = excluded.asset_id,
                source_url = excluded.source_url,
                original_asset_url = excluded.original_asset_url,
                edition_id = excluded.edition_id,
                status = excluded.status,
                error_message = excluded.error_message,
                page_number = excluded.page_number,
                extraction_method = excluded.extraction_method,
                license = excluded.license,
                license_url = excluded.license_url,
                attribution = excluded.attribution,
                modification_notice = excluded.modification_notice
            """,
            values,
        )


def deprecate_edition(course_edition: str) -> None:
    """Deprecate an entire course edition and invalidate its evidence."""
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        conn.execute(
            "UPDATE sources SET is_deprecated = 1 WHERE course_edition = ?",
            (course_edition,),
        )

        conn.execute(
            """
            UPDATE chunks
            SET is_stale = 1
            WHERE source_id IN (
                SELECT source_id
                FROM sources
                WHERE course_edition = ?
            )
            """,
            (course_edition,),
        )


def active_chunks(modality: Optional[str] = None) -> List[dict]:
    """Return only evidence matching its source's active version.

    The hash equality check is mandatory even if a stale flag was accidentally
    reset by a delayed writer or an older database operation.
    """
    query = """
        SELECT c.*
        FROM chunks AS c
        JOIN sources AS s
          ON s.source_id = c.source_id
         AND s.content_hash = c.content_hash
        WHERE c.is_stale = 0
          AND s.is_deprecated = 0
    """
    params = ()

    if modality is not None:
        if modality not in {"audio", "visual"}:
            raise ValueError("modality must be 'audio', 'visual', or None")
        query += " AND c.modality = ?"
        params = (modality,)

    query += " ORDER BY c.source_id, c.start_sec, c.chunk_id"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
