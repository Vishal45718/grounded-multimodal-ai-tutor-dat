"""DAT Tutor M8 Interactive Demo Application (FastAPI).

Provides a local interactive web interface for:
1. Grounded multimodal tutor query answering with live / mock status.
2. Synchronized evidence viewer for audio/video (timestamp bounds, jump URLs)
   and visual slide keyframes.
3. Live learner memory inspector with isolated storage, live preview of
   pedagogical styling, and full CRUD controls (Add, Correct, Delete, Purge).
4. Upload Video → Offline Ingest → Query & Inspect RAG tab (zero API keys).
5. Hardened path containment, database targeting protection, and XSS safety.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from demo.helpers import (
    ALLOWED_VIDEO_EXTENSIONS,
    DEFAULT_DEMO_MEMORY_DB,
    DEMO_CORPUS_DB,
    DEMO_UPLOADS_DIR,
    add_learner_memory_item,
    correct_learner_memory_item,
    delete_learner_memory_item,
    detect_backend_status,
    get_learner_memory_data,
    purge_learner_memory_items,
    run_demo_corpus_query,
    run_tutor_query,
    validate_demo_db_path,
    validate_media_path,
    validate_video_serve_path,
)
from demo.upload_ingest import (
    MAX_VIDEO_BYTES,
    ALLOWED_TRANSCRIPT_EXTENSIONS,
    ALLOWED_SLIDES_EXTENSIONS,
    DemoCorpusStore,
    ingest_uploaded_video,
    sanitize_filename,
)

app = FastAPI(
    title="DAT Tutor — M8 Interactive Demo",
    description="Multimodal Grounded AI Tutor with Synchronized Evidence and Learner Memory",
    version="1.0.0",
)


# ----------------------------------------------------------------------
# Request / Response Schemas
# ----------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=10)
    rerank: bool = Field(False)
    require_visual: bool = Field(False)
    use_cache: bool = Field(True)
    learner_id: Optional[str] = Field(None)
    memory_db_path: Optional[str] = Field(None)


class AddMemoryRequest(BaseModel):
    learner_id: str = Field(..., min_length=1)
    memory_type: str = Field("goal")
    topic: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    memory_db_path: Optional[str] = Field(None)


class CorrectMemoryRequest(BaseModel):
    memory_id: str = Field(..., min_length=1)
    new_content: str = Field(..., min_length=1)
    reason: str = Field("Demo correction")
    memory_db_path: Optional[str] = Field(None)


class DeleteMemoryRequest(BaseModel):
    learner_id: str = Field("")
    memory_id: str = Field(..., min_length=1)
    memory_db_path: Optional[str] = Field(None)


class PurgeLearnerRequest(BaseModel):
    learner_id: str = Field(..., min_length=1)
    memory_db_path: Optional[str] = Field(None)


# ----------------------------------------------------------------------
# API Endpoints
# ----------------------------------------------------------------------

@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    """Return backend runtime mode and API availability with clear effective indicators."""
    return detect_backend_status()


@app.post("/api/query")
def api_query(req: QueryRequest) -> Dict[str, Any]:
    """Execute tutor query with grounded retrieval and optional pedagogical styling."""
    try:
        validated_db = validate_demo_db_path(req.memory_db_path) if req.memory_db_path else None
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    try:
        result = run_tutor_query(
            query=req.query,
            top_k=req.top_k,
            rerank=req.rerank,
            require_visual=req.require_visual,
            use_cache=req.use_cache,
            learner_id=req.learner_id.strip() if req.learner_id else None,
            memory_db_path=validated_db,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/memory")
def api_get_memory(
    learner_id: str = Query(..., min_length=1),
    db_path: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Fetch all memories, mastery states, and pedagogical context for a learner."""
    try:
        validated_db = validate_demo_db_path(db_path)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    try:
        return get_learner_memory_data(learner_id=learner_id, db_path=validated_db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/memory/add")
def api_add_memory(req: AddMemoryRequest) -> Dict[str, Any]:
    """Add a new learner memory item with strict DB containment."""
    try:
        validated_db = validate_demo_db_path(req.memory_db_path)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    try:
        return add_learner_memory_item(
            learner_id=req.learner_id,
            memory_type=req.memory_type,
            topic=req.topic,
            content=req.content,
            confidence=req.confidence,
            db_path=validated_db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/memory/correct")
def api_correct_memory(req: CorrectMemoryRequest) -> Dict[str, Any]:
    """Correct an existing learner memory item with strict DB containment."""
    try:
        validated_db = validate_demo_db_path(req.memory_db_path)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    try:
        res = correct_learner_memory_item(
            memory_id=req.memory_id,
            new_content=req.new_content,
            reason=req.reason,
            db_path=validated_db,
        )
        if not res:
            raise HTTPException(status_code=404, detail=f"Memory item {req.memory_id} not found.")
        return res
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/memory/delete")
def api_delete_memory(req: DeleteMemoryRequest) -> Dict[str, Any]:
    """Soft delete an individual learner memory with strict DB containment."""
    try:
        validated_db = validate_demo_db_path(req.memory_db_path)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    try:
        success = delete_learner_memory_item(
            learner_id=req.learner_id,
            memory_id=req.memory_id,
            db_path=validated_db,
        )
        return {"success": success, "memory_id": req.memory_id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/memory/purge")
def api_purge_memory(req: PurgeLearnerRequest) -> Dict[str, Any]:
    """Purge all memories for a learner with strict DB containment."""
    try:
        validated_db = validate_demo_db_path(req.memory_db_path)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    try:
        count = purge_learner_memory_items(
            learner_id=req.learner_id,
            db_path=validated_db,
        )
        return {"purged_count": count, "learner_id": req.learner_id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/media")
def api_media(path: str = Query(..., min_length=1)):
    """Safely serve local image keyframe assets with extension and path restriction."""
    val = validate_media_path(path)
    if not val["valid"]:
        raise HTTPException(status_code=400, detail=val.get("error") or "Invalid media path.")
    if not val["exists"]:
        raise HTTPException(status_code=404, detail=val.get("error") or "Media file not found on disk.")

    resolved = val["resolved_path"]
    media_type = "image/jpeg"
    lower_path = resolved.lower()
    if lower_path.endswith(".png"):
        media_type = "image/png"
    elif lower_path.endswith(".webp"):
        media_type = "image/webp"

    return FileResponse(resolved, media_type=media_type)


# ---------------------------------------------------------------------------
# Video Media Serving (Demo Uploads — Range-request ready via FileResponse)
# ---------------------------------------------------------------------------

@app.get("/media/video")
def api_media_video(path: str = Query(..., min_length=1)):
    """Safely serve uploaded video files with strict path containment.

    Only allows files inside DEMO_UPLOADS_DIR. Supports HTTP Range requests
    via FastAPI's FileResponse so HTML5 <video> seeking works correctly.
    """
    val = validate_video_serve_path(path)
    if not val["valid"]:
        raise HTTPException(status_code=400, detail=val.get("error") or "Invalid video path.")
    if not val["exists"]:
        raise HTTPException(status_code=404, detail=val.get("error") or "Video file not found.")

    resolved = val["resolved_path"]
    ext = Path(resolved).suffix.lower()
    media_type_map = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }
    media_type = media_type_map.get(ext, "video/mp4")
    return FileResponse(resolved, media_type=media_type)


# ---------------------------------------------------------------------------
# Upload & Ingestion Endpoints
# ---------------------------------------------------------------------------

class DemoQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)
    source_id: Optional[str] = Field(None)
    demo_corpus_db: Optional[str] = Field(None)


@app.post("/api/upload")
async def api_upload(
    video: UploadFile = File(...),
    transcript: Optional[UploadFile] = File(None),
    slides_pdf: Optional[UploadFile] = File(None),
    title: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Accept a video upload (+ optional .vtt/.srt/.txt transcript and PDF slides)
    and ingest into the isolated data/demo_corpus.db.

    Returns an ingestion report with chunk counts and any capability warnings.
    """
    # Validate video extension and size
    video_ext = Path(video.filename or "").suffix.lower()
    if video_ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Video must be one of {sorted(ALLOWED_VIDEO_EXTENSIONS)}. Got '{video_ext}'.",
        )

    # Validate optional transcript extension
    if transcript and transcript.filename:
        tr_ext = Path(transcript.filename).suffix.lower()
        if tr_ext not in ALLOWED_TRANSCRIPT_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Transcript must be one of {sorted(ALLOWED_TRANSCRIPT_EXTENSIONS)}. Got '{tr_ext}'.",
            )

    # Validate optional PDF extension
    if slides_pdf and slides_pdf.filename:
        pdf_ext = Path(slides_pdf.filename).suffix.lower()
        if pdf_ext not in ALLOWED_SLIDES_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Slides must be a PDF. Got '{pdf_ext}'.",
            )

    stem = sanitize_filename(video.filename or "upload")
    effective_title = (title or "").strip() or stem.replace("_", " ").title()

    # Persist to uploads dir
    os.makedirs(DEMO_UPLOADS_DIR, exist_ok=True)
    video_dest = os.path.join(DEMO_UPLOADS_DIR, f"{stem}{video_ext}")

    # Read video and enforce size limit
    video_bytes = await video.read()
    if len(video_bytes) > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Video exceeds maximum allowed size of {MAX_VIDEO_BYTES // 1024 // 1024} MB.",
        )
    with open(video_dest, "wb") as f:
        f.write(video_bytes)

    transcript_path: Optional[str] = None
    slides_pdf_path: Optional[str] = None

    if transcript and transcript.filename:
        tr_ext = Path(transcript.filename).suffix.lower()
        transcript_dest = os.path.join(DEMO_UPLOADS_DIR, f"{stem}_transcript{tr_ext}")
        transcript_bytes = await transcript.read()
        with open(transcript_dest, "wb") as f:
            f.write(transcript_bytes)
        transcript_path = transcript_dest

    if slides_pdf and slides_pdf.filename:
        pdf_dest = os.path.join(DEMO_UPLOADS_DIR, f"{stem}_slides.pdf")
        pdf_bytes = await slides_pdf.read()
        with open(pdf_dest, "wb") as f:
            f.write(pdf_bytes)
        slides_pdf_path = pdf_dest

    try:
        report = ingest_uploaded_video(
            video_path=video_dest,
            title=effective_title,
            transcript_path=transcript_path,
            slides_pdf_path=slides_pdf_path,
            uploads_dir=DEMO_UPLOADS_DIR,
            demo_corpus_db=DEMO_CORPUS_DB,
        )
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


@app.get("/api/uploads")
def api_list_uploads() -> Dict[str, Any]:
    """List all ingested demo videos with chunk counts."""
    try:
        store = DemoCorpusStore(db_path=DEMO_CORPUS_DB)
        sources = store.list_sources()
        return {"sources": sources, "count": len(sources), "demo_corpus_db": DEMO_CORPUS_DB}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/uploads")
def api_clear_uploads() -> Dict[str, Any]:
    """Clear all ingested demo data (chunks + sources from demo_corpus.db
    and all files under data/demo_uploads/). Production databases are untouched.
    """
    try:
        if os.path.exists(DEMO_CORPUS_DB):
            store = DemoCorpusStore(db_path=DEMO_CORPUS_DB)
            store.clear_all()

        if os.path.isdir(DEMO_UPLOADS_DIR):
            shutil.rmtree(DEMO_UPLOADS_DIR)
            os.makedirs(DEMO_UPLOADS_DIR, exist_ok=True)

        return {"cleared": True, "demo_corpus_db": DEMO_CORPUS_DB, "uploads_dir": DEMO_UPLOADS_DIR}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/demo/query")
def api_demo_corpus_query(req: DemoQueryRequest) -> Dict[str, Any]:
    """Offline BM25 query over the demo corpus for RAG inspection.

    Returns ranked chunks with retrieval scores, timestamps, and full text
    so users can verify BM25 retrieval quality without any API key.
    """
    effective_db = req.demo_corpus_db or DEMO_CORPUS_DB
    try:
        return run_demo_corpus_query(
            query=req.query,
            top_k=req.top_k,
            source_id=req.source_id or None,
            demo_corpus_db=effective_db,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ----------------------------------------------------------------------
# Frontend HTML/CSS/JS Single-Page Application (XSS-Hardened)
# ----------------------------------------------------------------------

_HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DAT Tutor — M8 Interactive Demo</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --primary-hover: #0284c7;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --code-bg: #0b1120;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 0;
    }
    header {
      background: #1e293b;
      border-bottom: 1px solid var(--card-border);
      padding: 16px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    header h1 {
      font-size: 1.25rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .badge {
      font-size: 0.75rem;
      padding: 4px 10px;
      border-radius: 9999px;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .badge-live { background: rgba(16, 185, 129, 0.2); color: var(--success); border: 1px solid var(--success); }
    .badge-mock { background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid var(--warning); }
    .badge-audio { background: rgba(56, 189, 248, 0.15); color: var(--primary); border: 1px solid #0284c7; }
    .badge-visual { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid #9333ea; }
    .container {
      display: grid;
      grid-template-columns: 320px 1fr;
      min-height: calc(100vh - 65px);
    }
    aside {
      background: #131d31;
      border-right: 1px solid var(--card-border);
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    aside h2 {
      font-size: 0.9rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-bottom: 12px;
    }
    label {
      font-size: 0.825rem;
      font-weight: 600;
      color: var(--text-muted);
    }
    input, select, textarea {
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 0.875rem;
      font-family: inherit;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--primary);
    }
    .toggle-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 4px 0;
    }
    .toggle-row span {
      font-size: 0.85rem;
    }
    main {
      padding: 24px 32px;
      display: flex;
      flex-direction: column;
      gap: 24px;
      overflow-y: auto;
    }
    .tabs {
      display: flex;
      gap: 12px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 12px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 0.95rem;
      font-weight: 600;
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .tab-btn.active {
      background: var(--primary);
      color: #0b1120;
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 20px;
    }
    .card h3 {
      font-size: 1.1rem;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .btn {
      background: var(--primary);
      color: #0b1120;
      border: none;
      padding: 10px 18px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.875rem;
    }
    .btn:hover { background: var(--primary-hover); }
    .btn-secondary {
      background: #334155;
      color: var(--text);
    }
    .btn-secondary:hover { background: #475569; }
    .btn-danger {
      background: rgba(239, 68, 68, 0.2);
      color: var(--danger);
      border: 1px solid var(--danger);
    }
    .btn-danger:hover { background: rgba(239, 68, 68, 0.3); }
    .chip-container {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0;
    }
    .chip {
      background: #1e293b;
      border: 1px solid var(--card-border);
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 0.75rem;
      cursor: pointer;
      color: var(--text-muted);
    }
    .chip:hover { border-color: var(--primary); color: var(--primary); }
    .answer-box {
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 16px;
      font-size: 0.95rem;
      white-space: pre-wrap;
      line-height: 1.6;
      margin: 12px 0;
    }
    .evidence-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 16px;
      margin-top: 16px;
    }
    .evidence-card {
      background: #151e2e;
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .evidence-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .evidence-img-container {
      background: #000;
      border: 1px solid var(--card-border);
      border-radius: 4px;
      overflow: hidden;
      max-height: 220px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .evidence-img-container img {
      width: 100%;
      height: auto;
      object-fit: contain;
    }
    .img-placeholder {
      padding: 30px 10px;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.8rem;
    }
    .table-container {
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }
    th, td {
      border: 1px solid var(--card-border);
      padding: 8px 12px;
      text-align: left;
    }
    th { background: #151e2e; color: var(--text-muted); }
    .pedagogical-banner {
      background: rgba(245, 158, 11, 0.1);
      border: 1px solid var(--warning);
      border-radius: 6px;
      padding: 12px 16px;
      margin-bottom: 16px;
      font-size: 0.825rem;
      color: #fbbf24;
    }
    .context-preview {
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 14px;
      font-family: monospace;
      font-size: 0.8rem;
      white-space: pre-wrap;
      color: #38bdf8;
      max-height: 240px;
      overflow-y: auto;
    }
  </style>
</head>
<body>
  <header>
    <h1>🎓 DAT Tutor — M8 Interactive Demo</h1>
    <div id="backend-badge" class="badge badge-mock" title="Backend Status">Checking Backend...</div>
  </header>

  <div class="container">
    <aside>
      <div>
        <h2>System Controls</h2>
        <div class="form-group">
          <label>Top K Chunks: <span id="top-k-val">5</span></label>
          <input type="range" id="top-k-slider" min="1" max="10" value="5" oninput="document.getElementById('top-k-val').textContent = this.value">
        </div>
        <div class="toggle-row">
          <span>Reranker (M8)</span>
          <input type="checkbox" id="rerank-toggle">
        </div>
        <div class="toggle-row">
          <span>Require Visual</span>
          <input type="checkbox" id="require-vis-toggle">
        </div>
        <div class="toggle-row">
          <span>Use Cache</span>
          <input type="checkbox" id="use-cache-toggle" checked>
        </div>
      </div>

      <div>
        <h2>Learner Personalization</h2>
        <div class="form-group">
          <label>Active Learner ID</label>
          <input type="text" id="sidebar-learner-id" placeholder="e.g. learner_alice" value="learner_alice">
        </div>
        <div class="form-group">
          <label>Memory DB Path</label>
          <input type="text" id="sidebar-memory-db" value="data/demo_learner_memory.db">
          <small style="color:var(--text-muted); font-size:0.75rem;">Isolated demo database path (in data/)</small>
        </div>
      </div>

      <div>
        <h2>Corpus Selector</h2>
        <div class="form-group">
          <label>Query Corpus</label>
          <select id="corpus-selector">
            <option value="preloaded">📚 Pre-loaded CS50 Corpus</option>
            <option value="demo">📤 Uploaded Videos (Offline RAG)</option>
          </select>
        </div>
        <div id="demo-source-filter-group" class="form-group" style="display:none;">
          <label>Filter by Video</label>
          <select id="demo-source-filter">
            <option value="">All uploaded videos</option>
          </select>
        </div>
      </div>

      <div style="margin-top:auto; font-size:0.75rem; color:var(--text-muted);">
        DAT Tutor M1-M8 Architecture &middot; Offline Safe
      </div>
    </aside>

    <main>
      <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('query-tab', this)">🔍 Tutor Query &amp; Evidence</button>
        <button class="tab-btn" onclick="switchTab('upload-tab', this)">📤 Upload Video</button>
        <button class="tab-btn" onclick="switchTab('memory-tab', this)">🧠 Learner Memory Inspector</button>
      </div>

      <!-- TAB: UPLOAD VIDEO -->
      <div id="upload-tab" class="tab-content">
        <div class="card">
          <h3>📤 Upload Video for Offline RAG Ingestion</h3>
          <p style="font-size:0.875rem; color:var(--text-muted); margin-bottom:16px;">
            Upload a lecture video (MP4/WebM/MOV/MKV) with an optional transcript (.vtt/.srt/.txt) or slides (.pdf).
            Chunks are stored in <code>data/demo_corpus.db</code> — never in the production CS50 corpus.
            Works 100% offline (no API keys needed).
          </p>
          <form id="upload-form" onsubmit="submitUpload(event)">
            <div class="form-group">
              <label>Video File (.mp4 / .webm / .mov / .mkv, max 250 MB)</label>
              <input type="file" id="video-file" accept=".mp4,.webm,.mov,.mkv" required style="color:var(--text);">
            </div>
            <div class="form-group">
              <label>Transcript (optional: .vtt / .srt / .txt for speech search)</label>
              <input type="file" id="transcript-file" accept=".vtt,.srt,.txt" style="color:var(--text);">
            </div>
            <div class="form-group">
              <label>Slides PDF (optional, requires PyMuPDF)</label>
              <input type="file" id="slides-file" accept=".pdf" style="color:var(--text);">
            </div>
            <div class="form-group">
              <label>Title (optional — defaults to filename)</label>
              <input type="text" id="upload-title" placeholder="e.g. My Lecture on Pointers">
            </div>
            <button type="submit" class="btn" id="upload-btn">⬆️ Upload &amp; Ingest</button>
          </form>
          <div id="upload-progress" style="display:none; margin-top:16px; color:var(--warning);">
            ⏳ Uploading and ingesting... (keyframe extraction may take a moment)
          </div>
          <div id="upload-result" style="display:none; margin-top:16px;"></div>
        </div>

        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <h3>Ingested Demo Videos</h3>
            <div style="display:flex; gap:8px;">
              <button class="btn btn-secondary" onclick="loadUploadedVideos()">🔄 Refresh</button>
              <button class="btn btn-danger" onclick="clearDemoCorpus()">🗑️ Clear All</button>
            </div>
          </div>
          <div id="uploads-list"><p style="color:var(--text-muted);">Loading...</p></div>
        </div>

        <div class="card">
          <h3>🔎 Offline RAG Inspector — Query Uploaded Video</h3>
          <p style="font-size:0.875rem; color:var(--text-muted); margin-bottom:12px;">
            Run an offline BM25 retrieval query over your uploaded video corpus. No API key needed.
            Inspect retrieval scores, ranks, timestamps, and full text to verify RAG quality.
          </p>
          <div id="video-player-container" style="display:none; margin-bottom:16px;">
            <video id="demo-video-player" controls style="width:100%; border-radius:6px; background:#000; border:1px solid var(--card-border);">
              Your browser does not support HTML5 video.
            </video>
            <p id="video-player-label" style="font-size:0.8rem; color:var(--text-muted); margin-top:6px;"></p>
          </div>
          <div class="form-group">
            <label>Query</label>
            <textarea id="rag-query-input" rows="2" placeholder="e.g. What is explained about memory allocation?"></textarea>
          </div>
          <div class="form-group">
            <label>Filter by source (optional)</label>
            <input type="text" id="rag-source-filter" placeholder="e.g. demo-my_lecture">
          </div>
          <div class="form-group">
            <label>Top K: <span id="rag-top-k-val">5</span></label>
            <input type="range" id="rag-top-k-slider" min="1" max="20" value="5" oninput="document.getElementById('rag-top-k-val').textContent = this.value">
          </div>
          <button class="btn" onclick="submitRagQuery()">🔍 Inspect Retrieval</button>
          <div id="rag-result-container" style="margin-top:20px; display:none;"></div>
        </div>
      </div>

      <!-- TAB 1: QUERY & EVIDENCE -->
      <div id="query-tab" class="tab-content active">
        <div class="card">
          <h3>Ask the Tutor</h3>
          <div class="form-group">
            <textarea id="query-input" rows="3" placeholder="Ask a question about CS50 course material..."></textarea>
          </div>
          <div class="chip-container">
            <span style="font-size:0.75rem; color:var(--text-muted); align-self:center;">Try:</span>
            <div class="chip" onclick="setQuery('What is printf in C and how is it used?')">printf in C (Text/Audio)</div>
            <div class="chip" onclick="setQuery('Where is the compiler positioned in the block diagram?'); document.getElementById('require-vis-toggle').checked = true;">Compiler diagram (Visual Required)</div>
            <div class="chip" onclick="setQuery('Explain how scratch sprites interact with motion blocks')">Scratch sprites (Multimodal)</div>
            <div class="chip" onclick="setQuery('What does CS50 teach about quantum cryptography circuits?')">Quantum Cryptography (Abstain Test)</div>
          </div>
          <button class="btn" id="ask-btn" onclick="submitQuery()">🚀 Ask Tutor</button>
        </div>

        <div id="result-section" style="display:none;">
          <div class="card">
            <h3>
              <span>Tutor Answer</span>
              <span id="answer-status-badge" class="badge">Answered</span>
            </h3>
            <div id="pedagogical-alert" class="pedagogical-banner" style="display:none;">
              👤 <strong>Pedagogical Context Applied:</strong> Tutor styled its explanation depth and tone for active learner profile (Never cited as evidence).
            </div>
            <div id="answer-text" class="answer-box"></div>
          </div>

          <div class="card">
            <h3>Retrieved Evidence Citations (<span id="citation-count">0</span>)</h3>
            <div id="evidence-container" class="evidence-grid"></div>
          </div>
        </div>
      </div>

      <!-- TAB 2: MEMORY INSPECTOR -->
      <div id="memory-tab" class="tab-content">
        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3>Learner Profile & Pedagogical Context</h3>
            <button class="btn btn-secondary" onclick="loadMemoryData()">🔄 Refresh</button>
          </div>
          <div class="pedagogical-banner">
            ⚠️ <strong>Pedagogical Styling Only — Never Cited as Course Evidence.</strong><br>
            This context is injected strictly outside <code>&lt;untrusted_evidence_data&gt;</code> to tune tone and depth.
          </div>
          <div id="pedagogical-preview" class="context-preview">No pedagogical profile loaded.</div>
        </div>

        <div class="card">
          <h3>Active Memory Entries</h3>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Topic</th>
                  <th>Content</th>
                  <th>Conf</th>
                  <th>Revs</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody id="memory-table-body">
                <tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No memories found. Add one below!</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
          <!-- ADD MEMORY -->
          <div class="card">
            <h3>Add New Memory</h3>
            <div class="form-group">
              <label>Memory Type</label>
              <select id="new-mem-type">
                <option value="learning_goal">Goal (Learning objective)</option>
                <option value="struggled_concept">Struggled Concept (Difficult concept)</option>
                <option value="learning_preference">Preference (Explanation style)</option>
                <option value="misconception">Misconception</option>
                <option value="student_correction">Correction</option>
              </select>
            </div>
            <div class="form-group">
              <label>Topic</label>
              <input type="text" id="new-mem-topic" placeholder="e.g. pointers, recursion">
            </div>
            <div class="form-group">
              <label>Content</label>
              <textarea id="new-mem-content" rows="2" placeholder="e.g. Needs real-world analogies for memory addresses"></textarea>
            </div>
            <div class="form-group">
              <label>Confidence: <span id="conf-val">1.0</span></label>
              <input type="range" id="new-mem-conf" min="0.1" max="1.0" step="0.1" value="1.0" oninput="document.getElementById('conf-val').textContent = this.value">
            </div>
            <button class="btn" onclick="submitAddMemory()">➕ Add Memory</button>
          </div>

          <!-- CORRECT MEMORY -->
          <div class="card">
            <h3>Correct Memory Item</h3>
            <div class="form-group">
              <label>Memory ID</label>
              <input type="text" id="correct-mem-id" placeholder="Select 'Correct' from table or enter ID">
            </div>
            <div class="form-group">
              <label>New Content</label>
              <textarea id="correct-mem-content" rows="2" placeholder="Updated memory description..."></textarea>
            </div>
            <div class="form-group">
              <label>Reason for Correction</label>
              <input type="text" id="correct-mem-reason" value="Learner correction via demo UI">
            </div>
            <button class="btn btn-secondary" onclick="submitCorrectMemory()">✏️ Submit Correction</button>
          </div>
        </div>

        <div class="card" style="border-color: rgba(239,68,68,0.4);">
          <h3 style="color:var(--danger)">Privacy & GDPR Purge</h3>
          <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:12px;">
            Permanently remove all profile, memories, and mastery states for the active learner from the demo database.
          </p>
          <button class="btn btn-danger" onclick="submitPurgeLearner()">🗑️ Purge All Learner Memories</button>
        </div>
      </div>
    </main>
  </div>

  <script>
    async function init() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        const badge = document.getElementById('backend-badge');
        if (data.is_live) {
          badge.className = 'badge badge-live';
          badge.textContent = '🟢 Live Mode (' + (data.has_openai ? 'OpenAI' : '') + (data.has_gemini ? ' Gemini' : '') + ')';
        } else {
          badge.className = 'badge badge-mock';
          badge.textContent = '🟠 Mock / Offline Mode';
        }
        badge.title = data.status_description || '';
      } catch (err) {
        console.error('Status check failed:', err);
      }
    }

    function switchTab(tabId, btn) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      btn.classList.add('active');
      if (tabId === 'memory-tab') {
        loadMemoryData();
      } else if (tabId === 'upload-tab') {
        loadUploadedVideos();
      }
    }

    function setQuery(text) {
      document.getElementById('query-input').value = text;
    }

    async function submitQuery() {
      const query = document.getElementById('query-input').value.trim();
      if (!query) return;

      const askBtn = document.getElementById('ask-btn');
      askBtn.disabled = true;
      askBtn.textContent = '⏳ Retrieving & Generating...';

      const payload = {
        query: query,
        top_k: parseInt(document.getElementById('top-k-slider').value, 10),
        rerank: document.getElementById('rerank-toggle').checked,
        require_visual: document.getElementById('require-vis-toggle').checked,
        use_cache: document.getElementById('use-cache-toggle').checked,
        learner_id: document.getElementById('sidebar-learner-id').value.trim() || null,
        memory_db_path: document.getElementById('sidebar-memory-db').value.trim() || null
      };

      try {
        const res = await fetch('/api/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(errData.detail || 'Query failed');
        }
        const data = await res.json();

        document.getElementById('result-section').style.display = 'block';
        document.getElementById('answer-text').textContent = data.answer;

        const badge = document.getElementById('answer-status-badge');
        if (data.is_abstained) {
          badge.className = 'badge badge-mock';
          badge.textContent = 'Abstained';
        } else if (data.is_qualified) {
          badge.className = 'badge badge-mock';
          badge.textContent = 'Qualified';
        } else {
          badge.className = 'badge badge-live';
          badge.textContent = 'Answered';
        }

        const alertEl = document.getElementById('pedagogical-alert');
        alertEl.style.display = data.pedagogical_context_used ? 'block' : 'none';

        document.getElementById('citation-count').textContent = String(data.citation_count || 0);
        renderEvidence(data.citations);
      } catch (err) {
        alert('Query failed: ' + err.message);
      } finally {
        askBtn.disabled = false;
        askBtn.textContent = '🚀 Ask Tutor';
      }
    }

    // XSS-Safe DOM construction for evidence cards
    function renderEvidence(citations) {
      const container = document.getElementById('evidence-container');
      container.replaceChildren();

      if (!citations || citations.length === 0) {
        const emptyDiv = document.createElement('div');
        emptyDiv.style.cssText = 'color:var(--text-muted); font-size:0.85rem;';
        emptyDiv.textContent = 'No citations referenced.';
        container.appendChild(emptyDiv);
        return;
      }

      citations.forEach(c => {
        const card = document.createElement('div');
        card.className = 'evidence-card';

        const header = document.createElement('div');
        header.className = 'evidence-header';

        const strongLabel = document.createElement('strong');
        strongLabel.textContent = c.citation_label || '';
        header.appendChild(strongLabel);

        const isVisual = c.modality === 'visual';
        const modBadge = document.createElement('span');
        modBadge.className = isVisual ? 'badge badge-visual' : 'badge badge-audio';
        modBadge.textContent = isVisual ? '🖼️ Visual' : '🎧 Audio';
        header.appendChild(modBadge);

        const metaDiv = document.createElement('div');
        metaDiv.style.cssText = 'font-size:0.8rem; color:var(--text-muted);';
        const codeSource = document.createElement('code');
        codeSource.textContent = c.source_id || '';
        metaDiv.append('Source: ', codeSource, ' · ' + (c.time_bounds_str || ''));

        card.appendChild(header);
        card.appendChild(metaDiv);

        if (isVisual) {
          const imgContainer = document.createElement('div');
          imgContainer.className = 'evidence-img-container';
          if (c.image_path) {
            const img = document.createElement('img');
            img.src = '/media?path=' + encodeURIComponent(c.image_path);
            img.alt = 'Slide Image';
            img.onerror = () => {
              imgContainer.replaceChildren();
              const ph = document.createElement('div');
              ph.className = 'img-placeholder';
              ph.textContent = '⚠️ Image not found on disk: ' + c.image_path;
              imgContainer.appendChild(ph);
            };
            imgContainer.appendChild(img);
          } else {
            const ph = document.createElement('div');
            ph.className = 'img-placeholder';
            ph.textContent = 'No image path specified';
            imgContainer.appendChild(ph);
          }
          card.appendChild(imgContainer);
        }

        const textDiv = document.createElement('div');
        textDiv.style.cssText = 'font-size:0.85rem; color:#cbd5e1; max-height:100px; overflow-y:auto; line-height:1.4;';
        textDiv.textContent = c.text || '(No transcript text)';
        card.appendChild(textDiv);

        if (c.jump_url) {
          const link = document.createElement('a');
          link.href = c.jump_url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.style.cssText = 'color:var(--primary); font-size:0.8rem; text-decoration:none; font-weight:600;';
          link.textContent = '▶️ Jump to Source (' + (c.time_bounds_str || '') + ')';
          card.appendChild(link);
        }

        container.appendChild(card);
      });
    }

    async function loadMemoryData() {
      const learnerId = document.getElementById('sidebar-learner-id').value.trim();
      const dbPath = document.getElementById('sidebar-memory-db').value.trim();
      if (!learnerId) return;

      try {
        const res = await fetch(`/api/memory?learner_id=${encodeURIComponent(learnerId)}&db_path=${encodeURIComponent(dbPath)}`);
        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(errData.detail || 'Failed to load memory');
        }
        const data = await res.json();

        const preview = document.getElementById('pedagogical-preview');
        preview.textContent = data.pedagogical_context || '(No pedagogical profile active for this learner)';

        const tbody = document.getElementById('memory-table-body');
        tbody.replaceChildren();

        if (!data.memories || data.memories.length === 0) {
          const emptyTr = document.createElement('tr');
          const emptyTd = document.createElement('td');
          emptyTd.colSpan = 7;
          emptyTd.style.cssText = 'text-align:center; color:var(--text-muted);';
          emptyTd.textContent = 'No memories found.';
          emptyTr.appendChild(emptyTd);
          tbody.appendChild(emptyTr);
          return;
        }

        // XSS-Safe table row generation
        data.memories.forEach(m => {
          const tr = document.createElement('tr');

          const tdId = document.createElement('td');
          const codeId = document.createElement('code');
          codeId.textContent = (m.memory_id || '').substring(0, 10) + '...';
          tdId.appendChild(codeId);

          const tdType = document.createElement('td');
          const badgeType = document.createElement('span');
          badgeType.className = 'badge badge-audio';
          badgeType.textContent = m.memory_type_str || '';
          tdType.appendChild(badgeType);

          const tdTopic = document.createElement('td');
          const strongTopic = document.createElement('strong');
          strongTopic.textContent = m.topic || '';
          tdTopic.appendChild(strongTopic);

          const tdContent = document.createElement('td');
          tdContent.textContent = m.content || '';

          const tdConf = document.createElement('td');
          tdConf.textContent = Number(m.confidence || 0).toFixed(2);

          const tdRevs = document.createElement('td');
          tdRevs.textContent = String(m.revision_count || 0);

          const tdActions = document.createElement('td');
          const btnCorrect = document.createElement('button');
          btnCorrect.className = 'btn btn-secondary';
          btnCorrect.style.cssText = 'padding:4px 8px; font-size:0.75rem;';
          btnCorrect.textContent = 'Correct';
          btnCorrect.onclick = () => prefillCorrect(m.memory_id, m.content);

          const btnDel = document.createElement('button');
          btnDel.className = 'btn btn-danger';
          btnDel.style.cssText = 'padding:4px 8px; font-size:0.75rem;';
          btnDel.textContent = 'Del';
          btnDel.onclick = () => deleteMemory(m.memory_id);

          tdActions.append(btnCorrect, document.createTextNode(' '), btnDel);
          tr.append(tdId, tdType, tdTopic, tdContent, tdConf, tdRevs, tdActions);
          tbody.appendChild(tr);
        });
      } catch (err) {
        console.error('Failed to load memory:', err);
      }
    }

    function prefillCorrect(id, content) {
      document.getElementById('correct-mem-id').value = id || '';
      document.getElementById('correct-mem-content').value = content || '';
    }

    async function submitAddMemory() {
      const learnerId = document.getElementById('sidebar-learner-id').value.trim();
      const dbPath = document.getElementById('sidebar-memory-db').value.trim();
      const type = document.getElementById('new-mem-type').value;
      const topic = document.getElementById('new-mem-topic').value.trim();
      const content = document.getElementById('new-mem-content').value.trim();
      const confidence = parseFloat(document.getElementById('new-mem-conf').value);

      if (!topic || !content) {
        alert('Please fill out both topic and content.');
        return;
      }

      try {
        const res = await fetch('/api/memory/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            learner_id: learnerId,
            memory_type: type,
            topic: topic,
            content: content,
            confidence: confidence,
            memory_db_path: dbPath
          })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(errData.detail || 'Add memory failed');
        }
        document.getElementById('new-mem-topic').value = '';
        document.getElementById('new-mem-content').value = '';
        loadMemoryData();
      } catch (err) {
        alert('Add memory failed: ' + err.message);
      }
    }

    async function submitCorrectMemory() {
      const dbPath = document.getElementById('sidebar-memory-db').value.trim();
      const id = document.getElementById('correct-mem-id').value.trim();
      const content = document.getElementById('correct-mem-content').value.trim();
      const reason = document.getElementById('correct-mem-reason').value.trim();

      if (!id || !content) {
        alert('Please enter a memory ID and updated content.');
        return;
      }

      try {
        const res = await fetch('/api/memory/correct', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            memory_id: id,
            new_content: content,
            reason: reason,
            memory_db_path: dbPath
          })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(errData.detail || 'Correction failed');
        }
        document.getElementById('correct-mem-id').value = '';
        document.getElementById('correct-mem-content').value = '';
        loadMemoryData();
      } catch (err) {
        alert('Correction failed: ' + err.message);
      }
    }

    async function deleteMemory(memoryId) {
      if (!confirm('Soft delete memory item ' + memoryId + '?')) return;
      const learnerId = document.getElementById('sidebar-learner-id').value.trim();
      const dbPath = document.getElementById('sidebar-memory-db').value.trim();

      try {
        const res = await fetch('/api/memory/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            learner_id: learnerId,
            memory_id: memoryId,
            memory_db_path: dbPath
          })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(errData.detail || 'Delete failed');
        }
        loadMemoryData();
      } catch (err) {
        alert('Delete failed: ' + err.message);
      }
    }

    async function submitPurgeLearner() {
      const learnerId = document.getElementById('sidebar-learner-id').value.trim();
      const dbPath = document.getElementById('sidebar-memory-db').value.trim();
      if (!confirm('Are you sure you want to PERMANENTLY PURGE all memory records for learner "' + learnerId + '"?')) return;

      try {
        const res = await fetch('/api/memory/purge', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            learner_id: learnerId,
            memory_db_path: dbPath
          })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(errData.detail || 'Purge failed');
        }
        loadMemoryData();
      } catch (err) {
        alert('Purge failed: ' + err.message);
      }
    }

    // Upload tab & Demo RAG Player state & functions
    let currentDemoVideoPath = null;

    function playDemoVideo(path, title) {
      currentDemoVideoPath = path;
      const player = document.getElementById('demo-video-player');
      const container = document.getElementById('video-player-container');
      const label = document.getElementById('video-player-label');
      player.src = '/media/video?path=' + encodeURIComponent(path);
      label.textContent = 'Playing: ' + (title || path);
      container.style.display = 'block';
      player.load();
      player.play().catch(() => {});
    }

    function seekDemoVideo(startSec) {
      const player = document.getElementById('demo-video-player');
      const container = document.getElementById('video-player-container');
      if (!player.src && !currentDemoVideoPath) {
        alert('No video currently loaded in player.');
        return;
      }
      container.style.display = 'block';
      player.currentTime = startSec;
      player.play().catch(() => {});
      player.scrollIntoView({ behavior: 'smooth' });
    }

    async function submitUpload(event) {
      event.preventDefault();
      const videoFile = document.getElementById('video-file').files[0];
      if (!videoFile) return;
      const uploadBtn = document.getElementById('upload-btn');
      const progress = document.getElementById('upload-progress');
      const result = document.getElementById('upload-result');
      uploadBtn.disabled = true;
      progress.style.display = 'block';
      result.style.display = 'none';

      const fd = new FormData();
      fd.append('video', videoFile);
      const tr = document.getElementById('transcript-file').files[0];
      if (tr) fd.append('transcript', tr);
      const pdf = document.getElementById('slides-file').files[0];
      if (pdf) fd.append('slides_pdf', pdf);
      const title = document.getElementById('upload-title').value.trim();
      if (title) fd.append('title', title);

      try {
        const res = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();
        result.style.display = 'block';
        result.replaceChildren();
        if (!res.ok) {
          const errDiv = document.createElement('div');
          errDiv.style.color = 'var(--danger)';
          errDiv.textContent = '❌ Upload failed: ' + (data.detail || 'Unknown error');
          result.appendChild(errDiv);
        } else {
          const info = document.createElement('div');
          info.className = 'pedagogical-banner';
          const p = document.createElement('p');
          p.textContent = '✅ Ingested: ' + data.title + ' (' + data.audio_chunks + ' audio + ' + data.visual_chunks + ' visual chunks, total ' + data.total_chunks + ')';
          info.appendChild(p);
          if (data.video_path) {
            playDemoVideo(data.video_path, data.title);
          }
          if (data.warnings && data.warnings.length > 0) {
            data.warnings.forEach(w => {
              const wp = document.createElement('p');
              wp.textContent = '⚠️ ' + w;
              info.appendChild(wp);
            });
          }
          result.appendChild(info);
          loadUploadedVideos();
        }
      } catch (err) {
        result.style.display = 'block';
        result.textContent = '❌ ' + err.message;
      } finally {
        uploadBtn.disabled = false;
        progress.style.display = 'none';
      }
    }

    async function loadUploadedVideos() {
      const list = document.getElementById('uploads-list');
      if (!list) return;
      try {
        const res = await fetch('/api/uploads');
        const data = await res.json();
        list.replaceChildren();
        if (!data.sources || data.sources.length === 0) {
          const p = document.createElement('p');
          p.style.color = 'var(--text-muted)';
          p.textContent = 'No videos ingested yet. Upload one above.';
          list.appendChild(p);
          return;
        }
        data.sources.forEach(s => {
          const row = document.createElement('div');
          row.style.cssText = 'padding:12px; border:1px solid var(--card-border); border-radius:6px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;';
          const info = document.createElement('div');
          const title = document.createElement('strong');
          title.textContent = s.title;
          const meta = document.createElement('div');
          meta.style.cssText = 'font-size:0.8rem; color:var(--text-muted); margin-top:4px;';
          const codeId = document.createElement('code');
          codeId.textContent = s.source_id;
          meta.append(codeId, ' — ' + (s.audio_chunks || 0) + ' audio + ' + (s.visual_chunks || 0) + ' visual chunks (total ' + (s.chunk_count || 0) + ')');
          info.append(title, meta);
          row.appendChild(info);
          list.appendChild(row);
        });
      } catch (err) {
        list.textContent = 'Error loading uploads: ' + err.message;
      }
    }

    async function clearDemoCorpus() {
      if (!confirm('Clear all ingested demo videos and their chunks?')) return;
      try {
        await fetch('/api/uploads', { method: 'DELETE' });
        loadUploadedVideos();
        document.getElementById('rag-result-container').style.display = 'none';
        document.getElementById('video-player-container').style.display = 'none';
        currentDemoVideoPath = null;
      } catch (err) {
        alert('Clear failed: ' + err.message);
      }
    }

    async function submitRagQuery() {
      const query = document.getElementById('rag-query-input').value.trim();
      if (!query) return;
      const sourceFilter = document.getElementById('rag-source-filter').value.trim();
      const topK = parseInt(document.getElementById('rag-top-k-slider').value, 10) || 5;
      const container = document.getElementById('rag-result-container');
      container.style.display = 'block';
      container.replaceChildren();
      const loading = document.createElement('p');
      loading.style.color = 'var(--warning)';
      loading.textContent = '⏳ Running offline BM25 retrieval...';
      container.appendChild(loading);
      try {
        const res = await fetch('/api/demo/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: query, top_k: topK, source_id: sourceFilter || null })
        });
        const data = await res.json();
        container.replaceChildren();
        const header = document.createElement('div');
        header.style.cssText = 'margin-bottom:12px; font-size:0.85rem; color:var(--text-muted);';
        header.textContent = 'Retrieved ' + data.total_retrieved + ' chunks from ' + data.chunk_count + ' total chunks in demo corpus.';
        container.appendChild(header);
        if (!data.results || data.results.length === 0) {
          const empty = document.createElement('p');
          empty.style.color = 'var(--text-muted)';
          empty.textContent = 'No chunks matched. Try uploading a video with a transcript first.';
          container.appendChild(empty);
          return;
        }
        data.results.forEach(r => {
          const card = document.createElement('div');
          card.className = 'evidence-card';
          card.style.marginBottom = '12px';
          const hd = document.createElement('div');
          hd.className = 'evidence-header';
          const rankSpan = document.createElement('strong');
          rankSpan.textContent = '#' + r.rank + ' — ' + r.time_bounds_str;
          const scoreBadge = document.createElement('span');
          scoreBadge.className = 'badge badge-' + (r.modality === 'visual' ? 'visual' : 'audio');
          scoreBadge.textContent = (r.modality === 'visual' ? '🖼️' : '🎧') + ' Score: ' + r.score.toFixed(4);
          hd.append(rankSpan, scoreBadge);
          const sourceDiv = document.createElement('div');
          sourceDiv.style.cssText = 'font-size:0.8rem; color:var(--text-muted);';
          const codeSource = document.createElement('code');
          codeSource.textContent = r.source_id;
          sourceDiv.append('Source: ', codeSource, ' · Chunk: ' + (r.chunk_id || '').substring(0, 12) + '...');
          const textDiv = document.createElement('div');
          textDiv.style.cssText = 'font-size:0.875rem; color:#cbd5e1; white-space:pre-wrap; max-height:120px; overflow-y:auto; line-height:1.5;';
          textDiv.textContent = r.text || '(No text — visual keyframe only)';
          card.append(hd, sourceDiv, textDiv);
          if (r.start_sec !== null && r.start_sec !== undefined) {
            const seekBtn = document.createElement('button');
            seekBtn.className = 'btn btn-secondary';
            seekBtn.style.cssText = 'padding:4px 10px; font-size:0.8rem; margin-top:6px;';
            seekBtn.textContent = '▶️ Seek to ' + r.time_bounds_str;
            seekBtn.onclick = () => seekDemoVideo(r.start_sec);
            card.appendChild(seekBtn);
          }
          container.appendChild(card);
        });
      } catch (err) {
        container.textContent = 'RAG query failed: ' + err.message;
      }
    }

    // Initialize on page load
    window.onload = init;
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Render the primary interactive single-page application."""
    return HTMLResponse(content=_HTML_PAGE)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("demo.app:app", host="0.0.0.0", port=8000, reload=False)
