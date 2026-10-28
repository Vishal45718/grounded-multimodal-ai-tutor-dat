# Graph Report - dat_project  (2026-10-16)

## Corpus Check
- 40 files · ~169,917 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .jsonl 1, .db 1, .ini 1)

## Summary
- 480 nodes · 1223 edges · 26 communities (23 shown, 3 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 118 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6e748683`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_ingestion_version_safety.py
- generate_grounded_answer
- build_chunks
- MockVisionAdapter
- test_source_manifest.py
- test_pdf_rendering.py
- Pre-requisites (P0 — fix before anything else)
- This Week Plan — Grounded Multimodal AI Tutor
- vqa.py
- test_real_evidence.py
- test_benchmark.py
- scripts/ingest_official.py
- Real Public Lecture to Evidence Path
- active_chunks
- ocr.py
- 13. M4 Phase 3 — Align Evidence and Evaluate Visual QA (2026-10-16)
- 4. Evidence and Image-Path Data Flow
- 12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15)
- Modality and Perturbation Evaluation Report
- 10. P0 Changes Applied (2026-10-15)
- 2. Actual Test and Benchmark-Validator Results
- ask_tutor
- 11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15)
- setup_test_db

## God Nodes (most connected - your core abstractions)
1. `generate_grounded_answer()` - 36 edges
2. `active_chunks()` - 34 edges
3. `build_chunks()` - 33 edges
4. `TranscriptSegment` - 29 edges
5. `SourceVersion` - 28 edges
6. `ingest()` - 27 edges
7. `insert_chunks()` - 25 edges
8. `init_db()` - 24 edges
9. `upsert_source()` - 21 edges
10. `VisualPayload` - 19 edges

## Surprising Connections (you probably didn't know these)
- `What was NOT changed` --references--> `file_content_hash()`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Blockers (must fix before M4/M5)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Files changed` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `P0a — Fix `SourceVersion` dataclass (unblocks 11 failing tests)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- ``image_path` end-to-end flow` --references--> `test_asset_paths_are_version_isolated()`  [INFERRED]
  docs/this_week_plan.md → tests/test_ingestion_version_safety.py

## Import Cycles
- None detected.

## Communities (26 total, 3 thin omitted)

### Community 0 - "test_ingestion_version_safety.py"
Cohesion: 0.07
Nodes (33): Failing Tests (12) — Exact Errors, Module Map, Test result, transcribe(), file_content_hash(), text_content_hash(), extract_audio(), extract_keyframes() (+25 more)

### Community 1 - "generate_grounded_answer"
Cohesion: 0.06
Nodes (19): check_answer_correctness(), create_intelligent_mock_vision_adapter(), main(), MockRetrievalNode, run_modality_evaluation(), run_perturbation_evaluation(), TargetedRetriever, main() (+11 more)

### Community 2 - "build_chunks"
Cohesion: 0.16
Nodes (14): build_chunks(), compute_chunk_id(), _flush_audio(), split_long_segment(), TranscriptSegment, test_all_chunks_respect_max_duration(), test_evidence_id_is_deterministic(), test_long_transcript_segment_is_split() (+6 more)

### Community 3 - "MockVisionAdapter"
Cohesion: 0.08
Nodes (15): MockVisionAdapter, _create_dummy_jpeg(), MockNode, MockRetriever, test_answer_cites_correct_evidence_id_and_asset_metadata(), test_existing_text_only_queries_still_work(), test_max_images_limit_respected(), test_missing_required_image_causes_abstention() (+7 more)

### Community 4 - "test_source_manifest.py"
Cohesion: 0.07
Nodes (18): Benchmark Dataset, Labelling Policy, Schema, Validation, Config, build_source_version_from_manifest(), get_manifest_asset(), get_manifest_source() (+10 more)

### Community 5 - "test_pdf_rendering.py"
Cohesion: 0.13
Nodes (10): extract_pdf_slides(), _create_synthetic_pdf(), test_pdf_deterministic_page_identity(), test_pdf_does_not_invent_video_timestamps(), test_pdf_empty_text_handling(), test_pdf_extracted_text(), test_pdf_image_existence_after_temporary_download_deleted(), test_pdf_page_rendering_creates_valid_jpeg() (+2 more)

### Community 6 - "Pre-requisites (P0 — fix before anything else)"
Cohesion: 0.25
Nodes (8): 7. Prioritised Implementation Plan for M4 and M5, M4 — Visual Question Answering, P0a — Fix `SourceVersion` dataclass (unblocks 11 failing tests), P0b — Fix hash assertion in test (test bug, 1 line), P0c — Re-run pytest and confirm 0 failures, P0d — Run official ingest to populate DB for benchmark, Pre-requisites (P0 — fix before anything else), Step-by-step

### Community 7 - "This Week Plan — Grounded Multimodal AI Tutor"
Cohesion: 0.25
Nodes (7): 1. Repository Audit Findings, 3. Exact Commands Used, 5. Existing Local Image Availability, 6. Blockers and Risks, 9. Assumptions and Unresolved Questions, Blockers (must fix before M4/M5), This Week Plan — Grounded Multimodal AI Tutor

### Community 8 - "vqa.py"
Cohesion: 0.07
Nodes (9): Files Changed, BaseVisionAdapter, CallableVisionAdapter, get_vision_adapter(), GoogleGenAIVisionAdapter, LlamaIndexVisionAdapter, load_and_validate_image(), OpenAIVisionAdapter (+1 more)

### Community 9 - "test_real_evidence.py"
Cohesion: 0.17
Nodes (9): resolve_citation(), _columns(), _connect(), init_db(), test_audio_citation_remains_navigable(), test_citation_resolves_to_correct_source(), test_unknown_evidence_id_rejected(), test_visual_citation_does_not_create_fake_timestamp() (+1 more)

### Community 10 - "test_benchmark.py"
Cohesion: 0.18
Nodes (3): benchmark_cases(), load_cases(), test_invalid_benchmark_entries_rejected()

### Community 11 - "scripts/ingest_official.py"
Cohesion: 0.14
Nodes (13): Architecture Summary (verified), Files changed, Risks, EvidenceChunk, parse_srt(), SourceVersion, ingest_official(), insert_chunks() (+5 more)

### Community 12 - "Real Public Lecture to Evidence Path"
Cohesion: 0.18
Nodes (10): 1. Selected Lecture, 2. Source/Provenance, 3. Ingestion Command, 4. Evidence Storage, 5. One Real Evidence Record, 6. One Real Citation, 7. How an Evaluator Navigates to It, 8. How to Reproduce (+2 more)

### Community 13 - "active_chunks"
Cohesion: 0.11
Nodes (20): Architecture, M1 — Versioned Evidence Corpus, Roadmap for the following weeks (not built yet), Running it, What "done" means for M1, per the spec, What's already tested, Why SQLite and not a vector DB yet, W2 priority order (+12 more)

### Community 14 - "ocr.py"
Cohesion: 0.42
Nodes (8): ocr_keyframes(), OcrResult, Keyframe, test_ocr_failure_is_recorded(), test_ocr_failure_preserves_visual_asset(), test_ocr_success_records_success_status(), test_text_free_image_is_not_treated_as_ocr_failure(), test_visual_evidence_does_not_use_synthetic_video_timestamp()

### Community 15 - "13. M4 Phase 3 — Align Evidence and Evaluate Visual QA (2026-10-16)"
Cohesion: 0.29
Nodes (7): 13. M4 Phase 3 — Align Evidence and Evaluate Visual QA (2026-10-16), Baseline Investigation & Test Discrepancy Resolution, Evaluation Results, Evidence Mapping Summary, Files Changed, Goal, Outstanding Work

### Community 16 - "4. Evidence and Image-Path Data Flow"
Cohesion: 0.29
Nodes (6): 4. Evidence and Image-Path Data Flow, Chunk ID generation (deterministic), `image_path` end-to-end flow, `source_id` / `asset_id` / `edition_id` flow, Timestamp flow to M3 citations, test_changed_version_or_evidence_produces_different_id()

### Community 17 - "12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15)"
Cohesion: 0.40
Nodes (5): 12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15), Backend Configuration, Goal, Outstanding Limitations, Test Results

### Community 20 - "Modality and Perturbation Evaluation Report"
Cohesion: 0.50
Nodes (3): 1. Modality Breakdown, 2. Image Perturbation Results, Modality and Perturbation Evaluation Report

### Community 21 - "10. P0 Changes Applied (2026-10-15)"
Cohesion: 0.50
Nodes (4): 10. P0 Changes Applied (2026-10-15), Files changed, Remaining blockers, What was NOT changed

### Community 22 - "2. Actual Test and Benchmark-Validator Results"
Cohesion: 0.50
Nodes (4): 2. Actual Test and Benchmark-Validator Results, Benchmark Validator, Passing Tests (35), Test Suite

### Community 23 - "ask_tutor"
Cohesion: 0.67
Nodes (4): 8. Recommended Next-Step Order, M5 — Learner Memory, Step-by-step, ask_tutor()

### Community 24 - "11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15)"
Cohesion: 0.67
Nodes (3): 11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15), Goal, Test Results

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `active_chunks()` connect `active_chunks` to `test_ingestion_version_safety.py`, `generate_grounded_answer`, `build_chunks`, `test_source_manifest.py`, `test_pdf_rendering.py`, `Pre-requisites (P0 — fix before anything else)`, `vqa.py`, `test_real_evidence.py`, `scripts/ingest_official.py`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `generate_grounded_answer()` (e.g. with `Files Changed` and `Step-by-step`) actually correct?**
  _`generate_grounded_answer()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_ingestion_version_safety.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06646825396825397 - nodes in this community are weakly interconnected._
- **Why does `SourceVersion` connect `scripts/ingest_official.py` to `test_ingestion_version_safety.py`, `test_source_manifest.py`, `test_pdf_rendering.py`, `Pre-requisites (P0 — fix before anything else)`, `This Week Plan — Grounded Multimodal AI Tutor`, `test_real_evidence.py`, `active_chunks`, `10. P0 Changes Applied (2026-10-15)`, `ask_tutor`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `active_chunks()` (e.g. with `Architecture` and `Roadmap for the following weeks (not built yet)`) actually correct?**
  _`active_chunks()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `generate_grounded_answer` be split into smaller, more focused modules?**
  _Cohesion score 0.06377204884667571 - nodes in this community are weakly interconnected._
- **Why does `generate_grounded_answer()` connect `generate_grounded_answer` to `test_ingestion_version_safety.py`, `MockVisionAdapter`, `Pre-requisites (P0 — fix before anything else)`, `vqa.py`, `test_real_evidence.py`, `ask_tutor`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._