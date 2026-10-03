# M1 — Versioned Evidence Corpus

> Text, transcript, slide/image/code evidence and timestamp metadata are
> indexed while preserving source and content-version identifiers.

Broken into concrete requirements:
1. Ingest a lecture video → audio transcript **and** on-screen visual text, both timestamped.
2. Every chunk knows which source video and which *version* of that video it came from.
3. Re-ingesting an unchanged video is a no-op; re-ingesting an edited video invalidates the old chunks instead of duplicating or silently keeping stale ones (this is what M6's "content updates invalidate stale evidence" actually depends on — it has to be built into the corpus now, not bolted on in week 6).

## Architecture

```
video file
    │
    ├─► extract_audio()      ──► transcribe()      ──► TranscriptSegment[] (audio, timestamped)
    │
    └─► extract_keyframes()  ──► ocr_keyframes()    ──► OcrResult[] (visual, timestamped)
                                                              │
                                                              ▼
                                                        build_chunks()
                                                              │
                                                              ▼
                                                      EvidenceChunk[] ──► corpus_store (SQLite)
```

- **`ingestion/video_processor.py`** — ffmpeg-based audio extraction and
  keyframe extraction with version-isolated asset paths (`data/keyframes/<source_id>/<content_hash>/...`
  and `data/audio/<source_id>/<content_hash>/...`). Keyframes are picked by scene-change detection
  first (catches slide transitions / new code appearing on screen); if a
  video has too few scene changes (e.g. a static talking-head segment with
  code on screen the whole time), it falls back to fixed-interval sampling
  so visual evidence is never silently missed.
- **`ingestion/transcriber.py`** — `faster-whisper` ASR, returns
  start/end-timestamped segments.
- **`ingestion/ocr.py`** — Tesseract OCR over each keyframe. Frames with no
  detected text (pure talking-head shots) are dropped rather than indexed
  as empty evidence.
- **`ingestion/chunker.py`** — merges consecutive short ASR segments up to
  `CONFIG.max_chunk_duration_sec` (default 30s) and strictly splits individual
  oversized segments ($N = \lceil\text{duration}/\text{max\_duration}\rceil$) without
  inventing word-level timestamps. Evidence chunk IDs are generated deterministically
  via SHA-256 from stable evidence identity (`source_id`, `content_hash`, modality,
  start/end timestamps, text/frame metadata) ensuring stability across rebuilds without
  randomness. Visual chunks are one per OCR'd keyframe.
- **`ingestion/versioning.py`** — SHA-256 of the video file is the
  content-version id. Same bytes → same hash → re-ingestion is a no-op.
  Different bytes under the same `source_id` (a re-recorded or re-edited
  lecture) → old chunks get marked `is_stale`.
- **`storage/`** — SQLite schema (`sources`, `chunks`) plus a small CRUD
  API. `active_chunks()` is the one query M2's retriever should ever call —
  it strictly enforces that returned evidence matches the currently active
  source content version (`c.content_hash == s.content_hash`), excluding
  stale chunks and deprecated course editions.
- **Ingestion Lifecycle & Version Safety (V1 → V2):**
  1. Check if the source is already active at the exact `content_hash` (idempotent skip).
  2. Extract audio and keyframes into version-isolated paths (`data/audio/<source_id>/<content_hash>/` and `data/keyframes/<source_id>/<content_hash>/`).
  3. Transcribe audio and OCR keyframes.
  4. Build evidence chunks with deterministic IDs and strict chunk duration caps.
  5. Stage new chunks into the database via `insert_chunks(chunks)`. Chunks start as `is_stale = 1` while V1 remains active.
  6. Activate the new version via `upsert_source(version)`: marks old version chunks as stale (`is_stale = 1`), updates the active source entry to V2, and activates V2 chunks (`is_stale = 0`).
  7. Delayed superseded writes cannot become active (`existing.ingested_at > version.ingested_at`), and `active_chunks()` strictly serves the active version.

## Why SQLite and not a vector DB yet

M1 is about the *corpus*, not retrieval — there's no embedding or search
happening here on purpose. Bringing in a vector DB now would mean
re-deciding it again in M2 anyway once you know your actual embedding
model and reranker. `active_chunks()` is the seam: M2 reads from it and
builds whatever index it wants on top (FAISS/Qdrant for dense, a BM25
index for sparse) without touching this layer.

## Public Corpus Manifest & Provenance Model

The prototype relies on an authoritative, bounded public instructional corpus selected from Harvard University's CS50x OpenCourseWare:
- **Manifest Location:** `data/source_manifest.json` and `data/source_manifest.yaml`
- **Selected Corpus Subset:**
  - **CS50x 2024 Edition:** Weeks 0 through 5 (Scratch, C, Arrays, Algorithms, Memory, Data Structures).
  - **CS50x 2023 Edition:** Weeks 0 and 1 (Scratch, C) retained for cross-edition versioning, supersession, and deprecation evaluation.

### Edition and Version Identity
The system maintains strict separation between logical course topics, course editions, media assets, and byte-level content versions:
1. **Logical Source ID (`source_id`):** Identifies the logical course module across iterations (e.g. `cs50-lec00` for Week 0 Scratch).
2. **Course Edition (`edition_id`):** Distinguishes the specific offering/year (e.g. `2024` vs `2023`). A logical lecture taught in 2023 and 2024 has the same `source_id` but distinct `edition_id`s, different measured durations (7217s vs 7543s), and distinct asset URLs.
3. **Asset ID (`asset_id`):** Unambiguously identifies a specific public media asset within the manifest (e.g. `cs50-2024-lec00-video`).
4. **Content Version Hash (`content_hash`):** The SHA-256 digest of the actual local bytes. Only populated when an asset has been locally retrieved and hashed.
5. **Source & Original URLs:** Preserves both the canonical course landing page (`source_url`) and the specific original video location (`original_asset_url`).

### Cataloged vs Ingested Status
- All entries currently in `data/source_manifest.json` represent verified public instructional assets cataloged with real metadata (`ingestion_status: "cataloged"`).
- We do not claim full local corpus ingestion until assets are physically retrieved; their `content_hash` is explicitly recorded as `null` until actual local files are downloaded and verified.

### Provenance, Attribution, and Licensing
- **Attribution:** CS50's Introduction to Computer Science, David J. Malan, Harvard University.
- **Licence:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0).
- **Public Availability & Redistribution Policy:** Public accessibility on Harvard OpenCourseWare, edX, or YouTube does **not** imply unrestricted proprietary, commercial, or public redistribution. Assets must be accessed in accordance with CC BY-NC-SA 4.0 terms, respecting attribution, non-commercial restrictions, and share-alike licensing.

