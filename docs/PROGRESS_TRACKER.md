# Progress Tracker — Grounded Multimodal AI Tutor

**Baseline**: 162 / 162 pytest passing (74 regression + 88 memory unit tests)  
**Active Milestone Focus**: Phase 1 (M5 Learner Memory & Retrieval Benchmarking)

---

## Phase 1: M5 Learner Memory + Retrieval Evaluation + Live Vision

| Task ID | Task Description | Target File(s) | Status | Test / Proof |
|:---|:---|:---|:---:|:---|
| **P1.1** | Define Memory Data Models (`LearnerProfile`, `MemoryEntry`, `MasteryState`, `LearnerCorrection`) | `memory/__init__.py`, `memory/models.py` | ✅ Completed | 88/88 passing (`tests/test_learner_memory_models.py`) |
| **P1.2** | Implement Learner Memory Rules (Writing, Expiry/TTL, Correction, Deletion) | `memory/learner_memory.py` | ⏳ Pending | `test_learner_memory.py` |
| **P1.3** | SQLite Persistence & Schema Migration for Memory & Audit Logs | `storage/schema.sql`, `storage/corpus_store.py` | ⏳ Pending | `test_memory_storage.py` |
| **P1.4** | Wire Learner Memory into Generation Context (`ask_tutor`) | `generation/answer.py`, `main.py` | ⏳ Pending | E2E query test |
| **P1.5** | Build Retrieval Comparison Benchmark (BM25 vs. Dense vs. Hybrid) | `benchmark/evaluate_retrieval.py` | ⏳ Pending | Hit@5 & Recall@5 report |
| **P1.6** | Live Vision Test with Multimodal LLM on real rendered slides/frames | `generation/vqa.py`, `tests/test_vqa.py` | ⏳ Pending | Live visual QA test |

---

## Phase 2: M6 Zero Stale Leakage + M7 60+ Case Robustness Suite

| Task ID | Task Description | Target File(s) | Status | Test / Proof |
|:---|:---|:---|:---:|:---|
| **P2.1** | Implement Automated Invalidation & Deprecation Verification Script | `scripts/verify_zero_stale.py` | ⏳ Pending | Zero stale query leak |
| **P2.2** | Build Stale Leakage Adversarial Penetration Test | `tests/test_zero_stale_leakage.py` | ⏳ Pending | 100% rejection of V1 chunks |
| **P2.3** | Expand Benchmark Suite to 60+ Gold Cases | `benchmark/cases.jsonl` | ⏳ Pending | `benchmark/validate.py` (60/60) |
| **P2.4** | Create Prompt Injection & Memory Poisoning Test Suite | `tests/test_security_injection.py` | ⏳ Pending | Refusal on all attacks |
| **P2.5** | Single-Command Test Runner (`run_all_tests.sh`) | `scripts/run_all_tests.sh`, `pytest.ini` | ⏳ Pending | Exit code 0 across 60+ tests |

---

## Phase 3: M8 Latency vs Recall, Final Report & Interactive Demo

| Task ID | Task Description | Target File(s) | Status | Test / Proof |
|:---|:---|:---|:---:|:---|
| **P3.1** | Latency Profiling Instrumentation (TTFT, p50, p95 per stage) | `benchmark/evaluate_m8_tradeoffs.py` | ⏳ Pending | JSON timing report |
| **P3.2** | Speed vs Recall Tradeoff Evaluation across ≥ 2 Configurations | `benchmark/results/m8_tradeoffs.json` | ⏳ Pending | Speed vs Recall Pareto curve |
| **P3.3** | Final Architecture & Empirical Results Report | `docs/FINAL_REPORT.md` | ⏳ Pending | Peer-review ready report |
| **P3.4** | Interactive Demo UI (Video/Slide Synced Player + Memory Inspector) | `demo/app.py` | ⏳ Pending | Live working demo |
