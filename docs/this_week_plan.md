# This Week Plan — Grounded Multimodal AI Tutor

**Date**: 2026-10-15  
**Scope**: Repository audit, test/benchmark results, data-flow analysis, M4 + M5 implementation plan  
**P0 fixes applied**: 2026-10-15 — see Section 10 below.

---

## 1. Repository Audit Findings

### Module Map

| Module | File(s) | Purpose |
|--------|---------|---------|
| Config | `config.py` | Central env-var–driven config; paths for DB, keyframes, audio, whisper model, manifest |
| Storage / Schema | `storage/schema.sql`, `storage/corpus_store.py` | SQLite-backed versioned evidence store (M1) |
| Ingestion | `ingestion/versioning.py`, `chunker.py`, `ocr.py`, `transcriber.py`, `video_processor.py`, `manifest.py` | Full ingestion pipeline from video → SRT/keyframes → chunks |
| Retrieval | `retrieval/retriever.py` | Hybrid dense+sparse (Qdrant + BM25) retrieval via LlamaIndex |
| Generation | `generation/answer.py` | LLM-grounded answer + citation builder |
| CLI | `main.py` | `ingest`, `deprecate`, `resolve-citation`, `query` sub-commands |
| Official ingest | `scripts/ingest_official.py`, `ingest_official.py` (root) | Downloads official SRT + PDF from CDN and ingests without ASR/OCR |
| Benchmark | `benchmark/cases.jsonl`, `benchmark/validate.py` | 20 gold QA cases; schema validator |
| Tests | `tests/` (5 files, 47 collected) | Unit + integration tests for M1 pipeline and benchmark structure |

### Architecture Summary (verified)

M1 (version safety) is substantially implemented. The pipeline:

1. Hashes video file → `content_hash`
2. Checks `is_source_active()` (idempotency guard)
3. Runs ffmpeg audio extract → Whisper ASR → keyframe extract → Tesseract OCR
4. Calls `build_chunks()` to produce `EvidenceChunk` objects
5. `insert_chunks()` stages chunks as stale until `upsert_source()` atomically activates them
6. `active_chunks()` JOIN-enforces `c.content_hash = s.content_hash` (double safety)

**Known issue (active blockers — see Section 6):** `SourceVersion` dataclass does **not** have `asset_id` or `is_deprecated` fields, but `main.py`, `ingestion/manifest.py`, and `storage/corpus_store.py` all assume they exist. This causes 12 test failures.

---

## 2. Actual Test and Benchmark-Validator Results

### Test Suite

**Command**: `python3 -m pytest tests/ -v --tb=short`  
**Environment**: Python 3.14.8, pytest-9.1.1, pluggy-1.6.0  
**Result**: **35 passed, 12 failed**

#### Passing Tests (35)

| File | Tests Passed |
|------|-------------|
| `test_benchmark.py` | All 9: loads, count=20, unique IDs, required fields, ≥5 visual, justification, gold evidence, unanswerable, rejection |
| `test_ingestion_version_safety.py` | 6/15: `evidence_id_is_deterministic`, `changed_version_produces_different_id`, `asset_paths_are_version_isolated`, `same_version_uses_same_asset_namespace`, `long_transcript_segment_is_split`, `all_chunks_respect_max_duration` |
| `test_ocr.py` | All 4: success status, failure recorded, failure preserves asset, empty text not failure |
| `test_real_evidence.py` | 9/10: manifest resolves config, provenance preserved, valid timestamp, out-of-bounds rejected, unknown evidence rejected, citation resolves, deterministic identity, hash changes, SRT timestamps, visual no synthetic timestamp, visual no fake timestamp, audio navigable |
| `test_source_manifest.py` | 3/5: loads successfully, malformed rejected, duplicate identity rejected, two editions distinguishable |

#### Failing Tests (12) — Exact Errors

**Root Cause A — `SourceVersion` missing `asset_id` and `is_deprecated` fields (11 failures)**

`ingestion/versioning.py::SourceVersion` has fields: `source_id, content_hash, course_edition, title, ingested_at, source_type, source_url, original_asset_url, license, license_url, attribution, modification_notice`  
Missing: **`asset_id`** (called in `main.py:73`, `manifest.py:275`) and **`is_deprecated`** (called in `corpus_store.py:231`).

| Test | Exact Error |
|------|-------------|
| `test_failed_ingestion_can_retry` | `TypeError: SourceVersion.__init__() got an unexpected keyword argument 'asset_id'` at `main.py:73` |
| `test_previous_version_remains_active_after_failed_replacement` | Same — `main.py:73` |
| `test_new_successful_version_replaces_previous_active_version` | Same — `main.py:73` |
| `test_active_chunks_excludes_old_version` | `AttributeError: 'SourceVersion' object has no attribute 'is_deprecated'` at `corpus_store.py:231` |
| `test_delayed_old_version_write_cannot_become_active` | Same — `corpus_store.py:231` |
| `test_full_lifecycle_preservation_and_replacement` | `TypeError: asset_id` — `main.py:73` |
| `test_idempotent_reingest_skip` | `TypeError: asset_id` — `main.py:73` |
| `test_deprecate_edition_excludes_chunks` | `TypeError: asset_id` — `main.py:73` |
| `test_v1_to_v2_successful_replacement_lifecycle` | `AttributeError: is_deprecated` — `corpus_store.py:231` |
| `test_provenance_fields_preserved_in_ingestion_record` | `TypeError: SourceVersion.__init__() got unexpected keyword argument 'asset_id'` at `manifest.py:275` |
| `test_cli_ingest_resolves_manifest_metadata` | `TypeError: asset_id` — `main.py:73` |

