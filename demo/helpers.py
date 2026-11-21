"""Pure, testable UI-to-backend orchestration and formatting helpers.

Zero UI-framework coupling. Handles citation formatting, timestamp jump URLs,
media validation, backend status detection, tutor query execution, and
learner memory CRUD operations.
"""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import CONFIG
from storage.corpus_store import init_db
from retrieval.retriever import TutorRetriever
from generation.answer import generate_grounded_answer
from memory.models import (
    MemoryEntry,
    MemoryType,
    _normalize_memory_type,
    compute_memory_id,
)
from memory.store import LearnerMemoryStore


# Default demo database path (isolated from production learner_memory.db)
DEFAULT_DEMO_MEMORY_DB = "data/demo_learner_memory.db"

# Additional user-friendly UI aliases mapping to canonical MemoryType names
_UI_MEMORY_TYPE_ALIASES = {
    "struggle": "struggled_concept",
    "struggles": "struggled_concept",
    "style": "learning_preference",
    "background": "learning_preference",
    "preference": "learning_preference",
    "goal": "learning_goal",
    "correction": "student_correction",
    "mastery": "topic_mastery",
}


def format_time_seconds(sec: Optional[float]) -> str:
    """Format floating point seconds into [mm:ss] format."""
    if sec is None:
        return "00:00"
    total_sec = max(0, int(round(sec)))
    mins = total_sec // 60
    secs = total_sec % 60
    return f"{mins:02d}:{secs:02d}"


def format_citation_time_bounds(
    start_sec: Optional[float],
    end_sec: Optional[float],
    page_number: Optional[int] = None,
) -> str:
    """Format time bounds or page number for human-readable citation display."""
    if start_sec is not None and end_sec is not None:
        return f"[{format_time_seconds(start_sec)}] - [{format_time_seconds(end_sec)}]"
    elif start_sec is not None:
        return f"[{format_time_seconds(start_sec)}]"
    elif page_number is not None:
        return f"Slide Page {page_number}"
    else:
        return "Unknown"


def build_jump_url(source_url: Optional[str], start_sec: Optional[float]) -> Optional[str]:
    """Construct a direct timestamp jump link for video / audio sources."""
    if not source_url or start_sec is None:
        return None

    clean_url = source_url.strip()
    sec_int = max(0, int(round(start_sec)))

    delimiter = "&" if ("?" in clean_url or "&" in clean_url) else "?"
    return f"{clean_url}{delimiter}t={sec_int}s"


