
"""Content hashing and source-version metadata.

Real file content hashes use full SHA-256 digests. Short or descriptive
hash values are accepted for legacy records and tests, but callers creating
production ingestion records should use file_content_hash().
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def file_content_hash(file_path: str, chunk_size: int = 1024 * 1024) -> str:
    """Return the full SHA-256 digest of a file's bytes."""
    digest = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def text_content_hash(text: str) -> str:
    """Return the full SHA-256 digest of UTF-8 encoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceVersion:
    """Immutable identity and provenance for one source content version."""

    source_id: str
    content_hash: str
    course_edition: str
    title: str
    ingested_at: str = ""
    source_type: str = "unknown"
    source_url: Optional[str] = None
    original_asset_url: Optional[str] = None
    license: Optional[str] = None
    license_url: Optional[str] = None
    attribution: Optional[str] = None
    modification_notice: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id cannot be empty")

        if not self.course_edition.strip():
            raise ValueError("course_edition cannot be empty")

        if not self.title.strip():
            raise ValueError("title cannot be empty")

        if not self.content_hash.strip():
            raise ValueError("content_hash cannot be empty")

        # A blank timestamp is filled deterministically at object creation.
        if not self.ingested_at:
            object.__setattr__(
                self,
                "ingested_at",
                datetime.now(timezone.utc).isoformat(),
            )