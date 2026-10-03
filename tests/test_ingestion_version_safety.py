"""Tests for ingestion retry safety and active-version enforcement."""
import argparse
from unittest.mock import patch
import pytest

from config import CONFIG
from ingestion.chunker import EvidenceChunk
from ingestion.ocr import OcrResult
from ingestion.transcriber import TranscriptSegment
from ingestion.versioning import SourceVersion
from main import ingest
from storage.corpus_store import (
    active_chunks,
    deprecate_edition,
    init_db,
    insert_chunks,
    is_source_active,
    upsert_source,
)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use an isolated SQLite database for each test."""
    db_file = str(tmp_path / "test_corpus.db")
    monkeypatch.setattr(CONFIG, "corpus_db_path", db_file)
    init_db()
    return db_file


def _make_args(video_path: str, source_id: str = "cs5903-lec01", title: str = "Lecture 1", edition: str = "Fall2026"):
    return argparse.Namespace(
        video=video_path,
        source_id=source_id,
        title=title,
        course_edition=edition,
    )


def test_failed_ingestion_can_retry(tmp_path):
    """Bug 1: A failed extraction attempt must not register the source as active,
    and subsequent retries must perform extraction and succeed."""
    video_file = str(tmp_path / "lecture01.mp4")
    with open(video_file, "w") as f:
        f.write("dummy video v1 content")

    args = _make_args(video_file, source_id="cs5903-lec01")

    # Attempt 1: Extraction fails (e.g. ffmpeg / whisper crash)
    with patch("main.extract_audio", side_effect=RuntimeError("FFmpeg execution error")):
        with pytest.raises(RuntimeError, match="FFmpeg execution error"):
            ingest(args)

    # Verify source was not activated and no active chunks exist
    assert not is_source_active("cs5903-lec01", "dummy")
    assert len(active_chunks()) == 0

    # Attempt 2: Retry with successful extraction
    mock_transcript = [TranscriptSegment(start_sec=0.0, end_sec=10.0, text="Intro to algorithms")]
    mock_keyframes = []
    with patch("main.extract_audio", return_value="audio.wav"), \
         patch("main.transcribe", return_value=mock_transcript), \
         patch("main.extract_keyframes", return_value=mock_keyframes), \
         patch("main.ocr_keyframes", return_value=[]):
        ingest(args)

    # Ingestion should have succeeded on retry
    active = active_chunks()
    assert len(active) == 1
    assert active[0]["text"] == "Intro to algorithms"
    assert active[0]["source_id"] == "cs5903-lec01"


def test_previous_version_remains_active_after_failed_replacement(tmp_path):
    """Lifecycle D (steps 1-4): When replacing V1 with V2 fails during extraction,
    V1 must remain completely intact and active."""
    video_v1 = str(tmp_path / "lecture_v1.mp4")
    with open(video_v1, "w") as f:
        f.write("content of v1")

    args_v1 = _make_args(video_v1, source_id="cs5903-lec01")

    # 1. Ingest V1 successfully
    mock_t1 = [TranscriptSegment(start_sec=0.0, end_sec=5.0, text="V1 original lecture content")]
    with patch("main.extract_audio", return_value="audio.wav"), \
         patch("main.transcribe", return_value=mock_t1), \
         patch("main.extract_keyframes", return_value=[]), \
         patch("main.ocr_keyframes", return_value=[]):
        ingest(args_v1)

    # 2. Confirm V1 is active
    active = active_chunks()
    assert len(active) == 1
    assert active[0]["text"] == "V1 original lecture content"
    v1_hash = active[0]["content_hash"]

    # 3. Attempt V2 ingestion and force extraction failure
    video_v2 = str(tmp_path / "lecture_v2.mp4")
    with open(video_v2, "w") as f:
        f.write("different content of v2")
    args_v2 = _make_args(video_v2, source_id="cs5903-lec01")

    with patch("main.extract_audio", side_effect=RuntimeError("Whisper OOM error")):
        with pytest.raises(RuntimeError, match="Whisper OOM error"):
            ingest(args_v2)

    # 4. Confirm V1 is STILL active and unmodified
    active_after_failure = active_chunks()
    assert len(active_after_failure) == 1
    assert active_after_failure[0]["content_hash"] == v1_hash
    assert active_after_failure[0]["text"] == "V1 original lecture content"


def test_new_successful_version_replaces_previous_active_version(tmp_path):
    """Lifecycle D (steps 5-7): A new successful version replaces the previous version."""
    video_v1 = str(tmp_path / "lecture_v1.mp4")
    with open(video_v1, "w") as f:
        f.write("v1 content")
    video_v2 = str(tmp_path / "lecture_v2.mp4")
    with open(video_v2, "w") as f:
        f.write("v2 new content")

    args_v1 = _make_args(video_v1, source_id="cs5903-lec01")
    args_v2 = _make_args(video_v2, source_id="cs5903-lec01")

    # Ingest V1
    with patch("main.extract_audio", return_value="audio.wav"), \
         patch("main.transcribe", return_value=[TranscriptSegment(0.0, 5.0, "V1 text")]), \
         patch("main.extract_keyframes", return_value=[]), \
         patch("main.ocr_keyframes", return_value=[]):
        ingest(args_v1)

    assert len(active_chunks()) == 1
    assert active_chunks()[0]["text"] == "V1 text"

    # Ingest V2
    with patch("main.extract_audio", return_value="audio.wav"), \
         patch("main.transcribe", return_value=[TranscriptSegment(0.0, 5.0, "V2 updated text")]), \
         patch("main.extract_keyframes", return_value=[]), \
         patch("main.ocr_keyframes", return_value=[]):
        ingest(args_v2)

    # Confirm V2 is active and V1 is not
    active = active_chunks()
    assert len(active) == 1
    assert active[0]["text"] == "V2 updated text"


def test_active_chunks_excludes_old_version():
    """Bug 2: active_chunks must strictly enforce that chunks match the active
    source content_hash, even if a stale chunk has is_stale=0."""
    v1 = SourceVersion(source_id="cs101", content_hash="hash_v1", course_edition="Fall2026", title="Intro")
    v2 = SourceVersion(source_id="cs101", content_hash="hash_v2", course_edition="Fall2026", title="Intro")

    chunk_v1 = EvidenceChunk(
        chunk_id="c1", source_id="cs101", content_hash="hash_v1",
        modality="audio", start_sec=0.0, end_sec=10.0, text="V1 chunk",
    )
    chunk_v2 = EvidenceChunk(
        chunk_id="c2", source_id="cs101", content_hash="hash_v2",
        modality="audio", start_sec=0.0, end_sec=10.0, text="V2 chunk",
    )

    # Ingest V1
    insert_chunks([chunk_v1])
    upsert_source(v1)
    assert len(active_chunks()) == 1
    assert active_chunks()[0]["chunk_id"] == "c1"

    # Activate V2
    insert_chunks([chunk_v2])
    upsert_source(v2)

    active = active_chunks()
    assert len(active) == 1
    assert active[0]["chunk_id"] == "c2"
    assert active[0]["content_hash"] == "hash_v2"


def test_delayed_old_version_write_cannot_become_active():
    """Bug 3 & Requirement C / E: Attempting to insert a chunk from an old version
    after a new version is active must not activate the old chunk."""
    v1 = SourceVersion(source_id="cs101", content_hash="hash_v1", course_edition="Fall2026", title="Intro")
    v2 = SourceVersion(source_id="cs101", content_hash="hash_v2", course_edition="Fall2026", title="Intro")

    chunk_v1_early = EvidenceChunk(
        chunk_id="c1", source_id="cs101", content_hash="hash_v1",
        modality="audio", start_sec=0.0, end_sec=10.0, text="V1 initial chunk",
    )
    chunk_v2 = EvidenceChunk(
        chunk_id="c2", source_id="cs101", content_hash="hash_v2",
        modality="audio", start_sec=0.0, end_sec=10.0, text="V2 chunk",
    )
    delayed_v1_chunk = EvidenceChunk(
        chunk_id="c1_delayed", source_id="cs101", content_hash="hash_v1",
        modality="audio", start_sec=10.0, end_sec=20.0, text="V1 late chunk",
    )

    # 1. Ingest V1
    insert_chunks([chunk_v1_early])
    upsert_source(v1)
    assert len(active_chunks()) == 1

    # 2. Ingest V2 (replaces V1)
    insert_chunks([chunk_v2])
    upsert_source(v2)
    assert len(active_chunks()) == 1
    assert active_chunks()[0]["chunk_id"] == "c2"

    # 3. Delayed arrival of old V1 chunk
    insert_chunks([delayed_v1_chunk])

    # 4. Confirm delayed V1 chunk cannot become active
    active = active_chunks()
    assert len(active) == 1
    assert active[0]["chunk_id"] == "c2"
    assert active[0]["content_hash"] == "hash_v2"


def test_full_lifecycle_preservation_and_replacement(tmp_path):
    """Explicit test for Requirement D:
    1. Ingest V1 successfully.
    2. Confirm V1 is active.
    3. Attempt V2 and force extraction failure.
    4. Confirm V1 is still active.
    5. Retry V2 successfully.
    6. Confirm V2 becomes active.
    7. Confirm V1 is no longer active.
    """
    v1_file = str(tmp_path / "lec_v1.mp4")
    v2_file = str(tmp_path / "lec_v2.mp4")
    with open(v1_file, "w") as f:
        f.write("v1 video stream")
    with open(v2_file, "w") as f:
        f.write("v2 video stream")

    args_v1 = _make_args(v1_file, source_id="cs5903-lec01")
    args_v2 = _make_args(v2_file, source_id="cs5903-lec01")

    # 1. Ingest V1 successfully
    with patch("main.extract_audio", return_value="audio.wav"), \
         patch("main.transcribe", return_value=[TranscriptSegment(0.0, 10.0, "V1 lecture")]), \
         patch("main.extract_keyframes", return_value=[]), \
         patch("main.ocr_keyframes", return_value=[]):
        ingest(args_v1)

    # 2. Confirm V1 is active
    active = active_chunks()
    assert len(active) == 1
    assert active[0]["text"] == "V1 lecture"
    v1_hash = active[0]["content_hash"]

    # 3. Attempt V2 and force extraction failure
    with patch("main.extract_audio", side_effect=RuntimeError("Extraction failed mid-stream")):
        with pytest.raises(RuntimeError):
            ingest(args_v2)

    # 4. Confirm V1 is still active
    active = active_chunks()
    assert len(active) == 1
    assert active[0]["text"] == "V1 lecture"
    assert active[0]["content_hash"] == v1_hash

    # 5. Retry V2 successfully
    with patch("main.extract_audio", return_value="audio.wav"), \
         patch("main.transcribe", return_value=[TranscriptSegment(0.0, 10.0, "V2 lecture")]), \
         patch("main.extract_keyframes", return_value=[]), \
         patch("main.ocr_keyframes", return_value=[]):
        ingest(args_v2)

    # 6. Confirm V2 becomes active
    active = active_chunks()
    assert len(active) == 1
    assert active[0]["text"] == "V2 lecture"

    # 7. Confirm V1 is no longer active
    assert all(c["content_hash"] != v1_hash for c in active)


def test_idempotent_reingest_skip(tmp_path):
    """Re-ingesting the exact same active file should skip extraction."""
    video_file = str(tmp_path / "lec.mp4")
    with open(video_file, "w") as f:
        f.write("video content")

    args = _make_args(video_file, source_id="cs5903-lec01")

    with patch("main.extract_audio", return_value="audio.wav") as mock_extract, \
         patch("main.transcribe", return_value=[TranscriptSegment(0.0, 10.0, "text")]), \
         patch("main.extract_keyframes", return_value=[]), \
         patch("main.ocr_keyframes", return_value=[]):
        ingest(args)
        assert mock_extract.call_count == 1

        # Second call should skip extraction completely
        ingest(args)
        assert mock_extract.call_count == 1


def test_deprecate_edition_excludes_chunks(tmp_path):
    """Deprecating an edition must exclude its chunks from active_chunks."""
    video_file = str(tmp_path / "lec.mp4")
    with open(video_file, "w") as f:
        f.write("video content")

    args = _make_args(video_file, source_id="cs5903-lec01", edition="Fall2025")

    with patch("main.extract_audio", return_value="audio.wav"), \
         patch("main.transcribe", return_value=[TranscriptSegment(0.0, 10.0, "text")]), \
         patch("main.extract_keyframes", return_value=[]), \
         patch("main.ocr_keyframes", return_value=[]):
        ingest(args)

    assert len(active_chunks()) == 1
    deprecate_edition("Fall2025")
    assert len(active_chunks()) == 0