def validate_media_path(
    path: Optional[str],
    base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate whether an image / media path exists and is safely contained."""
    if not path or not path.strip():
        return {
            "valid": False,
            "exists": False,
            "path": "",
            "resolved_path": None,
            "error": "No media path provided.",
        }

    clean_path = path.strip()
    root = Path(base_dir or os.getcwd()).resolve()
    target = (root / clean_path).resolve() if not os.path.isabs(clean_path) else Path(clean_path).resolve()

    # Allowed root directories: if explicit base_dir is given, only check base_dir;
    # otherwise check workspace root and system temp directory
    if base_dir:
        allowed_roots = [Path(base_dir).resolve()]
    else:
        allowed_roots = [root, Path(tempfile.gettempdir()).resolve()]

    is_safe = False
    for ar in allowed_roots:
        try:
            target.relative_to(ar)
            is_safe = True
            break
        except ValueError:
            continue

    if not is_safe:
        return {
            "valid": False,
            "exists": False,
            "path": clean_path,
            "resolved_path": str(target),
            "error": "Path escapes authorized repository directory.",
        }

    exists = target.is_file()
    return {
        "valid": True,
        "exists": exists,
        "path": clean_path,
        "resolved_path": str(target),
        "error": None if exists else f"File not found on disk: {clean_path}",
    }


def format_citation_card(
    citation: Dict[str, Any],
    base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Enrich a raw citation dictionary with UI presentation fields."""
    start_sec = citation.get("start_sec")
    end_sec = citation.get("end_sec")
    page_num = citation.get("page_number")
    source_url = citation.get("source_url")
    image_path = citation.get("image_path")
    modality = citation.get("modality", "unknown")

    time_bounds_str = format_citation_time_bounds(start_sec, end_sec, page_num)
    jump_url = build_jump_url(source_url, start_sec)
    media_val = validate_media_path(image_path, base_dir=base_dir) if image_path else None

    return {
        "citation_label": citation.get("citation_label", ""),
        "chunk_id": citation.get("chunk_id", ""),
        "source_id": citation.get("source_id", ""),
        "asset_id": citation.get("asset_id", ""),
        "content_hash": citation.get("content_hash", ""),
        "edition_id": citation.get("edition_id") or citation.get("course_edition", ""),
        "modality": modality,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "page_number": page_num,
        "time_bounds_str": time_bounds_str,
        "source_url": source_url,
        "jump_url": jump_url,
        "image_path": image_path,
        "image_exists": bool(media_val and media_val["exists"]),
        "text": citation.get("text", ""),
    }


def detect_backend_status() -> Dict[str, Any]:
    """Inspect the environment to determine live vs offline backend availability."""
    has_openai = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    vision_backend = getattr(CONFIG, "vision_backend", "gemini")

    is_live = has_openai or has_gemini
    mode = "Live" if is_live else "Mock / Offline"

    return {
        "mode": mode,
        "is_live": is_live,
        "has_openai": has_openai,
        "has_gemini": has_gemini,
        "vision_backend": vision_backend,
    }


def run_tutor_query(
    query: str,
    top_k: int = 5,
    rerank: bool = False,
    require_visual: bool = False,
    use_cache: bool = True,
    learner_id: Optional[str] = None,
    memory_db_path: Optional[str] = None,
    retriever: Optional[Any] = None,
    llm: Optional[Any] = None,
    vision_model: Optional[Any] = None,
    base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute end-to-end tutor retrieval and answer generation with error handling."""
    init_db()

    target_memory_db = memory_db_path or DEFAULT_DEMO_MEMORY_DB
    memory_store: Optional[LearnerMemoryStore] = None
    if learner_id:
        memory_store = LearnerMemoryStore(db_path=target_memory_db)

    try:
        resolved_retriever = retriever
        if resolved_retriever is None:
            resolved_retriever = TutorRetriever(
                use_dense=True,
                use_sparse=True,
                use_reranker=rerank,
            )

        answer, citations = generate_grounded_answer(
            query=query,
            retriever=resolved_retriever,
            llm=llm,
            vision_model=vision_model,
            require_visual=require_visual,
            use_cache=use_cache,
            learner_id=learner_id,
            memory_store=memory_store,
        )

        # Status categorization
        if answer.startswith("I abstain"):
            status = "Abstained"
        elif "Answer qualified:" in answer or "answer qualified:" in answer.lower():
            status = "Qualified"
        else:
            status = "Answered"

        formatted_citations = [format_citation_card(c, base_dir=base_dir) for c in citations]

        return {
            "query": query,
            "answer": answer,
            "status": status,
            "is_abstained": status == "Abstained",
            "is_qualified": status == "Qualified",
            "citations": formatted_citations,
            "citation_count": len(formatted_citations),
            "pedagogical_context_used": bool(learner_id and memory_store),
            "learner_id": learner_id,
        }
    finally:
        if memory_store is not None:
            memory_store.close()


# ----------------------------------------------------------------------
# Learner Memory CRUD Orchestration
# ----------------------------------------------------------------------

def get_learner_memory_data(
    learner_id: str,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch all memories, mastery states, and pedagogical context preview for a learner."""
    target_db = db_path or DEFAULT_DEMO_MEMORY_DB
    store = LearnerMemoryStore(db_path=target_db)
    try:
        memories = store.get_memories(learner_id)
        mastery_states = store.get_mastery(learner_id)
        profile = store.get_profile(learner_id)
        pedagogical_context = store.build_pedagogical_context(learner_id)

        mem_list = []
        for m in memories:
            m_dict = m.to_dict()
            m_dict["memory_type_str"] = (
                m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type)
            )
            history = getattr(m, "history", None)
            if history is None and hasattr(m, "metadata") and isinstance(m.metadata, dict):
                history = m.metadata.get("history")
            m_dict["revision_count"] = len(history) if history else 0
            mem_list.append(m_dict)

        mastery_list = [ms.to_dict() for ms in mastery_states]

        return {
            "learner_id": learner_id,
            "memories": mem_list,
            "mastery_states": mastery_list,
            "profile": profile.to_dict() if profile else None,
            "pedagogical_context": pedagogical_context,
            "total_memories": len(mem_list),
            "db_path": target_db,
        }
    finally:
        store.close()


def add_learner_memory_item(
    learner_id: str,
    memory_type: str,
    topic: str,
    content: str,
    confidence: float = 1.0,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate and insert a new learner memory record."""
    if not learner_id or not topic or not content:
        raise ValueError("learner_id, topic, and content are all required.")

    cleaned = memory_type.strip().lower()
    canonical_type_name = _UI_MEMORY_TYPE_ALIASES.get(cleaned, cleaned)
    norm_type = _normalize_memory_type(canonical_type_name)
    mem_id = compute_memory_id(learner_id, norm_type, topic, content)

    target_db = db_path or DEFAULT_DEMO_MEMORY_DB
    store = LearnerMemoryStore(db_path=target_db)
    try:
        entry = MemoryEntry(
            memory_id=mem_id,
            learner_id=learner_id,
            memory_type=norm_type,
            topic=topic.strip(),
            content=content.strip(),
            confidence=max(0.0, min(1.0, float(confidence))),
            source={"demo_client": f"demo_web_{int(time.time())}"},
        )
        saved = store.add_memory(entry)
        return saved.to_dict()
    finally:
        store.close()


def correct_learner_memory_item(
    memory_id: str,
    new_content: str,
    reason: str = "Demo correction",
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Apply a learner-directed correction to an existing memory item."""
    if not memory_id or not new_content:
        raise ValueError("memory_id and new_content are required.")

    target_db = db_path or DEFAULT_DEMO_MEMORY_DB
    store = LearnerMemoryStore(db_path=target_db)
    try:
        updated = store.correct_memory(
            item_id=memory_id,
            new_content=new_content.strip(),
            reason=reason.strip(),
        )
        if updated:
            if hasattr(updated, "to_dict"):
                return updated.to_dict()
            from dataclasses import asdict, is_dataclass
            if is_dataclass(updated):
                return asdict(updated)
            if hasattr(updated, "__dict__"):
                return dict(updated.__dict__)
            return {"content": str(updated)}
        return None
    finally:
        store.close()


def delete_learner_memory_item(
    learner_id: str,
    memory_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Soft-delete an individual memory record."""
    if not memory_id:
        raise ValueError("memory_id is required.")

    target_db = db_path or DEFAULT_DEMO_MEMORY_DB
    store = LearnerMemoryStore(db_path=target_db)
    try:
        return store.delete_memory(learner_id or "", memory_id)
    finally:
        store.close()


def purge_learner_memory_items(
    learner_id: str,
    db_path: Optional[str] = None,
) -> int:
    """Purge all records for a learner (GDPR/privacy compliant)."""
    if not learner_id:
        raise ValueError("learner_id is required.")

    target_db = db_path or DEFAULT_DEMO_MEMORY_DB
    store = LearnerMemoryStore(db_path=target_db)
    try:
        return store.purge_learner(learner_id)
    finally:
        store.close()