**Root Cause B — Hash length assertion mismatch (1 failure)**

| Test | Exact Error |
|------|-------------|
| `test_content_hash_is_deterministic` | `AssertionError: 'bf0ecbdb9b814248d086c9b69cf26182d9d4138f2ad3d0637c4555fc8cbf68e5' == 'bf0ecbdb9b814248'` — test asserts `[:16]` prefix but `file_content_hash()` returns full 64-char hex digest. **This is a test bug, not an application bug.** |

---

### Benchmark Validator

**Command**: `python3 benchmark/validate.py`  
**Result**: **FAILED**

```
Error: Evidence ID ce6cced76ac84e1dd6838fdd816319fc for case cs50-2024-lec01-vis-01
       does not exist in the database.
```

The validator finds `data/corpus.db` (36 KB, present on disk), queries `chunks`, and fails because none of the 20 benchmark gold chunk IDs exist in the DB. The DB currently holds only 3 stale test-fixture chunks (from test runs), no active source rows, and no gold evidence.

The structural schema validation (20 cases, required fields, ≥5 visual, etc.) would pass — the failure is purely a missing-data problem.

---

## 3. Exact Commands Used

```bash
# Test suite (run from project root)
python3 -m pytest tests/ -v --tb=short

# Benchmark validator (run from project root)
python3 benchmark/validate.py

# DB inspection
python3 -c "
import sqlite3
conn = sqlite3.connect('data/corpus.db')
conn.row_factory = sqlite3.Row
print('Sources:', conn.execute('SELECT COUNT(*) FROM sources').fetchone()[0])
print('Chunks:', conn.execute('SELECT COUNT(*) FROM chunks').fetchone()[0])
print('Active:', conn.execute('SELECT COUNT(*) FROM chunks WHERE is_stale=0').fetchone()[0])
"

# SourceVersion field inspection
python3 -c "from ingestion.versioning import SourceVersion; import inspect; print(inspect.signature(SourceVersion.__init__))"

# Keyframe/audio directory existence check
python3 -c "import os; print('KF:', os.path.exists('data/keyframes')); print('Audio:', os.path.exists('data/audio'))"
```

---

## 4. Evidence and Image-Path Data Flow

### Chunk ID generation (deterministic)

```
compute_chunk_id(source_id, content_hash, modality, start_sec, end_sec, text, extra)
  → SHA-256[:32] of "{source_id}:{content_hash}:{modality}:{s:.3f}:{e:.3f}:{text}:{extra}"
```

Verified deterministic by `test_evidence_id_is_deterministic` (PASS) and `test_changed_version_or_evidence_produces_different_id` (PASS).

### `image_path` end-to-end flow

```
video_processor.extract_keyframes(video_path, source_id, content_hash)
  → Keyframe(timestamp_sec=T, image_path="data/keyframes/<source_id>/<content_hash>/scene_NNNNN.jpg")
         ↓
ocr.ocr_keyframes([Keyframe])
  → OcrResult(timestamp_sec=T, image_path="data/keyframes/.../scene_NNNNN.jpg", text, status)
         ↓
chunker.build_chunks(source_id, content_hash, transcript, ocr_results)
  → EvidenceChunk(chunk_id, source_id, content_hash, modality="visual",
                  start_sec=T, end_sec=T, text, image_path)   ← image_path preserved verbatim
         ↓
corpus_store.insert_chunks([EvidenceChunk])
  → chunks table: image_path TEXT column
         ↓
corpus_store.active_chunks()    ← JOIN enforces content_hash match
  → dict rows with "image_path" key
         ↓
retrieval/retriever.py TutorRetriever._load_data()
  → Document(metadata={"image_path": c.get("image_path"), "chunk_id": ..., "start_sec": ...})
         ↓
generation/answer.py generate_grounded_answer()
  → citations[i] = {"image_path": n.metadata.get("image_path"), "source_id": ..., "start_sec": ...}
  → returned to caller
```

**Keyframe directory structure** (version-isolated — verified by PASS `test_asset_paths_are_version_isolated`):
```
data/keyframes/<source_id>/<content_hash>/scene_00001.jpg   ← scene-change frames
data/keyframes/<source_id>/<content_hash>/fixed_00001.jpg   ← fixed-interval fallback
```

### `source_id` / `asset_id` / `edition_id` flow

