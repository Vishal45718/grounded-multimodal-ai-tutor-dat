"""Offline automated unit tests for PDF slide rendering and visual evidence extraction.

Covers:
1. Basic rendering of PDF pages to image files.
2. Persistence and verification of image paths on disk.
3. Embedded text extraction from slide pages.
4. Distinguishing text-free (empty) slides from extraction failures.
5. Deterministic chunk identity for rendered slide pages.
6. Version isolation of output slide image directories.
7. Graceful error handling on corrupted/invalid PDF inputs.
8. Preservation and propagation of page numbers.
9. Manifest and provenance retention on slide evidence.
"""
import os
import fitz
import pytest
from ingestion.ocr import extract_pdf_slides, OcrResult
from ingestion.chunker import build_chunks
from ingestion.versioning import file_content_hash


@pytest.fixture
def sample_pdf(tmp_path):
    """Creates a 3-page PDF: Page 1 with text, Page 2 with text, Page 3 blank/empty."""
    pdf_path = tmp_path / "test_slides.pdf"
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text((50, 50), "Hello, C programming!\nprintf('Hello, world\\n');")

    p2 = doc.new_page()
    p2.insert_text((50, 50), "Data Structures: Arrays, Trees, Hash Tables")

    # Page 3 is left intentionally blank (diagram or image placeholder)
    p3 = doc.new_page()

    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_pdf_rendering_basic(sample_pdf, tmp_path):
    out_dir = tmp_path / "keyframes"
    results = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="hash123")
    assert len(results) == 3
    assert all(isinstance(r, OcrResult) for r in results)


def test_pdf_image_persistence(sample_pdf, tmp_path):
    out_dir = tmp_path / "keyframes"
    results = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="hash123")
    for r in results:
        assert os.path.exists(r.image_path)
        assert os.path.getsize(r.image_path) > 0


def test_pdf_text_extraction(sample_pdf, tmp_path):
    out_dir = tmp_path / "keyframes"
    results = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="hash123")
    assert "Hello, C programming!" in results[0].text
    assert "Data Structures" in results[1].text


def test_empty_slide_distinguishable_from_failure(sample_pdf, tmp_path):
    out_dir = tmp_path / "keyframes"
    results = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="hash123")
    # Page 3 is empty
    assert results[2].status == "empty"
    assert results[2].text == ""
    assert results[2].error_message is None
    assert os.path.exists(results[2].image_path)


def test_slide_deterministic_chunk_identity(sample_pdf, tmp_path):
    out_dir = tmp_path / "keyframes"
    results1 = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="hash123")
    chunks1 = build_chunks("cs50-lec01", "hash123", [], results1)

    results2 = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="hash123")
    chunks2 = build_chunks("cs50-lec01", "hash123", [], results2)

    assert len(chunks1) == len(chunks2) == 3
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.chunk_id == c2.chunk_id


def test_version_isolated_directories(sample_pdf, tmp_path):
    out_dir = tmp_path / "keyframes"
    res_v1 = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="v1_hash")
    res_v2 = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="v2_hash")

    assert os.path.dirname(res_v1[0].image_path) != os.path.dirname(res_v2[0].image_path)
    assert "v1_hash" in res_v1[0].image_path
    assert "v2_hash" in res_v2[0].image_path


def test_corrupted_pdf_error_handling(tmp_path):
    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"not a valid pdf content")
    out_dir = tmp_path / "keyframes"

    # PyMuPDF should catch exception cleanly
    with pytest.raises(Exception):
        extract_pdf_slides(str(corrupt_pdf), out_dir=str(out_dir), source_id="test", content_hash="hash")


def test_page_number_propagation(sample_pdf, tmp_path):
    out_dir = tmp_path / "keyframes"
    results = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="hash123")
    assert [r.page_number for r in results] == [1, 2, 3]

    chunks = build_chunks("cs50-lec01", "hash123", [], results)
    assert [c.page_number for c in chunks] == [1, 2, 3]


def test_slide_provenance_retention(sample_pdf, tmp_path):
    out_dir = tmp_path / "keyframes"
    results = extract_pdf_slides(sample_pdf, out_dir=str(out_dir), source_id="cs50-lec01", content_hash="hash123")
    chunks = build_chunks(
        "cs50-lec01",
        "hash123",
        [],
        results,
        asset_id="cs50-2024-lec01-video",
        source_url="https://cs50.harvard.edu/x/2024/weeks/1/",
    )
    for c in chunks:
        assert c.asset_id == "cs50-2024-lec01-video"
        assert c.source_url == "https://cs50.harvard.edu/x/2024/weeks/1/"
        assert c.modality == "visual"
