# Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor

**Status**: Active  
**Baseline Test Suite**: 295 / 295 passing (`pytest -q`, 2026-11-21, M1–M8 unified)  
**Rule**: Every discovered bug must have an ID, severity, root cause analysis, failing test, and verification proof before closing.

---

## Active & Resolved Bug Ledger

| Bug ID | Severity | Status | Module | Summary | Root Cause & Resolution |
|:---:|:---:|:---:|:---:|:---|:---|
| **BUG-001** | P0 | ✅ Resolved | `ingestion/versioning.py` | `TypeError: SourceVersion missing asset_id and is_deprecated` | Dataclass lacked fields; added optional defaults. (Resolved 2026-10-15) |
| **BUG-002** | P1 | ✅ Resolved | `tests/test_real_evidence.py` | SHA-256 length assertion mismatch (`[:16]` slice) | Test sliced 16 chars instead of full 64-char hash. Fixed. (Resolved 2026-10-15) |
| **BUG-003** | P1 | ✅ Resolved | `memory/` | Learner Memory SQLite persistence and grounded answer integration (M5) | Implemented canonical `LearnerMemoryStore` (SQLite WAL, `PRAGMA foreign_keys = ON`, strict JSON serialization), wired into `LearnerMemoryEngine` and `generate_grounded_answer`. Verified with 150 memory tests + 19 store tests + integration suite. (Resolved 2026-11-21) |
| **BUG-004** | P2 | ✅ Resolved | `benchmark/evaluate_retrieval.py` | Retrieval benchmark lacks side-by-side Hit@5 / Recall@5 runner | Characterization runner `benchmark/characterize_performance.py` and evaluation harness implemented comparing Sparse (BM25) vs Dense vs Hybrid + Reranker across 60 benchmark cases. (Resolved 2026-11-21) |
| **BUG-005** | P2 | 🔍 Open | `generation/vqa.py` | Live multimodal VQA needs end-to-end integration test with live model | Unit mocks pass (`tests/test_vqa.py`). Live pipeline requires live API key. Exact verification command: `GEMINI_API_KEY=... python3 -m pytest tests/test_vqa.py -k "test_visual_question_sends_actual_image_payload" -v`. |
| **BUG-006** | P1 | ✅ Resolved | `tests/` | 60+ Test suite and prompt injection coverage not yet unified | 60-case benchmark (`benchmark/cases_60.jsonl`), adversarial prompt injection tests, and version-safety tests unified in `tests/test_red_team_and_eval.py` (all passing). (Resolved 2026-11-21) |
| **BUG-007** | P1 | ✅ Resolved | `tests/test_vqa.py`, `tests/test_real_evidence.py` | Production DB mutation during `pytest` | `test_pdf_citations_retain_unknown_time_bounds` and real evidence tests called `init_db()` / `upsert_source()` against default `data/corpus.db`. Fixed by redirecting to isolated `tmp_path` databases via monkeypatch. Verified zero hash delta across full test runs. (Resolved 2026-11-21) |
| **BUG-008** | P2 | ✅ Resolved | `main.py` | CLI `resolve-citation` database uninitialized bug | Subcommand `resolve-citation` failed when database tables were not yet initialized. Added `init_db()` guard before query execution. (Resolved 2026-11-21) |

---

## Severity Definitions
- **P0 (Blocker)**: System crashes, test suite failure, or data corruption.
- **P1 (Critical)**: Safety violation (stale leakage, prompt injection compromise, silent hallucination).
- **P2 (Major)**: Missing milestone feature or uncalibrated benchmark metrics.
- **P3 (Minor)**: Documentation mismatch, logging quirk, or non-blocking performance degradation.
