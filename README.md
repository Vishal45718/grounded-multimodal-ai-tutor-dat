# Grounded Multimodal AI Tutor (DAT Tutor)

An authoritative, multimodal instructional tutor grounded in Harvard University's CS50 OpenCourseWare lecture videos, slides, and transcripts. Built with strict non-hallucinatory grounding, timestamp-level citations `[mm:ss]`, multimodal visual VQA, persistent learner memory with pedagogical styling, zero-stale-leakage version safety, and calibrated abstention.

---

## Architecture & System Overview

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

- **M1: Ingestion & Corpus Store** (`ingestion/`, `storage/`): Ffmpeg-based audio and keyframe extraction, faster-whisper ASR, Tesseract OCR, deterministic chunking with duration caps, and SHA-256 byte-level content versioning.
- **M2: Hybrid Retrieval** (`retrieval/`): Sparse BM25 index + dense semantic embeddings combined with Reciprocal Rank Fusion (RRF) and optional cross-encoder reranking.
- **M3: Grounded Generation** (`generation/`): Strict attribution formatting, timestamped citations `[mm:ss]`, and jump URLs (`?t=XXs`) linked directly to source media.
- **M4: Multimodal VQA** (`generation/vqa.py`): Visual question answering over real keyframe slides and diagrams using pluggable vision adapters (Gemini / OpenAI / offline mock).
- **M5: Persistent Learner Memory** (`memory/`): Durable SQLite WAL store (`LearnerMemoryStore`) with foreign keys, retention TTLs, mastery tracking, pedagogical context injection, and GDPR deletion/purge.
- **M6: Version Safety & Calibrated Abstention** (`guardrails/`): Mathematical guarantee that superseded or deprecated course editions are invalidated; calibrated refusal on low-confidence or out-of-domain queries.
- **M7: Evaluation Benchmark & Red-Teaming** (`benchmark/`, `tests/`): 60-case gold benchmark QA suite (`benchmark/cases_60.jsonl`), adversarial prompt-injection defense, and end-to-end regression testing.
- **M8: Performance Tradeoffs & Interactive Demo** (`demo/`, `benchmark/`): Profiling of latency vs. recall Pareto frontiers and an interactive FastAPI web demo with synchronized media player and live Memory Inspector.

---

## Milestone Status Summary (M1–M8)

| Milestone | Capability | Status | Primary Modules |
|:---|:---|:---:|:---|
| **M1: Ingestion** | Video/audio extraction, Whisper ASR, OCR, deterministic chunking, content hash versioning | ✅ Complete | `ingestion/`, `storage/schema.sql`, `storage/corpus_store.py` |
| **M2: Hybrid Retrieval** | BM25 sparse + dense embeddings + Reciprocal Rank Fusion + cross-encoder reranking | ✅ Complete | `retrieval/retriever.py`, `retrieval/reranker.py` |
| **M3: Grounded Generation** | Strict timestamp `[mm:ss]` & slide citations; zero-hallucination guardrails | ✅ Complete | `generation/answer.py`, `generation/citation_resolver.py` |
| **M4: Multimodal VQA** | Visual question answering over real keyframes/slides; mock + live vision adapters | 🔍 Mocks Pass (Live key pending) | `generation/vqa.py`, `tests/test_vqa.py` (BUG-005) |
| **M5: Learner Memory** | SQLite WAL store (`LearnerMemoryStore`), policy/engine, pedagogical context, GDPR purge | ✅ Complete | `memory/store.py`, `memory/engine.py`, `memory/policy.py`, `memory/models.py` |
| **M6: Abstention & Version Safety** | Automated invalidation of stale/deprecated editions; calibrated refusal on low confidence | ✅ Complete | `guardrails/abstention_policy.py`, `tests/test_abstention_and_version_safety.py` |
| **M7: 60-Case Robustness Suite** | 60-case benchmark QA suite; direct/indirect prompt injection defense; adversarial testing | ✅ Complete | `benchmark/cases_60.jsonl`, `tests/test_red_team_and_eval.py` |
| **M8: Tradeoffs & Interactive Demo** | Latency vs Recall Pareto characterization; FastAPI interactive tutor with video player & memory inspector | ✅ Complete | `benchmark/characterize_performance.py`, `demo/app.py`, `demo/helpers.py` |

---

## Public Corpus Manifest & Provenance

