# Graph Report - dat_project  (2026-10-16)

## Corpus Check
- 33 files · ~162,452 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .jsonl 1, .db 1, .ini 1)

## Summary
- 431 nodes · 1088 edges · 20 communities (15 shown, 5 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 107 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6e748683`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_ingestion_version_safety.py
- scripts/ingest_official.py
- test_real_evidence.py
- test_vqa.py
- test_source_manifest.py
- test_pdf_rendering.py
- This Week Plan — Grounded Multimodal AI Tutor
- video_processor.py
- Files Changed
- init_db
- test_benchmark.py
- VisualPayload
- Real Public Lecture to Evidence Path
- M1 — Versioned Evidence Corpus
- Benchmark Dataset
- MockVisionAdapter
- OpenAIVisionAdapter
- Public Corpus Manifest & Provenance Model

## God Nodes (most connected - your core abstractions)
1. `build_chunks()` - 33 edges
2. `active_chunks()` - 30 edges
3. `TranscriptSegment` - 29 edges
4. `SourceVersion` - 28 edges
5. `generate_grounded_answer()` - 27 edges
6. `ingest()` - 27 edges
7. `insert_chunks()` - 25 edges
8. `init_db()` - 24 edges
9. `upsert_source()` - 21 edges
10. `extract_pdf_slides()` - 18 edges

## Surprising Connections (you probably didn't know these)
- `What was NOT changed` --references--> `file_content_hash()`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Blockers (must fix before M4/M5)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Files changed` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `P0a — Fix `SourceVersion` dataclass (unblocks 11 failing tests)` --references--> `SourceVersion`  [INFERRED]
  docs/this_week_plan.md → ingestion/versioning.py
- `Architecture` --references--> `active_chunks()`  [INFERRED]
  dat-tutor-m1-README.md → storage/corpus_store.py

## Import Cycles
- None detected.

## Communities (20 total, 5 thin omitted)

### Community 0 - "test_ingestion_version_safety.py"
Cohesion: 0.07
Nodes (41): 1. Repository Audit Findings, Architecture Summary (verified), Failing Tests (12) — Exact Errors, Module Map, Risks, Test result, W2 priority order, Week 1–2 Requirements Audit Report (+33 more)

### Community 1 - "scripts/ingest_official.py"
Cohesion: 0.07
Nodes (7): Config, parse_srt(), text_content_hash(), Document, TutorRetriever, ingest_official(), main()

### Community 2 - "test_real_evidence.py"
Cohesion: 0.10
Nodes (26): 4. Evidence and Image-Path Data Flow, Chunk ID generation (deterministic), `image_path` end-to-end flow, `source_id` / `asset_id` / `edition_id` flow, Timestamp flow to M3 citations, build_chunks(), compute_chunk_id(), _flush_audio() (+18 more)

### Community 3 - "test_vqa.py"
Cohesion: 0.11
Nodes (16): generate_grounded_answer(), _create_dummy_jpeg(), MockNode, MockRetriever, test_answer_cites_correct_evidence_id_and_asset_metadata(), test_existing_text_only_queries_still_work(), test_max_images_limit_respected(), test_missing_required_image_causes_abstention() (+8 more)

### Community 4 - "test_source_manifest.py"
Cohesion: 0.11
Nodes (13): main(), build_source_version_from_manifest(), get_manifest_asset(), get_manifest_source(), load_manifest(), ManifestValidationError, SourceAssetRecord, validate_manifest() (+5 more)

### Community 5 - "test_pdf_rendering.py"
Cohesion: 0.11
Nodes (17): Files changed, extract_pdf_slides(), ocr_keyframes(), OcrResult, Keyframe, test_ocr_failure_is_recorded(), test_ocr_failure_preserves_visual_asset(), test_ocr_success_records_success_status() (+9 more)

### Community 6 - "This Week Plan — Grounded Multimodal AI Tutor"
Cohesion: 0.06
Nodes (30): 10. P0 Changes Applied (2026-10-15), 11. M4 Phase 1 — Real Slide Evidence Ingestion (2026-10-15), 12. M4 Phase 2 — Real Multimodal Question Answering (2026-10-15), 2. Actual Test and Benchmark-Validator Results, 3. Exact Commands Used, 5. Existing Local Image Availability, 6. Blockers and Risks, 7. Prioritised Implementation Plan for M4 and M5 (+22 more)

### Community 7 - "video_processor.py"
Cohesion: 0.14
Nodes (13): 9. Assumptions and Unresolved Questions, file_content_hash(), extract_audio(), extract_keyframes(), _fixed_interval_keyframes(), get_audio_asset_dir(), get_audio_asset_path(), get_keyframe_asset_dir() (+5 more)

### Community 8 - "Files Changed"
Cohesion: 0.11
Nodes (6): Files Changed, BaseVisionAdapter, get_vision_adapter(), GoogleGenAIVisionAdapter, LlamaIndexVisionAdapter, load_and_validate_image()

### Community 9 - "init_db"
Cohesion: 0.13
Nodes (8): M5 — Learner Memory, Step-by-step, ask_tutor(), _columns(), init_db(), setup_test_db(), setup_test_db(), setup_test_db()

### Community 10 - "test_benchmark.py"
Cohesion: 0.18
Nodes (3): benchmark_cases(), load_cases(), test_invalid_benchmark_entries_rejected()

### Community 12 - "Real Public Lecture to Evidence Path"
Cohesion: 0.18
Nodes (10): 1. Selected Lecture, 2. Source/Provenance, 3. Ingestion Command, 4. Evidence Storage, 5. One Real Evidence Record, 6. One Real Citation, 7. How an Evaluator Navigates to It, 8. How to Reproduce (+2 more)

### Community 13 - "M1 — Versioned Evidence Corpus"
Cohesion: 0.25
Nodes (7): Architecture, M1 — Versioned Evidence Corpus, Roadmap for the following weeks (not built yet), Running it, What "done" means for M1, per the spec, What's already tested, Why SQLite and not a vector DB yet

### Community 14 - "Benchmark Dataset"
Cohesion: 0.33
Nodes (4): Benchmark Dataset, Labelling Policy, Schema, Validation

### Community 17 - "Public Corpus Manifest & Provenance Model"
Cohesion: 0.50
Nodes (4): Cataloged vs Ingested Status, Edition and Version Identity, Provenance, Attribution, and Licensing, Public Corpus Manifest & Provenance Model

## Knowledge Gaps
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `active_chunks()` connect `test_ingestion_version_safety.py` to `scripts/ingest_official.py`, `test_source_manifest.py`, `test_pdf_rendering.py`, `This Week Plan — Grounded Multimodal AI Tutor`, `Files Changed`, `M1 — Versioned Evidence Corpus`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `build_chunks()` (e.g. with `Architecture Summary (verified)` and `Files changed`) actually correct?**
  _`build_chunks()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_ingestion_version_safety.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07370600414078675 - nodes in this community are weakly interconnected._
- **Why does `Files Changed` connect `Files Changed` to `test_ingestion_version_safety.py`, `test_real_evidence.py`, `test_vqa.py`, `This Week Plan — Grounded Multimodal AI Tutor`, `VisualPayload`, `MockVisionAdapter`, `OpenAIVisionAdapter`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `active_chunks()` (e.g. with `Architecture` and `Roadmap for the following weeks (not built yet)`) actually correct?**
  _`active_chunks()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `scripts/ingest_official.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0700354609929078 - nodes in this community are weakly interconnected._
- **Why does `SourceVersion` connect `test_ingestion_version_safety.py` to `scripts/ingest_official.py`, `test_real_evidence.py`, `test_source_manifest.py`, `test_pdf_rendering.py`, `This Week Plan — Grounded Multimodal AI Tutor`, `video_processor.py`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._