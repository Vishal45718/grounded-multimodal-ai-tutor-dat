"""Demo-isolated upload validation and offline ingestion pipeline.

Provides:
1. Filename sanitization and upload validation.
2. Transcript parsing (VTT / SRT / plain TXT) → TranscriptSegment list.
3. Keyframe extraction from video via ffmpeg (graceful fallback when unavailable).
4. Offline ingestion into an isolated `data/demo_corpus.db` — NEVER touches
   `data/corpus.db` or `data/learner_memory.db`.
5. DemoCorpusStore: an isolated, path-validated wrapper around the SQLite
   schema that accepts an explicit db_path rather than reading CONFIG.
6. Retrieval helpers that build an in-memory BM25 index over the demo corpus
   so the existing TutorRetriever logic can be reused offline.

Design constraints:
- Zero API keys required (100% offline).
- cv2 / pytesseract are NOT available in this environment; OCR path silently
  skips OCR, sets text="" with status="success" so the visual chunk is still
  indexed by its timestamp and image path.
- faster_whisper is NOT available; local transcription falls back to a
  "no-transcript" notice and returns only visual keyframe chunks.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import CONFIG
from ingestion.chunker import EvidenceChunk, build_chunks, compute_chunk_id
from ingestion.transcriber import TranscriptSegment
from ingestion.versioning import SourceVersion, file_content_hash

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_UPLOADS_DIR = "data/demo_uploads"
DEMO_CORPUS_DB = "data/demo_corpus.db"
MAX_VIDEO_BYTES = 250 * 1024 * 1024  # 250 MB

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv"}
ALLOWED_TRANSCRIPT_EXTENSIONS = {".vtt", ".srt", ".txt"}
ALLOWED_SLIDES_EXTENSIONS = {".pdf"}
ALLOWED_MEDIA_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".pdf"}
ALLOWED_VIDEO_SERVE_EXTENSIONS = ALLOWED_MEDIA_EXTENSIONS

_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "schema.sql")

# ---------------------------------------------------------------------------
# Filename Sanitization
# ---------------------------------------------------------------------------

def sanitize_filename(raw_name: str) -> str:
    """Return a safe, lowercase filename stem stripped of special characters."""
    stem = Path(raw_name).stem
    safe = re.sub(r"[^\w\-]", "_", stem).lower().strip("_")
    safe = re.sub(r"_+", "_", safe)
    return safe[:64] or "upload"


def make_source_id(stem: str) -> str:
    return f"demo-{stem}"


# ---------------------------------------------------------------------------
# Isolated Demo Corpus Store
# ---------------------------------------------------------------------------

class DemoCorpusStore:
    """Thin SQLite wrapper that operates on an explicit db_path, completely
    independent of CONFIG.corpus_db_path.  Used exclusively by the demo
    upload pipeline so production databases are never touched.
    """

    def __init__(self, db_path: str = DEMO_CORPUS_DB) -> None:
        self.db_path = str(Path(db_path).resolve())
        self._ensure_schema()

    @contextmanager
    def _connect(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            # Apply column migrations defensively
            self._add_missing_columns(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_active_demo "
                "ON chunks(is_stale, source_id, content_hash)"
            )

    @staticmethod
    def _add_missing_columns(conn: sqlite3.Connection) -> None:
        def cols(table: str):
            return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

        source_missing = {
            "asset_id": "TEXT", "source_url": "TEXT", "original_asset_url": "TEXT",
            "license": "TEXT", "license_url": "TEXT", "attribution": "TEXT",
            "modification_notice": "TEXT",
        }
        chunk_missing = {
            "asset_id": "TEXT", "source_url": "TEXT", "original_asset_url": "TEXT",
            "edition_id": "TEXT", "status": "TEXT NOT NULL DEFAULT 'success'",
            "error_message": "TEXT", "page_number": "INTEGER", "extraction_method": "TEXT",
            "license": "TEXT", "license_url": "TEXT", "attribution": "TEXT",
            "modification_notice": "TEXT",
        }
        sc = cols("sources")
        for name, defn in source_missing.items():
            if name not in sc:
                conn.execute(f"ALTER TABLE sources ADD COLUMN {name} {defn}")
        cc = cols("chunks")
        for name, defn in chunk_missing.items():
            if name not in cc:
                try:
                    conn.execute(f"ALTER TABLE chunks ADD COLUMN {name} {defn}")
                except Exception:
                    pass

    def upsert_source(self, version: SourceVersion) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sources (
                    source_id, content_hash, course_edition, title,
                    ingested_at, is_deprecated, asset_id, source_url
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    title = excluded.title,
                    ingested_at = excluded.ingested_at,
                    is_deprecated = 0
                """,
                (
                    version.source_id, version.content_hash,
                    version.course_edition, version.title,
                    version.ingested_at,
                    version.asset_id, version.source_url,
                ),
            )
            # Stale old version chunks, activate new ones
            conn.execute(
                "UPDATE chunks SET is_stale = 1 "
                "WHERE source_id = ? AND content_hash != ?",
                (version.source_id, version.content_hash),
            )

    def insert_chunks(self, chunks: List[EvidenceChunk]) -> None:
        if not chunks:
            return
        values = [
            (
                c.chunk_id, c.source_id, c.content_hash, c.modality,
                c.start_sec, c.end_sec, c.text, c.image_path, 0,
                getattr(c, "asset_id", None), getattr(c, "source_url", None),
                None, getattr(c, "edition_id", None),
                getattr(c, "status", "success"), getattr(c, "error_message", None),
                getattr(c, "page_number", None), None,
                None, None, None, None,
            )
            for c in chunks
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO chunks (
                    chunk_id, source_id, content_hash, modality,
                    start_sec, end_sec, text, image_path, is_stale,
                    asset_id, source_url, original_asset_url, edition_id,
                    status, error_message, page_number, extraction_method,
                    license, license_url, attribution, modification_notice
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO NOTHING
                """,
                values,
            )
            # Activate newly inserted chunks
            if chunks:
                conn.execute(
                    "UPDATE chunks SET is_stale = 0 "
                    "WHERE source_id = ? AND content_hash = ?",
                    (chunks[0].source_id, chunks[0].content_hash),
                )

    def active_chunks(
        self, source_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT c.*, COALESCE(c.edition_id, s.course_edition) AS course_edition
            FROM chunks AS c
            JOIN sources AS s
              ON s.source_id = c.source_id AND s.content_hash = c.content_hash
            WHERE c.is_stale = 0 AND s.is_deprecated = 0
        """
        params: tuple = ()
        if source_id:
            query += " AND c.source_id = ?"
            params = (source_id,)
        query += " ORDER BY c.source_id, c.start_sec, c.chunk_id"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def list_sources(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.source_id, s.title, s.ingested_at,
                       COUNT(c.chunk_id) AS chunk_count,
                       SUM(CASE WHEN c.modality='audio' THEN 1 ELSE 0 END) AS audio_chunks,
                       SUM(CASE WHEN c.modality='visual' THEN 1 ELSE 0 END) AS visual_chunks
                FROM sources s
                LEFT JOIN chunks c ON c.source_id = s.source_id
                  AND c.content_hash = s.content_hash AND c.is_stale = 0
                WHERE s.is_deprecated = 0
                GROUP BY s.source_id
                ORDER BY s.ingested_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM sources")

    def integrity_check(self) -> str:
        with self._connect() as conn:
            return conn.execute("PRAGMA integrity_check").fetchone()[0]


# ---------------------------------------------------------------------------
# Transcript Parsing (VTT / SRT / TXT)
# ---------------------------------------------------------------------------

def _time_to_sec(t: str) -> float:
    t = t.strip().replace(",", ".")
    parts = t.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600 + float(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return float(m) * 60 + float(s)
    return float(parts[-1])


def parse_vtt(path: str) -> List[TranscriptSegment]:
    segments: List[TranscriptSegment] = []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Strip WEBVTT header and NOTE blocks
    content = re.sub(r"WEBVTT[^\n]*\n", "", content)
    content = re.sub(r"NOTE[^\n]*\n", "", content)
    blocks = re.split(r"\n{2,}", content.strip())
    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if " --> " in line:
                try:
                    start_str, end_str = line.split(" --> ")
                    start_sec = _time_to_sec(start_str.split()[0])
                    end_sec = _time_to_sec(end_str.split()[0])
                    text = " ".join(lines[i + 1:]).strip()
                    if text:
                        segments.append(TranscriptSegment(start_sec, end_sec, text))
                except (ValueError, IndexError):
                    pass
                break
    return segments


def parse_srt(path: str) -> List[TranscriptSegment]:
    segments: List[TranscriptSegment] = []
    with open(path, "r", encoding="utf-8") as f:
        blocks = f.read().strip().split("\n\n")
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if " --> " in line:
                try:
                    start_str, end_str = line.split(" --> ")
                    start_sec = _time_to_sec(start_str)
                    end_sec = _time_to_sec(end_str)
                    text = " ".join(lines[i + 1:]).strip()
                    if text:
                        segments.append(TranscriptSegment(start_sec, end_sec, text))
                except (ValueError, IndexError):
                    pass
                break
    return segments


def parse_txt_transcript(path: str) -> List[TranscriptSegment]:
    """Plain .txt: each non-empty line becomes a 10-second segment."""
    segments: List[TranscriptSegment] = []
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    for i, line in enumerate(lines):
        start = i * 10.0
        segments.append(TranscriptSegment(start, start + 10.0, line))
    return segments


def parse_transcript_file(path: str) -> Tuple[List[TranscriptSegment], str]:
    """Route to the right parser by extension. Returns (segments, format_name)."""
    ext = Path(path).suffix.lower()
    if ext == ".vtt":
        return parse_vtt(path), "vtt"
    elif ext == ".srt":
        return parse_srt(path), "srt"
    elif ext == ".txt":
        return parse_txt_transcript(path), "txt"
    else:
        raise ValueError(f"Unsupported transcript extension: {ext}")


# ---------------------------------------------------------------------------
# Keyframe Extraction (ffmpeg only, no cv2)
# ---------------------------------------------------------------------------

def extract_keyframes_demo(
    video_path: str,
    out_dir: str,
    interval_sec: float = 8.0,
    max_frames: int = 50,
) -> List[Tuple[float, str]]:
    """Extract up to max_frames keyframes at fixed intervals.

    Returns list of (timestamp_sec, image_path) tuples.
    Falls back gracefully when ffmpeg is unavailable or errors.
    """
    os.makedirs(out_dir, exist_ok=True)
    frames: List[Tuple[float, str]] = []

    try:
        # Probe duration
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        duration = float(result.stdout.strip())
    except Exception:
        return frames

    actual_interval = max(interval_sec, duration / max(1, max_frames))
    pattern = os.path.join(out_dir, "frame_%05d.jpg")

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_path,
                "-vf", f"fps=1/{actual_interval:.1f}",
                "-vframes", str(max_frames),
                pattern,
            ],
            check=True, capture_output=True, timeout=120,
        )
    except Exception:
        return frames

    files = sorted(f for f in os.listdir(out_dir) if f.startswith("frame_") and f.endswith(".jpg"))
    for i, fn in enumerate(files):
        ts = i * actual_interval
        if ts <= duration:
            frames.append((ts, os.path.join(out_dir, fn)))

    return frames


# ---------------------------------------------------------------------------
# Validate Upload Path
# ---------------------------------------------------------------------------

def validate_upload_video_path(path: str) -> None:
    """Raise ValueError if path is not safely inside DEMO_UPLOADS_DIR."""
    root = Path(os.getcwd()) / DEMO_UPLOADS_DIR
    target = Path(path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        raise ValueError(
            f"Video path '{path}' escapes the authorized demo uploads directory."
        )
    if target.suffix.lower() not in ALLOWED_VIDEO_SERVE_EXTENSIONS:
        raise ValueError(
            f"Extension '{target.suffix}' is not allowed. "
            f"Use {sorted(ALLOWED_VIDEO_SERVE_EXTENSIONS)}."
        )


def call_ocr_vlm(
    image_path: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 60.0,
) -> str:
    """Call an OpenAI-compatible OCR VLM (e.g. PaddlePaddle/PaddleOCR-VL-1.6) to extract text from a slide or frame."""
    resolved_api_key = api_key or getattr(CONFIG, "ocr_api_key", "")
    resolved_base_url = (base_url or getattr(CONFIG, "ocr_base_url", "")).rstrip("/")
    resolved_model = model or getattr(CONFIG, "ocr_model", "PaddlePaddle/PaddleOCR-VL-1.6")

    if not resolved_api_key or not resolved_base_url:
        return ""

    if not os.path.exists(image_path):
        return ""

    try:
        with open(image_path, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")

        prompt = "Transcribe all text, code snippets, titles, headings, and formulas visible in this slide or video frame accurately and verbatim. Return only the extracted text."
        payload = {
            "model": resolved_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"},
                        },
                    ],
                }
            ],
            "temperature": 0.0,
        }
        headers = {
            "Authorization": f"Bearer {resolved_api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{resolved_base_url}/chat/completions"

        try:
            import httpx
            with httpx.Client(timeout=timeout) as client:
                res = client.post(endpoint, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
        except ImportError:
            import json
            import urllib.request
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Audio Decoding & Whisper Transcription (PyAV metadata_errors Bypass)
# ---------------------------------------------------------------------------

def decode_audio_ffmpeg_pcm(media_path: str) -> Optional[Any]:
    """Decode video or audio file to 16 kHz mono float32 PCM using ffmpeg.

    Bypasses PyAV container metadata_errors bug in faster-whisper.
    Returns a 1D float32 NumPy array, or None if ffmpeg fails or is unavailable.
    """
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-i",
        str(media_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "f32le",
        "pipe:1",
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        import numpy as np
        if proc.stdout:
            return np.frombuffer(proc.stdout, dtype=np.float32)
        return None
    except Exception:
        return None


def transcribe_video_whisper(
    media_path: str,
    model_size: Optional[str] = None,
) -> List[TranscriptSegment]:
    """Transcribe video or audio using faster-whisper on CPU.

    Bypasses PyAV metadata_errors incompatibility by decoding to 16 kHz mono
    float32 PCM via ffmpeg before calling model.transcribe(audio_np, vad_filter=True).
    Falls back to file path if ffmpeg decoding fails or is unavailable.
    """
    from faster_whisper import WhisperModel

    model_name = (
        model_size
        or os.environ.get("WHISPER_MODEL_SIZE")
        or os.environ.get("WHISPER_MODEL")
        or getattr(CONFIG, "whisper_model_size", "tiny")
    )
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
    except Exception:
        fallback = "base" if model_name != "base" else "tiny"
        model = WhisperModel(fallback, device="cpu", compute_type="int8")

    pcm_data = decode_audio_ffmpeg_pcm(media_path)
    audio_input = pcm_data if (pcm_data is not None and len(pcm_data) > 0) else media_path

    segments, _info = model.transcribe(audio_input, vad_filter=True)
    return [
        TranscriptSegment(
            start_sec=float(seg.start),
            end_sec=float(seg.end),
            text=seg.text.strip(),
        )
        for seg in segments
    ]


# ---------------------------------------------------------------------------
# Core Ingestion Pipeline
# ---------------------------------------------------------------------------

def ingest_uploaded_video(
    video_path: str,
    title: str,
    transcript_path: Optional[str] = None,
    slides_pdf_path: Optional[str] = None,
    uploads_dir: str = DEMO_UPLOADS_DIR,
    demo_corpus_db: str = DEMO_CORPUS_DB,
) -> Dict[str, Any]:
    """
    Offline ingestion pipeline for a single uploaded video.

    Returns an ingestion report dict:
        source_id, title, audio_chunks, visual_chunks,
        keyframes_extracted, warnings, video_url, capabilities
    """
    warnings: List[str] = []
    capabilities: Dict[str, bool] = {
        "ffmpeg": False,
        "ffprobe": False,
        "pytesseract": False,
        "faster_whisper": False,
        "pymupdf": False,
    }

    # --- Probe available tools ---
    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run([tool, "-version"], capture_output=True, timeout=5)
            capabilities[tool] = True
        except Exception:
            pass

    try:
        import pymupdf  # noqa: F401
        capabilities["pymupdf"] = True
    except ImportError:
        try:
            import fitz  # noqa: F401
            capabilities["pymupdf"] = True
        except ImportError:
            pass

    try:
        import faster_whisper  # noqa: F401
        capabilities["faster_whisper"] = True
    except ImportError:
        pass

    try:
        import pytesseract  # noqa: F401
        capabilities["pytesseract"] = True
    except ImportError:
        pass

    # --- Compute content hash ---
    content_hash = file_content_hash(video_path)
    stem = sanitize_filename(Path(video_path).name)
    source_id = make_source_id(stem)

    # --- Upload directory for this video version ---
    source_upload_dir = os.path.join(uploads_dir, f"{stem}_{content_hash[:8]}")
    frames_dir = os.path.join(source_upload_dir, "keyframes")
    os.makedirs(frames_dir, exist_ok=True)

    # --- Transcript parsing ---
    transcript_segments: List[TranscriptSegment] = []
    transcript_format = None

    if transcript_path:
        try:
            segs, fmt = parse_transcript_file(transcript_path)
            transcript_segments = segs
            transcript_format = fmt
        except Exception as e:
            warnings.append(f"Transcript parse failed ({e}). Skipping speech chunks.")
    elif capabilities["faster_whisper"]:
        try:
            transcript_segments = transcribe_video_whisper(video_path)
            transcript_format = "whisper"
        except Exception as e:
            warnings.append(
                f"Local Whisper transcription failed ({e}). "
                "Upload a .vtt/.srt/.txt for speech search."
            )
    else:
        warnings.append(
            "No transcript uploaded and faster_whisper is not available. "
            "Only visual keyframe chunks will be indexed. "
            "Upload a .vtt, .srt, or .txt file alongside the video for speech search."
        )

    # --- Keyframe extraction ---
    keyframe_pairs: List[Tuple[float, str]] = []
    if capabilities["ffmpeg"] and capabilities["ffprobe"]:
        try:
            keyframe_pairs = extract_keyframes_demo(video_path, frames_dir)
        except Exception as e:
            warnings.append(f"Keyframe extraction failed ({e}). No visual chunks.")
    else:
        warnings.append("ffmpeg not available — skipping keyframe extraction.")

    # --- PDF slides ---
    pdf_ocr_results: List[Any] = []
    if slides_pdf_path and capabilities["pymupdf"]:
        try:
            from ingestion.ocr import extract_pdf_slides
            pdf_ocr = extract_pdf_slides(slides_pdf_path, source_id, content_hash, base_dir=frames_dir)
            for item in pdf_ocr:
                if not getattr(item, "text", "") and getattr(CONFIG, "ocr_api_key", "") and getattr(CONFIG, "ocr_base_url", ""):
                    vlm_text = call_ocr_vlm(item.image_path)
                    if vlm_text:
                        item.text = vlm_text
                pdf_ocr_results.append(item)
        except Exception as e:
            warnings.append(f"PDF slide extraction failed ({e}).")

    # --- Build OcrResult-like objects from keyframe pairs ---
    from ingestion.ocr import OcrResult
    ocr_results: List[OcrResult] = []

    for ts, img_path in keyframe_pairs:
        text = ""
        if getattr(CONFIG, "ocr_api_key", "") and getattr(CONFIG, "ocr_base_url", ""):
            text = call_ocr_vlm(img_path)
        if not text and capabilities["pytesseract"]:
            try:
                import pytesseract
                from PIL import Image
                text = pytesseract.image_to_string(Image.open(img_path)).strip()
            except Exception:
                pass
        ocr_results.append(OcrResult(
            timestamp_sec=ts,
            image_path=img_path,
            text=text,
            status="success",
        ))

    ocr_results.extend(pdf_ocr_results)

    # --- Build EvidenceChunks ---
    chunks = build_chunks(
        source_id=source_id,
        content_hash=content_hash,
        transcript=transcript_segments,
        ocr_results=ocr_results,
    )

    audio_chunks = [c for c in chunks if c.modality == "audio"]
    visual_chunks = [c for c in chunks if c.modality == "visual"]

    # --- Persist to isolated demo corpus DB ---
    store = DemoCorpusStore(db_path=demo_corpus_db)
    source_version = SourceVersion(
        source_id=source_id,
        content_hash=content_hash,
        course_edition="demo",
        title=title,
    )
    store.upsert_source(source_version)
    store.insert_chunks(chunks)

    # --- Relative video URL for serving ---
    video_url = f"/media/video?path={video_path}"

    return {
        "status": "ok",
        "source_id": source_id,
        "title": title,
        "content_hash": content_hash,
        "audio_chunks": len(audio_chunks),
        "visual_chunks": len(visual_chunks),
        "total_chunks": len(chunks),
        "keyframes_extracted": len(keyframe_pairs),
        "transcript_format": transcript_format,
        "video_path": video_path,
        "video_url": video_url,
        "demo_corpus_db": demo_corpus_db,
        "warnings": warnings,
        "capabilities": capabilities,
    }


def ingest_uploaded_pdf(
    pdf_path: str,
    title: Optional[str] = None,
    uploads_dir: str = DEMO_UPLOADS_DIR,
    demo_corpus_db: str = DEMO_CORPUS_DB,
) -> Dict[str, Any]:
    """Ingest a standalone uploaded PDF presentation or document into the demo corpus.

    Renders each PDF page into a JPEG under data/demo_uploads/<stem>_<hash>/pages/
    Extracts text per page (using PaddleOCR-VL-1.6 if configured, else PyMuPDF page text),
    and creates visual chunks with page_number and image_path.
    """
    warnings: List[str] = []
    capabilities: Dict[str, bool] = {
        "pymupdf": False,
        "ocr_vlm": bool(getattr(CONFIG, "ocr_api_key", "") and getattr(CONFIG, "ocr_base_url", "")),
        "pytesseract": False,
    }

    try:
        import pymupdf as fitz  # noqa: F401
        capabilities["pymupdf"] = True
    except ImportError:
        try:
            import fitz  # noqa: F401
            capabilities["pymupdf"] = True
        except ImportError:
            pass

    try:
        import pytesseract  # noqa: F401
        capabilities["pytesseract"] = True
    except ImportError:
        pass

    if not capabilities["pymupdf"]:
        raise RuntimeError("PyMuPDF / fitz is required for PDF ingestion but is not installed.")

    content_hash = file_content_hash(pdf_path)
    raw_name = Path(pdf_path).name
    stem = sanitize_filename(raw_name)
    source_id = make_source_id(stem)
    resolved_title = title.strip() if (title and title.strip()) else Path(pdf_path).stem

    # Isolated upload dir for rendered pages
    source_upload_dir = os.path.join(uploads_dir, f"{stem}_{content_hash[:8]}")
    pages_dir = os.path.join(source_upload_dir, "pages")
    os.makedirs(pages_dir, exist_ok=True)

    chunks: List[EvidenceChunk] = []
    import fitz
    doc = fitz.open(pdf_path)
    try:
        for idx, page in enumerate(doc):
            page_num = idx + 1
            image_name = f"slide_{page_num:05d}.jpg"
            image_path = os.path.join(pages_dir, image_name)

            # Render page to JPEG
            try:
                pix = page.get_pixmap(alpha=False)
                pix.save(image_path)
            except Exception as e:
                warnings.append(f"Failed to render slide page {page_num}: {e}")
                continue

            # Extract text
            page_text = ""
            if capabilities["ocr_vlm"]:
                vlm_text = call_ocr_vlm(image_path)
                if vlm_text:
                    page_text = vlm_text

            if not page_text:
                raw_text = page.get_text()
                page_text = raw_text.strip() if raw_text else ""

            if not page_text and capabilities["pytesseract"]:
                try:
                    from PIL import Image
                    page_text = pytesseract.image_to_string(Image.open(image_path)).strip()
                except Exception:
                    pass

            chunk_id = f"{source_id}_p{page_num:03d}"
            chunks.append(
                EvidenceChunk(
                    chunk_id=chunk_id,
                    source_id=source_id,
                    content_hash=content_hash,
                    modality="visual",
                    text=page_text or f"Slide Page {page_num}",
                    start_sec=None,
                    end_sec=None,
                    image_path=image_path,
                    asset_id=f"{source_id}_slide_{page_num:05d}",
                    page_number=page_num,
                )
            )
    finally:
        doc.close()

    # Persist to demo corpus DB
    store = DemoCorpusStore(db_path=demo_corpus_db)
    source_version = SourceVersion(
        source_id=source_id,
        content_hash=content_hash,
        course_edition="demo",
        title=resolved_title,
    )
    store.upsert_source(source_version)
    store.insert_chunks(chunks)

    pdf_url = f"/media/video?path={pdf_path}"

    return {
        "status": "ok",
        "source_id": source_id,
        "title": resolved_title,
        "content_hash": content_hash,
        "audio_chunks": 0,
        "visual_chunks": len(chunks),
        "total_chunks": len(chunks),
        "pdf_path": pdf_path,
        "video_path": pdf_path,
        "video_url": pdf_url,
        "pdf_url": pdf_url,
        "pages_rendered": len(chunks),
        "demo_corpus_db": demo_corpus_db,
        "warnings": warnings,
        "capabilities": capabilities,
    }


# ---------------------------------------------------------------------------
# Offline In-Memory Retriever backed by DemoCorpusStore
# ---------------------------------------------------------------------------

class DemoRetriever:
    """BM25-based retriever over an isolated demo corpus database.

    Wraps the existing PurePythonBM25 from retrieval/retriever.py without
    modifying that module. The TutorRetriever from retrieval/ reads from
    CONFIG.corpus_db_path; this class operates on a separate demo_corpus_db.
    """

    def __init__(
        self,
        demo_corpus_db: str = DEMO_CORPUS_DB,
        source_id: Optional[str] = None,
    ) -> None:
        from retrieval.retriever import FallbackNode, PurePythonBM25

        self.demo_corpus_db = demo_corpus_db
        self.source_id = source_id

        store = DemoCorpusStore(db_path=demo_corpus_db)
        rows = store.active_chunks(source_id=source_id)

        self._nodes = [
            FallbackNode(
                text=r["text"] or "",
                metadata={
                    "chunk_id": r["chunk_id"],
                    "source_id": r["source_id"],
                    "modality": r["modality"],
                    "start_sec": r["start_sec"],
                    "end_sec": r["end_sec"],
                    "image_path": r["image_path"],
                    "source_url": r.get("source_url"),
                    "page_number": r.get("page_number"),
                    "edition_id": r.get("edition_id", "demo"),
                    "content_hash": r["content_hash"],
                    "is_stale": r.get("is_stale", 0),
                },
            )
            for r in rows
        ]
        self._bm25 = PurePythonBM25(self._nodes) if self._nodes else None

    def retrieve(
        self, query: str, fusion: bool = False, top_k: int = 5
    ) -> List[Any]:
        if not self._bm25 or not self._nodes:
            return []
        # PurePythonBM25 uses .score() — returns List[(float, FallbackNode)]
        scored = self._bm25.score(query)[:top_k]
        nodes = [node for _, node in scored]
        # Attach scores so callers can inspect retrieval quality
        for (sc, node), node_out in zip(scored, nodes):
            node_out.score = sc
        return nodes

    def chunk_count(self) -> int:
        return len(self._nodes)
