"""DAT Tutor M8 Interactive Demo Application (FastAPI).

Provides a local interactive web interface for:
1. Grounded multimodal tutor query answering with live / mock status.
2. Synchronized evidence viewer for audio/video (timestamp bounds, jump URLs)
   and visual slide keyframes.
3. Live learner memory inspector with isolated storage, live preview of
   pedagogical styling, and full CRUD controls (Add, Correct, Delete, Purge).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from demo.helpers import (
    DEFAULT_DEMO_MEMORY_DB,
    add_learner_memory_item,
    correct_learner_memory_item,
    delete_learner_memory_item,
    detect_backend_status,
    get_learner_memory_data,
    purge_learner_memory_items,
    run_tutor_query,
    validate_media_path,
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
    """Return backend runtime mode and API availability."""
    return detect_backend_status()


@app.post("/api/query")
def api_query(req: QueryRequest) -> Dict[str, Any]:
    """Execute tutor query with grounded retrieval and optional pedagogical styling."""
    try:
        result = run_tutor_query(
            query=req.query,
            top_k=req.top_k,
            rerank=req.rerank,
            require_visual=req.require_visual,
            use_cache=req.use_cache,
            learner_id=req.learner_id.strip() if req.learner_id else None,
            memory_db_path=req.memory_db_path.strip() if req.memory_db_path else None,
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
        return get_learner_memory_data(learner_id=learner_id, db_path=db_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/memory/add")
def api_add_memory(req: AddMemoryRequest) -> Dict[str, Any]:
    """Add a new learner memory item."""
    try:
        return add_learner_memory_item(
            learner_id=req.learner_id,
            memory_type=req.memory_type,
            topic=req.topic,
            content=req.content,
            confidence=req.confidence,
            db_path=req.memory_db_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/memory/correct")
def api_correct_memory(req: CorrectMemoryRequest) -> Dict[str, Any]:
    """Correct an existing learner memory item."""
    try:
        res = correct_learner_memory_item(
            memory_id=req.memory_id,
            new_content=req.new_content,
            reason=req.reason,
            db_path=req.memory_db_path,
        )
        if not res:
            raise HTTPException(status_code=404, detail=f"Memory item {req.memory_id} not found.")
        return res
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/memory/delete")
def api_delete_memory(req: DeleteMemoryRequest) -> Dict[str, Any]:
    """Soft delete an individual learner memory."""
    try:
        success = delete_learner_memory_item(
            learner_id=req.learner_id,
            memory_id=req.memory_id,
            db_path=req.memory_db_path,
        )
        return {"success": success, "memory_id": req.memory_id}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/memory/purge")
def api_purge_memory(req: PurgeLearnerRequest) -> Dict[str, Any]:
    """Purge all memories for a learner."""
    try:
        count = purge_learner_memory_items(
            learner_id=req.learner_id,
            db_path=req.memory_db_path,
        )
        return {"purged_count": count, "learner_id": req.learner_id}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/media")
def api_media(path: str = Query(..., min_length=1)):
    """Safely serve local image keyframe assets."""
    val = validate_media_path(path)
    if not val["valid"] or not val["exists"]:
        raise HTTPException(status_code=404, detail=val.get("error") or "Media file not found")

    resolved = val["resolved_path"]
    media_type = "image/jpeg"
    if resolved.lower().endswith(".png"):
        media_type = "image/png"
    return FileResponse(resolved, media_type=media_type)


# ----------------------------------------------------------------------
# Frontend HTML/CSS/JS Single-Page Application
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
    <div id="backend-badge" class="badge badge-mock">Checking Backend...</div>
  </header>

  <div class="container">
    <aside>
      <div>
        <h2>System Controls</h2>
        <div class="form-group">
          <label>Top K Chunks: <span id="top-k-val">5</span></label>
          <input type="range" id="top-k-slider" min="1" max="10" value="5" oninput="document.getElementById('top-k-val').innerText = this.value">
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
          <small style="color:var(--text-muted); font-size:0.75rem;">Isolated demo database path</small>
        </div>
      </div>

      <div style="margin-top:auto; font-size:0.75rem; color:var(--text-muted);">
        DAT Tutor M1-M8 Architecture &middot; Offline Safe
      </div>
    </aside>

    <main>
      <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('query-tab', this)">🔍 Tutor Query & Evidence</button>
        <button class="tab-btn" onclick="switchTab('memory-tab', this)">🧠 Learner Memory Inspector</button>
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
                <option value="goal">Goal (Learning objective)</option>
                <option value="struggle">Struggle (Difficult concept)</option>
                <option value="preference">Preference (Explanation style)</option>
                <option value="style">Style (Concise / Detailed)</option>
                <option value="background">Background (Prior experience)</option>
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
              <input type="range" id="new-mem-conf" min="0.1" max="1.0" step="0.1" value="1.0" oninput="document.getElementById('conf-val').innerText = this.value">
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
          badge.innerText = '🟢 Live Mode (' + (data.has_openai ? 'OpenAI' : '') + (data.has_gemini ? ' Gemini' : '') + ')';
        } else {
          badge.className = 'badge badge-mock';
          badge.innerText = '🟠 Mock / Offline Mode';
        }
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
      askBtn.innerText = '⏳ Retrieving & Generating...';

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
        const data = await res.json();

        document.getElementById('result-section').style.display = 'block';
        document.getElementById('answer-text').innerText = data.answer;

        const badge = document.getElementById('answer-status-badge');
        if (data.is_abstained) {
          badge.className = 'badge badge-mock';
          badge.innerText = 'Abstained';
        } else if (data.is_qualified) {
          badge.className = 'badge badge-mock';
          badge.innerText = 'Qualified';
        } else {
          badge.className = 'badge badge-live';
          badge.innerText = 'Answered';
        }

        const alert = document.getElementById('pedagogical-alert');
        alert.style.display = data.pedagogical_context_used ? 'block' : 'none';

        document.getElementById('citation-count').innerText = data.citation_count;
        renderEvidence(data.citations);
      } catch (err) {
        alert('Query failed: ' + err.message);
      } finally {
        askBtn.disabled = false;
        askBtn.innerText = '🚀 Ask Tutor';
      }
    }

    function renderEvidence(citations) {
      const container = document.getElementById('evidence-container');
      container.innerHTML = '';
      if (!citations || citations.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem;">No citations referenced.</div>';
        return;
      }

      citations.forEach(c => {
        const card = document.createElement('div');
        card.className = 'evidence-card';

        const isVisual = c.modality === 'visual';
        const modBadge = isVisual
          ? '<span class="badge badge-visual">🖼️ Visual</span>'
          : '<span class="badge badge-audio">🎧 Audio</span>';

        let mediaHtml = '';
        if (isVisual) {
          if (c.image_path) {
            mediaHtml = `
              <div class="evidence-img-container">
                <img src="/media?path=${encodeURIComponent(c.image_path)}"
                     alt="Slide Image"
                     onerror="this.parentElement.innerHTML='<div class=\\'img-placeholder\\'>⚠️ Image not found on disk: ${c.image_path}</div>'">
              </div>
            `;
          } else {
            mediaHtml = '<div class="img-placeholder">No image path specified</div>';
          }
        }

        let navHtml = '';
        if (c.jump_url) {
          navHtml = `
            <a href="${c.jump_url}" target="_blank" rel="noopener noreferrer" style="color:var(--primary); font-size:0.8rem; text-decoration:none; font-weight:600;">
              ▶️ Jump to Source (${c.time_bounds_str})
            </a>
          `;
        }

        card.innerHTML = `
          <div class="evidence-header">
            <strong>${c.citation_label}</strong>
            ${modBadge}
          </div>
          <div style="font-size:0.8rem; color:var(--text-muted);">
            Source: <code>${c.source_id}</code> &middot; ${c.time_bounds_str}
          </div>
          ${mediaHtml}
          <div style="font-size:0.85rem; color:#cbd5e1; max-height:100px; overflow-y:auto; line-height:1.4;">
            ${c.text || '<em style="color:var(--text-muted);">No transcript text</em>'}
          </div>
          ${navHtml}
        `;
        container.appendChild(card);
      });
    }

    async function loadMemoryData() {
      const learnerId = document.getElementById('sidebar-learner-id').value.trim();
      const dbPath = document.getElementById('sidebar-memory-db').value.trim();
      if (!learnerId) return;

      try {
        const res = await fetch(`/api/memory?learner_id=${encodeURIComponent(learnerId)}&db_path=${encodeURIComponent(dbPath)}`);
        const data = await res.json();

        const preview = document.getElementById('pedagogical-preview');
        preview.innerText = data.pedagogical_context || '(No pedagogical profile active for this learner)';

        const tbody = document.getElementById('memory-table-body');
        tbody.innerHTML = '';
        if (!data.memories || data.memories.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No memories found.</td></tr>';
          return;
        }

        data.memories.forEach(m => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><code>${m.memory_id.substring(0, 10)}...</code></td>
            <td><span class="badge badge-audio">${m.memory_type_str}</span></td>
            <td><strong>${m.topic}</strong></td>
            <td>${m.content}</td>
            <td>${m.confidence.toFixed(2)}</td>
            <td>${m.revision_count}</td>
            <td>
              <button class="btn btn-secondary" style="padding:4px 8px; font-size:0.75rem;" onclick="prefillCorrect('${m.memory_id}', '${m.content.replace(/'/g, "\\\\'")}')">Correct</button>
              <button class="btn btn-danger" style="padding:4px 8px; font-size:0.75rem;" onclick="deleteMemory('${m.memory_id}')">Del</button>
            </td>
          `;
          tbody.appendChild(tr);
        });
      } catch (err) {
        console.error('Failed to load memory:', err);
      }
    }

    function prefillCorrect(id, content) {
      document.getElementById('correct-mem-id').value = id;
      document.getElementById('correct-mem-content').value = content;
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
        if (!res.ok) throw new Error(await res.text());
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
        if (!res.ok) throw new Error(await res.text());
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
        if (!res.ok) throw new Error(await res.text());
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
        if (!res.ok) throw new Error(await res.text());
        loadMemoryData();
      } catch (err) {
        alert('Purge failed: ' + err.message);
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
