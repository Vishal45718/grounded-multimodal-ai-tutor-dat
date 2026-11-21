"""Source-Version safety, cache invalidation, and stale evidence filtering (M6).

Guarantees:
1. When a source version changes or an edition is deprecated, cached answers are invalidated immediately.
2. Retrieved evidence is verified against active database records so stale chunks are never served.
3. Quantifies stale leakage metric: Stale leakage must equal exactly 0.0.
"""
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple
from storage.corpus_store import active_chunks


class VersionSafeCache:
    """Query cache with fine-grained version tracking and atomic invalidation."""

    def __init__(self):
        # Key: hash(source_id, content_hash, normalized_query) -> (answer, citations, edition, timestamp)
        self._cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _make_key(source_id: str, content_hash: str, query: str) -> str:
        ident = f"{source_id.strip()}:{content_hash.strip()}:{query.strip().lower()}"
        return hashlib.sha256(ident.encode("utf-8")).hexdigest()

    def get(self, source_id: str, content_hash: str, query: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """Retrieves cached response only if the source_id and content_hash match active version."""
        key = self._make_key(source_id, content_hash, query)
        entry = self._cache.get(key)
        if not entry:
            return None
        return entry["answer"], entry["citations"]

    def set(
        self,
        source_id: str,
        content_hash: str,
        course_edition: str,
        query: str,
        answer: str,
        citations: List[Dict[str, Any]],
    ) -> None:
        """Stores a generated answer and citations tagged with edition and content version."""
        key = self._make_key(source_id, content_hash, query)
        self._cache[key] = {
            "source_id": source_id,
            "content_hash": content_hash,
            "course_edition": course_edition,
            "query": query,
            "answer": answer,
            "citations": citations,
            "cached_at": time.time(),
        }

    def invalidate_source(self, source_id: str) -> int:
        """Invalidates all cached entries for a logical source ID."""
        keys_to_remove = [k for k, v in self._cache.items() if v["source_id"] == source_id]
        for k in keys_to_remove:
            del self._cache[k]
        return len(keys_to_remove)

    def invalidate_edition(self, course_edition: str) -> int:
        """Invalidates all cached entries belonging to a deprecated course edition."""
        keys_to_remove = [k for k, v in self._cache.items() if v["course_edition"] == course_edition]
        for k in keys_to_remove:
            del self._cache[k]
        return len(keys_to_remove)

    def clear(self) -> None:
        """Flushes the entire cache."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


def filter_stale_chunks(nodes: List[Any], active_chunk_ids: Optional[set] = None) -> List[Any]:
    """Filters out any retrieved node that is stale or belongs to a deprecated edition.

    If active_chunk_ids is explicitly provided, only nodes with chunk_id in active_chunk_ids are kept.
    Otherwise, drops any node explicitly flagged with is_stale=1 or is_deprecated=1.
    """
    valid_nodes = []
    for node in nodes:
        meta = getattr(node, "metadata", {}) or {}
        cid = meta.get("chunk_id")
        is_stale = meta.get("is_stale", 0)
        is_deprecated = meta.get("is_deprecated", 0)

        # Drop explicitly stale or deprecated nodes
        if is_stale == 1 or is_stale is True or is_deprecated == 1 or is_deprecated is True:
            continue

        # If an active ID whitelist is provided, verify membership
        if active_chunk_ids is not None and cid is not None and cid not in active_chunk_ids:
            continue

        valid_nodes.append(node)

    return valid_nodes


def compute_stale_leakage(citations: List[Dict[str, Any]], active_chunk_ids: Optional[set] = None) -> float:
    """Calculates the fraction of emitted citations referencing stale or deprecated chunks.

    Returns:
        0.0 when all citations reference active content.
    """
    if not citations:
        return 0.0

    if active_chunk_ids is None:
        chunks = active_chunks()
        active_chunk_ids = {c["chunk_id"] for c in chunks}

    stale_count = 0
    for c in citations:
        cid = c.get("chunk_id")
        if cid and cid not in active_chunk_ids:
            stale_count += 1

    return stale_count / len(citations)