The system relies on an authoritative, bounded public instructional corpus selected from Harvard University's CS50x OpenCourseWare:
- **Manifest Location:** `data/source_manifest.json` and `data/source_manifest.yaml`
- **Selected Corpus Subset:**
  - **CS50x 2024 Edition:** Weeks 0 through 5 (Scratch, C, Arrays, Algorithms, Memory, Data Structures).
  - **CS50x 2023 Edition:** Weeks 0 and 1 (Scratch, C) retained for cross-edition versioning, supersession, and deprecation evaluation.
- **Attribution & Licensing:** CS50's Introduction to Computer Science, David J. Malan, Harvard University. Licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0).

---

## Quickstart & Installation

```bash
# Clone and enter the repository
cd grounded-multimodal-ai-tutor-dat

# Install Python dependencies
pip install -r requirements.txt

# Ensure system dependencies are installed:
# - ffmpeg + ffprobe
# - tesseract-ocr
```

---

## Unified Command-Line Interface (`main.py`)

All system capabilities are exposed via the unified CLI in `main.py`:

### 1. Ingestion & Versioning
```bash
# Ingest lecture video with automatic manifest metadata resolution
python main.py ingest --video path/to/lecture00.mp4 --asset-id cs50-2024-lec00-video

# Ingest with explicit flags
python main.py ingest \
  --video path/to/lecture03.mp4 \
  --source-id cs50-lec03 \
  --title "Lecture 3: Algorithms" \
  --course-edition 2024

# Deprecate a superseded course edition (M6 invalidation)
python main.py deprecate --course-edition 2023
```

### 2. Citation Resolution
```bash
# Resolve chunk metadata, timestamps, and media jump URLs
python main.py resolve-citation --chunk-id c_audio_1234abcd
```

### 3. Grounded Tutor Querying
```bash
# Basic query with hybrid retrieval
python main.py query "How does binary search work in C?"

# Query with cross-encoder reranking and visual evidence requirement
python main.py query "Explain the memory layout diagram" --rerank --require-visual

# Query with pedagogical adaptation for a specific learner
python main.py query "Explain pointers" --learner-id student_101
```

### 4. Learner Memory Management
```bash
# List all active memories, mastery states, and pedagogical context
python main.py memory list --learner-id student_101

# Add a learner struggle, preference, or goal
python main.py memory add \
  --learner-id student_101 \
  --topic "pointers" \
  --content "Confused about pointer dereferencing with * vs &" \
  --type struggle \
  --confidence 0.95

# Correct an existing memory item
python main.py memory correct \
  --memory-id <MEMORY_ID> \
  --new-content "Understands & is address-of, still practicing *" \
  --reason "Learner clarified progress"

# Soft-delete a memory item
python main.py memory delete --learner-id student_101 --memory-id <MEMORY_ID>

# GDPR purge of all data for a learner
python main.py memory purge --learner-id student_101
```

### 5. Evaluation & Characterization
```bash
# Run the 60-case benchmark evaluation
python main.py eval --benchmark-file benchmark/cases_60.jsonl

# Run latency & recall characterization (profiling TTFT, p50, p95)
python main.py characterize --cases benchmark/cases_60.jsonl
```

---

## Interactive Web Demo (M8)

The M8 Interactive Demo provides a browser-based UI with synchronized video playback, slide viewers, citation jump links, and a real-time Learner Memory Inspector.

### Launching the Demo
```bash
python3 -m uvicorn demo.app:app --host 0.0.0.0 --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

### Key Capabilities
- **Synchronized Evidence Player:** Citations include direct jump links to lecture video timestamps (`?t=XXs`) and slide images.
- **Live Memory Inspector:** Add, correct, delete, and purge learner memories with real-time pedagogical prompt previews.
- **Security & Containment:** Hardened against directory traversal, XSS (safe DOM construction), and unintended mutation of production databases (`data/corpus.db`, `data/learner_memory.db`).

---

## Testing & Verification

The test suite runs offline with zero external API dependencies and zero mutation of tracked production databases.

```bash
# Run the full automated test suite (295 tests)
pytest -v

# Run demo-specific smoke and security hardening tests
pytest tests/test_demo_smoke.py -v

# Run 60-case red-team and robustness benchmark
pytest tests/test_red_team_and_eval.py -v

# Run live multimodal VQA verification (requires active API key)
GEMINI_API_KEY=... python3 -m pytest tests/test_vqa.py -k "test_visual_question_sends_actual_image_payload" -v
```
