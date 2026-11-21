# Graph Report - grounded-multimodal-ai-tutor-dat  (2026-11-21)

## Corpus Check
- 73 files · ~207,430 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: .jsonl 2, .db 2, (none) 1)

## Summary
- 1196 nodes · 3244 edges · 61 communities (52 shown, 9 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 418 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bf705d5c`
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
- AbstentionPolicy
- vqa.py
- test_real_evidence.py
- test_benchmark.py
- _validate_json_source
- Real Public Lecture to Evidence Path
- helpers.py
- test_ingestion_version_safety.py
- MemoryPolicy
- LearnerMemoryStore
- test_learner_memory_engine.py
- Modality and Perturbation Evaluation Report
- Any
- test_red_team_and_eval.py
- app.py
- test_learner_memory_models.py
- Repository Audit & Baseline Verification Report
- LearnerMemoryEngine
- TutorRetriever
- Progress Tracker — Grounded Multimodal AI Tutor
- test_pedagogical_context_injection_zero_citation_leakage
- FallbackNode
- run_eval.py
- LearnerCorrection
- Consolidation and Migration Plan: Canonical Repository Unification
- TutorReranker
- upload_ingest.py
- M1 — Versioned Evidence Corpus
- MemoryEntry
- Benchmark Dataset
- main.py
- VersionSafeCache
- store.py
- Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor
- Master Roadmap: Grounded Multimodal AI Tutor
- Grounded Multimodal AI Tutor (DAT Tutor)
- LearnerProfile
- answer.py
- ingest_uploaded_video
- json
- versioning.py
- api_list_uploads
- validate_demo_db_path
- VisualPayload
- run_demo_corpus_query
- api_upload
- Document
- file_store
- ask_tutor
- setup_test_db

## God Nodes (most connected - your core abstractions)
1. `MemoryEntry` - 76 edges
2. `MemoryType` - 64 edges
3. `generate_grounded_answer()` - 60 edges
4. `LearnerMemoryStore` - 57 edges
5. `MemoryPolicy` - 43 edges
6. `build_chunks()` - 35 edges
7. `TranscriptSegment` - 35 edges
8. `MasteryState` - 35 edges
9. `SourceVersion` - 34 edges
10. `LearnerMemoryEngine` - 34 edges

## Surprising Connections (you probably didn't know these)
- `Blockers (must fix before M4/M5)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Files changed` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `P0a — Fix `SourceVersion` dataclass (unblocks 11 failing tests)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Milestone Status Summary (M1–M8)` --references--> `LearnerMemoryStore`  [INFERRED]
  docs/MASTER_ROADMAP.md → memory/store.py
- `Architecture & System Overview` --references--> `LearnerMemoryStore`  [INFERRED]
  README.md → memory/store.py

## Import Cycles
- None detected.

## Communities (61 total, 9 thin omitted)

### Community 0 - "os"
Cohesion: 0.12
Nodes (19): extract_keyframes_demo(), validate_upload_video_path(), W2 priority order, Week 1–2 Requirements Audit Report, ocr_keyframes(), extract_audio(), extract_keyframes(), _fixed_interval_keyframes() (+11 more)

### Community 1 - "evaluate_modalities.py"
Cohesion: 0.13
Nodes (13): check_answer_correctness(), create_intelligent_mock_vision_adapter(), main(), MockRetrievalNode, run_modality_evaluation(), run_perturbation_evaluation(), TargetedRetriever, _create_dummy_jpeg() (+5 more)

### Community 2 - "build_chunks"
Cohesion: 0.12
Nodes (22): 1. Repository Audit Findings, Architecture Summary (verified), Chunk ID generation (deterministic), Files changed, Module Map, build_chunks(), compute_chunk_id(), EvidenceChunk (+14 more)

### Community 3 - "generate_grounded_answer"
Cohesion: 0.11
Nodes (17): generate_grounded_answer(), MockVisionAdapter, _create_dummy_jpeg(), MockNode, MockRetriever, test_answer_cites_correct_evidence_id_and_asset_metadata(), test_existing_text_only_queries_still_work(), test_max_images_limit_respected() (+9 more)

### Community 4 - "test_source_manifest.py"
Cohesion: 0.10
Nodes (14): build_source_version_from_manifest(), get_manifest_asset(), get_manifest_source(), load_manifest(), ManifestValidationError, SourceAssetRecord, validate_manifest(), test_manifest_resolves_configuration() (+6 more)

### Community 5 - "test_pdf_rendering.py"
Cohesion: 0.11
Nodes (11): extract_pdf_slides(), _create_synthetic_pdf(), setup_test_db(), test_pdf_deterministic_page_identity(), test_pdf_empty_text_handling(), test_pdf_extracted_text(), test_pdf_image_existence_after_temporary_download_deleted(), test_pdf_page_rendering_creates_valid_jpeg() (+3 more)

### Community 6 - "This Week Plan — Grounded Multimodal AI Tutor"
Cohesion: 0.05
Nodes (39): 11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15), 12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15), 13. M4 Phase 3 — Align Evidence and Evaluate Visual QA (2026-10-16), 2. Actual Test and Benchmark-Validator Results, 3. Exact Commands Used, 4. Evidence and Image-Path Data Flow, 5. Existing Local Image Availability, 6. Blockers and Risks (+31 more)

### Community 7 - "AbstentionPolicy"
Cohesion: 0.14
Nodes (5): AbstentionPolicy, DecisionType, test_abstention_policy_empty_nodes_abstains(), test_abstention_policy_low_similarity_abstains(), test_format_qualification()

### Community 8 - "vqa.py"
Cohesion: 0.11
Nodes (7): Files Changed, BaseVisionAdapter, get_vision_adapter(), GoogleGenAIVisionAdapter, LlamaIndexVisionAdapter, load_and_validate_image(), OpenAIVisionAdapter

### Community 9 - "test_real_evidence.py"
Cohesion: 0.13
Nodes (15): parse_srt(), ingest_official(), resolve_citation(), _columns(), _connect(), init_db(), insert_chunks(), is_source_active() (+7 more)

### Community 10 - "test_benchmark.py"
Cohesion: 0.18
Nodes (3): benchmark_cases(), load_cases(), test_invalid_benchmark_entries_rejected()

### Community 12 - "Real Public Lecture to Evidence Path"
Cohesion: 0.18
Nodes (10): 1. Selected Lecture, 2. Source/Provenance, 3. Ingestion Command, 4. Evidence Storage, 5. One Real Evidence Record, 6. One Real Citation, 7. How an Evaluator Navigates to It, 8. How to Reproduce (+2 more)

### Community 13 - "helpers.py"
Cohesion: 0.08
Nodes (17): build_jump_url(), detect_backend_status(), format_citation_card(), format_citation_time_bounds(), format_time_seconds(), run_tutor_query(), validate_media_path(), isolated_corpus_and_memory_db() (+9 more)

### Community 14 - "test_ingestion_version_safety.py"
Cohesion: 0.15
Nodes (18): Failing Tests (12) — Exact Errors, Risks, Test result, SourceVersion, ingest(), active_chunks(), _make_args(), test_active_chunks_excludes_old_version() (+10 more)

### Community 15 - "MemoryPolicy"
Cohesion: 0.10
Nodes (27): MemoryDecision, MemoryPolicy, MemoryPolicyError, PolicyEvaluation, _validate_unit_interval(), _entry(), FrozenClock, test_confidence_threshold_accept_and_reject() (+19 more)

### Community 16 - "LearnerMemoryStore"
Cohesion: 0.09
Nodes (8): now_utc(), _dt_to_iso(), _iso_to_dt(), LearnerMemoryStore, _to_dt(), _serialize_json(), _serialize_source(), test_persistent_in_memory_store_across_calls()

### Community 17 - "test_learner_memory_engine.py"
Cohesion: 0.12
Nodes (28): MemoryNotFound, MemoryRejected, _engine(), FrozenClock, _mem(), test_compact_learner_context_is_labeled_and_excludes_expired(), test_confidence_based_rejection(), test_context_respects_entry_limit_deterministically() (+20 more)

### Community 20 - "Modality and Perturbation Evaluation Report"
Cohesion: 0.50
Nodes (3): 1. Modality Breakdown, 2. Image Perturbation Results, Modality and Perturbation Evaluation Report

### Community 21 - "Any"
Cohesion: 0.13
Nodes (7): compute_correction_id(), _validate_confidence(), _validate_mastery_level(), _validate_non_empty_str(), _validate_utc_datetime(), test_deterministic_correction_id_computation(), test_memory_entry_serialization_round_trip()

### Community 22 - "test_red_team_and_eval.py"
Cohesion: 0.14
Nodes (13): evaluate_retrieval(), InjectionDefense, test_clean_course_queries_not_flagged_as_injection(), test_detects_prompt_injection_signatures(), test_evaluate_retrieval_miss(), test_evaluate_retrieval_perfect_rank_1(), test_evaluate_retrieval_rank_3(), test_sanitize_citations_all_valid() (+5 more)

### Community 23 - "app.py"
Cohesion: 0.11
Nodes (14): AddMemoryRequest, api_add_memory(), api_clear_uploads(), api_correct_memory(), api_delete_memory(), api_demo_corpus_query(), api_purge_memory(), api_query() (+6 more)

### Community 24 - "test_learner_memory_models.py"
Cohesion: 0.16
Nodes (22): MasteryState, test_empty_content_rejected(), test_empty_correction_fields_rejected(), test_empty_learner_id_rejected_across_models(), test_empty_memory_id_rejected_when_explicitly_passed(), test_empty_topic_rejected(), test_expires_at_cannot_precede_created_at(), test_invalid_confidence_rejection_mastery_state() (+14 more)

### Community 25 - "Repository Audit & Baseline Verification Report"
Cohesion: 0.12
Nodes (16): 1. Executive Summary, 2. Actual Repository Architecture, 3. Verified Historical Baseline vs. Current Actuals, 4. Verification Commands and Actual Output, 5. Subsystem Status Audit, 6. Audit of Existing Bugs (BUG-001 through BUG-006), 7. Blockers and Dependency Assessment, A. Full Pytest Suite (+8 more)

### Community 26 - "LearnerMemoryEngine"
Cohesion: 0.14
Nodes (3): LearnerMemoryEngine, _topic_key(), test_engine_persistence_across_restarts()

### Community 27 - "TutorRetriever"
Cohesion: 0.18
Nodes (11): compute_percentiles(), evaluate_configuration(), run_characterization(), TutorRetriever, test_compute_percentiles_empty_list(), test_compute_percentiles_known_values(), test_performance_characterization_report_structure(), test_retriever_dense_only_mode() (+3 more)

### Community 28 - "Progress Tracker — Grounded Multimodal AI Tutor"
Cohesion: 0.50
Nodes (3): Phase 2: M6 Zero Stale Leakage + M7 60+ Case Robustness Suite, Phase 3: M8 Latency vs Recall, Final Report & Interactive Demo, Progress Tracker — Grounded Multimodal AI Tutor

### Community 29 - "test_pedagogical_context_injection_zero_citation_leakage"
Cohesion: 0.18
Nodes (4): MockNode, MockRetriever, test_abstention_triggers_when_corpus_evidence_absent_despite_memory(), test_pedagogical_context_injection_zero_citation_leakage()

### Community 30 - "FallbackNode"
Cohesion: 0.17
Nodes (5): D. Vector Index Synchronization Logic, FallbackNode, PurePythonBM25, PurePythonDenseSim, tokenize()

### Community 31 - "run_eval.py"
Cohesion: 0.17
Nodes (6): compute_token_f1(), extract_tokens(), print_scorecard(), run_benchmark(), run_eval_cli(), test_compute_token_f1()

### Community 32 - "LearnerCorrection"
Cohesion: 0.20
Nodes (5): Phase 1: M5 Learner Memory + Retrieval Evaluation + Live Vision, LearnerCorrection, test_learner_correction_creation_and_attribution(), test_learner_correction_serialization_round_trip(), test_canonical_model_round_trips()

### Community 33 - "Consolidation and Migration Plan: Canonical Repository Unification"
Cohesion: 0.12
Nodes (15): 1. Executive Summary & Context, 2. Uncommitted Changes & Safety Assessment, 4. Comprehensive File-by-File Migration Table, 5. Proposed Final Canonical Repository Structure, 6. Small, Independently Verifiable Migration Steps, 7. Migration Readiness Checklist, Category A: Unique Files in Nested (Move directly to Root), Category B: Unique Files in Root (Retain Unchanged) (+7 more)

### Community 35 - "TutorReranker"
Cohesion: 0.22
Nodes (4): TutorReranker, test_reranker_boosts_visual_query_for_visual_nodes(), test_reranker_handles_empty_nodes(), test_reranker_promotes_exact_code_matches()

### Community 36 - "upload_ingest.py"
Cohesion: 0.09
Nodes (14): _is_relative_to(), validate_video_serve_path(), make_source_id(), parse_srt(), parse_transcript_file(), parse_txt_transcript(), parse_vtt(), _time_to_sec() (+6 more)

### Community 37 - "M1 — Versioned Evidence Corpus"
Cohesion: 0.25
Nodes (7): Architecture, M1 — Versioned Evidence Corpus, Roadmap for the following weeks (not built yet), Running it, What "done" means for M1, per the spec, What's already tested, Why SQLite and not a vector DB yet

### Community 38 - "MemoryEntry"
Cohesion: 0.12
Nodes (21): Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy), 8. Recommended Implementation Order for M5 (Learner Memory), manage_memory(), compute_memory_id(), MemoryEntry, MemoryType, SourceSerializationError, test_deterministic_memory_id_computation() (+13 more)

### Community 39 - "Benchmark Dataset"
Cohesion: 0.33
Nodes (4): Benchmark Dataset, Labelling Policy, Schema, Validation

### Community 40 - "main.py"
Cohesion: 0.14
Nodes (10): Config, 3. Subsystem Canonical Ownership Matrix, E. Frontend, Backend, and API Interfaces, Key Components:, transcribe(), deprecate(), main(), resolve_citation() (+2 more)

### Community 41 - "VersionSafeCache"
Cohesion: 0.17
Nodes (5): VersionSafeCache, test_version_safe_cache_clear(), test_version_safe_cache_invalidate_edition(), test_version_safe_cache_invalidate_source(), test_version_safe_cache_set_and_get()

### Community 42 - "store.py"
Cohesion: 0.16
Nodes (4): LearnerContext, MasteryStatus, _normalize_mastery_status(), _normalize_memory_type()

### Community 43 - "Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor"
Cohesion: 0.50
Nodes (3): Active & Resolved Bug Ledger, Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor, Severity Definitions

### Community 44 - "Master Roadmap: Grounded Multimodal AI Tutor"
Cohesion: 0.40
Nodes (4): Architecture & Milestone Mapping, Master Roadmap: Grounded Multimodal AI Tutor, Milestone Status Summary (M1–M8), Phase Execution Summary

### Community 45 - "Grounded Multimodal AI Tutor (DAT Tutor)"
Cohesion: 0.12
Nodes (15): 1. Ingestion & Versioning, 2. Citation Resolution, 3. Grounded Tutor Querying, 4. Learner Memory Management, 5. Evaluation & Characterization, Architecture & System Overview, Grounded Multimodal AI Tutor (DAT Tutor), Interactive Web Demo (M8) (+7 more)

### Community 46 - "LearnerProfile"
Cohesion: 0.16
Nodes (9): Step 4: Reconcile M5 Learner Memory Subsystem, A. Memory Functionality & Architecture, LearnerProfile, test_caller_mutation_of_dict_does_not_mutate_model(), test_default_metadata_and_preferences_isolated_between_instances(), test_learner_profile_creation_full(), test_learner_profile_creation_minimal(), test_learner_profile_serialization_round_trip() (+1 more)

### Community 47 - "answer.py"
Cohesion: 0.14
Nodes (12): compute_stale_leakage(), filter_stale_chunks(), MockNode, SimpleRetriever, test_abstention_policy_high_similarity_answers(), test_abstention_policy_medium_similarity_qualifies(), test_compute_stale_leakage_positive_when_stale_leaks(), test_compute_stale_leakage_zero_for_clean_citations() (+4 more)

### Community 48 - "ingest_uploaded_video"
Cohesion: 0.19
Nodes (4): DemoCorpusStore, ingest_uploaded_video(), test_demo_corpus_store_schema_and_integrity(), test_ingest_uploaded_video_pipeline()

### Community 49 - "json"
Cohesion: 0.23
Nodes (4): main(), main(), test_evidence_alignment_report_schema_and_completeness(), test_benchmark_60_cases_schema_and_distribution()

### Community 50 - "versioning.py"
Cohesion: 0.20
Nodes (7): 10. P0 Changes Applied (2026-10-15), Files changed, Remaining blockers, What was NOT changed, file_content_hash(), text_content_hash(), test_content_hash_changes_when_input_changes()

### Community 51 - "api_list_uploads"
Cohesion: 0.20
Nodes (4): api_list_uploads(), api_media(), api_media_video(), index()

### Community 52 - "validate_demo_db_path"
Cohesion: 0.14
Nodes (9): api_get_memory(), add_learner_memory_item(), correct_learner_memory_item(), delete_learner_memory_item(), get_learner_memory_data(), purge_learner_memory_items(), validate_demo_db_path(), test_learner_memory_crud_flow() (+1 more)

### Community 55 - "run_demo_corpus_query"
Cohesion: 0.39
Nodes (3): run_demo_corpus_query(), DemoRetriever, test_demo_retriever_query()

### Community 56 - "api_upload"
Cohesion: 0.29
Nodes (3): api_upload(), sanitize_filename(), test_sanitize_filename()

### Community 59 - "ask_tutor"
Cohesion: 1.00
Nodes (3): M5 — Learner Memory, Step-by-step, ask_tutor()

## Knowledge Gaps
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate_grounded_answer()` connect `generate_grounded_answer` to `evaluate_modalities.py`, `This Week Plan — Grounded Multimodal AI Tutor`, `AbstentionPolicy`, `vqa.py`, `helpers.py`, `test_red_team_and_eval.py`, `test_pedagogical_context_injection_zero_citation_leakage`, `run_eval.py`, `MemoryEntry`, `main.py`, `VersionSafeCache`, `store.py`, `Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor`, `Master Roadmap: Grounded Multimodal AI Tutor`, `LearnerProfile`, `answer.py`, `json`, `VisualPayload`, `ask_tutor`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `MemoryEntry` (e.g. with `Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy)` and `Step 4: Reconcile M5 Learner Memory Subsystem`) actually correct?**
  _`MemoryEntry` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.11742424242424243 - nodes in this community are weakly interconnected._
- **Why does `LearnerMemoryStore` connect `LearnerMemoryStore` to `LearnerCorrection`, `file_store`, `MemoryEntry`, `main.py`, `store.py`, `Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor`, `Master Roadmap: Grounded Multimodal AI Tutor`, `helpers.py`, `LearnerProfile`, `MemoryPolicy`, `Grounded Multimodal AI Tutor (DAT Tutor)`, `validate_demo_db_path`, `test_learner_memory_models.py`, `LearnerMemoryEngine`, `ask_tutor`, `test_pedagogical_context_injection_zero_citation_leakage`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 44 inferred relationships involving `MemoryType` (e.g. with `Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy)` and `8. Recommended Implementation Order for M5 (Learner Memory)`) actually correct?**
  _`MemoryType` has 44 INFERRED edges - model-reasoned connections that need verification._
- **Should `evaluate_modalities.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1253968253968254 - nodes in this community are weakly interconnected._
- **Why does `MemoryEntry` connect `MemoryEntry` to `LearnerCorrection`, `main.py`, `store.py`, `helpers.py`, `LearnerProfile`, `MemoryPolicy`, `LearnerMemoryStore`, `test_learner_memory_engine.py`, `validate_demo_db_path`, `Any`, `test_learner_memory_models.py`, `LearnerMemoryEngine`, `test_pedagogical_context_injection_zero_citation_leakage`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._