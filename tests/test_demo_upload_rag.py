"""Offline unit and integration tests for demo video upload, ingestion, and RAG inspector.

Verifies:
1. DemoCorpusStore schema initialization and integrity check.
2. Transcript parsers (VTT, SRT, TXT) and filename sanitization.
3. Path validation and video serve security.
4. End-to-end offline ingestion pipeline (ffmpeg-generated synthetic video + VTT).
5. Offline BM25 retrieval over demo corpus.
6. FastAPI endpoints (/api/upload, /api/uploads, /api/demo/query, /media/video).
7. Strict zero mutation of production databases (data/corpus.db and data/learner_memory.db).
"""

import hashlib
import io
import os
import shutil
import subprocess
import pytest
from fastapi.testclient import TestClient

from ingestion.versioning import SourceVersion
from demo.upload_ingest import (
    DemoCorpusStore,
    DemoRetriever,
    sanitize_filename,
    parse_vtt,
    parse_srt,
    parse_txt_transcript,
    parse_transcript_file,
    ingest_uploaded_video,
)
from demo.helpers import (
    validate_video_serve_path,
    run_demo_corpus_query,
)
from demo.app import app

CORPUS_DB_BASELINE_SHA = "8d6c45da998ed15d5498b333215cb8996973f2b74100dc7055bffbc970b3440f"
MEMORY_DB_BASELINE_SHA = "163c579862b2707d0fa4c9f8b07a64b5f2e2fb643e755bafbc558152a1d513d9"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture
def synthetic_video(tmp_path):
    """Generate a minimal valid 1-second MP4 test file using ffmpeg."""
    out_path = tmp_path / "test_synth.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
        "-shortest", "-c:v", "libx264", "-c:a", "aac",
        str(out_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        pytest.skip("ffmpeg not available or failed to create synthetic video")
    return str(out_path)


def test_demo_corpus_store_schema_and_integrity(tmp_path):
    """Verify DemoCorpusStore initializes schema and passes integrity check."""
    db_file = str(tmp_path / "demo_test.db")
    store = DemoCorpusStore(db_path=db_file)
    assert store.integrity_check() == "ok"
    assert store.list_sources() == []
    assert store.active_chunks() == []

    # Insert a dummy source via SourceVersion
    version = SourceVersion(
        source_id="test_src_1",
        content_hash="abc12345",
        course_edition="2024",
        title="Test Source",
    )
    store.upsert_source(version)
    sources = store.list_sources()
    assert len(sources) == 1
    assert sources[0]["source_id"] == "test_src_1"
    assert sources[0]["title"] == "Test Source"

    # Test clear_all
    store.clear_all()
    assert store.list_sources() == []
    assert store.active_chunks() == []


def test_sanitize_filename():
    """Verify filename sanitization produces a clean, safe stem."""
    assert sanitize_filename("../../etc/passwd.mp4") == "passwd"
    assert sanitize_filename("lecture 01: intro & pointers!.mp4") == "lecture_01_intro_pointers"
    assert sanitize_filename("") == "upload"
    assert sanitize_filename("   ") == "upload"


def test_transcript_parsers(tmp_path):
    """Verify VTT, SRT, and TXT parsing with timestamp conversions."""
    # 1. VTT
    vtt_content = """WEBVTT

00:00:01.000 --> 00:00:04.500
Hello world, welcome to computer science.

00:00:05.000 --> 00:00:08.200
Today we discuss pointers and memory addresses.
"""
    vtt_file = tmp_path / "sample.vtt"
    vtt_file.write_text(vtt_content, encoding="utf-8")
    vtt_segs = parse_vtt(str(vtt_file))
    assert len(vtt_segs) == 2
    assert vtt_segs[0].start_sec == 1.0
    assert vtt_segs[0].end_sec == 4.5
    assert "Hello world" in vtt_segs[0].text
    assert vtt_segs[1].start_sec == 5.0
    assert "pointers" in vtt_segs[1].text

    # 2. SRT
    srt_content = """1
00:00:02,000 --> 00:00:06,000
Binary search requires sorted arrays.

2
00:00:07,500 --> 00:00:10,000
Its complexity is O(log n).
"""
    srt_file = tmp_path / "sample.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    srt_segs = parse_srt(str(srt_file))
    assert len(srt_segs) == 2
    assert srt_segs[0].start_sec == 2.0
    assert srt_segs[0].end_sec == 6.0
    assert "Binary search" in srt_segs[0].text
    assert srt_segs[1].start_sec == 7.5

    # 3. TXT
    txt_content = "Line one topic\nLine two topic\nLine three topic\n"
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text(txt_content, encoding="utf-8")
    txt_segs = parse_txt_transcript(str(txt_file))
    assert len(txt_segs) == 3
    assert txt_segs[0].start_sec == 0.0
    assert txt_segs[1].start_sec == 10.0

    # 4. Auto detector
    vtt_parsed, vtt_fmt = parse_transcript_file(str(vtt_file))
    assert len(vtt_parsed) == 2
    assert vtt_fmt == "vtt"
    srt_parsed, srt_fmt = parse_transcript_file(str(srt_file))
    assert len(srt_parsed) == 2
    assert srt_fmt == "srt"
    txt_parsed, txt_fmt = parse_transcript_file(str(txt_file))
    assert len(txt_parsed) == 3
    assert txt_fmt == "txt"


def test_validate_video_serve_path(tmp_path):
    """Verify video serve path validation and security containment."""
    allowed_root = tmp_path / "uploads"
    allowed_root.mkdir()
    valid_vid = allowed_root / "demo.mp4"
    valid_vid.write_bytes(b"dummy video content")

    # Valid file inside root
    res = validate_video_serve_path(str(valid_vid), uploads_dir=str(allowed_root))
    assert res["valid"] is True
    assert res["exists"] is True

    # Invalid extension
    bad_ext = allowed_root / "exploit.py"
    bad_ext.write_text("print(1)")
    res = validate_video_serve_path(str(bad_ext), uploads_dir=str(allowed_root))
    assert res["valid"] is False

    # Path traversal outside root
    escape_vid = tmp_path / "escaped.mp4"
    escape_vid.write_bytes(b"dummy")
    res = validate_video_serve_path(str(escape_vid), uploads_dir=str(allowed_root))
    assert res["valid"] is False

    # Nonexistent file (path syntax & containment valid, but file missing)
    res = validate_video_serve_path(str(allowed_root / "nonexistent.mp4"), uploads_dir=str(allowed_root))
    assert res["valid"] is True
    assert res["exists"] is False


def test_ingest_uploaded_video_pipeline(synthetic_video, tmp_path):
    """Verify full ingestion of uploaded video with VTT transcript."""
    demo_db = str(tmp_path / "demo.db")
    uploads_dir = str(tmp_path / "uploads")

    vtt_content = """WEBVTT

00:00:00.100 --> 00:00:00.900
Introduction to algorithm analysis and asymptotic notation.
"""
    vtt_path = str(tmp_path / "test.vtt")
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)

    report = ingest_uploaded_video(
        video_path=synthetic_video,
        transcript_path=vtt_path,
        title="Algorithms 101",
        demo_corpus_db=demo_db,
        uploads_dir=uploads_dir,
    )

    assert report["status"] == "ok"
    assert report["title"] == "Algorithms 101"
    assert report["audio_chunks"] >= 1
    assert report["total_chunks"] >= 1
    assert report["demo_corpus_db"] == demo_db

    # Inspect store
    store = DemoCorpusStore(db_path=demo_db)
    sources = store.list_sources()
    assert len(sources) == 1
    assert sources[0]["title"] == "Algorithms 101"
    assert sources[0]["chunk_count"] == report["total_chunks"]

    # Verify active chunks
    chunks = store.active_chunks(source_id=report["source_id"])
    assert len(chunks) == report["total_chunks"]
    audio_chunks = [c for c in chunks if c.get("modality") == "audio"]
    assert len(audio_chunks) >= 1
    assert "asymptotic" in audio_chunks[0]["text"]


