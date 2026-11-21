# Consolidation and Migration Plan: Canonical Repository Unification

**Document Status:** Ready for Review  
**Date:** 2026-11-21  
**Milestone Focus:** Repository Unification across M1–M8  

---

## 1. Executive Summary & Context

The repository currently exists in a split state due to divergent work by two contributors:
1. **Root (`/`)**: Holds foundational architectural audits, bug trackers, the rich M5.1/M5.2 selective learner-memory models, policy engine, and in-memory engine (`memory/models.py`, `memory/policy.py`, `memory/engine.py`), backed by **224 passing unit tests** in `tests/`.
2. **Nested (`grounded-multimodal-ai-tutor-dat/`)**: Holds the recent additions for M2 (BM25 + RRF + Reranker), M6 (Abstention & Version Safety guardrails), M7 (60-case benchmark harness and red-team injection tests), M8 (latency/recall performance characterization), and SQLite learner memory persistence (`memory/store.py`), with **129 passing tests** in `grounded-multimodal-ai-tutor-dat/tests/`.

### Core Directive
Consolidate the codebase into one canonical root repository without modifying application code during this planning phase, preserving all Git history, avoiding destructive overwrites, retaining the rich root memory models, and preserving the nested M2/M6/M7/M8 subsystems and SQLite persistence.

---

## 2. Uncommitted Changes & Safety Assessment

Running `git status --porcelain` reveals:
- **No uncommitted source code modifications (`.py`, `.md`, `.sql`)** exist in either the root or nested directory.
- The only unstaged changes are runtime artifacts:
  - Tracked binary SQLite databases: `data/corpus.db`, `grounded-multimodal-ai-tutor-dat/data/corpus.db`.
  - Stale Python bytecode files in tracked `__pycache__/*.pyc`.
  - Untracked cache file: `graphify-out/cache/last_query_stamp`.
- **Verdict:** Safe to proceed with migration planning. No user application edits will be lost.

---

## 3. Subsystem Canonical Ownership Matrix

| Subsystem | Canonical Implementation | Rationale |
|:---|:---:|:---|
| **M1: Ingestion & Storage** | **Root + Nested Schema** | Root has verified provenance & edition isolation; nested has schema columns (`edition_id`, `page_number`, `status`). Merge non-destructively. |
| **M2: Retrieval & Reranking** | **Nested** | Nested implements pure-Python BM25 with length normalization, dense vector cosine similarity, RRF, and `TutorReranker`. |
| **M3: Grounded Answers** | **Nested (with Root Context)** | Nested `answer.py` incorporates injection defense, abstention policy, version-safe caching, and citation sanitization. |
| **M4: Multimodal Evaluation** | **Root + Nested** | Both root (20 cases, 220 slide keyframes) and nested (mock/perturbation harnesses) are compatible; root contains the full suite of slide rendering tests. |
| **M5: Learner Memory Models & Engine** | **Root** | Root contains the authoritative 491-line `memory/models.py` (validated dataclasses, TTL, corrections, confidence) and `memory/engine.py` (224 passing tests). |
| **M5: Learner Memory SQLite Store** | **Nested** | Nested `memory/store.py` provides SQLite persistence (`data/learner_memory.db`). |
| **M6: Guardrails & Abstention** | **Nested** | Unique to nested: `guardrails/abstention_policy.py`, `guardrails/injection_defense.py`, `guardrails/version_safety.py`. |
| **M7: 60-Case Eval Harness & Red Team** | **Nested** | Unique to nested: `benchmark/cases_60.jsonl`, `benchmark/run_eval.py`, `tests/test_red_team_and_eval.py`. |
| **M8: Performance Characterization** | **Nested** | Unique to nested: `benchmark/characterize_performance.py`, `tests/test_performance_characterization.py`. |
| **CLI (`main.py`)** | **Nested (adapted for root M5)** | Nested provides full M1–M8 CLI (`ingest`, `deprecate`, `resolve-citation`, `query`, `memory`, `eval`, `characterize`). |

---

## 4. Comprehensive File-by-File Migration Table

### Category A: Unique Files in Nested (Move directly to Root)

These files exist *only* in `grounded-multimodal-ai-tutor-dat/` and have no collision in the root.

