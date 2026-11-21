# Graph Report - grounded-multimodal-ai-tutor-dat  (2026-11-21)

## Corpus Check
- 73 files · ~210,402 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: .jsonl 2, .db 2, .example 1)

## Summary
- 1255 nodes · 3388 edges · 60 communities (49 shown, 11 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 451 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0120dbea`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- os
- evaluate_modalities.py
- test_changed_version_or_evidence_produces_different_id
- test_vqa.py
- test_source_manifest.py
- test_pdf_rendering.py
- This Week Plan — Grounded Multimodal AI Tutor
- test_abstention_and_version_safety.py
- vqa.py
- test_real_evidence.py
- test_benchmark.py
- detect_backend_status
- Real Public Lecture to Evidence Path
- test_demo_smoke.py
- test_ingestion_version_safety.py
- MemoryPolicy
- LearnerMemoryStore
- test_learner_memory_engine.py
- Modality and Perturbation Evaluation Report
- helpers.py
- test_red_team_and_eval.py
- app.py
- MemoryEntry
- Repository Audit & Baseline Verification Report
- LearnerMemoryEngine
- TutorRetriever
- Progress Tracker — Grounded Multimodal AI Tutor
- test_memory_generation_integration.py
- retriever.py
- run_eval.py
- LearnerCorrection
- Consolidation and Migration Plan: Canonical Repository Unification
- test_openai_compatible_vision_adapter
- TutorReranker
- test_demo_upload_rag.py
- M1 — Versioned Evidence Corpus
- test_learner_memory_store.py
- Benchmark Dataset
- main.py
- .get_memories
- store.py
- generate_grounded_answer
- test_openai_compatible_llm_adapter
- Grounded Multimodal AI Tutor (DAT Tutor)
- MasteryState
- test_call_ocr_vlm_adapter
- DemoCorpusStore
- OpenAIVisionAdapter
- upload_ingest.py
- api_list_uploads
- validate_demo_db_path
- VisualPayload
- run_demo_corpus_query
- ingest_uploaded_video
- Document
- api_clear_uploads
- setup_test_db

## God Nodes (most connected - your core abstractions)
1. `MemoryEntry` - 76 edges
2. `generate_grounded_answer()` - 66 edges
3. `MemoryType` - 64 edges
4. `LearnerMemoryStore` - 57 edges
5. `MemoryPolicy` - 43 edges
6. `build_chunks()` - 35 edges
7. `TranscriptSegment` - 35 edges
8. `SourceVersion` - 35 edges
9. `MasteryState` - 35 edges
10. `LearnerMemoryEngine` - 34 edges

## Surprising Connections (you probably didn't know these)
- `What was NOT changed` --references--> `file_content_hash()`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Blockers (must fix before M4/M5)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Files changed` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `P0a — Fix `SourceVersion` dataclass (unblocks 11 failing tests)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Architecture & System Overview` --references--> `LearnerMemoryStore`  [INFERRED]
  README.md → memory/store.py

## Import Cycles
- None detected.

## Communities (60 total, 11 thin omitted)

### Community 0 - "os"
Cohesion: 0.12
Nodes (19): extract_keyframes_demo(), validate_upload_video_path(), W2 priority order, Week 1–2 Requirements Audit Report, ocr_keyframes(), extract_audio(), extract_keyframes(), _fixed_interval_keyframes() (+11 more)

### Community 1 - "evaluate_modalities.py"
Cohesion: 0.13
Nodes (13): check_answer_correctness(), create_intelligent_mock_vision_adapter(), main(), MockRetrievalNode, run_modality_evaluation(), run_perturbation_evaluation(), TargetedRetriever, _create_dummy_jpeg() (+5 more)

### Community 3 - "test_vqa.py"
Cohesion: 0.11
Nodes (15): _create_dummy_jpeg(), MockNode, MockRetriever, test_answer_cites_correct_evidence_id_and_asset_metadata(), test_existing_text_only_queries_still_work(), test_max_images_limit_respected(), test_missing_required_image_causes_abstention(), test_ocr_text_alone_not_treated_as_visual_understanding_when_visual_required() (+7 more)

### Community 4 - "test_source_manifest.py"
Cohesion: 0.10
Nodes (13): build_source_version_from_manifest(), get_manifest_asset(), get_manifest_source(), load_manifest(), ManifestValidationError, SourceAssetRecord, validate_manifest(), test_manifest_resolves_configuration() (+5 more)

### Community 5 - "test_pdf_rendering.py"
Cohesion: 0.10
Nodes (10): _create_synthetic_pdf(), setup_test_db(), test_pdf_deterministic_page_identity(), test_pdf_empty_text_handling(), test_pdf_extracted_text(), test_pdf_image_existence_after_temporary_download_deleted(), test_pdf_page_rendering_creates_valid_jpeg(), test_pdf_processing_failure_records_error_distinctly() (+2 more)

### Community 6 - "This Week Plan — Grounded Multimodal AI Tutor"
Cohesion: 0.04
Nodes (46): 10. P0 Changes Applied (2026-10-15), 11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15), 12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15), 13. M4 Phase 3 — Align Evidence and Evaluate Visual QA (2026-10-16), 2. Actual Test and Benchmark-Validator Results, 3. Exact Commands Used, 4. Evidence and Image-Path Data Flow, 5. Existing Local Image Availability (+38 more)