def test_demo_retriever_query(synthetic_video, tmp_path):
    """Verify DemoRetriever retrieves matched chunks by BM25 scoring."""
    demo_db = str(tmp_path / "demo.db")
    uploads_dir = str(tmp_path / "uploads")

    vtt_content = """WEBVTT

00:00:00.100 --> 00:00:00.500
Bubble sort has quadratic complexity.

00:00:00.500 --> 00:00:00.900
Merge sort operates in divide and conquer.
"""
    vtt_path = str(tmp_path / "test.vtt")
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)

    ingest_uploaded_video(
        video_path=synthetic_video,
        transcript_path=vtt_path,
        title="Sorting Algorithms",
        demo_corpus_db=demo_db,
        uploads_dir=uploads_dir,
    )

    retriever = DemoRetriever(demo_corpus_db=demo_db)
    results = retriever.retrieve("quadratic complexity", top_k=5)
    assert len(results) >= 1
    top_node = results[0]
    assert "quadratic" in top_node.text
    assert top_node.score > 0

    # Also test run_demo_corpus_query helper
    q_res = run_demo_corpus_query("divide and conquer", demo_corpus_db=demo_db, top_k=3)
    assert q_res["total_retrieved"] >= 1
    assert "Merge sort" in q_res["results"][0]["text"]
    assert q_res["results"][0]["rank"] == 1


