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
  keyframe extraction. Keyframes are picked by scene-change detection
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
  a configurable max duration (default 30s) so retrieval isn't indexing a
  chunk per two-second utterance, while capping chunk length so a citation
  stays a useful pointer. Visual chunks are one per OCR'd keyframe.
- **`ingestion/versioning.py`** — SHA-256 of the video file is the
  content-version id. Same bytes → same hash → re-ingestion is a no-op.
  Different bytes under the same `source_id` (a re-recorded or re-edited
  lecture) → old chunks get marked `is_stale`.
- **`storage/`** — SQLite schema (`sources`, `chunks`) plus a small CRUD
  API. `active_chunks()` is the one query M2's retriever should ever call —
  it strictly enforces that returned evidence matches the currently active
  source content version (`c.content_hash == s.content_hash`), excluding
  stale chunks and deprecated course editions.
- **Ingestion Lifecycle & Version Safety:**
  1. Check if the source is already active at the exact `content_hash` (idempotent skip).
  2. Extract audio, transcribe (ASR), and extract/OCR keyframes.
  3. Build evidence chunks.
  4. Store chunks and activate the new source version in a safe sequence.
  If extraction fails at any point, the source is never activated, the previous active version remains untouched and usable, and subsequent ingestion attempts can retry cleanly. Delayed writes from superseded versions are marked stale (`is_stale = 1`) and rejected by `active_chunks()`.

## Why SQLite and not a vector DB yet

M1 is about the *corpus*, not retrieval — there's no embedding or search
happening here on purpose. Bringing in a vector DB now would mean
re-deciding it again in M2 anyway once you know your actual embedding
model and reranker. `active_chunks()` is the seam: M2 reads from it and
builds whatever index it wants on top (FAISS/Qdrant for dense, a BM25
index for sparse) without touching this layer.

## Running it

```bash
pip install -r requirements.txt
# ffmpeg + ffprobe must also be on PATH (system packages, not pip)
# tesseract-ocr must also be on PATH for pytesseract to work

python main.py ingest \
  --video path/to/lecture03.mp4 \
  --source-id cs5903-lec03 \
  --title "Lecture 3: Hybrid Search" \
  --course-edition Fall2026

# Simulating a superseded course edition (M6):
python main.py deprecate --course-edition Fall2025

# Running test suite:
pytest -v
```

Re-running `ingest` on the exact same file is a safe no-op. Re-running it
on an edited file (different bytes, same `--source-id`) marks the old
chunks stale and indexes the new ones. If extraction fails mid-way, the
previous active version remains intact and retrying works immediately.

## What's tested

Automated unit tests in `tests/test_ingestion_version_safety.py` verify:
- Failed ingestion can be retried without getting blocked.
- Previous active version remains active and usable if a replacement fails.
- Successful new version activates and replaces the previous version.
- `active_chunks()` strictly excludes old or superseded content hashes.
- Delayed old-version writes cannot become active.
- Edition-wide deprecation invalidates active evidence.

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