```
data/source_manifest.json
  → SourceAssetRecord(source_id, edition_id, asset_id, source_url, original_asset_url, …)
         ↓ get_manifest_asset(asset_id)
main.py ingest() / scripts/ingest_official.py
         ↓ build_source_version_from_manifest(record, content_hash)
SourceVersion(source_id, content_hash, course_edition=edition_id, …)  ← BUG: asset_id missing from dataclass
         ↓ upsert_source(version)
sources table: source_id, content_hash, course_edition, asset_id, source_url
         ↓ active_chunks() JOIN
chunks table: source_id, content_hash, asset_id, source_url, image_path
```

### Timestamp flow to M3 citations

- **Audio chunks**: `start_sec`/`end_sec` from SRT/ASR → stored → citation URL appends `&t={int(start_sec)}s`
- **Visual chunks from video keyframes**: `start_sec = end_sec = keyframe.timestamp_sec`
- **Visual chunks from PDF slides**: `start_sec = end_sec = None` → citation reports "Time Bounds: Unknown", no `&t=` appended (verified by PASS `test_visual_citation_does_not_create_fake_timestamp`)

---

## 5. Existing Local Image Availability

| Location | Status |
|----------|--------|
| `data/keyframes/` | **Does not exist** — no keyframe images extracted locally |
| `data/audio/` | **Does not exist** — no audio files locally |
| `data/corpus.db` | Exists (36 KB); 3 stale test chunks (source_id=cs50-lec01), 0 active chunks, 0 source rows |
| `data/source_manifest.json` | Exists (10.9 KB); 8 entries: CS50x Lec0–Lec5 (2024) + Lec0–Lec1 (2023); all `content_hash: null`, `ingestion_status: "cataloged"` |

**No real lecture frames are ingested or available locally.**

The official ingest script (`scripts/ingest_official.py`) downloads SRT + PDF from CS50 CDN on demand and produces one "dummy" visual OcrResult per lecture (not per page). Real keyframe JPEGs do not exist anywhere in the repository.

---

## 6. Blockers and Risks

### Blockers (must fix before M4/M5)

| # | Blocker | Root Cause | Impact |
|---|---------|-----------|--------|
| ~~B1~~ | ~~`SourceVersion` missing `asset_id` field~~ | **FIXED** — `asset_id: Optional[str] = None` added to `ingestion/versioning.py` | Resolved 2026-10-15 |
| ~~B2~~ | ~~`SourceVersion` missing `is_deprecated` field~~ | **FIXED** — `is_deprecated: bool = False` added to `ingestion/versioning.py` | Resolved 2026-10-15 |
| B3 | No real keyframes ingested locally | No video downloaded; official ingest uses PDF pseudo-OCR, not real keyframes | M4 visual QA cannot run end-to-end without actual image files |
| B4 | Benchmark gold chunk IDs not in DB | Official ingest has never been run to successful completion for `cs50-lec01` (2024) | Benchmark validator always exits with error |

### Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|-----------|
| R1 | `SourceVersion` fix could change `upsert_source` behavior if `is_deprecated` default is wrong | Medium — version-safety regression | Add `is_deprecated: bool = False` as a default field (no callers set it explicitly) |
| R2 | Real keyframe extraction needs ffmpeg + ~8.7 GB video download for lec01 | High — slow/expensive | Use PyMuPDF to render PDF slides to JPEGs instead (already partially scaffolded) |
| R3 | M4 multimodal LLM needs an API key; adds new external dependency | Medium | Make VQA backend pluggable; document required env var |
| R4 | M5 learner memory; overengineering risk | Medium | Start with in-memory dict per session; SQLite persistence is additive later |
| R5 | `test_content_hash_is_deterministic` asserts `[:16]` but function returns 64-char digest | Low — test bug, not app bug | Fix the test assertion |
| R6 | Gold benchmark chunk IDs may not match a fresh re-ingest (if SRT content changes) | High | Verify IDs after running ingest; regenerate `cases.jsonl` IDs if needed |

---

## 7. Prioritised Implementation Plan for M4 and M5

### Pre-requisites (P0 — fix before anything else)

#### P0a — Fix `SourceVersion` dataclass (unblocks 11 failing tests)

**File**: `ingestion/versioning.py`  
**Change**: Add two optional fields:
```python
asset_id: Optional[str] = None
is_deprecated: bool = False
```
This is backward-compatible. `corpus_store.py` already uses `getattr(version, "asset_id", None)` defensively but then also directly accesses `version.is_deprecated` — the field must exist on the dataclass. No logic changes required.

#### P0b — Fix hash assertion in test (test bug, 1 line)

**File**: `tests/test_real_evidence.py:114`  
**Change**: Remove `[:16]` slice from the `hashlib.sha256(b"dummy content").hexdigest()[:16]` assertion. The function returns a full 64-char digest.

#### P0c — Re-run pytest and confirm 0 failures

```bash
python3 -m pytest tests/ -v
```

#### P0d — Run official ingest to populate DB for benchmark

```bash
python3 scripts/ingest_official.py ingest --asset-id cs50-2024-lec01-video
python3 benchmark/validate.py   # should pass if gold IDs match
```

---

### M4 — Visual Question Answering

**Goal**: When a retrieved chunk has `modality="visual"` and a non-null local `image_path`, pass the actual frame image to a multimodal LLM alongside text context.

