# Graph Report - grounded-multimodal-ai-tutor-dat  (2026-11-21)

## Corpus Check
- 67 files · ~195,991 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: .jsonl 2, .db 2, (none) 1)

## Summary
- 1017 nodes · 2769 edges · 44 communities (37 shown, 7 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 395 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7743f182`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- os
- evaluate_modalities.py
- build_chunks
- generate_grounded_answer
- test_source_manifest.py
- test_pdf_rendering.py
- This Week Plan — Grounded Multimodal AI Tutor
- test_abstention_and_version_safety.py
- vqa.py
- main.py
- test_benchmark.py
- test_learner_memory_store.py
- Real Public Lecture to Evidence Path
- Public Corpus Manifest & Provenance Model
- test_ingestion_version_safety.py
- MemoryPolicy
- LearnerMemoryStore
- test_learner_memory_engine.py
- Modality and Perturbation Evaluation Report
- MemoryType
- test_red_team_and_eval.py
- Document
- MemoryEntry
- Repository Audit & Baseline Verification Report
- LearnerMemoryEngine
- test_performance_characterization.py
- Progress Tracker — Grounded Multimodal AI Tutor
- test_memory_generation_integration.py
- FallbackNode
- answer.py
- LearnerCorrection
- Consolidation and Migration Plan: Canonical Repository Unification
- TutorReranker
- MockNode
- M1 — Versioned Evidence Corpus
- ask_tutor
- Benchmark Dataset
- setup_test_db
- Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor
- Master Roadmap: Grounded Multimodal AI Tutor
- setup_test_db

## God Nodes (most connected - your core abstractions)
1. `MemoryEntry` - 74 edges
2. `MemoryType` - 63 edges
3. `generate_grounded_answer()` - 57 edges
4. `LearnerMemoryStore` - 45 edges
5. `MemoryPolicy` - 43 edges
6. `active_chunks()` - 38 edges
7. `MasteryState` - 35 edges
8. `LearnerProfile` - 34 edges
9. `LearnerCorrection` - 34 edges
10. `build_chunks()` - 33 edges

## Surprising Connections (you probably didn't know these)
- `Summary of Phases and Owners` --references--> `generate_grounded_answer()`  [INFERRED]
  docs/MASTER_ROADMAP.md → generation/answer.py
- `What was NOT changed` --references--> `file_content_hash()`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Blockers (must fix before M4/M5)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Files changed` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `P0a — Fix `SourceVersion` dataclass (unblocks 11 failing tests)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py

## Import Cycles
- None detected.

## Communities (44 total, 7 thin omitted)

### Community 0 - "os"
Cohesion: 0.17
Nodes (15): ocr_keyframes(), extract_audio(), extract_keyframes(), _fixed_interval_keyframes(), get_audio_asset_dir(), get_audio_asset_path(), get_keyframe_asset_dir(), Keyframe (+7 more)

### Community 1 - "evaluate_modalities.py"
Cohesion: 0.13
Nodes (13): check_answer_correctness(), create_intelligent_mock_vision_adapter(), main(), MockRetrievalNode, run_modality_evaluation(), run_perturbation_evaluation(), TargetedRetriever, _create_dummy_jpeg() (+5 more)

### Community 2 - "build_chunks"
Cohesion: 0.10
Nodes (20): Config, Chunk ID generation (deterministic), build_chunks(), compute_chunk_id(), _flush_audio(), split_long_segment(), OcrResult, transcribe() (+12 more)

### Community 3 - "generate_grounded_answer"
Cohesion: 0.11
Nodes (16): generate_grounded_answer(), _create_dummy_jpeg(), MockNode, MockRetriever, test_answer_cites_correct_evidence_id_and_asset_metadata(), test_existing_text_only_queries_still_work(), test_max_images_limit_respected(), test_missing_required_image_causes_abstention() (+8 more)

### Community 4 - "test_source_manifest.py"
Cohesion: 0.10
Nodes (13): build_source_version_from_manifest(), get_manifest_asset(), get_manifest_source(), load_manifest(), ManifestValidationError, SourceAssetRecord, validate_manifest(), test_manifest_resolves_configuration() (+5 more)

### Community 5 - "test_pdf_rendering.py"
Cohesion: 0.08
Nodes (17): Key Components:, Files changed, extract_pdf_slides(), parse_srt(), file_content_hash(), text_content_hash(), ingest_official(), upsert_source() (+9 more)

### Community 6 - "This Week Plan — Grounded Multimodal AI Tutor"
Cohesion: 0.05
Nodes (42): 10. P0 Changes Applied (2026-10-15), 11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15), 12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15), 13. M4 Phase 3 — Align Evidence and Evaluate Visual QA (2026-10-16), 2. Actual Test and Benchmark-Validator Results, 3. Exact Commands Used, 4. Evidence and Image-Path Data Flow, 5. Existing Local Image Availability (+34 more)

### Community 7 - "test_abstention_and_version_safety.py"
Cohesion: 0.06
Nodes (22): AbstentionPolicy, DecisionType, compute_stale_leakage(), filter_stale_chunks(), VersionSafeCache, MockNode, SimpleRetriever, test_abstention_policy_empty_nodes_abstains() (+14 more)

### Community 8 - "vqa.py"
Cohesion: 0.07
Nodes (10): Files Changed, BaseVisionAdapter, CallableVisionAdapter, get_vision_adapter(), GoogleGenAIVisionAdapter, LlamaIndexVisionAdapter, load_and_validate_image(), MockVisionAdapter (+2 more)

### Community 9 - "main.py"
Cohesion: 0.12
Nodes (19): 3. Subsystem Canonical Ownership Matrix, E. Frontend, Backend, and API Interfaces, deprecate(), main(), resolve_citation(), run_characterization_cli(), resolve_citation(), _columns() (+11 more)

### Community 10 - "test_benchmark.py"
Cohesion: 0.18
Nodes (3): benchmark_cases(), load_cases(), test_invalid_benchmark_entries_rejected()

### Community 11 - "test_learner_memory_store.py"
Cohesion: 0.15
Nodes (6): SourceSerializationError, _validate_json_source(), test_foreign_keys_and_profile_independence(), test_strict_source_serialization_accepted_types(), test_strict_source_serialization_rejected_types(), test_transaction_rollback()

### Community 12 - "Real Public Lecture to Evidence Path"
Cohesion: 0.18
Nodes (10): 1. Selected Lecture, 2. Source/Provenance, 3. Ingestion Command, 4. Evidence Storage, 5. One Real Evidence Record, 6. One Real Citation, 7. How an Evaluator Navigates to It, 8. How to Reproduce (+2 more)

### Community 13 - "Public Corpus Manifest & Provenance Model"
Cohesion: 0.50
Nodes (4): Cataloged vs Ingested Status, Edition and Version Identity, Provenance, Attribution, and Licensing, Public Corpus Manifest & Provenance Model

### Community 14 - "test_ingestion_version_safety.py"
Cohesion: 0.09
Nodes (31): 1. Repository Audit Findings, Architecture Summary (verified), Failing Tests (12) — Exact Errors, Module Map, Risks, Step-by-step, Test result, W2 priority order (+23 more)

### Community 15 - "MemoryPolicy"
Cohesion: 0.10
Nodes (27): MemoryDecision, MemoryPolicy, MemoryPolicyError, PolicyEvaluation, _validate_unit_interval(), _entry(), FrozenClock, test_confidence_threshold_accept_and_reject() (+19 more)

### Community 16 - "LearnerMemoryStore"
Cohesion: 0.09
Nodes (6): _dt_to_iso(), _iso_to_dt(), LearnerMemoryStore, _serialize_json(), _serialize_source(), test_persistent_in_memory_store_across_calls()

### Community 17 - "test_learner_memory_engine.py"
Cohesion: 0.12
Nodes (28): MemoryNotFound, MemoryRejected, _engine(), FrozenClock, _mem(), test_compact_learner_context_is_labeled_and_excludes_expired(), test_confidence_based_rejection(), test_context_respects_entry_limit_deterministically() (+20 more)

### Community 20 - "Modality and Perturbation Evaluation Report"
Cohesion: 0.50
Nodes (3): 1. Modality Breakdown, 2. Image Perturbation Results, Modality and Perturbation Evaluation Report

### Community 21 - "MemoryType"
Cohesion: 0.08
Nodes (21): 8. Recommended Implementation Order for M5 (Learner Memory), LearnerContext, compute_correction_id(), compute_memory_id(), MasteryStatus, MemoryType, _normalize_mastery_status(), _normalize_memory_type() (+13 more)

### Community 22 - "test_red_team_and_eval.py"
Cohesion: 0.10
Nodes (18): compute_token_f1(), evaluate_retrieval(), print_scorecard(), run_benchmark(), InjectionDefense, run_eval_cli(), test_clean_course_queries_not_flagged_as_injection(), test_compute_token_f1() (+10 more)

### Community 24 - "MemoryEntry"
Cohesion: 0.11
Nodes (35): Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy), Step 4: Reconcile M5 Learner Memory Subsystem, A. Memory Functionality & Architecture, manage_memory(), LearnerProfile, MasteryState, MemoryEntry, test_caller_mutation_of_dict_does_not_mutate_model() (+27 more)

### Community 25 - "Repository Audit & Baseline Verification Report"
Cohesion: 0.11
Nodes (17): 1. Executive Summary, 2. Actual Repository Architecture, 3. Verified Historical Baseline vs. Current Actuals, 4. Verification Commands and Actual Output, 5. Subsystem Status Audit, 6. Audit of Existing Bugs (BUG-001 through BUG-006), 7. Blockers and Dependency Assessment, A. Full Pytest Suite (+9 more)

### Community 26 - "LearnerMemoryEngine"
Cohesion: 0.12
Nodes (3): LearnerMemoryEngine, _topic_key(), test_engine_persistence_across_restarts()

### Community 27 - "test_performance_characterization.py"
Cohesion: 0.18
Nodes (11): compute_percentiles(), evaluate_configuration(), run_characterization(), TutorRetriever, test_compute_percentiles_empty_list(), test_compute_percentiles_known_values(), test_performance_characterization_report_structure(), test_retriever_dense_only_mode() (+3 more)

### Community 28 - "Progress Tracker — Grounded Multimodal AI Tutor"
Cohesion: 0.50
Nodes (3): Phase 2: M6 Zero Stale Leakage + M7 60+ Case Robustness Suite, Phase 3: M8 Latency vs Recall, Final Report & Interactive Demo, Progress Tracker — Grounded Multimodal AI Tutor

### Community 29 - "test_memory_generation_integration.py"
Cohesion: 0.15
Nodes (5): file_store(), mem_store(), MockRetriever, test_abstention_triggers_when_corpus_evidence_absent_despite_memory(), test_pedagogical_context_injection_zero_citation_leakage()

### Community 30 - "FallbackNode"
Cohesion: 0.17
Nodes (5): FallbackNode, PurePythonBM25, PurePythonDenseSim, tokenize(), test_reranker_boosts_visual_query_for_visual_nodes()

### Community 31 - "answer.py"
Cohesion: 0.11
Nodes (6): extract_tokens(), main(), main(), test_backwards_compatibility_adapter_methods(), test_evidence_alignment_report_schema_and_completeness(), test_benchmark_60_cases_schema_and_distribution()

### Community 32 - "LearnerCorrection"
Cohesion: 0.11
Nodes (8): Phase 1: M5 Learner Memory + Retrieval Evaluation + Live Vision, LearnerCorrection, test_learner_correction_creation_and_attribution(), test_learner_correction_serialization_round_trip(), test_learner_profile_serialization_round_trip(), test_memory_entry_serialization_round_trip(), test_apply_correction_semantics(), test_canonical_model_round_trips()

### Community 33 - "Consolidation and Migration Plan: Canonical Repository Unification"
Cohesion: 0.12
Nodes (15): 1. Executive Summary & Context, 2. Uncommitted Changes & Safety Assessment, 4. Comprehensive File-by-File Migration Table, 5. Proposed Final Canonical Repository Structure, 6. Small, Independently Verifiable Migration Steps, 7. Migration Readiness Checklist, Category A: Unique Files in Nested (Move directly to Root), Category B: Unique Files in Root (Retain Unchanged) (+7 more)

### Community 35 - "TutorReranker"
Cohesion: 0.29
Nodes (3): TutorReranker, test_reranker_handles_empty_nodes(), test_reranker_promotes_exact_code_matches()

### Community 37 - "M1 — Versioned Evidence Corpus"
Cohesion: 0.25
Nodes (7): Architecture, M1 — Versioned Evidence Corpus, Roadmap for the following weeks (not built yet), Running it, What "done" means for M1, per the spec, What's already tested, Why SQLite and not a vector DB yet

### Community 38 - "ask_tutor"
Cohesion: 1.00
Nodes (3): M5 — Learner Memory, Step-by-step, ask_tutor()

### Community 39 - "Benchmark Dataset"
Cohesion: 0.33
Nodes (4): Benchmark Dataset, Labelling Policy, Schema, Validation

### Community 43 - "Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor"
Cohesion: 0.50
Nodes (3): Active & Resolved Bug Ledger, Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor, Severity Definitions

### Community 44 - "Master Roadmap: Grounded Multimodal AI Tutor"
Cohesion: 0.50
Nodes (3): Architecture & Milestone Mapping, Master Roadmap: Grounded Multimodal AI Tutor, Summary of Phases and Owners

## Knowledge Gaps
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate_grounded_answer()` connect `generate_grounded_answer` to `evaluate_modalities.py`, `test_pdf_rendering.py`, `ask_tutor`, `test_abstention_and_version_safety.py`, `vqa.py`, `main.py`, `Master Roadmap: Grounded Multimodal AI Tutor`, `test_ingestion_version_safety.py`, `MemoryType`, `test_red_team_and_eval.py`, `MemoryEntry`, `test_memory_generation_integration.py`, `answer.py`?**
  _High betweenness centrality (0.123) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `MemoryEntry` (e.g. with `Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy)` and `Step 4: Reconcile M5 Learner Memory Subsystem`) actually correct?**
  _`MemoryEntry` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Should `evaluate_modalities.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1253968253968254 - nodes in this community are weakly interconnected._
- **Why does `MemoryEntry` connect `MemoryEntry` to `LearnerCorrection`, `main.py`, `test_learner_memory_store.py`, `MemoryPolicy`, `LearnerMemoryStore`, `test_learner_memory_engine.py`, `MemoryType`, `LearnerMemoryEngine`, `test_memory_generation_integration.py`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Are the 44 inferred relationships involving `MemoryType` (e.g. with `Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy)` and `8. Recommended Implementation Order for M5 (Learner Memory)`) actually correct?**
  _`MemoryType` has 44 INFERRED edges - model-reasoned connections that need verification._
- **Should `build_chunks` be split into smaller, more focused modules?**
  _Cohesion score 0.10158730158730159 - nodes in this community are weakly interconnected._
- **Why does `LearnerMemoryStore` connect `LearnerMemoryStore` to `LearnerCorrection`, `ask_tutor`, `main.py`, `test_learner_memory_store.py`, `MemoryPolicy`, `MemoryType`, `MemoryEntry`, `LearnerMemoryEngine`, `test_memory_generation_integration.py`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._