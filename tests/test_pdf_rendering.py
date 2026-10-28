import os
import shutil
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from config import CONFIG
from ingestion.chunker import build_chunks, compute_chunk_id
from ingestion.ocr import extract_pdf_slides, OcrResult
from ingestion.versioning import SourceVersion
from storage.corpus_store import init_db, insert_chunks, upsert_source, active_chunks
from scripts.ingest_official import resolve_citation


def _create_synthetic_pdf(path: str, pages_data: list) -> str:
    """Helper to generate a small synthetic PDF offline.
    
    pages_data is a list of dicts: [{"text": str or None, "draw_rect": bool}]
    """
    doc = fitz.open()
    for item in pages_data:
        page = doc.new_page(width=720, height=405)
        if item.get("draw_rect"):
            page.draw_rect(fitz.Rect(50, 50, 200, 200), color=(1, 0, 0), fill=(0, 0.5, 0.8))
        if item.get("text"):
            page.insert_text(fitz.Point(60, 100), item["text"], fontsize=14)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use an isolated SQLite database and keyframes directory for each test."""
    db_file = str(tmp_path / "test_corpus.db")
    kf_dir = str(tmp_path / "keyframes")
    monkeypatch.setattr(CONFIG, "corpus_db_path", db_file)
    monkeypatch.setattr(CONFIG, "keyframes_dir", kf_dir)
    init_db()
    return db_file


def test_pdf_page_rendering_creates_valid_jpeg(tmp_path):
    """Requirement 2 & 3: Render PDF pages to real JPEG images in the version-isolated dir."""
    pdf_path = str(tmp_path / "sample.pdf")
    _create_synthetic_pdf(
        pdf_path,
        [
            {"text": "First page title", "draw_rect": True},
            {"text": "Second page content", "draw_rect": False},
        ],
    )

    results = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="test_hash_123",
        base_dir=str(tmp_path / "keyframes"),
    )

    assert len(results) == 2

    for idx, r in enumerate(results, 1):
        assert r.status == "success"
        assert r.error_message is None
        assert r.timestamp_sec is None
        assert r.page_number == idx
        assert r.image_path.endswith(f"slide_{idx:05d}.jpg")
        assert os.path.exists(r.image_path)
        assert os.path.getsize(r.image_path) > 0

        # Verify real JPEG format via header magic bytes and PyMuPDF image document
        with open(r.image_path, "rb") as f:
            header = f.read(3)
            assert header == b"\xff\xd8\xff", f"File {r.image_path} missing JPEG magic bytes"

        with fitz.open(r.image_path) as img_doc:
            assert img_doc.page_count == 1
            rect = img_doc[0].rect
            assert rect.width > 0
            assert rect.height > 0



def test_pdf_extracted_text(tmp_path):
    """Requirement 4: Extract actual embedded text from each page."""
    pdf_path = str(tmp_path / "text_slides.pdf")
    _create_synthetic_pdf(
        pdf_path,
        [
            {"text": "Syntax Highlighting in C", "draw_rect": False},
            {"text": "printf(\"hello, world\\n\");", "draw_rect": True},
        ],
    )

    results = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="hash_text",
        base_dir=str(tmp_path / "keyframes"),
    )

    assert len(results) == 2
    assert "Syntax Highlighting in C" in results[0].text
    assert "printf(\"hello, world\\n\");" in results[1].text


def test_pdf_empty_text_handling(tmp_path):
    """Requirement 4: Empty-text pages are not treated as processing failures."""
    pdf_path = str(tmp_path / "empty_pages.pdf")
    _create_synthetic_pdf(
        pdf_path,
        [
            {"text": None, "draw_rect": True},      # pure drawing, no text
            {"text": "   \n\t  ", "draw_rect": False}, # whitespace only
        ],
    )

    results = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="hash_empty",
        base_dir=str(tmp_path / "keyframes"),
    )

    assert len(results) == 2
    for r in results:
        assert r.status == "success"
        assert r.error_message is None
        assert r.text == ""
        assert os.path.exists(r.image_path)


def test_pdf_image_existence_after_temporary_download_deleted(tmp_path):
    """Requirement 3: Rendered images remain persistently available after temp files are deleted."""
    temp_download_dir = tmp_path / "download_tmp"
    temp_download_dir.mkdir()
    pdf_path = str(temp_download_dir / "downloaded_slides.pdf")
    _create_synthetic_pdf(
        pdf_path,
        [{"text": "Persistent slide 1", "draw_rect": True}],
    )

    results = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="hash_persist",
        base_dir=str(tmp_path / "keyframes"),
    )

    image_path = results[0].image_path
    assert os.path.exists(image_path)

    # Delete the source PDF and its directory (simulating tempdir cleanup)
    shutil.rmtree(str(temp_download_dir))
    assert not os.path.exists(pdf_path)

    # The rendered slide image MUST still exist and be a valid JPEG
    assert os.path.exists(image_path)
    with open(image_path, "rb") as f:
        assert f.read(3) == b"\xff\xd8\xff"
    with fitz.open(image_path) as img_doc:
        assert img_doc.page_count == 1



def test_pdf_deterministic_page_identity(tmp_path):
    """Requirement 5 & 7: Chunk IDs and filenames are deterministic across rebuilds."""
    pdf_path = str(tmp_path / "deterministic.pdf")
    _create_synthetic_pdf(
        pdf_path,
        [
            {"text": "Deterministic Slide 1", "draw_rect": False},
            {"text": "Deterministic Slide 2", "draw_rect": False},
        ],
    )

    # Run 1
    results1 = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="hash_det",
        base_dir=str(tmp_path / "keyframes"),
    )
    chunks1 = build_chunks(
        source_id="cs50-lec01",
        content_hash="hash_det",
        transcript=[],
        ocr_results=results1,
        asset_id="cs50-2024-lec01-video",
    )

    # Run 2
    results2 = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="hash_det",
        base_dir=str(tmp_path / "keyframes"),
    )
    chunks2 = build_chunks(
        source_id="cs50-lec01",
        content_hash="hash_det",
        transcript=[],
        ocr_results=results2,
        asset_id="cs50-2024-lec01-video",
    )

    assert len(chunks1) == len(chunks2) == 2
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.image_path == c2.image_path
        assert c1.page_number == c2.page_number
        assert c1.text == c2.text


def test_pdf_version_isolated_paths(tmp_path):
    """Requirement 3 & 7: Different content hashes produce isolated paths and do not collide."""
    pdf_path = str(tmp_path / "slides.pdf")
    _create_synthetic_pdf(pdf_path, [{"text": "Version isolation test", "draw_rect": False}])

    results_v1 = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="hash_v1",
        base_dir=str(tmp_path / "keyframes"),
    )
    results_v2 = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="hash_v2",
        base_dir=str(tmp_path / "keyframes"),
    )

    path_v1 = results_v1[0].image_path
    path_v2 = results_v2[0].image_path

    assert path_v1 != path_v2
    assert "hash_v1" in path_v1
    assert "hash_v2" in path_v2
    assert os.path.exists(path_v1)
    assert os.path.exists(path_v2)


def test_pdf_does_not_invent_video_timestamps(tmp_path, capsys):
    """Requirement 6: A PDF page number is not a video timestamp; keep bounds unknown."""
    pdf_path = str(tmp_path / "slides.pdf")
    _create_synthetic_pdf(pdf_path, [{"text": "Slide on screen", "draw_rect": False}])

    results = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="hash_ts",
        base_dir=str(tmp_path / "keyframes"),
    )
    chunks = build_chunks(
        source_id="cs50-lec01",
        content_hash="hash_ts",
        transcript=[],
        ocr_results=results,
        asset_id="cs50-2024-lec01-video",
        source_url="https://cs50.harvard.edu/x/2024/weeks/1/",
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.start_sec is None
    assert chunk.end_sec is None

    # Insert into database and resolve citation
    insert_chunks([chunk])
    resolve_citation(chunk.chunk_id)
    captured = capsys.readouterr()

    assert "Time Bounds: Unknown" in captured.out
    assert "Video Nav:" not in captured.out
    assert "Visual Nav:  " in captured.out
    assert chunk.image_path in captured.out


def test_pdf_processing_failure_records_error_distinctly(tmp_path):
    """Requirement 4: Page failures are recorded as status='failed' with error_message, preserving asset path."""
    pdf_path = str(tmp_path / "error_test.pdf")
    _create_synthetic_pdf(
        pdf_path,
        [
            {"text": "Page 1 ok", "draw_rect": False},
            {"text": "Page 2 fails", "draw_rect": False},
        ],
    )

    # Patch get_pixmap on the second page to raise an error
    original_get_pixmap = fitz.Page.get_pixmap
    call_count = [0]

    def mock_get_pixmap(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("MuPDF rendering error")
        return original_get_pixmap(self, *args, **kwargs)

    with patch.object(fitz.Page, "get_pixmap", mock_get_pixmap):
        results = extract_pdf_slides(
            pdf_path=pdf_path,
            source_id="cs50-lec01",
            content_hash="hash_err",
            base_dir=str(tmp_path / "keyframes"),
        )

    assert len(results) == 2
    # Page 1 succeeded
    assert results[0].status == "success"
    assert results[0].text == "Page 1 ok"
    assert results[0].error_message is None

    # Page 2 failed gracefully
    assert results[1].status == "failed"
    assert results[1].text == ""
    assert results[1].error_message == "RuntimeError"
    assert results[1].image_path.endswith("slide_00002.jpg")
    assert results[1].page_number == 2


def test_pdf_provenance_and_database_persistence(tmp_path):
    """Requirement 5: Visual chunks preserve provenance, asset_id, page_number and persist in DB."""
    pdf_path = str(tmp_path / "persistence.pdf")
    _create_synthetic_pdf(pdf_path, [{"text": "DB persistence test", "draw_rect": True}])

    results = extract_pdf_slides(
        pdf_path=pdf_path,
        source_id="cs50-lec01",
        content_hash="hash_db",
        base_dir=str(tmp_path / "keyframes"),
    )
    chunks = build_chunks(
        source_id="cs50-lec01",
        content_hash="hash_db",
        transcript=[],
        ocr_results=results,
        asset_id="cs50-2024-lec01-video",
        source_url="https://cs50.harvard.edu/x/2024/weeks/1/",
    )
    version = SourceVersion(
        source_id="cs50-lec01",
        content_hash="hash_db",
        course_edition="2024",
        title="Lecture 1",
        asset_id="cs50-2024-lec01-video",
        source_url="https://cs50.harvard.edu/x/2024/weeks/1/",
    )

    insert_chunks(chunks)
    upsert_source(version)

    active = active_chunks(modality="visual")
    assert len(active) == 1
    rec = active[0]
    assert rec["chunk_id"] == chunks[0].chunk_id
    assert rec["source_id"] == "cs50-lec01"
    assert rec["content_hash"] == "hash_db"
    assert rec["asset_id"] == "cs50-2024-lec01-video"
    assert rec["source_url"] == "https://cs50.harvard.edu/x/2024/weeks/1/"
    assert rec["page_number"] == 1
    assert rec["status"] == "success"
    assert os.path.exists(rec["image_path"])
