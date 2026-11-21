"""Offline unit and integration tests for demo video/PDF upload, ingestion, RAG inspector,
and OpenAI-compatible live mentor model stack adapters (Gemma4-12B, GLM-4.6V-Flash, PaddleOCR-VL-1.6).

Verifies:
1. DemoCorpusStore schema initialization and integrity check.
2. Transcript parsers (VTT, SRT, TXT) and filename sanitization.
3. Path validation and video/pdf media serve security.
4. End-to-end video ingestion pipeline with synthetic video + transcript.
5. Standalone PDF upload ingestion and slide rendering.
6. Either/or upload validation in FastAPI (video OR pdf, rejecting empty requests).
7. OpenAI-compatible text LLM adapter (Gemma4-12B FP8) with mocked completion.
8. OpenAI-compatible VLM adapter (GLM-4.6V-Flash) with image base64 delivery.
9. OpenAI-compatible OCR VLM (PaddleOCR-VL-1.6) text extraction.
10. Grounded Q&A over demo corpus returning live answer + citations.
11. Strict zero mutation of production databases (data/corpus.db and data/learner_memory.db).
"""

import hashlib
import io
import json
import os
import shutil
import subprocess
import pytest
from fastapi.testclient import TestClient

from config import CONFIG
from ingestion.versioning import SourceVersion
from generation.answer import OpenAICompatibleLLM, generate_grounded_answer
from generation.vqa import OpenAICompatibleVisionAdapter, VisualPayload
from demo.upload_ingest import (
    DemoCorpusStore,
    DemoRetriever,
    call_ocr_vlm,
    decode_audio_ffmpeg_pcm,
    ingest_uploaded_pdf,
    ingest_uploaded_video,
    parse_srt,
    parse_transcript_file,
    parse_txt_transcript,
    parse_vtt,
    sanitize_filename,
    transcribe_video_whisper,
)
from demo.helpers import (
    detect_backend_status,
    run_demo_corpus_query,
    validate_video_serve_path,
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


@pytest.fixture
def synthetic_pdf(tmp_path):
    """Generate a minimal 2-page PDF file for standalone slide upload tests."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    out_path = tmp_path / "test_slides.pdf"
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 50), "CS50 Lecture on Pointer Arithmetic")
    p2 = doc.new_page()
    p2.insert_text((50, 50), "Memory allocation with malloc and free")
    doc.save(str(out_path))
    doc.close()
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

    # Valid PDF file inside root
    valid_pdf = allowed_root / "slides.pdf"
    valid_pdf.write_bytes(b"dummy pdf content")
    res_pdf = validate_video_serve_path(str(valid_pdf), uploads_dir=str(allowed_root))
    assert res_pdf["valid"] is True
    assert res_pdf["exists"] is True

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

    # Nonexistent file
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


def test_ingest_standalone_pdf(synthetic_pdf, tmp_path):
    """Verify standalone PDF slides ingestion renders JPEG pages and stores visual chunks."""
    demo_db = str(tmp_path / "demo_pdf.db")
    uploads_dir = str(tmp_path / "uploads_pdf")

    report = ingest_uploaded_pdf(
        pdf_path=synthetic_pdf,
        title="Pointer Arithmetic Lecture",
        uploads_dir=uploads_dir,
        demo_corpus_db=demo_db,
    )

    assert report["status"] == "ok"
    assert report["title"] == "Pointer Arithmetic Lecture"
    assert report["audio_chunks"] == 0
    assert report["visual_chunks"] == 2
    assert report["total_chunks"] == 2

    # Check database persistence
    store = DemoCorpusStore(db_path=demo_db)
    sources = store.list_sources()
    assert len(sources) == 1
    assert sources[0]["visual_chunks"] == 2

    chunks = store.active_chunks(source_id=report["source_id"])
    assert len(chunks) == 2
    assert chunks[0]["page_number"] == 1
    assert chunks[1]["page_number"] == 2
    assert "Pointer" in chunks[0]["text"]
    assert "malloc" in chunks[1]["text"]
    # Check rendered image on disk
    assert os.path.exists(chunks[0]["image_path"])
    assert os.path.exists(chunks[1]["image_path"])


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
    assert "answer" in q_res
    assert "citations" in q_res


def test_openai_compatible_llm_adapter(monkeypatch):
    """Verify OpenAICompatibleLLM dispatches requests to OpenAI-compatible endpoint."""
    fake_called = False

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "According to the lecture [Evidence 1], pointers store memory addresses."
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json=None, headers=None):
            nonlocal fake_called
            fake_called = True
            assert "/chat/completions" in url
            assert json["model"] == "google/gemma-4-12b-it-fp8"
            assert "Authorization" in headers
            return FakeResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", FakeClient)

    llm = OpenAICompatibleLLM(
        base_url="http://fake-vllm:8000/v1",
        api_key="fake-test-key",
        model="google/gemma-4-12b-it-fp8",
    )

    resp = llm.complete("Explain pointer arithmetic in C.")
    assert fake_called is True
    assert "[Evidence 1]" in resp.text


def test_openai_compatible_error_surfacing(monkeypatch):
    """Verify OpenAICompatibleLLM and OpenAICompatibleVisionAdapter surface exact HTTP status and body."""
    import httpx

    class ErrorResponse:
        status_code = 404
        text = '{"error": "model not supported"}'

        def raise_for_status(self):
            request = httpx.Request("POST", "http://fake/chat/completions")
            response = httpx.Response(404, request=request, text=self.text)
            raise httpx.HTTPStatusError("Not Found", request=request, response=response)

    class FakeErrorClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, json=None, headers=None):
            return ErrorResponse()

    monkeypatch.setattr(httpx, "Client", FakeErrorClient)

    llm = OpenAICompatibleLLM(base_url="http://fake/v1", api_key="k", model="test-m")
    with pytest.raises(RuntimeError) as exc_info:
        llm.complete("hello")
    assert "HTTP 404" in str(exc_info.value)
    assert "model not supported" in str(exc_info.value)


def test_openai_compatible_vision_adapter(tmp_path, monkeypatch):
    """Verify OpenAICompatibleVisionAdapter formats base64 images and calls endpoint."""
    fake_called = False

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "The slide displays a memory diagram with addresses [Evidence 1]."
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json=None, headers=None):
            nonlocal fake_called
            fake_called = True
            assert "/chat/completions" in url
            assert json["model"] == "zai-org/GLM-4.6V-Flash"
            content = json["messages"][0]["content"]
            assert any(part.get("type") == "image_url" for part in content)
            return FakeResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", FakeClient)

    adapter = OpenAICompatibleVisionAdapter(
        base_url="http://fake-vision:8000/v1",
        api_key="fake-vision-key",
        model_name="zai-org/GLM-4.6V-Flash",
    )
    assert adapter.is_available() is True

    img_file = tmp_path / "test.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)
    payload = VisualPayload(
        label="[Evidence 1]",
        image_path=str(img_file),
        image_bytes=img_file.read_bytes(),
    )

    ans = adapter.generate("What is in this diagram?", [payload])
    assert fake_called is True
    assert "[Evidence 1]" in ans


def test_call_ocr_vlm_adapter(tmp_path, monkeypatch):
    """Verify call_ocr_vlm calls PaddleOCR-VL-1.6 endpoint with image."""
    fake_called = False

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "int *ptr = malloc(sizeof(int));"
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json=None, headers=None):
            nonlocal fake_called
            fake_called = True
            assert json["model"] == "PaddlePaddle/PaddleOCR-VL-1.6"
            return FakeResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", FakeClient)

    img_file = tmp_path / "code_slide.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)

    extracted = call_ocr_vlm(
        image_path=str(img_file),
        base_url="http://fake-ocr:8000/v1",
        api_key="fake-ocr-key",
        model="PaddlePaddle/PaddleOCR-VL-1.6",
    )
    assert fake_called is True
    assert "malloc" in extracted


def test_detect_backend_status_reporting(monkeypatch):
    """Verify detect_backend_status reflects configured OpenAI-compatible endpoints."""
    monkeypatch.setattr(CONFIG, "llm_api_key", "mock-llm-key")
    monkeypatch.setattr(CONFIG, "llm_model", "google/gemma-4-12b-it-fp8")
    monkeypatch.setattr(CONFIG, "vision_api_key", "mock-vis-key")
    monkeypatch.setattr(CONFIG, "vision_model", "zai-org/GLM-4.6V-Flash")
    monkeypatch.setattr(CONFIG, "ocr_api_key", "mock-ocr-key")
    monkeypatch.setattr(CONFIG, "ocr_base_url", "http://fake-ocr/v1")
    monkeypatch.setattr(CONFIG, "ocr_model", "PaddlePaddle/PaddleOCR-VL-1.6")

    status = detect_backend_status()
    assert status["is_live"] is True
    assert "google/gemma-4-12b-it-fp8" in status["effective_llm"]
    assert "zai-org/GLM-4.6V-Flash" in status["effective_vision_backend"]
    assert "PaddlePaddle/PaddleOCR-VL-1.6" in status["effective_ocr"]


def test_fastapi_upload_and_rag_endpoints(synthetic_video, synthetic_pdf, tmp_path, monkeypatch):
    """Verify FastAPI integration for video + standalone PDF uploads, either/or checks, and live Q&A."""
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

    # 1. Reject empty upload (neither video nor pdf)
    res = client.post("/api/upload", data={"title": "Empty Upload"})
    assert res.status_code == 400

    # 2. Upload standalone PDF
    with open(synthetic_pdf, "rb") as pf:
        pdf_bytes = pf.read()

    res = client.post(
        "/api/upload",
        files={"slides_pdf": ("lecture_slides.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"title": "Standalone Slides Lecture"}
    )
    assert res.status_code == 200, res.text
    pdf_data = res.json()
    assert pdf_data["status"] == "ok"
    assert pdf_data["visual_chunks"] == 2
    assert pdf_data["audio_chunks"] == 0

    # 3. Upload video with transcript
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
    v_data = res.json()
    assert v_data["status"] == "ok"
    video_path = v_data["video_path"]

    # 4. List uploads -> should have 2 sources (PDF + Video)
    res = client.get("/api/uploads")
    assert res.status_code == 200
    assert res.json()["count"] == 2

    # 5. RAG Q&A query -> returns grounded answer and citations
    res = client.post("/api/demo/query", json={"query": "FastAPI integration", "top_k": 3})
    assert res.status_code == 200
    q_data = res.json()
    assert q_data["total_retrieved"] >= 1
    assert "answer" in q_data
    assert "citations" in q_data

    # 6. Media video serve endpoint for both video and pdf
    res = client.get(f"/media/video?path={video_path}")
    assert res.status_code in (200, 206)
    assert "video/mp4" in res.headers.get("content-type", "")

    res_pdf = client.get(f"/media/video?path={pdf_data['pdf_path']}")
    assert res_pdf.status_code in (200, 206)
    assert "application/pdf" in res_pdf.headers.get("content-type", "")

    # 7. Reject invalid media paths
    res = client.get("/media/video?path=config.py")
    assert res.status_code == 400

    # 8. Clear uploads
    res = client.delete("/api/uploads")
    assert res.status_code == 200
    assert res.json()["cleared"] is True

    # 9. List should be empty again
    res = client.get("/api/uploads")
    assert res.status_code == 200
    assert res.json()["count"] == 0


def test_decode_audio_ffmpeg_pcm_and_whisper_bypass(synthetic_video, monkeypatch):
    """Verify decode_audio_ffmpeg_pcm extracts float32 PCM and faster-whisper bypasses PyAV."""
    import numpy as np

    # 1. Test direct PCM extraction via ffmpeg
    pcm = decode_audio_ffmpeg_pcm(synthetic_video)
    assert pcm is not None
    assert isinstance(pcm, np.ndarray)
    assert pcm.dtype == np.float32
    # 1 second of 16kHz audio ~ 16000 samples
    assert len(pcm) >= 15000

    # 2. Test fallback when ffmpeg fails or file doesn't exist
    res_invalid = decode_audio_ffmpeg_pcm("non_existent_file.mp4")
    assert res_invalid is None

    # 3. Test transcribe_video_whisper with mocked WhisperModel to verify
    #    it passes numpy float32 array to model.transcribe(audio_np, vad_filter=True)
    transcribe_args = {}

    class DummySegment:
        start = 0.0
        end = 1.0
        text = "Hello world from audio"

    class DummyWhisperModel:
        def __init__(self, model_size, device="cpu", compute_type="int8"):
            assert device == "cpu"
            assert compute_type == "int8"
            assert model_size in ("tiny", "base")

        def transcribe(self, audio, vad_filter=True):
            transcribe_args["audio"] = audio
            transcribe_args["vad_filter"] = vad_filter
            return [DummySegment()], None

    import sys
    import types
    fake_mod = types.ModuleType("faster_whisper")
    fake_mod.WhisperModel = DummyWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_mod)

    segs = transcribe_video_whisper(synthetic_video, model_size="tiny")
    assert len(segs) == 1
    assert segs[0].start_sec == 0.0
    assert segs[0].end_sec == 1.0
    assert segs[0].text == "Hello world from audio"
    assert isinstance(transcribe_args["audio"], np.ndarray)
    assert transcribe_args["audio"].dtype == np.float32
    assert transcribe_args["vad_filter"] is True

    # 4. Test fallback to path when ffmpeg decoding returns None
    from demo import upload_ingest
    monkeypatch.setattr(upload_ingest, "decode_audio_ffmpeg_pcm", lambda path: None)
    segs_fallback = transcribe_video_whisper("fallback_video.mp4", model_size="tiny")
    assert len(segs_fallback) == 1
    assert transcribe_args["audio"] == "fallback_video.mp4"


def test_production_db_hashes_unchanged():
    """Verify that tests never modified the production tracked databases."""
    assert os.path.exists("data/corpus.db")
    assert os.path.exists("data/learner_memory.db")
    assert _sha256("data/corpus.db") == CORPUS_DB_BASELINE_SHA
    assert _sha256("data/learner_memory.db") == MEMORY_DB_BASELINE_SHA
