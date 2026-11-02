# Repository Audit & Baseline Verification Report

**Date**: 2026-11-03  
**Milestone Baseline Status**: M4 Complete (Phases 1–3 Verified)  
**Primary Verification Status**: All 74 tests passing (`pytest tests/ -v`), benchmark validated (`python3 benchmark/validate.py` passing)  
**Target Next Milestone**: M5 (Learner Memory & Retrieval Benchmarking)

---

## 1. Executive Summary

This repository audit establishes the empirical ground truth for the **Grounded Multimodal AI Tutor** as of November 2, 2026. Prior documentation (notably historical reports such as `W1_W2_AUDIT.md`) described early prototype stages where evidence IDs were non-deterministic (UUIDs), version-isolation was missing, and tests failed.

The current codebase is in a substantially advanced, robust state:
1. **74 / 74 Pytest unit & integration tests pass** cleanly in 0.80 seconds.
2. **Benchmark validator (`benchmark/validate.py`) passes** completely across all 20 gold QA cases against the active database.
3. **Real evidence corpus (`data/corpus.db`) is populated and active**:
   - 1 active source: `cs50-lec01` (Edition 2024, content hash `44469ebd8de3e045`, deprecated: 0).
   - 530 active chunks total (310 audio transcript chunks, 220 visual slide chunks).
   - 220 real JPEG slide images extracted locally into `data/keyframes/cs50-lec01/44469ebd8de3e045/` (pages 1 to 220).
4. **Controlled Modality and Perturbation Evaluation** (`benchmark/evaluate_modalities.py --mode mock`) passes:
   - 100% safe abstention on transcript-only and OCR-only conditions when visual evidence is required.
   - 100% correct grounded answers when valid visual image payloads are delivered.
   - 100% detection and rejection of removed or swapped image perturbations.
5. **No memory module exists in the active workspace root** (`memory/` folder is absent from the project root; existing draft code exists in the nested directory `grounded-multimodal-ai-tutor-dat/memory/`).

---

## 2. Actual Repository Architecture

```
                                  [Video / PDF Assets]
                                           │
                                    (M1: Ingestion)
                         scripts/ingest_official.py / main.py
                                           ▼
                                 [Versioned Corpus DB]
                                    data/corpus.db
                        (530 active chunks: 310 audio, 220 visual)
                                           │
                 ┌─────────────────────────┴────────────────────────┐
                 ▼                                                  ▼
     (Sparse: BM25 Index)                                (Dense: Qdrant / Embeddings)
   Fallback: Keyword Matcher                           Optional: QdrantClient (in-memory)
                 │                                                  │
                 └─────────────────────────┬────────────────────────┘
                                           ▼
                                (M2: Hybrid Retrieval)
                               retrieval/retriever.py
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
             (M4: Multimodal VQA)                   (M5: Learner Memory)
         generation/vqa.py (Adapters)                [NOT YET IMPLEMENTED]
         generation/answer.py (Grounding)             Target: memory/
                        │                                     │
                        └──────────────────┬──────────────────┘
                                           ▼
                                 (M3: Grounded Answer)
                              Strict Non-Stale Citations
                                           │
                 ┌─────────────────────────┴────────────────────────┐
                 ▼                                                  ▼
     (M6: Zero Stale Invalidation)                         (M7: 60+ Test Suite)
        is_stale / is_deprecated                             Active: 74 tests
                                           │
                                           ▼
                                 (M8: Final Evaluation)
                             Latency vs. Recall & Live Demo
```

### Key Components:
- **`config.py`**: Central configuration with environment overrides for database path, keyframe paths, audio paths, chunk duration limits, manifest path, vision backends (`gemini`, `openai`, `mock`), and maximum visual images.
- **`storage/`**: SQLite persistence engine.
  - `schema.sql`: Tables `sources` and `chunks`.
  - `corpus_store.py`: Atomic version activation (`upsert_source`), staged writing (`insert_chunks`), edition deprecation (`deprecate_edition`), and active query filtering (`active_chunks`) enforcing `c.content_hash == s.content_hash` and `c.is_stale = 0`.