| File Path in Nested | Target Canonical Path in Root | Action | Verification |
|:---|:---|:---:|:---|
| `guardrails/__init__.py` | `guardrails/__init__.py` | Move/Copy | `python3 -c "import guardrails"` |
| `guardrails/abstention_policy.py` | `guardrails/abstention_policy.py` | Move/Copy | Unit test imports |
| `guardrails/injection_defense.py` | `guardrails/injection_defense.py` | Move/Copy | Unit test imports |
| `guardrails/version_safety.py` | `guardrails/version_safety.py` | Move/Copy | Unit test imports |
| `retrieval/reranker.py` | `retrieval/reranker.py` | Move/Copy | `python3 -c "from retrieval.reranker import TutorReranker"` |
| `benchmark/cases_60.jsonl` | `benchmark/cases_60.jsonl` | Move/Copy | File validation (60 lines JSON) |
| `benchmark/run_eval.py` | `benchmark/run_eval.py` | Move/Copy | `python3 benchmark/run_eval.py --help` |
| `benchmark/characterize_performance.py` | `benchmark/characterize_performance.py` | Move/Copy | `python3 benchmark/characterize_performance.py --help` |
| `benchmark/results/evaluation_report.json` | `benchmark/results/evaluation_report.json` | Move/Copy | Valid JSON check |
| `benchmark/results/performance_characterization.json` | `benchmark/results/performance_characterization.json` | Move/Copy | Valid JSON check |
| `data/learner_memory.db` | `data/learner_memory.db` | Move/Copy | SQLite integrity check |
| `tests/test_abstention_and_version_safety.py` | `tests/test_abstention_and_version_safety.py` | Move/Copy | `pytest tests/test_abstention_and_version_safety.py` |
| `tests/test_performance_characterization.py` | `tests/test_performance_characterization.py` | Move/Copy | `pytest tests/test_performance_characterization.py` |
| `tests/test_red_team_and_eval.py` | `tests/test_red_team_and_eval.py` | Move/Copy | `pytest tests/test_red_team_and_eval.py` |

---

### Category B: Unique Files in Root (Retain Unchanged)

These files exist *only* in root and define the rigorous testing and architectural baselines.

| File Path in Root | Action | Role / Notes |
|:---|:---:|:---|
| `memory/engine.py` | Retain | Root M5.2 in-memory learner memory engine (23 tests). |
| `tests/test_learner_memory_engine.py` | Retain | 23 tests validating learner profiles, confidence, misconceptions, and deletions. |
| `tests/test_learner_memory_models.py` | Retain | 88 tests validating data models, TTL, serialization, and immutability. |
| `tests/test_learner_memory_policy.py` | Retain | 39 tests validating acceptance, retention, decay, and correction policies. |
| `docs/BUG_TRACKER.md` | Retain | Active bug ledger and root-cause analysis (BUG-001 through BUG-006). |
| `docs/MASTER_ROADMAP.md` | Retain | Master roadmap for M1–M8. |
| `docs/PROGRESS_TRACKER.md` | Retain | Task breakdown and implementation verification log. |
| `docs/REPOSITORY_AUDIT.md` | Retain | Comprehensive baseline audit report. |
| `data/keyframes/cs50-lec01/44469ebd8de3e045/` | Retain | 220 local extracted JPEG slide images (Slides 1–220). |
| `.agents/` | Retain | Antigravity and Graphify agent rules and workflows. |

---

### Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy)

