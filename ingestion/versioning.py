"""Content-version identifiers so retrieval can distinguish and invalidate
stale course editions (feeds M1's corpus schema and M6's version-safety
requirement)."""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional


def file_content_hash(path: str, chunk_size: int = 1 << 20) -> str:
    """SHA-256 hash of the file's bytes -- used as the immutable content-
    version id. Two uploads of the literal same video produce the same
    hash, so re-ingestion is a safe no-op; any edit (re-encode, trim,
    re-record) yields a new hash, which is exactly the signal M6 needs to
    tell a retriever "this evidence chunk no longer matches the source."
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()[:16]


@dataclass
class SourceVersion:
    source_id: str          # stable logical id, e.g. "cs5903-lec03"
    content_hash: str       # changes whenever the underlying file changes
    course_edition: str     # e.g. "Fall2026" -- lets us invalidate a whole edition at once
    title: str
    ingested_at: float = field(default_factory=time.time)
    is_deprecated: bool = False
    asset_id: Optional[str] = None
    source_url: Optional[str] = None