- **`ingestion/`**:
  - `versioning.py`: SHA-256 content hashing (`file_content_hash`) and `SourceVersion` dataclass.
  - `chunker.py`: Deterministic chunk ID generator (`compute_chunk_id`) based on SHA-256[:32], duration cap splitter (max 30s), and `EvidenceChunk` dataclass.
  - `ocr.py`: PDF slide page extraction (`extract_pdf_slides`) via PyMuPDF rendering to JPEG, plus keyframe OCR.
  - `manifest.py`: Loader and schema validator for `data/source_manifest.json`.
- **`retrieval/`**:
  - `retriever.py`: `TutorRetriever` with dense/sparse abstraction. Uses `qdrant_client` and `llama_index` if available; otherwise falls back gracefully to deterministic keyword-matching over active chunks.
- **`generation/`**:
  - `vqa.py`: Pluggable vision adapters (`GoogleGenAIVisionAdapter`, `OpenAIVisionAdapter`, `MockVisionAdapter`, `CallableVisionAdapter`, `LlamaIndexVisionAdapter`), image validation (`load_and_validate_image` checking JPEG/PNG magic bytes and file size), and `VisualPayload`.
  - `answer.py`: `generate_grounded_answer()` enforcing grounded answering, inline citation checking (`[Evidence X]`), image byte loading, citation validation against retrieved evidence, and mandatory visual abstention when visual evidence or vision backends are missing.
- **`benchmark/`**:
  - `cases.jsonl`: 20 gold evaluation cases (5 visual, 2 cross-modal, 2 terminology, 3 conceptual, 2 code, 2 time/evidence, 2 partial, 2 unanswerable).
  - `validate.py`: Validates schema, case count, visual justification notes, and checks that all referenced evidence IDs exist in `data/corpus.db`.
  - `evaluate_modalities.py`: 3-condition modality evaluation harness (transcript-only, OCR-only, visual-input) and perturbation test harness (correct, removed, swapped).

---

## 3. Verified Historical Baseline vs. Current Actuals

| Baseline Metric | Historical Documentation | Verified Current Actual | Evidence / Status |
|:---|:---:|:---:|:---|
| **M4 Phase 1** (Slide Evidence) | Completed | **VERIFIED** | 220 slide JPEGs in `data/keyframes/cs50-lec01/44469ebd8de3e045/` |
| **M4 Phase 2** (Multimodal VQA) | Completed | **VERIFIED** | `generation/vqa.py` + `generation/answer.py` tested offline with mocks |
| **M4 Phase 3** (Benchmark & Modality Eval) | Completed | **VERIFIED** | `benchmark/evaluate_modalities.py` passes all 3 conditions & perturbations |
| **Real Slide JPEGs** | 220 extracted | **220 verified on disk** | Slide 1 to 220 confirmed, valid JPEG magic bytes |
| **Evidence Chunks Ingested** | 530 active | **530 active (534 total)** | 310 audio + 220 visual active in `data/corpus.db`; 4 stale test chunks |
| **Benchmark QA Cases** | 20 cases | **20 cases verified** | 5 visual, 2 cross-modal, 2 term, 3 conc, 2 code, 2 time, 2 part, 2 unans |
| **Pytest Pass Count** | 74 passing | **74 passed, 0 failed, 0 skipped** | Execution time: 0.80s (`pytest tests/ -v`) |
| **Benchmark Validator** | Passing | **Passed** | `python3 benchmark/validate.py` exits 0 |
| **Offline Perturbation Tests** | Passing | **Passed** | 100% abstention on removed/swapped images |

---

## 4. Verification Commands and Actual Output

### A. Full Pytest Suite

```bash
python3 -m pytest tests/ -v --tb=short
```