### Community 7 - "test_abstention_and_version_safety.py"
Cohesion: 0.06
Nodes (22): AbstentionPolicy, DecisionType, compute_stale_leakage(), filter_stale_chunks(), VersionSafeCache, MockNode, SimpleRetriever, test_abstention_policy_empty_nodes_abstains() (+14 more)

### Community 8 - "vqa.py"
Cohesion: 0.13
Nodes (4): BaseVisionAdapter, get_vision_adapter(), GoogleGenAIVisionAdapter, LlamaIndexVisionAdapter

### Community 9 - "test_real_evidence.py"
Cohesion: 0.11
Nodes (27): main(), Files changed, build_chunks(), split_long_segment(), extract_pdf_slides(), OcrResult, parse_srt(), TranscriptSegment (+19 more)

### Community 10 - "test_benchmark.py"
Cohesion: 0.18
Nodes (3): benchmark_cases(), load_cases(), test_invalid_benchmark_entries_rejected()

### Community 11 - "detect_backend_status"
Cohesion: 0.24
Nodes (4): Config, detect_backend_status(), test_detect_backend_status(), test_detect_backend_status_reporting()

### Community 12 - "Real Public Lecture to Evidence Path"
Cohesion: 0.18
Nodes (10): 1. Selected Lecture, 2. Source/Provenance, 3. Ingestion Command, 4. Evidence Storage, 5. One Real Evidence Record, 6. One Real Citation, 7. How an Evaluator Navigates to It, 8. How to Reproduce (+2 more)

### Community 13 - "test_demo_smoke.py"
Cohesion: 0.09
Nodes (13): build_jump_url(), format_citation_card(), format_citation_time_bounds(), format_time_seconds(), run_tutor_query(), isolated_corpus_and_memory_db(), MockNode, MockRetriever (+5 more)

### Community 14 - "test_ingestion_version_safety.py"
Cohesion: 0.11
Nodes (26): 1. Repository Audit Findings, Architecture Summary (verified), Failing Tests (12) — Exact Errors, Module Map, Risks, Test result, SourceVersion, ingest() (+18 more)

### Community 15 - "MemoryPolicy"
Cohesion: 0.10
Nodes (27): MemoryDecision, MemoryPolicy, MemoryPolicyError, PolicyEvaluation, _validate_unit_interval(), _entry(), FrozenClock, test_confidence_threshold_accept_and_reject() (+19 more)

