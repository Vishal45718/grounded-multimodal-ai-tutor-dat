# Graph Report - grounded-multimodal-ai-tutor-dat  (2026-11-21)

## Corpus Check
- 73 files · ~211,042 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: .jsonl 2, .db 2, .example 1)

## Summary
- 1270 nodes · 3410 edges · 63 communities (49 shown, 14 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 452 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `29427ffc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- os
- test_modality_evaluation.py
- file_content_hash
- test_real_evidence.py
- SourceVersion
- test_pdf_rendering.py
- This Week Plan — Grounded Multimodal AI Tutor
- test_abstention_and_version_safety.py
- generate_grounded_answer
- _columns
- validate_demo_db_path
- detect_backend_status
- Real Public Lecture to Evidence Path
- helpers.py
- test_ingestion_version_safety.py
- MemoryPolicy
- LearnerMemoryStore
- test_learner_memory_engine.py
- Modality and Perturbation Evaluation Report
- answer.py
- test_red_team_and_eval.py
- app.py
- test_learner_memory_models.py
- Repository Audit & Baseline Verification Report
- LearnerMemoryEngine
- TutorRetriever
- Master Roadmap: Grounded Multimodal AI Tutor
- test_pedagogical_context_injection_zero_citation_leakage
- retriever.py
- run_eval.py
- test_benchmark.py
- Consolidation and Migration Plan: Canonical Repository Unification
- test_openai_compatible_vision_adapter
- TutorReranker
- test_demo_upload_rag.py
- M1 — Versioned Evidence Corpus
- store.py
- Benchmark Dataset
- main.py
- LearnerProfile
- MemoryEntry
- LearnerCorrection
- test_openai_compatible_llm_adapter
- Grounded Multimodal AI Tutor (DAT Tutor)
- Any
- test_call_ocr_vlm_adapter
- DemoCorpusStore
- sys
- upload_ingest.py
- validate_video_serve_path
- decode_audio_ffmpeg_pcm
- LlamaIndexVisionAdapter
- DemoRetriever
- ingest_uploaded_video
- Document
- GoogleGenAIVisionAdapter
- OpenAIVisionAdapter
- file_store
- api_clear_uploads
- Progress Tracker — Grounded Multimodal AI Tutor

## God Nodes (most connected - your core abstractions)
1. `MemoryEntry` - 76 edges
2. `generate_grounded_answer()` - 66 edges
3. `MemoryType` - 64 edges
4. `LearnerMemoryStore` - 57 edges
5. `MemoryPolicy` - 43 edges
6. `TranscriptSegment` - 36 edges
7. `build_chunks()` - 35 edges
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
- `Milestone Status Summary (M1–M8)` --references--> `LearnerMemoryStore`  [INFERRED]
  docs/MASTER_ROADMAP.md → memory/store.py

## Import Cycles
- None detected.

## Communities (63 total, 14 thin omitted)

### Community 0 - "os"
Cohesion: 0.11
Nodes (20): extract_keyframes_demo(), validate_upload_video_path(), W2 priority order, Week 1–2 Requirements Audit Report, ocr_keyframes(), extract_audio(), extract_keyframes(), _fixed_interval_keyframes() (+12 more)

### Community 1 - "test_modality_evaluation.py"
Cohesion: 0.13
Nodes (12): check_answer_correctness(), create_intelligent_mock_vision_adapter(), MockRetrievalNode, run_modality_evaluation(), run_perturbation_evaluation(), TargetedRetriever, _create_dummy_jpeg(), test_image_swap_perturbation_prevents_silent_acceptance() (+4 more)

### Community 2 - "file_content_hash"
Cohesion: 0.29
Nodes (6): 6. Blockers and Risks, Blockers (must fix before M4/M5), Risks, file_content_hash(), test_content_hash_changes_when_input_changes(), test_content_hash_is_deterministic()

### Community 3 - "test_real_evidence.py"
Cohesion: 0.08
Nodes (25): Active & Resolved Bug Ledger, resolve_citation(), init_db(), insert_chunks(), test_pdf_does_not_invent_video_timestamps(), setup_test_db(), test_audio_citation_remains_navigable(), test_citation_resolves_to_correct_source() (+17 more)

### Community 4 - "SourceVersion"
Cohesion: 0.07
Nodes (20): load_dotenv(), build_source_version_from_manifest(), get_manifest_asset(), get_manifest_source(), load_manifest(), ManifestValidationError, SourceAssetRecord, validate_manifest() (+12 more)

### Community 5 - "test_pdf_rendering.py"
Cohesion: 0.11
Nodes (11): extract_pdf_slides(), _create_synthetic_pdf(), setup_test_db(), test_pdf_deterministic_page_identity(), test_pdf_empty_text_handling(), test_pdf_extracted_text(), test_pdf_image_existence_after_temporary_download_deleted(), test_pdf_page_rendering_creates_valid_jpeg() (+3 more)

### Community 6 - "This Week Plan — Grounded Multimodal AI Tutor"
Cohesion: 0.05
Nodes (41): 10. P0 Changes Applied (2026-10-15), 11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15), 12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15), 13. M4 Phase 3 — Align Evidence and Evaluate Visual QA (2026-10-16), 1. Repository Audit Findings, 2. Actual Test and Benchmark-Validator Results, 3. Exact Commands Used, 4. Evidence and Image-Path Data Flow (+33 more)

### Community 7 - "test_abstention_and_version_safety.py"
Cohesion: 0.06
Nodes (22): AbstentionPolicy, DecisionType, compute_stale_leakage(), filter_stale_chunks(), VersionSafeCache, MockNode, SimpleRetriever, test_abstention_policy_empty_nodes_abstains() (+14 more)

### Community 8 - "generate_grounded_answer"
Cohesion: 0.10
Nodes (7): Key Components:, Files Changed, generate_grounded_answer(), OpenAICompatibleLLM, CallableVisionAdapter, load_and_validate_image(), VisualPayload

### Community 9 - "_columns"
Cohesion: 0.12
Nodes (5): Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor, Severity Definitions, _columns(), setup_test_db(), setup_test_db()

### Community 10 - "validate_demo_db_path"
Cohesion: 0.15
Nodes (10): api_get_memory(), add_learner_memory_item(), correct_learner_memory_item(), delete_learner_memory_item(), get_learner_memory_data(), purge_learner_memory_items(), run_tutor_query(), validate_demo_db_path() (+2 more)

### Community 11 - "detect_backend_status"
Cohesion: 0.30
Nodes (3): Config, detect_backend_status(), test_detect_backend_status()

### Community 12 - "Real Public Lecture to Evidence Path"
Cohesion: 0.18
Nodes (10): 1. Selected Lecture, 2. Source/Provenance, 3. Ingestion Command, 4. Evidence Storage, 5. One Real Evidence Record, 6. One Real Citation, 7. How an Evaluator Navigates to It, 8. How to Reproduce (+2 more)

### Community 13 - "helpers.py"
Cohesion: 0.08
Nodes (15): build_jump_url(), format_citation_card(), format_citation_time_bounds(), format_time_seconds(), run_demo_corpus_query(), validate_media_path(), isolated_corpus_and_memory_db(), MockNode (+7 more)

### Community 14 - "test_ingestion_version_safety.py"
Cohesion: 0.08
Nodes (38): Architecture Summary (verified), Chunk ID generation (deterministic), Failing Tests (12) — Exact Errors, Files changed, Test result, build_chunks(), compute_chunk_id(), EvidenceChunk (+30 more)

### Community 15 - "MemoryPolicy"
Cohesion: 0.09
Nodes (27): MemoryDecision, MemoryPolicy, MemoryPolicyError, PolicyEvaluation, _validate_unit_interval(), _entry(), FrozenClock, test_confidence_threshold_accept_and_reject() (+19 more)

### Community 16 - "LearnerMemoryStore"
Cohesion: 0.09
Nodes (7): _dt_to_iso(), _iso_to_dt(), LearnerMemoryStore, _to_dt(), _serialize_json(), _serialize_source(), test_persistent_in_memory_store_across_calls()

### Community 17 - "test_learner_memory_engine.py"
Cohesion: 0.12
Nodes (28): MemoryNotFound, MemoryRejected, _engine(), FrozenClock, _mem(), test_compact_learner_context_is_labeled_and_excludes_expired(), test_confidence_based_rejection(), test_context_respects_entry_limit_deterministically() (+20 more)

### Community 20 - "Modality and Perturbation Evaluation Report"
Cohesion: 0.50
Nodes (3): 1. Modality Breakdown, 2. Image Perturbation Results, Modality and Perturbation Evaluation Report

### Community 21 - "answer.py"
Cohesion: 0.15
Nodes (5): main(), BaseVisionAdapter, get_vision_adapter(), MockVisionAdapter, test_evidence_alignment_report_schema_and_completeness()

### Community 22 - "test_red_team_and_eval.py"
Cohesion: 0.13
Nodes (14): evaluate_retrieval(), InjectionDefense, test_benchmark_60_cases_schema_and_distribution(), test_clean_course_queries_not_flagged_as_injection(), test_detects_prompt_injection_signatures(), test_evaluate_retrieval_miss(), test_evaluate_retrieval_perfect_rank_1(), test_evaluate_retrieval_rank_3() (+6 more)

### Community 23 - "app.py"
Cohesion: 0.09
Nodes (17): AddMemoryRequest, api_add_memory(), api_correct_memory(), api_delete_memory(), api_demo_corpus_query(), api_list_uploads(), api_media(), api_purge_memory() (+9 more)

### Community 24 - "test_learner_memory_models.py"
Cohesion: 0.17
Nodes (22): MasteryState, test_empty_content_rejected(), test_empty_correction_fields_rejected(), test_empty_learner_id_rejected_across_models(), test_empty_memory_id_rejected_when_explicitly_passed(), test_empty_topic_rejected(), test_expires_at_cannot_precede_created_at(), test_invalid_confidence_rejection_mastery_state() (+14 more)

### Community 25 - "Repository Audit & Baseline Verification Report"
Cohesion: 0.11
Nodes (17): 1. Executive Summary, 2. Actual Repository Architecture, 3. Verified Historical Baseline vs. Current Actuals, 4. Verification Commands and Actual Output, 5. Subsystem Status Audit, 6. Audit of Existing Bugs (BUG-001 through BUG-006), 7. Blockers and Dependency Assessment, A. Full Pytest Suite (+9 more)

### Community 26 - "LearnerMemoryEngine"
Cohesion: 0.14
Nodes (3): LearnerMemoryEngine, _topic_key(), test_engine_persistence_across_restarts()

### Community 27 - "TutorRetriever"
Cohesion: 0.18
Nodes (10): compute_percentiles(), evaluate_configuration(), TutorRetriever, test_compute_percentiles_empty_list(), test_compute_percentiles_known_values(), test_performance_characterization_report_structure(), test_retriever_dense_only_mode(), test_retriever_hybrid_fusion_mode() (+2 more)

### Community 28 - "Master Roadmap: Grounded Multimodal AI Tutor"
Cohesion: 0.40
Nodes (4): Architecture & Milestone Mapping, Master Roadmap: Grounded Multimodal AI Tutor, Milestone Status Summary (M1–M8), Phase Execution Summary

### Community 29 - "test_pedagogical_context_injection_zero_citation_leakage"
Cohesion: 0.18
Nodes (4): MockNode, MockRetriever, test_abstention_triggers_when_corpus_evidence_absent_despite_memory(), test_pedagogical_context_injection_zero_citation_leakage()

### Community 30 - "retriever.py"
Cohesion: 0.11
Nodes (5): D. Vector Index Synchronization Logic, FallbackNode, PurePythonBM25, PurePythonDenseSim, tokenize()

### Community 31 - "run_eval.py"
Cohesion: 0.22
Nodes (3): compute_token_f1(), extract_tokens(), test_compute_token_f1()

### Community 32 - "test_benchmark.py"
Cohesion: 0.18
Nodes (3): benchmark_cases(), load_cases(), test_invalid_benchmark_entries_rejected()

### Community 33 - "Consolidation and Migration Plan: Canonical Repository Unification"
Cohesion: 0.12
Nodes (16): 1. Executive Summary & Context, 2. Uncommitted Changes & Safety Assessment, 3. Subsystem Canonical Ownership Matrix, 4. Comprehensive File-by-File Migration Table, 5. Proposed Final Canonical Repository Structure, 6. Small, Independently Verifiable Migration Steps, 7. Migration Readiness Checklist, Category A: Unique Files in Nested (Move directly to Root) (+8 more)

### Community 35 - "TutorReranker"
Cohesion: 0.27
Nodes (4): TutorReranker, test_reranker_boosts_visual_query_for_visual_nodes(), test_reranker_handles_empty_nodes(), test_reranker_promotes_exact_code_matches()

### Community 36 - "test_demo_upload_rag.py"
Cohesion: 0.10
Nodes (9): sanitize_filename(), _sha256(), synthetic_pdf(), synthetic_video(), test_detect_backend_status_reporting(), test_fastapi_upload_and_rag_endpoints(), test_production_db_hashes_unchanged(), test_sanitize_filename() (+1 more)

### Community 37 - "M1 — Versioned Evidence Corpus"
Cohesion: 0.25
Nodes (7): Architecture, M1 — Versioned Evidence Corpus, Roadmap for the following weeks (not built yet), Running it, What "done" means for M1, per the spec, What's already tested, Why SQLite and not a vector DB yet

### Community 38 - "store.py"
Cohesion: 0.14
Nodes (5): LearnerContext, MasteryStatus, _normalize_mastery_status(), SourceSerializationError, _validate_json_source()

### Community 39 - "Benchmark Dataset"
Cohesion: 0.33
Nodes (4): Benchmark Dataset, Labelling Policy, Schema, Validation

### Community 40 - "main.py"
Cohesion: 0.15
Nodes (14): run_characterization(), print_scorecard(), run_benchmark(), 8. Recommended Next-Step Order, M5 — Learner Memory, Step-by-step, ask_tutor(), deprecate() (+6 more)

### Community 41 - "LearnerProfile"
Cohesion: 0.16
Nodes (9): Step 4: Reconcile M5 Learner Memory Subsystem, A. Memory Functionality & Architecture, LearnerProfile, test_caller_mutation_of_dict_does_not_mutate_model(), test_default_metadata_and_preferences_isolated_between_instances(), test_learner_profile_creation_full(), test_learner_profile_creation_minimal(), test_learner_profile_serialization_round_trip() (+1 more)

### Community 42 - "MemoryEntry"
Cohesion: 0.11
Nodes (21): 8. Recommended Implementation Order for M5 (Learner Memory), compute_memory_id(), MemoryEntry, MemoryType, _normalize_memory_type(), now_utc(), test_deterministic_memory_id_computation(), test_different_learner_ids_produce_different_memory_ids() (+13 more)

### Community 43 - "LearnerCorrection"
Cohesion: 0.28
Nodes (4): Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy), Phase 1: M5 Learner Memory + Retrieval Evaluation + Live Vision, LearnerCorrection, test_learner_correction_creation_and_attribution()

### Community 45 - "Grounded Multimodal AI Tutor (DAT Tutor)"
Cohesion: 0.12
Nodes (15): 1. Ingestion & Versioning, 2. Citation Resolution, 3. Grounded Tutor Querying, 4. Learner Memory Management, 5. Evaluation & Characterization, Architecture & System Overview, Grounded Multimodal AI Tutor (DAT Tutor), Interactive Web Demo (M8) (+7 more)

### Community 46 - "Any"
Cohesion: 0.11
Nodes (7): compute_correction_id(), _validate_confidence(), _validate_mastery_level(), _validate_non_empty_str(), _validate_utc_datetime(), test_deterministic_correction_id_computation(), test_learner_correction_serialization_round_trip()

### Community 48 - "DemoCorpusStore"
Cohesion: 0.19
Nodes (4): DemoCorpusStore, test_demo_corpus_store_schema_and_integrity(), test_ingest_standalone_pdf(), test_ingest_uploaded_video_pipeline()

### Community 50 - "upload_ingest.py"
Cohesion: 0.29
Nodes (6): parse_srt(), parse_transcript_file(), parse_txt_transcript(), parse_vtt(), _time_to_sec(), test_transcript_parsers()

### Community 51 - "validate_video_serve_path"
Cohesion: 0.25
Nodes (3): api_media_video(), _is_relative_to(), validate_video_serve_path()

### Community 52 - "decode_audio_ffmpeg_pcm"
Cohesion: 0.29
Nodes (3): decode_audio_ffmpeg_pcm(), transcribe_video_whisper(), test_decode_audio_ffmpeg_pcm_and_whisper_bypass()

### Community 56 - "ingest_uploaded_video"
Cohesion: 0.31
Nodes (4): call_ocr_vlm(), ingest_uploaded_pdf(), ingest_uploaded_video(), make_source_id()

### Community 62 - "Progress Tracker — Grounded Multimodal AI Tutor"
Cohesion: 0.50
Nodes (3): Phase 2: M6 Zero Stale Leakage + M7 60+ Case Robustness Suite, Phase 3: M8 Latency vs Recall, Final Report & Interactive Demo, Progress Tracker — Grounded Multimodal AI Tutor

## Knowledge Gaps
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate_grounded_answer()` connect `generate_grounded_answer` to `test_modality_evaluation.py`, `test_real_evidence.py`, `test_demo_upload_rag.py`, `This Week Plan — Grounded Multimodal AI Tutor`, `test_abstention_and_version_safety.py`, `main.py`, `LearnerProfile`, `validate_demo_db_path`, `MemoryEntry`, `detect_backend_status`, `helpers.py`, `store.py`, `sys`, `answer.py`, `test_red_team_and_eval.py`, `Master Roadmap: Grounded Multimodal AI Tutor`, `test_pedagogical_context_injection_zero_citation_leakage`, `run_eval.py`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `MemoryEntry` (e.g. with `Category C: Conflicting Files (Detailed Analysis & Reconciliation Strategy)` and `Step 4: Reconcile M5 Learner Memory Subsystem`) actually correct?**
  _`MemoryEntry` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.10810810810810811 - nodes in this community are weakly interconnected._
- **Why does `MemoryEntry` connect `MemoryEntry` to `store.py`, `main.py`, `LearnerProfile`, `validate_demo_db_path`, `LearnerCorrection`, `helpers.py`, `MemoryPolicy`, `LearnerMemoryStore`, `test_learner_memory_engine.py`, `test_learner_memory_models.py`, `LearnerMemoryEngine`, `test_pedagogical_context_injection_zero_citation_leakage`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `generate_grounded_answer()` (e.g. with `Active & Resolved Bug Ledger` and `Phase Execution Summary`) actually correct?**
  _`generate_grounded_answer()` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_modality_evaluation.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1268939393939394 - nodes in this community are weakly interconnected._
- **Why does `LearnerMemoryStore` connect `LearnerMemoryStore` to `test_real_evidence.py`, `store.py`, `main.py`, `LearnerProfile`, `validate_demo_db_path`, `LearnerCorrection`, `MemoryEntry`, `helpers.py`, `Grounded Multimodal AI Tutor (DAT Tutor)`, `MemoryPolicy`, `file_store`, `test_learner_memory_models.py`, `LearnerMemoryEngine`, `Master Roadmap: Grounded Multimodal AI Tutor`, `test_pedagogical_context_injection_zero_citation_leakage`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._