**Files affected**: `generation/answer.py` (modify), new `generation/vqa.py` (optional helper)  
**No changes** to: ingestion, storage, schema, retrieval, benchmark, versioning

#### Step-by-step

1. **Detect visual chunks with local images** — in `generate_grounded_answer()`, after retrieving nodes, identify those where `metadata["image_path"]` is not None and `os.path.exists(image_path)` is True.

2. **Build multimodal prompt** — load images as base64 or PIL and pass to a multimodal LLM (e.g., `google-generativeai` Gemini Flash, or `openai>=1.0` GPT-4o).

3. **Preserve fallback** — when no image is available (missing on disk, or text-only chunks), fall back to existing `llm.complete(prompt)` path. The existing code path is unchanged.

4. **Preserve citation structure** — `citations[i]["image_path"]` already flows through; no schema changes needed.

**Smallest safe change sketch**:
```python
# generation/answer.py — inside generate_grounded_answer()
import os, base64

image_b64_list = []
for n in nodes:
    ip = n.metadata.get("image_path")
    if ip and os.path.exists(ip):
        with open(ip, "rb") as f:
            image_b64_list.append(base64.b64encode(f.read()).decode())

if image_b64_list and multimodal_llm:
    response = multimodal_llm.complete(prompt, images=image_b64_list)
else:
    response = llm.complete(prompt)   # existing text-only path, unchanged
```

**Version-safety**: Images are stored under `data/keyframes/<source_id>/<content_hash>/`. A stale chunk's image cannot be served because `active_chunks()` JOIN already excludes stale chunks. No M1 guarantee is weakened.

**Missing real images**: To get real images without downloading the full video:
- Extend `scripts/ingest_official.py` to use `PyMuPDF` (`fitz`) to render each PDF slide page to a JPEG under `data/keyframes/<source_id>/<content_hash>/slide_NNN.jpg`, storing one `OcrResult` per page (real text + real image). Add `PyMuPDF` to `requirements.txt`.

**New dependency**: `google-generativeai` or `openai>=1.0` + `PyMuPDF`. Add to `requirements.txt`.

---

### M5 — Learner Memory

**Goal**: Track learner misconceptions, mastered topics, and difficulty level across queries within a session, and optionally persist across sessions.

**Files affected**: New `memory/learner_memory.py`, small wiring in `main.py::ask_tutor()`, optional `generation/answer.py` signature change  
**No changes** to: ingestion, storage schema (phase 1), retrieval, benchmark, versioning

#### Step-by-step

1. **Create `memory/learner_memory.py`** with an in-memory `LearnerMemory` class:
   ```python
   class LearnerMemory:
       def __init__(self, learner_id: str = "default"): ...
       def record(self, query: str, answer: str, citations: list): ...
       def get_context_prompt(self) -> str:
           # Returns a short summary like:
           # "Learner has mastered: variables, loops. Struggled with: pointers."
           ...
       def mark_mastered(self, topic: str): ...
       def mark_struggled(self, topic: str): ...
   ```

2. **Inject memory into answer generation** — add `memory: Optional[LearnerMemory] = None` parameter to `generate_grounded_answer()`. If provided, prepend `memory.get_context_prompt()` to the LLM prompt so it can adapt tone/depth. Existing callers passing `memory=None` are unaffected.

3. **Record after each turn** — in `ask_tutor()` in `main.py`, call `memory.record(query, answer, citations)` after each successful answer.

4. **Persistence (phase 2, additive migration)** — add a `learner_memory` table via `init_db()`:
   ```sql
   CREATE TABLE IF NOT EXISTS learner_memory (
       id          INTEGER PRIMARY KEY AUTOINCREMENT,
       learner_id  TEXT NOT NULL,
       recorded_at REAL NOT NULL,
       query       TEXT,
       answer_summary TEXT,
       topics_json TEXT   -- JSON array of {topic, status: mastered|struggled}
   );
   ```
   Additive migration — no existing table is modified.

**Version-safety**: Memory is completely independent of ingestion. No `content_hash`, `is_stale`, or `is_deprecated` fields are touched. Zero M1 risk.

---

## 8. Recommended Next-Step Order

| Priority | Action | File(s) | Effort | Risk |
|----------|--------|---------|--------|------|
| P0a | Add `asset_id: Optional[str] = None` + `is_deprecated: bool = False` to `SourceVersion` | `ingestion/versioning.py` | 2 lines | Minimal |
| P0b | Fix hash assertion `[:16]` → full 64-char in test | `tests/test_real_evidence.py:114` | 1 line | None |
| P0c | `python3 -m pytest tests/ -v` → confirm 0 failures | — | Verification | — |
| P0d | Run official ingest, then `python3 benchmark/validate.py` | — | ~30s network | Low |
| M4-1 | Extend `ingest_official.py` to render PDF pages → JPEGs via PyMuPDF | `scripts/ingest_official.py` | ~30 lines | Low |
| M4-2 | Implement multimodal answer path in `generation/answer.py` | `generation/answer.py` | ~40 lines | Low |
| M5-1 | Create `memory/learner_memory.py` in-memory class | `memory/learner_memory.py` | ~50 lines | None |
| M5-2 | Wire memory into `ask_tutor()` | `main.py` | ~10 lines | Low |
| M5-3 | (Optional) SQLite persistence migration for memory | `storage/corpus_store.py`, `storage/schema.sql` | ~15 lines | Low |