**Output**:
```
============================= test session starts ==============================
platform linux -- Python 3.14.8, pytest-9.2.0, pluggy-1.7.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/jonsnow/Desktop/DAT_project/dat_project
configfile: pytest.ini
collected 74 items

tests/test_benchmark.py                         9/9  PASSED
tests/test_ingestion_version_safety.py         15/15 PASSED
tests/test_modality_evaluation.py               6/6  PASSED
tests/test_ocr.py                               4/4  PASSED
tests/test_pdf_rendering.py                     9/9  PASSED
tests/test_real_evidence.py                    13/13 PASSED
tests/test_source_manifest.py                   6/6  PASSED
tests/test_vqa.py                              12/12 PASSED

======================== 74 passed, 1 warning in 0.80s =========================
```

### B. Benchmark Schema and Evidence ID Validation

```bash
python3 benchmark/validate.py
```

**Output**:
```
Validation passed successfully.
```

### C. Database and Keyframe Asset Verification

```bash
python3 -c "
import sqlite3, os
conn = sqlite3.connect('data/corpus.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM chunks WHERE is_stale = 0')
print('Active chunks:', c.fetchone()[0])
c.execute('SELECT modality, COUNT(*) FROM chunks WHERE is_stale = 0 GROUP BY modality')
for r in c.fetchall(): print(r)
print('Keyframe JPEG count:', len(os.listdir('data/keyframes/cs50-lec01/44469ebd8de3e045')))
"
```

**Output**:
```
Active chunks: 530
('audio', 310)
('visual', 220)
Keyframe JPEG count: 220
```

### D. Modality Evaluation (Offline Mock Mode)

```bash
python3 benchmark/evaluate_modalities.py --mode mock
```

**Output**:
```
Loaded 530 active chunks from corpus.db (220 visual).
Loaded 20 cases from benchmark/cases.jsonl.

--- Running 3-Condition Modality Evaluation ---
Saved modality results to benchmark/results/modality_evaluation_mock.json (15 condition trials).

--- Running Image Perturbation Evaluation (Removal & Swap) ---
Saved perturbation results to benchmark/results/perturbation_evaluation_mock.json (15 trials).

================== MODALITY EVALUATION SUMMARY ==================
Condition: TRANSCRIPT_ONLY  -> Correct: 0 | Abstained: 5 | Incorrect: 0
Condition: OCR_ONLY         -> Correct: 0 | Abstained: 5 | Incorrect: 0
Condition: VISUAL_INPUT     -> Correct: 5 | Abstained: 0 | Incorrect: 0

================ PERTURBATION EVALUATION SUMMARY ================
Test: CORRECT_IMAGE    -> Correct: 5 | Abstained: 0 | Incorrect: 0
Test: REMOVED_IMAGE    -> Correct: 0 | Abstained: 5 | Incorrect: 0
Test: SWAPPED_IMAGE    -> Correct: 0 | Abstained: 5 | Incorrect: 0
```

---

## 5. Subsystem Status Audit

### A. Memory Functionality & Architecture
- **Current Status**: **Unimplemented in active project root**.
- **Existing Drafts**: A draft memory implementation exists in `grounded-multimodal-ai-tutor-dat/memory/` containing `models.py`, `policy.py`, `store.py`. However, it is not imported by `main.py`, not referenced in `storage/schema.sql`, and has no unit tests in `tests/`.
- **Target Design for M5**:
  - `LearnerProfile`, `MemoryEntry`, `MasteryState` models.
  - Policy rules: writing (confidence threshold), TTL/expiry, correction, deletion.
  - SQLite persistence schema in `storage/` for auditability and learner state.
  - Injection of memory context into `ask_tutor()` / `generate_grounded_answer()`.

### B. Session Management, Authentication & Learner Identity
- **Current Status**: **None**.
- The CLI (`main.py`) and generation pipelines operate statelessly per query. No user authentication, session tokens, or learner IDs are currently tracked or passed.

