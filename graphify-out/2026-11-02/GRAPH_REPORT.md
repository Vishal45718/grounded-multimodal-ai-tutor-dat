# Graph Report - dat_project  (2026-11-02)

## Corpus Check
- 87 files · ~198,131 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: .jsonl 2, .db 2, .ini 2)

## Summary
- 1015 nodes · 2531 edges · 50 communities (40 shown, 10 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 163 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0d603e83`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- file_content_hash
- os
- build_chunks
- generate_grounded_answer
- SourceAssetRecord
- tests/test_pdf_rendering.py
- This Week Plan — Grounded Multimodal AI Tutor
- LearnerMemoryItem
- generation/vqa.py
- init_db
- grounded-multimodal-ai-tutor-dat/tests/test_benchmark.py
- scripts/ingest_official.py
- Real Public Lecture to Evidence Path
- M1 — Versioned Evidence Corpus
- tests/test_ingestion_version_safety.py
- grounded-multimodal-ai-tutor-dat/generation/vqa.py
- grounded-multimodal-ai-tutor-dat/tests/test_ingestion_version_safety.py
- MockVisionAdapter
- Modality and Perturbation Evaluation Report
- memory/models.py
- hashlib
- TutorRetriever
- pytest
- Repository Audit & Baseline Verification Report
- json
- _connect
- MemoryEntry
- grounded-multimodal-ai-tutor-dat/tests/test_modality_evaluation.py
- test_learner_memory_models.py
- generation/answer.py
- LearnerCorrection
- Real Public Lecture to Evidence Path
- M1 — Versioned Evidence Corpus
- memory/__init__.py
- M1 — Versioned Evidence Corpus
- M1 — Versioned Evidence Corpus
- Benchmark Dataset
- Benchmark Dataset
- grounded-multimodal-ai-tutor-dat/ingestion/transcriber.py
- .from_dict
- Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor
- Master Roadmap: Grounded Multimodal AI Tutor
- Week 1–2 Requirements Audit Report
- Week 1–2 Requirements Audit Report
- test_pdf_provenance_and_database_persistence

## God Nodes (most connected - your core abstractions)
1. `build_chunks()` - 53 edges
2. `TranscriptSegment` - 51 edges
3. `generate_grounded_answer()` - 48 edges
4. `TranscriptSegment` - 45 edges
5. `MockVisionAdapter` - 39 edges
6. `init_db()` - 39 edges
7. `insert_chunks()` - 37 edges
8. `active_chunks()` - 35 edges
9. `ingest()` - 34 edges
10. `SourceVersion` - 31 edges

## Surprising Connections (you probably didn't know these)
- `Key Components:` --references--> `load_and_validate_image()`  [INFERRED]
  docs/REPOSITORY_AUDIT.md → generation/vqa.py
- `Files Changed` --references--> `load_and_validate_image()`  [INFERRED]
  docs/this_week_plan.md → generation/vqa.py
- `Phase 1: M5 Learner Memory + Retrieval Evaluation + Live Vision` --references--> `LearnerProfile`  [INFERRED]
  docs/PROGRESS_TRACKER.md → memory/models.py
- `8. Recommended Implementation Order for M5 (Learner Memory)` --references--> `LearnerProfile`  [INFERRED]
  docs/REPOSITORY_AUDIT.md → memory/models.py
- `A. Memory Functionality & Architecture` --references--> `LearnerProfile`  [INFERRED]
  docs/REPOSITORY_AUDIT.md → memory/models.py

## Import Cycles
- None detected.

## Communities (50 total, 10 thin omitted)

### Community 0 - "file_content_hash"
Cohesion: 0.06
Nodes (39): Config, extract_pdf_slides(), ocr_keyframes(), extract_audio(), extract_keyframes(), _fixed_interval_keyframes(), get_audio_asset_dir(), get_audio_asset_path() (+31 more)

### Community 1 - "os"
Cohesion: 0.12
Nodes (13): check_answer_correctness(), create_intelligent_mock_vision_adapter(), main(), MockRetrievalNode, run_modality_evaluation(), run_perturbation_evaluation(), TargetedRetriever, _create_dummy_jpeg() (+5 more)

### Community 2 - "build_chunks"
Cohesion: 0.13
Nodes (35): OcrResult, TranscriptSegment, test_all_chunks_respect_max_duration(), test_evidence_id_is_deterministic(), test_audio_citation_remains_navigable(), test_citation_resolves_to_correct_source(), test_out_of_bounds_timestamp_rejected(), test_produced_evidence_preserves_provenance() (+27 more)

### Community 3 - "generate_grounded_answer"
Cohesion: 0.11
Nodes (17): generate_grounded_answer(), load_and_validate_image(), _create_dummy_jpeg(), MockNode, MockRetriever, test_answer_cites_correct_evidence_id_and_asset_metadata(), test_existing_text_only_queries_still_work(), test_max_images_limit_respected() (+9 more)

### Community 4 - "SourceAssetRecord"
Cohesion: 0.06
Nodes (19): build_source_version_from_manifest(), get_manifest_asset(), get_manifest_source(), load_manifest(), ManifestValidationError, SourceAssetRecord, validate_manifest(), test_manifest_resolves_configuration() (+11 more)

### Community 5 - "tests/test_pdf_rendering.py"
Cohesion: 0.08
Nodes (21): sample_pdf(), test_corrupted_pdf_error_handling(), test_empty_slide_distinguishable_from_failure(), test_page_number_propagation(), test_pdf_image_persistence(), test_pdf_rendering_basic(), test_pdf_text_extraction(), test_slide_deterministic_chunk_identity() (+13 more)

### Community 6 - "This Week Plan — Grounded Multimodal AI Tutor"
Cohesion: 0.04
Nodes (47): 10. P0 Changes Applied (2026-10-15), 11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15), 13. M4 Phase 3 — Align Evidence and Evaluate Visual QA (2026-10-16), 1. Repository Audit Findings, 2. Actual Test and Benchmark-Validator Results, 3. Exact Commands Used, 4. Evidence and Image-Path Data Flow, 5. Existing Local Image Availability (+39 more)

### Community 7 - "LearnerMemoryItem"
Cohesion: 0.06
Nodes (19): EphemeralSession, LearnerMemoryItem, LearnerMemoryPolicy, LearnerMemoryStore, memory_store(), test_correction_policy_preserves_history(), test_deletion_policy_immediate_erasure(), test_ephemeral_session_working_memory_discarded() (+11 more)

### Community 8 - "generation/vqa.py"
Cohesion: 0.06
Nodes (15): 2. Actual Repository Architecture, Key Components:, 12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15), Backend Configuration, Files Changed, Goal, Outstanding Limitations, Test Results (+7 more)

### Community 9 - "init_db"
Cohesion: 0.10
Nodes (18): ask_tutor(), deprecate(), ingest(), main(), resolve_citation(), setup_test_db(), transcribe(), ask_tutor() (+10 more)

### Community 10 - "grounded-multimodal-ai-tutor-dat/tests/test_benchmark.py"
Cohesion: 0.09
Nodes (6): benchmark_cases(), load_cases(), test_invalid_benchmark_entries_rejected(), benchmark_cases(), load_cases(), test_invalid_benchmark_entries_rejected()

### Community 11 - "scripts/ingest_official.py"
Cohesion: 0.15
Nodes (11): Config, ingest_official(), resolve_citation(), test_two_editions_of_same_lecture_distinguishable(), build_source_version_from_manifest(), get_manifest_asset(), get_manifest_source(), parse_srt() (+3 more)

### Community 12 - "Real Public Lecture to Evidence Path"
Cohesion: 0.18
Nodes (10): 1. Selected Lecture, 2. Source/Provenance, 3. Ingestion Command, 4. Evidence Storage, 5. One Real Evidence Record, 6. One Real Citation, 7. How an Evaluator Navigates to It, 8. How to Reproduce (+2 more)

### Community 13 - "M1 — Versioned Evidence Corpus"
Cohesion: 0.18
Nodes (10): Architecture, Cataloged vs Ingested Status, Edition and Version Identity, M1 — Versioned Evidence Corpus, Provenance, Attribution, and Licensing, Public Corpus Manifest & Provenance Model, Roadmap for the following weeks (not built yet), Running it (+2 more)

### Community 14 - "tests/test_ingestion_version_safety.py"
Cohesion: 0.11
Nodes (18): _make_args(), test_deprecate_edition_excludes_chunks(), test_failed_ingestion_can_retry(), test_full_lifecycle_preservation_and_replacement(), test_idempotent_reingest_skip(), test_new_successful_version_replaces_previous_active_version(), test_previous_version_remains_active_after_failed_replacement(), ingest() (+10 more)

### Community 15 - "grounded-multimodal-ai-tutor-dat/generation/vqa.py"
Cohesion: 0.11
Nodes (6): BaseVisionAdapter, CallableVisionAdapter, create_vision_adapter(), GoogleGenAIVisionAdapter, MockVisionAdapter, OpenAIVisionAdapter

### Community 16 - "grounded-multimodal-ai-tutor-dat/tests/test_ingestion_version_safety.py"
Cohesion: 0.07
Nodes (16): SourceVersion, setup_test_db(), test_active_chunks_excludes_old_version(), test_changed_version_or_evidence_produces_different_id(), test_delayed_old_version_write_cannot_become_active(), test_long_transcript_segment_is_split(), test_v1_to_v2_successful_replacement_lifecycle(), compute_chunk_id() (+8 more)

### Community 17 - "MockVisionAdapter"
Cohesion: 0.11
Nodes (16): MockVisionAdapter, DummyNode, DummyRetriever, sample_images(), test_callable_vision_adapter(), test_create_vision_adapter_factory(), test_empty_images_list_triggers_abstention(), test_image_removal_perturbation() (+8 more)

### Community 20 - "Modality and Perturbation Evaluation Report"
Cohesion: 0.50
Nodes (3): 1. Modality Breakdown, 2. Image Perturbation Results, Modality and Perturbation Evaluation Report

### Community 21 - "memory/models.py"
Cohesion: 0.15
Nodes (9): compute_correction_id(), _normalize_mastery_status(), _normalize_memory_type(), now_utc(), _validate_confidence(), _validate_mastery_level(), _validate_non_empty_str(), _validate_utc_datetime() (+1 more)

### Community 22 - "hashlib"
Cohesion: 0.13
Nodes (9): build_chunks(), compute_chunk_id(), EvidenceChunk, _flush_audio(), split_long_segment(), file_content_hash(), text_content_hash(), compute_memory_id() (+1 more)

### Community 23 - "TutorRetriever"
Cohesion: 0.11
Nodes (4): generate_grounded_answer(), FallbackNode, TutorRetriever, Document

### Community 24 - "pytest"
Cohesion: 0.18
Nodes (17): MasteryState, test_empty_content_rejected(), test_empty_memory_id_rejected_when_explicitly_passed(), test_empty_topic_rejected(), test_expires_at_cannot_precede_created_at(), test_invalid_confidence_rejection_mastery_state(), test_invalid_confidence_rejection_memory_entry(), test_invalid_evidence_count_rejected() (+9 more)

### Community 25 - "Repository Audit & Baseline Verification Report"
Cohesion: 0.11
Nodes (17): 1. Executive Summary, 3. Verified Historical Baseline vs. Current Actuals, 4. Verification Commands and Actual Output, 5. Subsystem Status Audit, 6. Audit of Existing Bugs (BUG-001 through BUG-006), 7. Blockers and Dependency Assessment, A. Full Pytest Suite, B. Benchmark Schema and Evidence ID Validation (+9 more)

### Community 26 - "json"
Cohesion: 0.17
Nodes (6): main(), FixedNodeRetriever, run_modality_evaluation(), SimpleNode, main(), test_evidence_alignment_report_schema_and_completeness()

### Community 27 - "_connect"
Cohesion: 0.12
Nodes (8): active_chunks(), _columns(), _connect(), deprecate_edition(), init_db(), insert_chunks(), is_source_active(), upsert_source()

### Community 28 - "MemoryEntry"
Cohesion: 0.14
Nodes (10): Phase 1: M5 Learner Memory + Retrieval Evaluation + Live Vision, Phase 2: M6 Zero Stale Leakage + M7 60+ Case Robustness Suite, Phase 3: M8 Latency vs Recall, Final Report & Interactive Demo, Progress Tracker — Grounded Multimodal AI Tutor, A. Memory Functionality & Architecture, MemoryEntry, test_deterministic_memory_id_computation(), test_memory_entry_serialization_round_trip() (+2 more)

### Community 29 - "grounded-multimodal-ai-tutor-dat/tests/test_modality_evaluation.py"
Cohesion: 0.17
Nodes (9): FixedRetriever, MockNode, slide_assets(), test_condition_1_transcript_only_abstains(), test_condition_2_ocr_text_only_abstains(), test_condition_3_actual_visual_input(), test_condition_4_correct_image_accepted(), test_condition_5_image_removed_perturbation() (+1 more)

### Community 30 - "test_learner_memory_models.py"
Cohesion: 0.21
Nodes (9): LearnerProfile, test_caller_mutation_of_dict_does_not_mutate_model(), test_default_metadata_and_preferences_isolated_between_instances(), test_learner_profile_creation_full(), test_learner_profile_creation_minimal(), test_learner_profile_serialization_round_trip(), test_naive_timestamps_rejected(), test_non_utc_timezone_normalized_to_utc() (+1 more)

### Community 31 - "generation/answer.py"
Cohesion: 0.31
Nodes (3): main(), TutorRetriever, main()

### Community 32 - "LearnerCorrection"
Cohesion: 0.19
Nodes (5): LearnerCorrection, test_empty_correction_fields_rejected(), test_empty_learner_id_rejected_across_models(), test_learner_correction_creation_and_attribution(), test_learner_correction_serialization_round_trip()

### Community 33 - "Real Public Lecture to Evidence Path"
Cohesion: 0.18
Nodes (10): 1. Selected Lecture, 2. Source/Provenance, 3. Ingestion Command, 4. Evidence Storage, 5. One Real Evidence Record, 6. One Real Citation, 7. How an Evaluator Navigates to It, 8. How to Reproduce (+2 more)

### Community 35 - "M1 — Versioned Evidence Corpus"
Cohesion: 0.18
Nodes (10): Architecture, Cataloged vs Ingested Status, Edition and Version Identity, M1 — Versioned Evidence Corpus, Provenance, Attribution, and Licensing, Public Corpus Manifest & Provenance Model, Roadmap for the following weeks (not built yet), Running it (+2 more)

### Community 36 - "memory/__init__.py"
Cohesion: 0.28
Nodes (3): 8. Recommended Implementation Order for M5 (Learner Memory), MasteryStatus, MemoryType

### Community 37 - "M1 — Versioned Evidence Corpus"
Cohesion: 0.25
Nodes (7): Architecture, M1 — Versioned Evidence Corpus, Roadmap for the following weeks (not built yet), Running it, What "done" means for M1, per the spec, What's already tested, Why SQLite and not a vector DB yet

### Community 38 - "M1 — Versioned Evidence Corpus"
Cohesion: 0.25
Nodes (7): Architecture, M1 — Versioned Evidence Corpus, Roadmap for the following weeks (not built yet), Running it, What "done" means for M1, per the spec, What's already tested, Why SQLite and not a vector DB yet

### Community 39 - "Benchmark Dataset"
Cohesion: 0.40
Nodes (4): Benchmark Dataset, Labelling Policy, Schema, Validation

### Community 40 - "Benchmark Dataset"
Cohesion: 0.40
Nodes (4): Benchmark Dataset, Labelling Policy, Schema, Validation

### Community 43 - "Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor"
Cohesion: 0.50
Nodes (3): Active & Resolved Bug Ledger, Bug Tracker & Risk Ledger — Grounded Multimodal AI Tutor, Severity Definitions

### Community 44 - "Master Roadmap: Grounded Multimodal AI Tutor"
Cohesion: 0.50
Nodes (3): Architecture & Milestone Mapping, Master Roadmap: Grounded Multimodal AI Tutor, Summary of Phases and Owners

## Knowledge Gaps
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Files Changed` connect `generation/vqa.py` to `generate_grounded_answer`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `build_chunks()` (e.g. with `OcrResult` and `TranscriptSegment`) actually correct?**
  _`build_chunks()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `file_content_hash` be split into smaller, more focused modules?**
  _Cohesion score 0.06128364389233954 - nodes in this community are weakly interconnected._
- **Why does `12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15)` connect `generation/vqa.py` to `This Week Plan — Grounded Multimodal AI Tutor`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `TranscriptSegment` (e.g. with `build_chunks()` and `_flush_audio()`) actually correct?**
  _`TranscriptSegment` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.12312312312312312 - nodes in this community are weakly interconnected._
- **Why does `This Week Plan — Grounded Multimodal AI Tutor` connect `This Week Plan — Grounded Multimodal AI Tutor` to `generation/vqa.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._