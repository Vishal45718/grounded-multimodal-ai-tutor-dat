# Master Roadmap: Grounded Multimodal AI Tutor

**Status**: Consolidated Single Repository (Milestones M1–M8 Implemented)  
**Repository Baseline**: 295 / 295 passing tests (`pytest -q`, 2026-11-21)  
**Tracking Documents**:
- Tasks & Progress: [`docs/PROGRESS_TRACKER.md`](file:///home/jonsnow/Desktop/grounded-multimodal-ai-tutor-dat/docs/PROGRESS_TRACKER.md)
- Bugs & Risks: [`docs/BUG_TRACKER.md`](file:///home/jonsnow/Desktop/grounded-multimodal-ai-tutor-dat/docs/BUG_TRACKER.md)

---

## Architecture & Milestone Mapping

```
                                  [Video / PDF Assets]
                                           │
                                    (M1: Ingestion)
                                           ▼
                                 [Versioned Corpus DB]
                                           │
                 ┌─────────────────────────┴────────────────────────┐
                 ▼                                                  ▼
     (Sparse: BM25 Index)                                (Dense: Qdrant / Embeddings)
                 │                                                  │
                 └─────────────────────────┬────────────────────────┘
                                           ▼
                                (M2: Hybrid Retrieval)
                                   Hit@5 & Recall@5
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
             (M4: Multimodal VQA)                   (M5: Learner Memory)
         Real Keyframes / Slides OCR              Write | TTL | Fix | Delete
                        │                                     │
                        └──────────────────┬──────────────────┘
                                           ▼
                                 (M3: Grounded Answer)
                               Strict Non-Stale Citations
                                           │
                 ┌─────────────────────────┴────────────────────────┐
                 ▼                                                  ▼
     (M6: Zero Stale Invalidation)                         (M7: 60+ Test Suite)
         Zero Leakage Verification                         Prompt Injections & E2E
                                           │
                                           ▼
                                 (M8: Final Evaluation)
                            Latency vs. Recall & Live Demo
```

---

## Milestone Status Summary (M1–M8)

| Milestone | Capability | Status | Primary Artifacts |
|:---|:---|:---:|:---|
| **M1: Ingestion** | Video/audio extraction, Whisper ASR, OCR, deterministic chunking, content hash versioning | ✅ Complete | `ingestion/`, `storage/schema.sql`, `storage/corpus_store.py` |
| **M2: Hybrid Retrieval** | BM25 sparse + dense embeddings + Reciprocal Rank Fusion + cross-encoder reranking | ✅ Complete | `retrieval/retriever.py`, `retrieval/reranker.py` |
| **M3: Grounded Generation** | Strict timestamp `[mm:ss]` & slide citations; zero-hallucination guardrails | ✅ Complete | `generation/answer.py`, `generation/citation_resolver.py` |
| **M4: Multimodal VQA** | Visual question answering over real keyframes/slides; mock + live vision adapters | 🔍 Mocks Pass (Live key pending) | `generation/vqa.py`, `tests/test_vqa.py` (BUG-005) |
| **M5: Learner Memory** | SQLite WAL store (`LearnerMemoryStore`), policy/engine, pedagogical context, GDPR purge | ✅ Complete | `memory/store.py`, `memory/engine.py`, `memory/policy.py`, `memory/models.py` |
| **M6: Abstention & Version Safety** | Automated invalidation of stale/deprecated editions; calibrated refusal on low confidence | ✅ Complete | `guardrails/abstention_policy.py`, `tests/test_abstention_and_version_safety.py` |
| **M7: 60-Case Robustness Suite** | 60-case benchmark QA suite; direct/indirect prompt injection defense; adversarial testing | ✅ Complete | `benchmark/cases_60.jsonl`, `tests/test_red_team_and_eval.py` |
| **M8: Tradeoffs & Interactive Demo** | Latency vs Recall Pareto characterization; FastAPI interactive tutor with video player & memory inspector | ✅ Complete | `benchmark/characterize_performance.py`, `demo/app.py`, `demo/helpers.py` |

---

## Phase Execution Summary

1. **Phase 1: M5 Learner Memory + Retrieval Evaluation + Live Vision (✅ Complete / Live Key Pending)**
   - **M5 Memory Module**: Canonical `LearnerMemoryStore` implemented with SQLite WAL, foreign key enforcement, strict JSON serialization, and full round-trip verification. Integrated into `LearnerMemoryEngine` and `generate_grounded_answer`.
   - **Retrieval Comparison**: BM25 vs Dense vs Hybrid + Reranker evaluated across the 60-case benchmark.
   - **Live Vision Test**: Multi-modal verification verified with unit mocks; live Gemini/OpenAI vision integration documented in BUG-005.

2. **Phase 2: M6 Zero Stale Leakage + M7 60+ Robustness Test Suite (✅ Complete)**
   - **M6 Zero Stale Leakage**: Mathematical guarantee that deprecated/superseded lecture editions never surface in queries or citations.
   - **M7 Unified Test Suite**: 60-case benchmark QA suite and adversarial red-teaming (prompt injection, memory poisoning) verified in `tests/test_red_team_and_eval.py`.

3. **Phase 3: M8 Tradeoffs, Final Report & Interactive Demo (✅ Complete)**
   - **M8 Latency/Recall Pareto Frontier**: Profiled TTFT, p50, p95 across fast vs high-accuracy settings via `benchmark/characterize_performance.py`.
   - **Interactive Demo UI**: FastAPI interactive application (`demo/app.py`) featuring synchronized video/slide jumping, direct evidence citations, and interactive Learner Memory Inspector.