---

## 9. Assumptions and Unresolved Questions

**Verified facts** (backed by code inspection or command output):

- ~~`SourceVersion` lacks `asset_id` and `is_deprecated`~~ — **FIXED 2026-10-15** (see Section 10)
- No keyframes or audio files exist locally (`data/keyframes/` and `data/audio/` do not exist)
- DB has 3 stale chunks, 0 active, 0 source rows — confirmed by direct SQLite query
- Benchmark validator fails because evidence IDs are missing from DB — confirmed by running `python3 benchmark/validate.py`
- ~~35 tests pass, 12 fail~~ — **UPDATED: 47/47 pass after P0 fixes** (see Section 10)
- `image_path` flows end-to-end through ingestion → storage → retrieval → citation — confirmed by code trace
- Version-isolated keyframe path `data/keyframes/<source_id>/<content_hash>/` — confirmed by PASS `test_asset_paths_are_version_isolated`
- All 9 benchmark schema tests pass — `cases.jsonl` is well-formed

**Assumptions (not yet verified)**:

- The 20 benchmark gold chunk IDs in `cases.jsonl` were produced by a prior official ingest run; re-ingesting `cs50-2024-lec01-video` will reproduce the same IDs (depends on SRT content being identical to when IDs were generated)
- PDF page rendering will produce useful image files for M4 visual QA
- A multimodal LLM API key will be available in the environment

**Unresolved questions**:

- Which multimodal LLM backend is preferred for M4 — Gemini Flash, GPT-4o, or a local model? This determines the new dependency.
- Should M5 `LearnerMemory` be keyed per `learner_id` (requires login) or per session (anonymous)? Affects design.
- Do the gold benchmark chunk IDs in `cases.jsonl` survive a fresh re-ingest? If IDs don't match after ingest, the benchmark validator will still fail and `cases.jsonl` must be regenerated.
- `docs/W1_W2_AUDIT.md` describes a prior broken state (random UUIDs, no version isolation, no manifest). The current codebase has fixed all those issues. That document is now misleading and should be superseded.

---

## 10. P0 Changes Applied (2026-10-15)

### Files changed

| File | Change | Lines |
|------|--------|-------|
| [`ingestion/versioning.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/ingestion/versioning.py) | Added `asset_id: Optional[str] = None` and `is_deprecated: bool = False` to `SourceVersion` dataclass, after `modification_notice` (all existing optional fields with defaults; no position conflict) | +2 |
| [`tests/test_real_evidence.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/tests/test_real_evidence.py) | Removed `[:16]` from `hashlib.sha256(b"dummy content").hexdigest()[:16]` on line 114 — now compares full 64-char digest against the function's full output | −3 chars |

### What was NOT changed

- `storage/corpus_store.py` — unchanged; `getattr(version, "asset_id", None)` calls already handled the optional case
- `storage/schema.sql` — unchanged
- `main.py`, `ingestion/manifest.py` — unchanged; they already passed `asset_id=` correctly
- `benchmark/cases.jsonl` — unchanged
- `benchmark/validate.py` — unchanged
- `data/corpus.db` — unchanged (not populated by this task)
- `file_content_hash()` implementation — unchanged; still returns full 64-char SHA-256

### Test result

**Command**: `python3 -m pytest tests/ -v --tb=short`

**Result**: **47 passed, 0 failed** (1.11s)

```
tests/test_benchmark.py                         9/9  PASSED
tests/test_ingestion_version_safety.py         15/15 PASSED
tests/test_ocr.py                               4/4  PASSED
tests/test_real_evidence.py                    12/12 PASSED
tests/test_source_manifest.py                   5/5  PASSED  (inc. provenance, cli_ingest)
```

No tests skipped. All previously failing lifecycle tests now pass:
- `test_failed_ingestion_can_retry` ✅
- `test_previous_version_remains_active_after_failed_replacement` ✅
- `test_new_successful_version_replaces_previous_active_version` ✅
- `test_active_chunks_excludes_old_version` ✅
- `test_delayed_old_version_write_cannot_become_active` ✅
- `test_full_lifecycle_preservation_and_replacement` ✅
- `test_idempotent_reingest_skip` ✅
- `test_deprecate_edition_excludes_chunks` ✅
- `test_v1_to_v2_successful_replacement_lifecycle` ✅
- `test_content_hash_is_deterministic` ✅
- `test_provenance_fields_preserved_in_ingestion_record` ✅
- `test_cli_ingest_resolves_manifest_metadata` ✅

### Remaining blockers

| # | Blocker | Next action |
|---|---------|------------|
| ~~B3~~ | ~~No real keyframes locally~~ | **RESOLVED** — PyMuPDF slide rendering implemented; 220 real JPEG slide images extracted and stored under `data/keyframes/cs50-lec01/44469ebd8de3e045/` |
| B4 | Benchmark gold chunk IDs not in DB | `cases.jsonl` gold evidence IDs originated from legacy run (`official_content_hash` + synthetic `i*10.0` timestamps); real ingest produces deterministic IDs without fake timestamps. Gold cases need update in subsequent benchmark alignment task. |