| File | Root Version | Nested Version | Recommended Resolution Strategy |
|:---|:---|:---|:---|
| **`memory/models.py`** | 491 lines: Rich `LearnerProfile`, `MemoryEntry`, `MasteryState`, `LearnerCorrection`, `MemoryType`, `InteractionContext`. 88 unit tests. | 69 lines: Simplified `LearnerMemoryItem`, `MemoryRevision`, `LearnerProfile`. 11 unit tests. | **Keep Root as Primary Canonical.** Add alias adapters or backwards-compatible mapping for any nested `LearnerMemoryItem` attributes required by SQLite store. |
| **`memory/policy.py`** | 211 lines: Rigorous policy with confidence thresholds, retention decay, GDPR wipe, audit trail. 39 unit tests. | 69 lines: Simplified policy for write/expiry/purge. | **Keep Root as Primary Canonical.** |
| **`memory/store.py`** | Does not exist in root. | 404 lines: SQLite database store (`data/learner_memory.db`) with tables `learner_memory` and `learner_memory_history`. | **Move to `memory/store.py` in Root.** Wire it to serialize Root's rich `MemoryEntry` / `LearnerProfile` models into SQLite columns. Rename nested test `test_learner_memory.py` to `test_learner_memory_store.py`. |
| **`memory/__init__.py`** | Exports rich models and `LearnerMemoryEngine`. | Exports simplified items. | **Reconcile in Root:** Export `LearnerProfile`, `MemoryEntry`, `MasteryState`, `LearnerCorrection`, `LearnerMemoryEngine`, and `LearnerMemoryStore`. |
| **`generation/answer.py`** | 251 lines: Basic citation checking and visual loading. Lacks guardrails. | 198 lines: Integrates `guardrails.abstention_policy`, `guardrails.injection_defense`, `guardrails.version_safety`, and query caching. | **Adopt Nested Version into Root.** Retain root's explicit typing and parameter compatibility. |
| **`retrieval/retriever.py`** | 111 lines: Fallback keyword counter; depends heavily on external `llama_index`. | 253 lines: Self-contained pure-Python BM25 (with IDF & length norm), dense cosine similarity, RRF, and neural/lexical reranking. | **Adopt Nested Version into Root.** Completely eliminates offline ranking degradation. |
| **`main.py`** | 148 lines: CLI supporting `ingest`, `deprecate`, `resolve-citation`, `query`. | 280 lines: Full CLI supporting `ingest`, `deprecate`, `resolve-citation`, `query`, `memory`, `eval`, and `characterize`. | **Adopt Nested Version into Root.** Adjust `manage_memory` CLI function to interface cleanly with Root's unified memory engine and store. |
| **`config.py`** | Has `vision_backend="gemini"`. Missing memory DB path. | Adds `memory_db_path`, `vision_backend="mock"`, `vision_model`. | **Merge into Root:** Include `memory_db_path`, keep safe default `vision_backend = os.environ.get("VISION_BACKEND", "mock")` so offline runs do not crash without API keys. |
| **`storage/schema.sql`** | 32 lines: Basic sources and chunks tables. | 45 lines: Includes columns for `edition_id`, `status`, `error_message`, `page_number`, `extraction_method`, and licensing. | **Adopt Nested Version into Root.** Enables full slide provenance and error tracking. |
| **`storage/corpus_store.py`** | Line 404: `SELECT c.*, COALESCE(c.edition_id, s.course_edition) AS course_edition`. | Line 404: `SELECT c.*`. | **Keep Root Version:** The `COALESCE` clause is strictly required by `tests/test_source_manifest.py` for edition fallback. |
| **`ingestion/chunker.py`** | Preserves `edition_id` in chunking calls. | Omitted `edition_id` parameter. | **Keep Root Version.** Preserves multi-edition integrity. |
| **`ingestion/versioning.py`** | Minor field declaration ordering. | Identical logic. | **Keep Root Version.** |
| **`ingestion/ocr.py`** | Detailed error preservation. | Refactored parameters. | **Keep Root Version.** All 4 root OCR tests pass cleanly against it. |
| **`pytest.ini`** | `pythonpath = .` | `pythonpath = .` | **Update Root:** Add `testpaths = tests` and `norecursedirs = grounded-multimodal-ai-tutor-dat` to prevent discovery collisions during migration. |
| **`requirements.txt`** | Pins `PyMuPDF==1.28.2`. | `PyMuPDF>=1.23.0`. | **Keep Root Version** (or broaden to `>=1.23.0`). |
| **`test_m2_m3.py`** | Lacks safe formatting for `start_sec=None`. | Formats slide page number when `start_sec` is None. | **Adopt Nested Version into Root.** |
| **`tests/test_modality_evaluation.py`** | 225 lines (6 comprehensive tests). | 140 lines (6 tests). | **Keep Root Version** (superseded root version contains full fixture validation). |
| **`tests/test_pdf_rendering.py`** | 370 lines (9 comprehensive tests). | 130 lines (9 tests). | **Keep Root Version.** |
| **`tests/test_vqa.py`** | 446 lines (12 comprehensive tests). | 199 lines (12 tests). | **Keep Root Version.** |

---

## 5. Proposed Final Canonical Repository Structure

