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

# Demo corpus DB path (isolated from production data/corpus.db)
DEMO_CORPUS_DB = "data/demo_corpus.db"
# Upload storage root
DEMO_UPLOADS_DIR = "data/demo_uploads"

# Permitted image file extensions for media serving
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

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


def validate_demo_db_path(
    db_path: Optional[str],
    base_dir: Optional[str] = None,
) -> str:
    """Validate that a requested database path is safely contained and never targets production databases.

    Rules:
    1. Rejects any attempt to target production data/corpus.db or data/learner_memory.db.
    2. Rejects path traversal and ensures target resides in data/ or system temp directory.
    3. Rejects invalid extensions (must be SQLite .db or .sqlite).
    """
    if not db_path or not db_path.strip():
        return DEFAULT_DEMO_MEMORY_DB

    clean = db_path.strip()
    root = Path(base_dir or os.getcwd()).resolve()
    target = (root / clean).resolve() if not os.path.isabs(clean) else Path(clean).resolve()

    # 1. Explicitly protect production databases
    prod_corpus = (root / "data" / "corpus.db").resolve()
    prod_memory = (root / "data" / "learner_memory.db").resolve()
    if target in (prod_corpus, prod_memory):
        raise ValueError(f"Access to production database '{clean}' is strictly prohibited in demo mode.")

    if hasattr(CONFIG, "corpus_db_path"):
        cfg_corpus = Path(CONFIG.corpus_db_path).resolve()
        if target == cfg_corpus and target.name == "corpus.db":
            raise ValueError(f"Access to production corpus database '{clean}' is strictly prohibited.")

    if hasattr(CONFIG, "memory_db_path"):
        cfg_mem = Path(CONFIG.memory_db_path).resolve()
        if target == cfg_mem and target.name == "learner_memory.db":
            raise ValueError(f"Access to production learner memory database '{clean}' is strictly prohibited.")

    # 2. Containment check: must be within data/ under workspace or system temp dir
    allowed_dirs = [
        (root / "data").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]
    if base_dir:
        allowed_dirs.append(Path(base_dir).resolve())

    is_contained = False
    for ad in allowed_dirs:
        try:
            target.relative_to(ad)
            is_contained = True
            break
        except ValueError:
            continue

    if not is_contained:
        raise ValueError(
            f"Database path '{clean}' escapes authorized demo directories. "
            "Must be located within 'data/' or temporary test directory."
        )

    # 3. Extension check
    if not any(clean.lower().endswith(ext) for ext in [".db", ".sqlite", ".sqlite3"]):
        raise ValueError(f"Database path '{clean}' must have a valid SQLite extension (.db, .sqlite).")

    return str(target)


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
    """Validate whether an image / media path exists, is an authorized image format, and is safely contained."""
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

    # 1. Extension check
    ext = target.suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return {
            "valid": False,
            "exists": False,
            "path": clean_path,
            "resolved_path": str(target),
            "error": f"Invalid media extension '{ext}'. Only {sorted(ALLOWED_IMAGE_EXTENSIONS)} are allowed.",
        }

    # 2. Allowed root directories: if explicit base_dir is given, only check base_dir;
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
    """Inspect the environment to determine actual live vs offline backend availability."""
    has_openai = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    has_llm_api = bool(getattr(CONFIG, "llm_api_key", "").strip())
    has_vision_api = bool(getattr(CONFIG, "vision_api_key", "").strip())
    has_ocr_api = bool(getattr(CONFIG, "ocr_api_key", "").strip() and getattr(CONFIG, "ocr_base_url", "").strip())

    is_live = has_openai or has_gemini or has_llm_api or has_vision_api
    mode = "Live" if is_live else "Mock / Offline"

    if has_llm_api:
        llm_model_name = getattr(CONFIG, "llm_model", "Gemma4-12B")
        effective_llm = f"{llm_model_name} (OpenAI-compatible)"
    elif has_openai:
        effective_llm = "OpenAI (gpt-4o-mini)"
    else:
        effective_llm = "Offline deterministic fallback"

    if has_vision_api:
        vision_model_name = getattr(CONFIG, "vision_model", "GLM-4.6V-Flash")
        effective_vision_backend = f"{vision_model_name} (OpenAI-compatible)"
    else:
        configured_vision = getattr(CONFIG, "vision_backend", "gemini").lower().strip()
        if configured_vision == "gemini" and not has_gemini:
            effective_vision_backend = "MockVisionAdapter (GEMINI_API_KEY unset)"
        elif configured_vision == "openai" and not has_openai:
            effective_vision_backend = "MockVisionAdapter (OPENAI_API_KEY unset)"
        else:
            effective_vision_backend = configured_vision

    if has_ocr_api:
        ocr_model_name = getattr(CONFIG, "ocr_model", "PaddleOCR-VL-1.6")
        effective_ocr = f"{ocr_model_name} (OpenAI-compatible)"
    else:
        effective_ocr = "Local PyMuPDF / Tesseract"

    return {
        "mode": mode,
        "is_live": is_live,
        "has_openai": has_openai,
        "has_gemini": has_gemini,
        "has_llm_api": has_llm_api,
        "has_vision_api": has_vision_api,
        "has_ocr_api": has_ocr_api,
        "llm_model": getattr(CONFIG, "llm_model", "google/gemma-4-12b-it-fp8"),
        "vision_model": getattr(CONFIG, "vision_model", "zai-org/GLM-4.6V-Flash"),
        "ocr_model": getattr(CONFIG, "ocr_model", "PaddlePaddle/PaddleOCR-VL-1.6"),
        "vision_backend": effective_vision_backend,
        "configured_vision_backend": getattr(CONFIG, "vision_backend", "gemini"),
        "effective_vision_backend": effective_vision_backend,
        "effective_llm": effective_llm,
        "effective_ocr": effective_ocr,
        "status_description": f"{mode} Mode — LLM: {effective_llm}, Vision: {effective_vision_backend}, OCR: {effective_ocr}",
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

    target_memory_db = validate_demo_db_path(memory_db_path, base_dir=base_dir)
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
    base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch all memories, mastery states, and pedagogical context preview for a learner."""
    target_db = validate_demo_db_path(db_path, base_dir=base_dir)
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
    base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate and insert a new learner memory record."""
    if not learner_id or not topic or not content:
        raise ValueError("learner_id, topic, and content are all required.")

    cleaned = memory_type.strip().lower()
    canonical_type_name = _UI_MEMORY_TYPE_ALIASES.get(cleaned, cleaned)
    norm_type = _normalize_memory_type(canonical_type_name)
    mem_id = compute_memory_id(learner_id, norm_type, topic, content)

    target_db = validate_demo_db_path(db_path, base_dir=base_dir)
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
    base_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Apply a learner-directed correction to an existing memory item."""
    if not memory_id or not new_content:
        raise ValueError("memory_id and new_content are required.")

    target_db = validate_demo_db_path(db_path, base_dir=base_dir)
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
    base_dir: Optional[str] = None,
) -> bool:
    """Soft-delete an individual memory record."""
    if not memory_id:
        raise ValueError("memory_id is required.")

    target_db = validate_demo_db_path(db_path, base_dir=base_dir)
    store = LearnerMemoryStore(db_path=target_db)
    try:
        return store.delete_memory(learner_id or "", memory_id)
    finally:
        store.close()


def purge_learner_memory_items(
    learner_id: str,
    db_path: Optional[str] = None,
    base_dir: Optional[str] = None,
) -> int:
    """Purge all records for a learner (GDPR/privacy compliant)."""
    if not learner_id:
        raise ValueError("learner_id is required.")

    target_db = validate_demo_db_path(db_path, base_dir=base_dir)
    store = LearnerMemoryStore(db_path=target_db)
    try:
        return store.purge_learner(learner_id)
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Video Media Path Validation (Demo Uploads)
# ---------------------------------------------------------------------------

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".pdf"}


def validate_video_serve_path(
    path: Optional[str],
    uploads_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate that a video path is safely inside DEMO_UPLOADS_DIR.

    Returns a dict with keys: valid, exists, path, resolved_path, error.
    """
    if not path or not path.strip():
        return {"valid": False, "exists": False, "path": "", "resolved_path": None,
                "error": "No video path provided."}

    clean = path.strip()
    root = Path(os.getcwd()).resolve()

    # Resolve absolute or relative path
    target = Path(clean).resolve() if os.path.isabs(clean) else (root / clean).resolve()

    # Extension check
    ext = target.suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        return {
            "valid": False, "exists": False, "path": clean,
            "resolved_path": str(target),
            "error": f"Invalid video extension '{ext}'. Only {sorted(ALLOWED_VIDEO_EXTENSIONS)} are allowed.",
        }

    # Allowed directory: DEMO_UPLOADS_DIR and system temp (for tests)
    if uploads_dir:
        base_uploads = Path(uploads_dir).resolve() if os.path.isabs(uploads_dir) else (root / uploads_dir).resolve()
        allowed = [base_uploads]
    else:
        base_uploads = (root / DEMO_UPLOADS_DIR).resolve()
        allowed = [base_uploads, Path(tempfile.gettempdir()).resolve()]

    is_safe = any(
        _is_relative_to(target, ad) for ad in allowed
    )
    if not is_safe:
        return {
            "valid": False, "exists": False, "path": clean,
            "resolved_path": str(target),
            "error": "Video path escapes authorized uploads directory.",
        }

    # Symlink check
    try:
        real = target.resolve(strict=False)
        if not any(_is_relative_to(real, ad) for ad in allowed):
            return {
                "valid": False, "exists": False, "path": clean,
                "resolved_path": str(target),
                "error": "Symlink escapes authorized uploads directory.",
            }
    except Exception:
        pass

    exists = target.is_file()
    return {
        "valid": True,
        "exists": exists,
        "path": clean,
        "resolved_path": str(target),
        "error": None if exists else f"Video file not found on disk: {clean}",
    }


def _is_relative_to(child: Path, parent: Path) -> bool:
    """Python 3.9+ has Path.is_relative_to; support older versions too."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Demo Corpus Query (Offline BM25 over uploaded videos)
# ---------------------------------------------------------------------------

def run_demo_corpus_query(
    query: str,
    top_k: int = 5,
    source_id: Optional[str] = None,
    demo_corpus_db: str = DEMO_CORPUS_DB,
    base_dir: Optional[str] = None,
    require_visual: bool = False,
    generate_answer: bool = True,
) -> Dict[str, Any]:
    """Execute hybrid retrieval over the demo corpus, and optionally generate
    a grounded answer with source citations.

    Returns a dict with:
        query, answer, status, is_abstained, is_qualified, citations,
        results (list of chunk dicts with score/rank/text/timestamps),
        total_retrieved, corpus_db, demo_corpus_db, source_id_filter, chunk_count
    """
    from demo.upload_ingest import DemoCorpusStore, DemoRetriever
    from generation.answer import generate_grounded_answer

    store = DemoCorpusStore(db_path=demo_corpus_db)
    retriever = DemoRetriever(demo_corpus_db=demo_corpus_db, source_id=source_id)

    nodes = retriever.retrieve(query, top_k=top_k)

    results = []
    for rank, node in enumerate(nodes, start=1):
        meta = node.metadata if hasattr(node, "metadata") else {}
        start_sec = meta.get("start_sec")
        end_sec = meta.get("end_sec")
        time_bounds = format_citation_time_bounds(start_sec, end_sec, page_number=meta.get("page_number"))
        results.append({
            "rank": rank,
            "score": round(getattr(node, "score", 0.0), 4),
            "chunk_id": meta.get("chunk_id", ""),
            "source_id": meta.get("source_id", ""),
            "modality": meta.get("modality", ""),
            "start_sec": start_sec,
            "end_sec": end_sec,
            "page_number": meta.get("page_number"),
            "image_path": meta.get("image_path"),
            "time_bounds_str": time_bounds,
            "text": node.text or node.get_content() if hasattr(node, "get_content") else (node.text or ""),
        })

    answer_text = ""
    citations_list: List[Dict[str, Any]] = []
    status = "Answered"

    if generate_answer and nodes:
        class _DemoRetrieverAdapter:
            def __init__(self, n):
                self._nodes = n

            def retrieve(self, q, fusion=True):
                return self._nodes

        adapter = _DemoRetrieverAdapter(nodes)
        try:
            answer_text, raw_citations = generate_grounded_answer(
                query=query,
                retriever=adapter,
                require_visual=require_visual,
                use_cache=False,
            )
            citations_list = [format_citation_card(c, base_dir=base_dir) for c in raw_citations]
            if answer_text.startswith("I abstain"):
                status = "Abstained"
            elif "Answer qualified:" in answer_text or "answer qualified:" in answer_text.lower():
                status = "Qualified"
            else:
                status = "Answered"
        except Exception as exc:
            answer_text = f"I abstain from answering due to an error: {exc}"
            status = "Abstained"
    elif not nodes:
        answer_text = "I abstain from answering because no relevant evidence was found in the demo corpus."
        status = "Abstained"

    return {
        "query": query,
        "answer": answer_text,
        "status": status,
        "is_abstained": status == "Abstained",
        "is_qualified": status == "Qualified",
        "citations": citations_list,
        "results": results,
        "total_retrieved": len(results),
        "corpus_db": demo_corpus_db,
        "demo_corpus_db": demo_corpus_db,
        "source_id_filter": source_id,
        "chunk_count": retriever.chunk_count(),
    }