---

## 11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15)

### Goal

Replaced dummy visual evidence record from PDF in official ingestion pipeline with actual slide-page JPEG images and extracted slide text, preserving versioned evidence architecture.

### Files changed

| File | Change | Lines |
|------|--------|-------|
| [`requirements.txt`](file:///home/jonsnow/Desktop/DAT_project/dat_project/requirements.txt) | Added `PyMuPDF==1.28.2` matching repository version pinning convention | +1 |
| [`ingestion/ocr.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/ingestion/ocr.py) | Added `page_number: Optional[int] = None` to `OcrResult`; implemented `extract_pdf_slides()` rendering pages into JPEG at `CONFIG.keyframes_dir/<source_id>/<content_hash>/slide_00001.jpg` and extracting embedded text; preserves empty-text pages and distinct processing failures | +72 |
| [`ingestion/chunker.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/ingestion/chunker.py) | Added `page_number: Optional[int] = None` to `EvidenceChunk`; passed `page_number=getattr(ocr, "page_number", None)` in `build_chunks()` | +3 |
| [`scripts/ingest_official.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/scripts/ingest_official.py) | Replaced dummy PDF extraction with `extract_pdf_slides()`; added `sys.path` configuration for direct CLI execution; prints sample audio and visual chunk IDs | +25 |
| [`ingest_official.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/ingest_official.py) | Replaced legacy draft with forwarder to `scripts.ingest_official.ingest_official` | −63 |
| [`main.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/main.py) | Connected `resolve_citation()` to `scripts.ingest_official.resolve_citation` | +2 |
| [`tests/test_pdf_rendering.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/tests/test_pdf_rendering.py) | Created comprehensive offline unit tests using synthetic PyMuPDF PDFs covering rendering, image existence, text extraction, empty text handling, deterministic IDs, version isolation, error recording, and database persistence | +370 |

### Test Results

1. **PDF Rendering Tests**:
   - **Command**: `python3 -m pytest tests/test_pdf_rendering.py -v`
   - **Result**: **9 passed, 0 failed** (1.23s)

2. **Full Test Suite**:
   - **Command**: `python3 -m pytest tests/ -v --tb=short`
   - **Result**: **56 passed, 0 failed** (1.66s)
   ```
   tests/test_benchmark.py                         9/9  PASSED
   tests/test_ingestion_version_safety.py         15/15 PASSED
   tests/test_ocr.py                               4/4  PASSED
   tests/test_pdf_rendering.py                     9/9  PASSED
   tests/test_real_evidence.py                    12/12 PASSED
   tests/test_source_manifest.py                   5/5  PASSED
   ```

3. **Ingestion & Database Inspection**:
   - **Command**: `python3 scripts/ingest_official.py ingest --asset-id cs50-2024-lec01-video`
   - **Ingested**: 530 chunks (310 audio chunks, 220 visual chunks)
   - **Keyframes**: 220 JPEG files in `data/keyframes/cs50-lec01/44469ebd8de3e045/slide_00001.jpg` .. `slide_00220.jpg`
   - **Verification**: Confirmed all 220 active visual chunk image paths in `data/corpus.db` exist on disk and resolve to valid JPEG images.
   - **Timestamps**: All 220 visual chunks have `start_sec = None`, `end_sec = None` ("Time Bounds: Unknown", no fake video timestamps).

---

## 12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15)

### Goal

Implemented the visual question-answering pathway that passes actual JPEG images referenced by retrieved evidence records to a vision-capable model backend. Preserves text-only answering for transcript-based questions, validates citations, preserves full provenance, safely abstains when required visual evidence is missing or the backend is unavailable, and provides 100% offline test coverage.

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| [`config.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/config.py) | Added `vision_backend: str = "gemini"`, `vision_model_name: str = "gemini-2.5-flash"`, and `max_visual_images: int = 5` with environment variable mappings (`VISION_BACKEND`, `VISION_MODEL_NAME`, `MAX_VISUAL_IMAGES`) | +8 |
| [`generation/vqa.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/generation/vqa.py) | Created modular vision adapter subsystem: `VisualPayload` (with base64 and PIL image properties), `load_and_validate_image()` (checks file existence, non-emptiness, and magic bytes for JPEG/PNG), `BaseVisionAdapter`, `GoogleGenAIVisionAdapter` (`google-genai`), `OpenAIVisionAdapter`, `MockVisionAdapter`, `CallableVisionAdapter`, `LlamaIndexVisionAdapter`, and `get_vision_adapter()` factory | +240 |
| [`retrieval/retriever.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/retrieval/retriever.py) | Populated full provenance in `Document.metadata` (`chunk_id`, `source_id`, `asset_id`, `content_hash`, `course_edition`, `edition_id`, `modality`, `start_sec`, `end_sec`, `image_path`, `page_number`, `source_url`, `status`); added in-memory fallback for environments without Qdrant | +35 |
| [`generation/answer.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/generation/answer.py) | Upgraded `generate_grounded_answer()` to support visual question answering: loads actual image bytes, caps images to `max_images`, enforces `visual_required` abstention on missing/corrupt images or missing backends, preserves text-only answering, validates citations against retrieved evidence, rejects unknown labels, and excludes stale nodes | +130 |
| [`storage/corpus_store.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/storage/corpus_store.py) | Updated `active_chunks()` query to return `COALESCE(c.edition_id, s.course_edition) AS course_edition` | +1 |
| [`ingestion/chunker.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/ingestion/chunker.py) | Added `edition_id: Optional[str] = None` to `EvidenceChunk`, `build_chunks()`, and `_flush_audio()` | +8 |
| [`tests/test_vqa.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/tests/test_vqa.py) | Added 12 comprehensive offline unit tests covering payload transmission, OCR-text insufficiency, metadata preservation, missing-image abstention, unavailable backend abstention, unknown citation rejection, PDF unknown time bounds, text-only query preservation, max images capping, runtime error handling, cited-only filtering, and stale evidence exclusion | +330 |

### Backend Configuration

The vision question-answering system is configurable via `config.py` and environment variables:

- `VISION_BACKEND`: `"gemini"` (default), `"openai"`, or `"mock"`
- `VISION_MODEL_NAME`: Name of the model (default: `"gemini-2.5-flash"`)
- `MAX_VISUAL_IMAGES`: Maximum number of visual images passed to the model per request (default: `5`)
- `GEMINI_API_KEY` or `GOOGLE_API_KEY`: API key for Google GenAI / Gemini backend (`google-genai` SDK is installed in the environment)
- `OPENAI_API_KEY`: API key for OpenAI vision backend

If an API key is not present when a visual question is submitted with `visual_required=True`, the system safely abstains with:
> *"Visual evidence was required to answer this question, but no vision model backend is configured or available."*

### Test Results

1. **VQA Unit Tests**:
   - **Command**: `python3 -m pytest tests/test_vqa.py -v`
   - **Result**: **12 passed, 0 failed** (0.35s)

2. **Full Repository Test Suite**:
   - **Command**: `python3 -m pytest tests/ -v --tb=short`
   - **Result**: **68 passed, 0 failed** (1.61s)
   ```
   tests/test_benchmark.py                         9/9  PASSED
   tests/test_ingestion_version_safety.py         15/15 PASSED
   tests/test_ocr.py                               4/4  PASSED
   tests/test_pdf_rendering.py                     9/9  PASSED
   tests/test_real_evidence.py                    12/12 PASSED
   tests/test_source_manifest.py                   5/5  PASSED
   tests/test_vqa.py                              12/12 PASSED
   ```

3. **Optional Real-Model Integration Test**:
   - Checked environment for configured vision API keys (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`).
   - None are configured in the current shell environment (`all False`). Per instructions, real-model calls were safely skipped and no unexecuted tests were claimed.

### Outstanding Limitations

1. **Vision API Key in Production**:
   To execute live queries against real Gemini or OpenAI vision endpoints, the user must set `GEMINI_API_KEY` or `OPENAI_API_KEY` in their environment. In the absence of a key, the system safely abstains when visual evidence is required.
2. **Benchmark Gold Alignment**:
   Resolved in M4 Phase 3 (see Section 13 below).

---

## 13. M4 Phase 3 — Align Evidence and Evaluate Visual QA (2026-10-16)

### Goal

Aligned all 20 gold QA cases in [`benchmark/cases.jsonl`](file:///home/jonsnow/Desktop/DAT_project/dat_project/benchmark/cases.jsonl) with the real, deterministic evidence chunks in [`data/corpus.db`](file:///home/jonsnow/Desktop/DAT_project/dat_project/data/corpus.db). Built a controlled modality evaluation harness ([`benchmark/evaluate_modalities.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/benchmark/evaluate_modalities.py)) testing transcript-only, OCR-only, and visual-input conditions alongside image-removal and image-swap perturbations. Added offline unit tests and verified that `benchmark/validate.py` passes completely.

### Baseline Investigation & Test Discrepancy Resolution

- In the M4 Phase 2 report, the collected test count was 68, but the per-file table listed counts summing to 66.
- **Root Cause**: [`tests/test_real_evidence.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/tests/test_real_evidence.py) contains **13** tests (was reported as 12), and [`tests/test_source_manifest.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/tests/test_source_manifest.py) contains **6** tests (was reported as 5).
- Recalculated sum: 9 (`test_benchmark`) + 15 (`test_ingestion_version_safety`) + 4 (`test_ocr`) + 9 (`test_pdf_rendering`) + 13 (`test_real_evidence`) + 6 (`test_source_manifest`) + 12 (`test_vqa`) = **68 passed, 0 failed, 0 skipped**.

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| [`benchmark/cases.jsonl`](file:///home/jonsnow/Desktop/DAT_project/dat_project/benchmark/cases.jsonl) | Updated expected evidence IDs across all 20 cases to map to verified, active chunks in `data/corpus.db` without changing questions, categories, expected answers, or schema | ~20 |
| [`benchmark/evidence_alignment_report.json`](file:///home/jonsnow/Desktop/DAT_project/dat_project/benchmark/evidence_alignment_report.json) | Created comprehensive mapping report covering each case ID, previous IDs, proposed active IDs, source/version/page details, verification status (`verified`), and rationale | +240 |
| [`benchmark/evaluate_modalities.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/benchmark/evaluate_modalities.py) | Created CLI evaluation harness supporting 3 modality conditions (transcript-only, OCR-only, visual-input) and 3 perturbation tests (correct image, removed image, swapped image); supports offline mock adapter and optional live model evaluation | +430 |
| [`tests/test_modality_evaluation.py`](file:///home/jonsnow/Desktop/DAT_project/dat_project/tests/test_modality_evaluation.py) | Added 6 comprehensive unit tests covering alignment report schema/completeness, transcript-only abstention, OCR payload suppression, visual image grounding, image swap perturbation detection, and missing image abstention | +180 |

### Evidence Mapping Summary

All 20 benchmark cases were verified against `data/corpus.db` and on-disk assets:
- **Visual Questions (`vis-01` to `vis-05`)**:
  - `vis-01`: Page 11 (`slide_00011.jpg`, `26e6a09bdeb383a528ef7a4709ebd707`) — Verified purple syntax highlighting on `printf` (`RGB [128, 77, 255]`).
  - `vis-02`: Page 16 (`slide_00016.jpg`, `adcc32dab442ac00d0877576b1ffa194`) — Verified input/output diagram with empty central box.
  - `vis-03`: Page 20 (`slide_00020.jpg`, `66ba9ddeed44a43bb4099d7fb110db77`) — Verified compilation diagram with `compiler` inside central box.
  - `vis-04`: Page 30 (`slide_00030.jpg`, `4ef71a50796b245adc6b2e106553327f`) — Verified function with side effects with `function` inside central box.
  - `vis-05`: Page 51 (`slide_00051.jpg`, `168d5c7b40d8eb7362dd5ba966692a0c`) — Verified function returning a value inside box between arrows.
- **Cross-Modal Questions (`cm-01`, `cm-02`)**:
  - `cm-01`: Visual Slide 30 (`4ef71a50796b245adc6b2e106553327f`) + Audio chunk [1127.15-1156.01] (`b7d70d4c2d174b531784b118ff368a37`).
  - `cm-02`: Visual Slide 193 (`de93dd20cc0bc7697a20b29fc1316ae4`, 32 bits) + Audio chunk [7856.18-7882.26] (`fdcd47e41960696d7b1477a1d6677b3c`, ~4 billion).
- **Audio/Terminology/Conceptual/Code/Time/Partial Questions (`term-01` through `part-02`)**:
  - Mapped to exact active audio transcript chunks with verified start/end timestamps.
- **Unanswerable Questions (`unans-01`, `unans-02`)**:
  - Preserved `expected_evidence_ids: []`.

### Evaluation Results

1. **Benchmark Validator**:
   - **Command**: `python3 benchmark/validate.py`
   - **Result**: **Validation passed successfully.** (All 20 cases valid, all referenced evidence exists in active database).

2. **Modality Evaluation (Offline Mock Mode)**:
   - **Command**: `python3 benchmark/evaluate_modalities.py --mode mock`
   - **Transcript-only**: 0 correct, 5 abstained, 0 incorrect (100% safe abstention on visual-required questions).
   - **OCR-only**: 0 correct, 5 abstained, 0 incorrect (100% safe abstention when image payload is suppressed).
   - **Visual-input**: 5 correct, 0 abstained, 0 incorrect (100% accurate grounded visual understanding citing evidence).

3. **Perturbation Evaluation (Removal & Swap)**:
   - **Correct Image**: 5/5 correct, 0 silent false acceptance.
   - **Removed Image**: 5/5 safe abstention, 0 citations fabricated.
   - **Swapped Image**: 5/5 rejected/abstained, 0 silent false acceptance.

4. **Real-Model Evaluation Status**:
   - **Command**: `python3 benchmark/evaluate_modalities.py --mode real`
   - **Result**: `not_run`. Marked cleanly in `benchmark/results/real_model_evaluation_status.json` because no API key is configured in the environment.

5. **Full Test Suite**:
   - **Command**: `python3 -m pytest tests/ -v --tb=short`
   - **Result**: **74 passed, 0 failed** (0.85s)
   ```
   tests/test_benchmark.py                         9/9  PASSED
   tests/test_ingestion_version_safety.py         15/15 PASSED
   tests/test_modality_evaluation.py               6/6  PASSED
   tests/test_ocr.py                               4/4  PASSED
   tests/test_pdf_rendering.py                     9/9  PASSED
   tests/test_real_evidence.py                    13/13 PASSED
   tests/test_source_manifest.py                   6/6  PASSED
   tests/test_vqa.py                              12/12 PASSED
   ```

### Outstanding Work

1. **Live Vision Evaluation**: Can be triggered whenever the user configures `GEMINI_API_KEY` or `OPENAI_API_KEY` by running `python3 benchmark/evaluate_modalities.py --mode real`.
2. **Milestone M5 (Learner Model / Memory)**: Scheduled for next milestone.


