import pytest
import sqlite3
from ingestion.manifest import get_manifest_asset
from ingestion.chunker import build_chunks, EvidenceChunk
from ingestion.versioning import SourceVersion
from storage.corpus_store import init_db, insert_chunks, upsert_source
from ingestion.transcriber import TranscriptSegment
from scripts.ingest_official import resolve_citation
from config import CONFIG
import sys
from io import StringIO

from unittest.mock import patch
from ingestion.manifest import SourceAssetRecord

@patch('ingestion.manifest.load_manifest')
def test_manifest_resolves_configuration(mock_load_manifest):
    mock_load_manifest.return_value = [SourceAssetRecord(
        source_id="cs50-lec01",
        edition_id="2024",
        asset_id="cs50-2024-lec01-video",
        title="Lecture 1",
        source_url="url",
        original_asset_url="url2",
        modality="video"
    )]
    record = get_manifest_asset("cs50-2024-lec01-video", manifest_path="data/source_manifest.yaml")
    assert record is not None
    assert record.source_id == "cs50-lec01"
    assert record.edition_id == "2024"

def test_produced_evidence_preserves_provenance():
    transcript = [TranscriptSegment(start_sec=10.0, end_sec=20.0, text="Hello world")]
    chunks = build_chunks(
        source_id="cs50-lec01",
        content_hash="testhash",
        transcript=transcript,
        ocr_results=[],
        asset_id="cs50-2024-lec01-video",
        source_url="https://cs50.harvard.edu/x/2024/weeks/1/"
    )
    assert len(chunks) == 1
    assert chunks[0].source_id == "cs50-lec01"
    assert chunks[0].content_hash == "testhash"
    assert chunks[0].asset_id == "cs50-2024-lec01-video"
    assert chunks[0].source_url == "https://cs50.harvard.edu/x/2024/weeks/1/"

def test_valid_timestamp_interval_accepted():
    transcript = [TranscriptSegment(start_sec=5.0, end_sec=15.0, text="Valid")]
    chunks = build_chunks(
        source_id="cs50-lec01",
        content_hash="testhash",
        transcript=transcript,
        ocr_results=[],
        asset_id="cs50-2024-lec01-video"
    )
    assert len(chunks) == 1
    assert chunks[0].start_sec >= 0
    assert chunks[0].end_sec > chunks[0].start_sec

def test_out_of_bounds_timestamp_rejected():
    transcript = [TranscriptSegment(start_sec=20.0, end_sec=10.0, text="Invalid")]
    with pytest.raises(ValueError):
        build_chunks(
            source_id="cs50-lec01",
            content_hash="testhash",
            transcript=transcript,
            ocr_results=[]
        )

def test_unknown_evidence_id_rejected(capsys):
    resolve_citation("unknown_id_123")
    captured = capsys.readouterr()
    assert "Error: Unknown evidence ID" in captured.out

def test_citation_resolves_to_correct_source(capsys):
    init_db()
    transcript = [TranscriptSegment(start_sec=50.0, end_sec=60.0, text="Citation test")]
    chunks = build_chunks(
        source_id="cs50-lec01",
        content_hash="citationhash",
        transcript=transcript,
        ocr_results=[],
        asset_id="cs50-2024-lec01-video",
        source_url="https://test.url"
    )
    insert_chunks(chunks)
    
    resolve_citation(chunks[0].chunk_id)
    captured = capsys.readouterr()
    assert "Source ID:   cs50-lec01" in captured.out
    assert "Time Bounds: 50.0s - 60.0s" in captured.out
    assert "Video Nav:   https://test.url&t=50s" in captured.out

def test_repeated_ingestion_preserves_deterministic_identity():
    transcript = [TranscriptSegment(start_sec=10.0, end_sec=20.0, text="Hello world")]
    chunks1 = build_chunks("cs50-lec01", "testhash", transcript, [], asset_id="cs50-2024-lec01-video")
    chunks2 = build_chunks("cs50-lec01", "testhash", transcript, [], asset_id="cs50-2024-lec01-video")
    
    assert len(chunks1) == 1
    assert len(chunks2) == 1
    assert chunks1[0].chunk_id == chunks2[0].chunk_id

def test_content_hash_is_deterministic(tmp_path):
    from ingestion.versioning import file_content_hash
    import hashlib
    file1 = tmp_path / "test1.txt"
    file1.write_text("dummy content")
    
    hash1 = file_content_hash(str(file1))
    hash2 = file_content_hash(str(file1))
    
    assert hash1 == hash2
    assert hash1 == hashlib.sha256(b"dummy content").hexdigest()[:16]

def test_content_hash_changes_when_input_changes(tmp_path):
    from ingestion.versioning import file_content_hash
    file1 = tmp_path / "test1.txt"
    file1.write_text("dummy content 1")
    
    file2 = tmp_path / "test2.txt"
    file2.write_text("dummy content 2")
    
    hash1 = file_content_hash(str(file1))
    hash2 = file_content_hash(str(file2))
    
    assert hash1 != hash2

def test_srt_evidence_uses_real_timestamps():
    transcript = [TranscriptSegment(start_sec=10.5, end_sec=20.5, text="Hello world")]
    chunks = build_chunks(
        source_id="cs50-lec01",
        content_hash="testhash",
        transcript=transcript,
        ocr_results=[],
        asset_id="cs50-2024-lec01-video",
    )
    assert len(chunks) == 1
    assert chunks[0].start_sec == 10.5
    assert chunks[0].end_sec == 20.5

def test_visual_evidence_does_not_use_synthetic_video_timestamp():
    from ingestion.ocr import OcrResult
    ocr_results = [OcrResult(timestamp_sec=None, image_path="slides.pdf", text="Slide 1")]
    chunks = build_chunks(
        source_id="cs50-lec01",
        content_hash="testhash",
        transcript=[],
        ocr_results=ocr_results,
        asset_id="cs50-2024-lec01-video",
    )
    assert len(chunks) == 1
    assert chunks[0].start_sec is None
    assert chunks[0].end_sec is None

def test_visual_citation_does_not_create_fake_timestamp(capsys):
    init_db()
    from ingestion.ocr import OcrResult
    ocr_results = [OcrResult(timestamp_sec=None, image_path="slides.pdf", text="Slide 1")]
    chunks = build_chunks(
        source_id="cs50-lec01",
        content_hash="testhash",
        transcript=[],
        ocr_results=ocr_results,
        asset_id="cs50-2024-lec01-video",
        source_url="https://test.url"
    )
    insert_chunks(chunks)
    resolve_citation(chunks[0].chunk_id)
    captured = capsys.readouterr()
    assert "Time Bounds: Unknown" in captured.out
    assert "Video Nav: " not in captured.out
    assert "Visual Nav:  slides.pdf" in captured.out

def test_audio_citation_remains_navigable(capsys):
    init_db()
    transcript = [TranscriptSegment(start_sec=10.0, end_sec=20.0, text="Hello world")]
    chunks = build_chunks(
        source_id="cs50-lec01",
        content_hash="testhash",
        transcript=transcript,
        ocr_results=[],
        asset_id="cs50-2024-lec01-video",
        source_url="https://test.url"
    )
    insert_chunks(chunks)
    resolve_citation(chunks[0].chunk_id)
    captured = capsys.readouterr()
    assert "Time Bounds: 10.0s - 20.0s" in captured.out
    assert "Video Nav:   https://test.url&t=10s" in captured.out