### Community 16 - "LearnerMemoryStore"
Cohesion: 0.07
Nodes (10): Architecture & Milestone Mapping, Master Roadmap: Grounded Multimodal AI Tutor, Milestone Status Summary (M1–M8), Phase Execution Summary, LearnerMemoryStore, _serialize_json(), _serialize_source(), file_store() (+2 more)

### Community 17 - "test_learner_memory_engine.py"
Cohesion: 0.12
Nodes (28): MemoryNotFound, MemoryRejected, _engine(), FrozenClock, _mem(), test_compact_learner_context_is_labeled_and_excludes_expired(), test_confidence_based_rejection(), test_context_respects_entry_limit_deterministically() (+20 more)

### Community 20 - "Modality and Perturbation Evaluation Report"
Cohesion: 0.50
Nodes (3): 1. Modality Breakdown, 2. Image Perturbation Results, Modality and Perturbation Evaluation Report

### Community 21 - "helpers.py"
Cohesion: 0.18
Nodes (5): api_media(), _is_relative_to(), validate_media_path(), validate_video_serve_path(), test_validate_media_path()

### Community 22 - "test_red_team_and_eval.py"
Cohesion: 0.11
Nodes (16): evaluate_retrieval(), run_benchmark(), InjectionDefense, test_evidence_alignment_report_schema_and_completeness(), test_benchmark_60_cases_schema_and_distribution(), test_clean_course_queries_not_flagged_as_injection(), test_detects_prompt_injection_signatures(), test_evaluate_retrieval_miss() (+8 more)

### Community 23 - "app.py"
Cohesion: 0.12
Nodes (13): AddMemoryRequest, api_add_memory(), api_correct_memory(), api_delete_memory(), api_demo_corpus_query(), api_purge_memory(), api_query(), api_status() (+5 more)

### Community 24 - "MemoryEntry"
Cohesion: 0.13
Nodes (33): MemoryEntry, MemoryType, test_default_metadata_and_preferences_isolated_between_instances(), test_deterministic_memory_id_computation(), test_different_learner_ids_produce_different_memory_ids(), test_different_topics_or_types_produce_different_memory_ids(), test_empty_content_rejected(), test_empty_correction_fields_rejected() (+25 more)

### Community 25 - "Repository Audit & Baseline Verification Report"
Cohesion: 0.12
Nodes (16): 1. Executive Summary, 2. Actual Repository Architecture, 3. Verified Historical Baseline vs. Current Actuals, 4. Verification Commands and Actual Output, 5. Subsystem Status Audit, 6. Audit of Existing Bugs (BUG-001 through BUG-006), 7. Blockers and Dependency Assessment, A. Full Pytest Suite (+8 more)

### Community 26 - "LearnerMemoryEngine"
Cohesion: 0.12
Nodes (3): LearnerMemoryEngine, _topic_key(), test_engine_persistence_across_restarts()

### Community 27 - "TutorRetriever"
Cohesion: 0.15
Nodes (12): compute_percentiles(), evaluate_configuration(), run_characterization(), TutorRetriever, test_backwards_compatibility_adapter_methods(), test_compute_percentiles_empty_list(), test_compute_percentiles_known_values(), test_performance_characterization_report_structure() (+4 more)

### Community 28 - "Progress Tracker — Grounded Multimodal AI Tutor"
Cohesion: 0.50
Nodes (3): Phase 2: M6 Zero Stale Leakage + M7 60+ Case Robustness Suite, Phase 3: M8 Latency vs Recall, Final Report & Interactive Demo, Progress Tracker — Grounded Multimodal AI Tutor

### Community 29 - "test_memory_generation_integration.py"
Cohesion: 0.18
Nodes (4): MockNode, MockRetriever, test_abstention_triggers_when_corpus_evidence_absent_despite_memory(), test_pedagogical_context_injection_zero_citation_leakage()

### Community 30 - "retriever.py"
Cohesion: 0.11
Nodes (5): D. Vector Index Synchronization Logic, FallbackNode, PurePythonBM25, PurePythonDenseSim, tokenize()