### C. Retrieval Implementation (Sparse, Dense, Hybrid)
- **Current Status**: **Functional with offline fallback**.
- `retrieval/retriever.py` defines `TutorRetriever(use_dense=True, use_sparse=True)`.
- If `llama_index` and `qdrant_client` are installed, it builds an in-memory Qdrant vector store and a LlamaIndex BM25 retriever, combining them via `QueryFusionRetriever` (reciprocal reranking).
- When `llama_index` is not installed, it falls back to an offline keyword count retriever over all active chunks.
- Note: `benchmark/evaluate_retrieval.py` does not yet exist to quantify side-by-side Hit@5 and Recall@5 metrics for Sparse vs Dense vs Hybrid (BUG-004).

### D. Vector Index Synchronization Logic
- **Current Status**: **Recomputed on startup**.
- `TutorRetriever._load_data()` queries `active_chunks()` from SQLite on instantiation and builds the in-memory index dynamically.
- No asynchronous background vector sync daemon or external persistent vector DB is currently configured.

### E. Frontend, Backend, and API Interfaces
- **Current Status**: **CLI only**.
- Entry points: `main.py` (`ingest`, `deprecate`, `resolve-citation`, `query`), `scripts/ingest_official.py`, and `benchmark/` CLI runners.
- No REST API (FastAPI / Flask) or Web UI (`demo/app.py`) exists yet. Scheduled for M8 (Phase 3).

### F. Multimodal Vision Implementation
- **Current Status**: **Architecture complete, verified offline**.
- Modular adapter pattern supporting `gemini`, `openai`, `mock`, `callable`, and `llamaindex`.
- Image validation strictly validates image path, size, and header magic bytes.
- When API keys are not supplied in the environment, the system abstains safely without crashing.
- Live external API calls require user to set `GEMINI_API_KEY` or `OPENAI_API_KEY`.

---

## 6. Audit of Existing Bugs (BUG-001 through BUG-006)

| Bug ID | Severity | Status | Affected Modules | Description | Current Verification Finding |
|:---:|:---:|:---:|:---|:---|:---|
| **BUG-001** | P0 | ✅ Resolved | `ingestion/versioning.py` | `TypeError: SourceVersion missing asset_id and is_deprecated` | Verified resolved; fields exist with defaults; all version safety tests pass. |
| **BUG-002** | P1 | ✅ Resolved | `tests/test_real_evidence.py` | SHA-256 length assertion mismatch (`[:16]` slice) | Verified resolved; test asserts full 64-character hex digest. |
| **BUG-003** | P1 | 🔍 Open | `memory/` | Learner Memory Unimplemented | Still open. Memory package does not exist in root codebase; scheduled for M5 (Tasks P1.1–P1.4). |
| **BUG-004** | P2 | 🔍 Open | `benchmark/` | Retrieval benchmark lacks side-by-side Hit@5 / Recall@5 runner | Still open. `benchmark/evaluate_retrieval.py` does not exist; scheduled for Task P1.5. |
| **BUG-005** | P2 | 🔍 Open | `generation/vqa.py` | Live multimodal VQA needs end-to-end integration test with live model | Open pending live API key; offline mock tests pass 100%. |
| **BUG-006** | P1 | 🔍 Open | `tests/` | 60+ test suite and prompt injection coverage not yet unified | Open. Current suite has 74 tests across unit/integration; unified runner and prompt injection/adversarial suite scheduled for Phase 2 (M6/M7). |

### Newly Discovered Issues

1. **ISSUE-001: Subdirectory Duplication (`grounded-multimodal-ai-tutor-dat/`)**
   - **Severity**: P3 (Minor / Housekeeping)
   - **Description**: There is a nested copy of the repository at `grounded-multimodal-ai-tutor-dat/` which contains an exploratory draft of the memory module (`memory/models.py`, `memory/policy.py`, `memory/store.py`).
   - **Recommendation**: Do not import directly from the nested directory; cleanly implement the official memory module in the root workspace `memory/` directory to maintain clean module resolution and test boundaries.