def test_fastapi_upload_and_rag_endpoints(synthetic_video, tmp_path, monkeypatch):
    """Verify FastAPI integration for upload, list, query, and video serve."""
    demo_db = str(tmp_path / "api_demo.db")
    uploads_dir = str(tmp_path / "api_uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    # Patch paths across demo modules
    monkeypatch.setattr("demo.app.DEMO_CORPUS_DB", demo_db)
    monkeypatch.setattr("demo.app.DEMO_UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr("demo.helpers.DEMO_CORPUS_DB", demo_db)
    monkeypatch.setattr("demo.helpers.DEMO_UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr("demo.upload_ingest.DEMO_CORPUS_DB", demo_db)
    monkeypatch.setattr("demo.upload_ingest.DEMO_UPLOADS_DIR", uploads_dir)

    client = TestClient(app)

    # 1. Initial list should be empty
    res = client.get("/api/uploads")
    assert res.status_code == 200
    assert res.json()["count"] == 0

    # 2. Upload video with transcript
    with open(synthetic_video, "rb") as vf:
        v_bytes = vf.read()
    vtt_bytes = b"WEBVTT\n\n00:00:00.100 --> 00:00:00.900\nFastAPI integration test transcript.\n"

    res = client.post(
        "/api/upload",
        files={
            "video": ("lecture.mp4", io.BytesIO(v_bytes), "video/mp4"),
            "transcript": ("sub.vtt", io.BytesIO(vtt_bytes), "text/vtt"),
        },
        data={"title": "Test Lecture API"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "ok"
    assert data["title"] == "Test Lecture API"
    assert data["total_chunks"] >= 1
    video_path = data["video_path"]

    # 3. List should now have 1 source
    res = client.get("/api/uploads")
    assert res.status_code == 200
    assert res.json()["count"] == 1

    # 4. RAG inspection query
    res = client.post("/api/demo/query", json={"query": "FastAPI integration", "top_k": 3})
    assert res.status_code == 200
    q_data = res.json()
    assert q_data["total_retrieved"] >= 1
    assert "FastAPI" in q_data["results"][0]["text"]

    # 5. Media video serve endpoint
    res = client.get(f"/media/video?path={video_path}")
    assert res.status_code in (200, 206)
    assert "video/mp4" in res.headers.get("content-type", "")

    # 6. Reject invalid video path
    res = client.get("/media/video?path=config.py")
    assert res.status_code == 400

    # 7. Clear uploads
    res = client.delete("/api/uploads")
    assert res.status_code == 200
    assert res.json()["cleared"] is True

    # 8. List should be empty again
    res = client.get("/api/uploads")
    assert res.status_code == 200
    assert res.json()["count"] == 0


def test_production_db_hashes_unchanged():
    """Verify that tests never modified the production tracked databases."""
    assert os.path.exists("data/corpus.db")
    assert os.path.exists("data/learner_memory.db")
    assert _sha256("data/corpus.db") == CORPUS_DB_BASELINE_SHA
    assert _sha256("data/learner_memory.db") == MEMORY_DB_BASELINE_SHA
