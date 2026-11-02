# Master Roadmap: Grounded Multimodal AI Tutor

**Status**: Active  
**Repository Baseline**: 162 / 162 passing tests (`pytest tests/ -q`)  
**Tracking Documents**:
- Tasks & Progress: [`docs/PROGRESS_TRACKER.md`](file:///home/jonsnow/Desktop/DAT_project/dat_project/docs/PROGRESS_TRACKER.md)
- Bugs & Risks: [`docs/BUG_TRACKER.md`](file:///home/jonsnow/Desktop/DAT_project/dat_project/docs/BUG_TRACKER.md)

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

## Summary of Phases and Owners

1. **Phase 1: M5 Learner Memory + Retrieval Evaluation + Live Vision**
   - **M5 Memory Module**: Design rules for writing, expiry/decay, corrections, and deletion.
   - **Retrieval Comparison**: BM25 vs Dense vs Hybrid evaluated on `Hit@5` and `Recall@5`.
   - **Live Vision Test**: Multi-modal verification with real rendered slide/frame assets.

2. **Phase 2: M6 Zero Stale Leakage + M7 60+ Robustness Test Suite**
   - **M6 Zero Stale Leakage**: Mathematical guarantee that deprecated/superseded lecture editions never surface in queries or citations.
   - **M7 Unified Test Suite**: 60+ benchmark QA cases + adversarial attacks + direct/indirect prompt injection defense. Single-command execution.

3. **Phase 3: M8 Tradeoffs, Final Report & Interactive Demo**
   - **M8 Latency/Recall Pareto Frontier**: Profile TTFT, p50, p95 across fast vs high-accuracy settings.
   - **Final Report & Interactive Demo**: Synchronized video/slide player with live Memory Inspector.