```
grounded-multimodal-ai-tutor-dat/
├── .agents/                               # Knowledge graph & agent rules
├── benchmark/
│   ├── cases.jsonl                        # 20 gold evaluation QA cases
│   ├── cases_60.jsonl                     # 60 extended QA & adversarial cases (M7)
│   ├── evaluate_modalities.py             # 3-condition modality evaluation harness (M4)
│   ├── validate.py                        # Benchmark schema and DB validator
│   ├── run_eval.py                        # Automated RAG evaluation & scorecard (M7)
│   ├── characterize_performance.py        # Latency & recall trade-off runner (M8)
│   └── results/                           # JSON reports and performance artifacts
├── config.py                              # Unified environment configuration
├── data/
│   ├── corpus.db                          # Active SQLite corpus DB (530 chunks)
│   ├── learner_memory.db                  # Persistent SQLite learner memory DB (M5)
│   ├── source_manifest.json               # Canonical course manifest
│   ├── source_manifest.yaml               # YAML manifest definition
│   └── keyframes/                         # 220 local extracted JPEG slide images
├── docs/
│   ├── BUG_TRACKER.md                     # Active and historical bug ledger
│   ├── CONSOLIDATION_PLAN.md              # This document
│   ├── MASTER_ROADMAP.md                  # Milestone mapping (M1–M8)
│   ├── PROGRESS_TRACKER.md                # Task-level implementation tracker
│   └── REPOSITORY_AUDIT.md                # Empirical baseline audit report
├── generation/
│   ├── answer.py                          # Grounded answer generation + guardrails
│   └── vqa.py                             # Multimodal vision adapters
├── guardrails/                            # M6 & M7 safety layers
│   ├── __init__.py
│   ├── abstention_policy.py               # Abstention gating (Answer/Qualify/Abstain)
│   ├── injection_defense.py               # Prompt injection delimiters & sanitization
│   └── version_safety.py                  # Zero stale leakage filters & query cache
├── ingestion/
│   ├── chunker.py                         # Deterministic chunking & duration limits
│   ├── manifest.py                        # Manifest validator & loader
│   ├── ocr.py                             # PyMuPDF rendering & keyframe OCR
│   ├── transcriber.py                     # Whisper ASR transcription
│   ├── versioning.py                      # Content hashing & SourceVersion
│   └── video_processor.py                 # Ffmpeg audio & keyframe extraction
├── main.py                                # Canonical CLI (ingest, query, memory, eval, characterize)
├── memory/                                # Unified M5 selective learner memory
│   ├── __init__.py                        # Unified exports
│   ├── engine.py                          # In-memory policy engine (M5.2)
│   ├── models.py                          # Comprehensive data models (M5.1)
│   ├── policy.py                          # Lifecycle, TTL, correction & deletion policy
│   └── store.py                           # SQLite durable persistence (M5.3)
├── retrieval/
│   ├── reranker.py                        # Composite neural/lexical reranker (M2/M8)
│   └── retriever.py                       # Pure-Python BM25 + Dense + RRF hybrid retriever
├── scripts/
│   └── ingest_official.py                 # Direct Harvard OCW CDN ingestion utility
├── storage/
│   ├── corpus_store.py                    # Corpus SQLite CRUD API & active_chunks()
│   └── schema.sql                         # Full database schema with provenance
├── tests/                                 # Consolidated test suite (Target: ~270+ passing)
│   ├── test_abstention_and_version_safety.py  # M6 tests (15 tests)
│   ├── test_benchmark.py                      # Schema tests (9 tests)
│   ├── test_ingestion_version_safety.py       # Ingestion version safety (15 tests)
│   ├── test_learner_memory_engine.py          # Root memory engine (23 tests)
│   ├── test_learner_memory_models.py          # Root memory models (88 tests)
│   ├── test_learner_memory_policy.py          # Root memory policy (39 tests)
│   ├── test_learner_memory_store.py           # SQLite store tests (11 tests)
│   ├── test_modality_evaluation.py            # Modality tests (6 tests)
│   ├── test_ocr.py                            # OCR tests (4 tests)
│   ├── test_pdf_rendering.py                  # Slide rendering tests (9 tests)
│   ├── test_performance_characterization.py   # M8 performance tests (10 tests)
│   ├── test_real_evidence.py                  # Real evidence tests (13 tests)
│   ├── test_red_team_and_eval.py              # M7 red team & eval tests (19 tests)
│   ├── test_source_manifest.py                # Manifest tests (6 tests)
│   └── test_vqa.py                            # Multimodal VQA tests (12 tests)
├── pytest.ini                             # Scoped to tests/, avoiding subfolder collisions
└── requirements.txt                       # Unified Python dependencies
```

