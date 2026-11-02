# Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor

**Status**: Active  
**Baseline Test Suite**: 162 / 162 passing  
**Rule**: Every discovered bug must have an ID, severity, root cause analysis, failing test, and verification proof before closing.

---

## Active & Resolved Bug Ledger

| Bug ID | Severity | Status | Module | Summary | Root Cause & Resolution |
|:---:|:---:|:---:|:---:|:---|:---|
| **BUG-001** | P0 | ✅ Resolved | `ingestion/versioning.py` | `TypeError: SourceVersion missing asset_id and is_deprecated` | Dataclass lacked fields; added optional defaults. (Resolved 2026-10-15) |
| **BUG-002** | P1 | ✅ Resolved | `tests/test_real_evidence.py` | SHA-256 length assertion mismatch (`[:16]` slice) | Test sliced 16 chars instead of full 64-char hash. Fixed. (Resolved 2026-10-15) |
| **BUG-003** | P1 | 🔍 Open | `memory/` | Learner Memory Unimplemented | Foundational models defined (Task P1.1, 88 tests); remains open until policy engine (P1.2), SQLite persistence (P1.3), and answer generation integration (P1.4) are verified. |
| **BUG-004** | P2 | 🔍 Open | `benchmark/evaluate_retrieval.py` | Retrieval benchmark lacks side-by-side Hit@5 / Recall@5 runner | Sparse vs Dense vs Hybrid runner needed for Task P1.5. |
| **BUG-005** | P2 | 🔍 Open | `generation/vqa.py` | Live multimodal VQA needs end-to-end integration test with live model | Unit mocks pass (test_vqa.py), live pipeline execution pending (Task P1.6). |
| **BUG-006** | P1 | 🔍 Open | `tests/` | 60+ Test suite and prompt injection coverage not yet unified | Current test count is 74 unit tests; comprehensive 60+ benchmark QA cases + adversarial tests needed. |

---

## Severity Definitions
- **P0 (Blocker)**: System crashes, test suite failure, or data corruption.
- **P1 (Critical)**: Safety violation (stale leakage, prompt injection compromise, silent hallucination).
- **P2 (Major)**: Missing milestone feature or uncalibrated benchmark metrics.
- **P3 (Minor)**: Documentation mismatch, logging quirk, or non-blocking performance degradation.