### Community 31 - "run_eval.py"
Cohesion: 0.19
Nodes (4): compute_token_f1(), extract_tokens(), print_scorecard(), test_compute_token_f1()

### Community 32 - "LearnerCorrection"
Cohesion: 0.18
Nodes (4): Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy), LearnerCorrection, test_learner_correction_serialization_round_trip(), test_apply_correction_semantics()

### Community 33 - "Consolidation and Migration Plan: Canonical Repository Unification"
Cohesion: 0.12
Nodes (15): 1. Executive Summary & Context, 2. Uncommitted Changes & Safety Assessment, 4. Comprehensive File-by-File Migration Table, 5. Proposed Final Canonical Repository Structure, 6. Small, Independently Verifiable Migration Steps, 7. Migration Readiness Checklist, Category A: Unique Files in Nested (Move directly to Root), Category B: Unique Files in Root (Retain Unchanged) (+7 more)

### Community 35 - "TutorReranker"
Cohesion: 0.22
Nodes (4): TutorReranker, test_reranker_boosts_visual_query_for_visual_nodes(), test_reranker_handles_empty_nodes(), test_reranker_promotes_exact_code_matches()

### Community 36 - "test_demo_upload_rag.py"
Cohesion: 0.11
Nodes (12): parse_srt(), parse_transcript_file(), parse_txt_transcript(), parse_vtt(), _time_to_sec(), _sha256(), synthetic_pdf(), synthetic_video() (+4 more)

### Community 37 - "M1 — Versioned Evidence Corpus"
Cohesion: 0.25
Nodes (7): Architecture, M1 — Versioned Evidence Corpus, Roadmap for the following weeks (not built yet), Running it, What "done" means for M1, per the spec, What's already tested, Why SQLite and not a vector DB yet

### Community 38 - "test_learner_memory_store.py"
Cohesion: 0.17
Nodes (8): now_utc(), SourceSerializationError, _validate_json_source(), test_build_pedagogical_context(), test_canonical_model_round_trips(), test_expiry_and_inactive_filtering(), test_purge_learner_isolation(), test_transaction_rollback()

### Community 39 - "Benchmark Dataset"
Cohesion: 0.33
Nodes (4): Benchmark Dataset, Labelling Policy, Schema, Validation

### Community 40 - "main.py"
Cohesion: 0.31
Nodes (7): 3. Subsystem Canonical Ownership Matrix, E. Frontend, Backend, and API Interfaces, deprecate(), main(), resolve_citation(), run_characterization_cli(), run_eval_cli()

### Community 41 - ".get_memories"
Cohesion: 0.21
Nodes (3): _dt_to_iso(), _iso_to_dt(), _to_dt()

### Community 42 - "store.py"
Cohesion: 0.11
Nodes (11): manage_memory(), LearnerContext, compute_correction_id(), compute_memory_id(), MasteryStatus, _normalize_mastery_status(), _normalize_memory_type(), _validate_confidence() (+3 more)

### Community 43 - "generate_grounded_answer"
Cohesion: 0.17
Nodes (6): Active & Resolved Bug Ledger, Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor, Severity Definitions, generate_grounded_answer(), OpenAICompatibleLLM, main()

### Community 45 - "Grounded Multimodal AI Tutor (DAT Tutor)"
Cohesion: 0.12
Nodes (15): 1. Ingestion & Versioning, 2. Citation Resolution, 3. Grounded Tutor Querying, 4. Learner Memory Management, 5. Evaluation & Characterization, Architecture & System Overview, Grounded Multimodal AI Tutor (DAT Tutor), Interactive Web Demo (M8) (+7 more)

### Community 46 - "MasteryState"
Cohesion: 0.10
Nodes (13): Step 4: Reconcile M5 Learner Memory Subsystem, Phase 1: M5 Learner Memory + Retrieval Evaluation + Live Vision, 8. Recommended Implementation Order for M5 (Learner Memory), A. Memory Functionality & Architecture, LearnerProfile, MasteryState, _validate_mastery_level(), test_caller_mutation_of_dict_does_not_mutate_model() (+5 more)