2. **ISSUE-002: Offline Keyword Retrieval Scoring for Complex Visual Queries**
   - **Severity**: P2 (Major for offline CLI queries)
   - **Description**: In environments where LlamaIndex/Qdrant are not installed, `TutorRetriever.retrieve()` uses a simple bag-of-words word count. On visual questions with long natural language prompts (e.g., "In the first C code example for hello world shown on screen..."), audio chunks with frequent conversational words can outscore the visual slide chunk (slide 11), causing retrieval to miss the visual chunk and abstain.
   - **Mitigation/Fix**: Ensure that for M5 and retrieval benchmarking, either BM25/Dense retrieval is evaluated with calibrated stop-word filtering or LlamaIndex packages are installed.

---

## 7. Blockers and Dependency Assessment

| Category | Item | Status | Classification | Impact |
|:---|:---|:---:|:---:|:---|
| **System Tools** | `ffmpeg`, `ffprobe`, `tesseract` | Found on PATH | Available | Full audio extraction and OCR work locally. |
| **Python Package** | `PyMuPDF` (`fitz`), `Pillow` | Installed | Available | PDF slide rendering and image validation work locally. |
| **Python Package** | `google-genai` | Installed | Available | Google GenAI SDK is available for live vision when key is set. |
| **Python Package** | `llama-index`, `qdrant-client` | Not in system Python | Optional / Fallback active | System operates with offline fallback keyword retrieval. |
| **Python Package** | `openai` | Not installed | Optional | Only needed if OpenAI backend is selected. |
| **Environment** | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Not set (`False`) | Potential Blocker for live vision | System safely abstains on visual questions; does not crash. Mock mode works. |
| **Environment** | `OPENAI_API_KEY` | Not set (`False`) | Optional | Fallback to Gemini or mock. |
| **Database** | `data/corpus.db` | Exists (530 active chunks) | Available | Fully verified and operational. |
| **Vector DB** | Qdrant Server | Not running | Offline mode active | In-memory `:memory:` client used when library is available. |

---

## 8. Recommended Implementation Order for M5 (Learner Memory)

To achieve Milestone M5 without disrupting the passing baseline, the following phased sequence is recommended:

1. **Step 1: Define Memory Models (`memory/models.py`)**
   - Implement `LearnerProfile`, `MemoryEntry`, `MasteryState`, `MemoryType` (`goal`, `mastery`, `misconception`).
   - Implement deterministic `compute_memory_id()`.
   - Comprehensive unit tests in `tests/test_learner_memory_models.py`.

2. **Step 2: Implement Memory Policy & Rules (`memory/policy.py`, `memory/learner_memory.py`)**
   - Writing criteria (confidence thresholds, source attribution).
   - TTL & decay policy (expiry of temporary states, persistence of mastered concepts).
   - Correction and updating mechanisms (superseding old misconceptions).
   - Deletion & GDPR/privacy reset ("forget learner").
   - Unit tests in `tests/test_learner_memory_policy.py`.

3. **Step 3: Storage Schema Migration (`storage/schema.sql`, `storage/corpus_store.py`)**
   - Additive tables in SQLite: `learner_profiles`, `learner_memories`, `learner_memory_audit`.
   - Persistence layer in `memory/store.py` (or integrated into `storage/corpus_store.py`).
   - Verify zero impact on existing `sources` and `chunks` tables.

4. **Step 4: Wire Memory into Tutor Generation Pipeline (`generation/answer.py`, `main.py`)**
   - Pass optional `learner_id` / `session_id` to `generate_grounded_answer()`.
   - Format memory context into prompt prefix.
   - Record updated mastery/misconceptions upon question completion.

5. **Step 5: Retrieval Benchmarking Suite (`benchmark/evaluate_retrieval.py`)** (Addresses BUG-004)
   - Side-by-side evaluation runner for Sparse (BM25) vs Dense vs Hybrid.
   - Computes `Hit@5` and `Recall@5` across the 20 benchmark cases.