---

## 6. Small, Independently Verifiable Migration Steps

Each step is atomic, verifiable via test execution, and rollback-safe:

### Step 1: Fix Test Discovery Collision (`pytest.ini`)
- **Action:** Update `pytest.ini` in root to restrict collection:
  ```ini
  [pytest]
  testpaths = tests
  norecursedirs = grounded-multimodal-ai-tutor-dat .git data
  pythonpath = .
  ```
- **Verification:** Run `pytest tests` from root. Ensure all **224 root tests** pass without collection mismatch errors.

### Step 2: Migrate Non-Conflicting Nested Modules
- **Action:** Copy unique directories and files into root:
  - Copy `grounded-multimodal-ai-tutor-dat/guardrails/` → `guardrails/`
  - Copy `grounded-multimodal-ai-tutor-dat/retrieval/reranker.py` → `retrieval/reranker.py`
  - Copy `grounded-multimodal-ai-tutor-dat/benchmark/cases_60.jsonl` → `benchmark/cases_60.jsonl`
  - Copy `grounded-multimodal-ai-tutor-dat/benchmark/run_eval.py` → `benchmark/run_eval.py`
  - Copy `grounded-multimodal-ai-tutor-dat/benchmark/characterize_performance.py` → `benchmark/characterize_performance.py`
  - Copy `grounded-multimodal-ai-tutor-dat/data/learner_memory.db` → `data/learner_memory.db`
  - Copy new test files into `tests/`:
    - `test_abstention_and_version_safety.py`
    - `test_performance_characterization.py`
    - `test_red_team_and_eval.py`
- **Verification:** Run `pytest tests/test_abstention_and_version_safety.py tests/test_performance_characterization.py tests/test_red_team_and_eval.py`.

### Step 3: Integrate Retrieval, Storage Schema, and Guarded Generation
- **Action:**
  - Update `storage/schema.sql` with provenance columns while keeping root `storage/corpus_store.py`.
  - Update `retrieval/retriever.py` with pure-Python BM25 + Dense + RRF + Reranker.
  - Update `generation/answer.py` with abstention gating, injection defense, and query cache.
  - Update `config.py` with `memory_db_path` and `vision_backend = "mock"`.
- **Verification:** Run `pytest tests/test_benchmark.py tests/test_ingestion_version_safety.py tests/test_modality_evaluation.py tests/test_real_evidence.py tests/test_vqa.py`.

### Step 4: Reconcile M5 Learner Memory Subsystem
- **Action:**
  - Retain root `memory/models.py`, `memory/policy.py`, and `memory/engine.py`.
  - Bring nested `memory/store.py` into root as `memory/store.py`.
  - Ensure `memory/store.py` integrates cleanly with root's `LearnerProfile` and `MemoryEntry`.
  - Bring `grounded-multimodal-ai-tutor-dat/tests/test_learner_memory.py` into root as `tests/test_learner_memory_store.py`.
  - Expose unified API in `memory/__init__.py`.
- **Verification:** Run `pytest tests/test_learner_memory_*.py`. Ensure all 150+ root memory tests and SQLite store tests pass.

### Step 5: Update Root CLI & E2E Validation
- **Action:** Update root `main.py` and `test_m2_m3.py` to support all subcommands (`query`, `memory`, `eval`, `characterize`).
- **Verification:**
  - Run full test suite: `pytest -v` (expected: ~270+ passing tests).
  - Run benchmark validator: `python3 benchmark/validate.py`.
  - Run M7 eval test: `python3 main.py eval --mode mock`.
  - Run M8 characterization: `python3 main.py characterize`.

### Step 6: Final Housekeeping & Archival of Nested Directory
- **Action:** Only after Steps 1–5 are verified, remove or git-archive `grounded-multimodal-ai-tutor-dat/`. Clean up tracked `.pyc` files and commit changes.

---

## 7. Migration Readiness Checklist

- [x] Zero application code touched during planning.
- [x] Git working tree status verified (no uncommitted source edits).
- [x] All 224 root unit tests verified passing.
- [x] All 129 nested unit tests verified passing.
- [x] File-by-file mapping completed.
- [x] Preservation plan for root M5 and nested M2/M6/M7/M8 defined.
- [ ] User approval received to proceed with implementation.