### Community 48 - "DemoCorpusStore"
Cohesion: 0.19
Nodes (4): DemoCorpusStore, test_demo_corpus_store_schema_and_integrity(), test_ingest_standalone_pdf(), test_ingest_uploaded_video_pipeline()

### Community 50 - "upload_ingest.py"
Cohesion: 0.11
Nodes (9): load_dotenv(), compute_chunk_id(), EvidenceChunk, _flush_audio(), transcribe(), file_content_hash(), text_content_hash(), _columns() (+1 more)

### Community 51 - "api_list_uploads"
Cohesion: 0.25
Nodes (3): api_list_uploads(), api_media_video(), index()

### Community 52 - "validate_demo_db_path"
Cohesion: 0.15
Nodes (9): api_get_memory(), add_learner_memory_item(), correct_learner_memory_item(), delete_learner_memory_item(), get_learner_memory_data(), purge_learner_memory_items(), validate_demo_db_path(), test_learner_memory_crud_flow() (+1 more)

### Community 54 - "VisualPayload"
Cohesion: 0.13
Nodes (6): Key Components:, Files Changed, CallableVisionAdapter, load_and_validate_image(), MockVisionAdapter, VisualPayload

### Community 55 - "run_demo_corpus_query"
Cohesion: 0.25
Nodes (3): run_demo_corpus_query(), DemoRetriever, test_demo_retriever_query()

### Community 56 - "ingest_uploaded_video"
Cohesion: 0.18
Nodes (7): api_upload(), call_ocr_vlm(), ingest_uploaded_pdf(), ingest_uploaded_video(), make_source_id(), sanitize_filename(), test_sanitize_filename()

## Knowledge Gaps
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate_grounded_answer()` connect `generate_grounded_answer` to `evaluate_modalities.py`, `test_vqa.py`, `test_demo_upload_rag.py`, `This Week Plan — Grounded Multimodal AI Tutor`, `test_abstention_and_version_safety.py`, `vqa.py`, `main.py`, `detect_backend_status`, `test_demo_smoke.py`, `MasteryState`, `LearnerMemoryStore`, `helpers.py`, `test_red_team_and_eval.py`, `run_demo_corpus_query`, `VisualPayload`, `test_memory_generation_integration.py`, `run_eval.py`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `MemoryEntry` (e.g. with `Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy)` and `Step 4: Reconcile M5 Learner Memory Subsystem`) actually correct?**
  _`MemoryEntry` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.11596638655462185 - nodes in this community are weakly interconnected._
- **Why does `MemoryEntry` connect `MemoryEntry` to `LearnerCorrection`, `test_learner_memory_store.py`, `main.py`, `.get_memories`, `store.py`, `MasteryState`, `MemoryPolicy`, `LearnerMemoryStore`, `test_learner_memory_engine.py`, `validate_demo_db_path`, `helpers.py`, `LearnerMemoryEngine`, `test_memory_generation_integration.py`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `generate_grounded_answer()` (e.g. with `Active & Resolved Bug Ledger` and `Phase Execution Summary`) actually correct?**
  _`generate_grounded_answer()` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Should `evaluate_modalities.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1253968253968254 - nodes in this community are weakly interconnected._
- **Why does `LearnerMemoryStore` connect `LearnerMemoryStore` to `LearnerCorrection`, `This Week Plan — Grounded Multimodal AI Tutor`, `test_learner_memory_store.py`, `main.py`, `.get_memories`, `store.py`, `generate_grounded_answer`, `test_demo_smoke.py`, `MasteryState`, `MemoryPolicy`, `Grounded Multimodal AI Tutor (DAT Tutor)`, `validate_demo_db_path`, `helpers.py`, `MemoryEntry`, `LearnerMemoryEngine`, `test_memory_generation_integration.py`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._