## Running it

```bash
pip install -r requirements.txt
# ffmpeg + ffprobe must also be on PATH (system packages, not pip)
# tesseract-ocr must also be on PATH for pytesseract to work

# Ingest using manifest asset resolution (auto-resolves title, edition, source_id, and provenance):
python main.py ingest \
  --video path/to/lecture00.mp4 \
  --asset-id cs50-2024-lec00-video

# Or ingest with explicit flags:
python main.py ingest \
  --video path/to/lecture03.mp4 \
  --source-id cs50-lec03 \
  --title "Lecture 3: Algorithms" \
  --course-edition 2024

# Simulating a superseded course edition (M6):
python main.py deprecate --course-edition 2023

# Running test suite:
pytest -v
```

Re-running `ingest` on the exact same file is a safe no-op. Re-running it
on an edited file (different bytes, same `--source-id`) marks the old
chunks stale and indexes the new ones. If extraction fails mid-way, the
previous active version remains intact and retrying works immediately.

## What's tested

Automated unit tests in `tests/test_ingestion_version_safety.py` and `tests/test_source_manifest.py` verify:
- Failed ingestion can be retried without getting blocked.
- Previous active version remains active and usable if a replacement fails.
- Successful new version activates and replaces the previous version (V1 → V2 lifecycle).
- `active_chunks()` strictly excludes old or superseded content hashes.
- Delayed old-version writes cannot become active.
- Edition-wide deprecation invalidates active evidence.
- Evidence IDs are deterministic and stable across identical rebuilds.
- Changing version, source, modality, time, or text produces different evidence IDs.
- Audio and keyframe asset paths are version-isolated by source ID and content hash.
- Reprocessing the same version resolves to the same asset namespace.
- Transcript segments exceeding max duration are split deterministically without data loss.
- All generated chunks respect the configured maximum duration cap.
- Manifest loads and validates real CS50 public instructional sources successfully.
- Malformed manifest records (missing fields, invalid modalities, placeholder URLs) are rejected.
- Accidental duplicate source/version/asset identities and URLs are rejected.
- Provenance metadata (`asset_id`, `source_url`) is preserved in `SourceVersion`, `EvidenceChunk`, and database queries (`active_chunks`).
- Cross-edition logical lectures (`2023` vs `2024`) remain strictly distinguishable.
- CLI auto-resolves metadata and provenance from manifest when `--asset-id` is supplied.

## Roadmap for the following weeks (not built yet)

- **M2 — Hybrid retrieval:** read from `active_chunks()`, build a dense
  index (embeddings) and a sparse index (BM25) separately, combine with
  Reciprocal Rank Fusion, add a reranker for ambiguous/high-recall queries.
  Evaluate retrieval quality *per query class* (conceptual vs. syntax/code)
  since that's the whole reason for hybrid search — decide the two classes
  and how you'll label queries into them before writing the retriever.
- **M3 — Timestamp-grounded answers:** generate answers that cite
  `[mm:ss]` from the retrieved chunk's `start_sec`/`end_sec`, precise
  enough for a player to seek to.
- **M4 — Multimodal evidence benchmark:** you already have the visual
  chunks from M1; next is building a benchmark subset of questions
  answerable *only* from OCR'd/visual chunks, to prove the tutor actually
  uses them.
- **M5 — Learner memory:** a separate store (durable profile — mastery,
  goals, misconceptions) from ephemeral per-conversation state, with
  explicit write/expiry/correction/deletion policies. This is independent
  of M1–M4 and could be built in parallel.
- **M6 — Abstention + version safety:** mostly plumbing at this point —
  `active_chunks()` already excludes stale/deprecated content; the
  remaining work is the retriever/generator refusing to answer when
  nothing relevant comes back above a confidence threshold.
- **M7 — Eval harness + red team:** retrieval quality, answer correctness,
  citation support, abstention rate, stale-source handling, and adversarial
  prompt-injection tests (e.g. injected instructions hidden in slide OCR
  text — M1's OCR path is exactly where that attack surface lives, worth
  keeping in mind when M7 designs its red-team cases).
- **M8 — Performance characterization:** latency/quality tradeoffs across
  ≥2 retrieval/chunking/reranking configs — the `CONFIG` dataclass in
  `config.py` already isolates the chunking knobs (`max_chunk_duration_sec`,
  `keyframe_interval_sec`, etc.) so this is a parameter sweep, not a rewrite.
