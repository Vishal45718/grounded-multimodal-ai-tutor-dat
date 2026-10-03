import argparse
import sqlite3
from unittest.mock import patch
import pytest

from config import CONFIG
from ingestion.chunker import (
    EvidenceChunk,
    build_chunks,
    compute_chunk_id,
    split_long_segment,
)
from ingestion.ocr import OcrResult
from ingestion.transcriber import TranscriptSegment
from ingestion.versioning import SourceVersion
from ingestion.video_processor import (
    get_audio_asset_dir,
    get_audio_asset_path,
    get_keyframe_asset_dir,
)
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


def test_evidence_id_is_deterministic():
    """Requirement 1: Rebuilding the same input evidence produces identical IDs,
    with no process randomness."""
    transcript = [
        TranscriptSegment(0.0, 5.0, "deterministic chunk one"),
        TranscriptSegment(5.0, 10.0, "deterministic chunk two"),
    ]
    ocr_results = [
        OcrResult(timestamp_sec=2.5, text="slide title", image_path="/data/keyframes/s1/h1/scene_00001.jpg"),
    ]

    # Run 1
    chunks_run1 = build_chunks("cs5903-lec01", "hash_abc123", transcript, ocr_results)
    ids_run1 = [c.chunk_id for c in chunks_run1]

    # Run 2 (rebuild)
    chunks_run2 = build_chunks("cs5903-lec01", "hash_abc123", transcript, ocr_results)
    ids_run2 = [c.chunk_id for c in chunks_run2]

    assert ids_run1 == ids_run2
    assert len(ids_run1) == 2  # 1 audio (merged 0-10s) + 1 visual

    # Direct helper test
    id1 = compute_chunk_id("cs5903-lec01", "hash_abc123", "audio", 0.0, 10.0, "text")
    id2 = compute_chunk_id("cs5903-lec01", "hash_abc123", "audio", 0.0, 10.0, "text")
    assert id1 == id2


def test_changed_version_or_evidence_produces_different_id():
    """Requirement 1: Changing version identity, modality, time, or content changes the ID."""
    base_id = compute_chunk_id("cs101", "v1", "audio", 0.0, 10.0, "hello world")

    # Changed content/version identity
    assert compute_chunk_id("cs101", "v2", "audio", 0.0, 10.0, "hello world") != base_id
    # Changed source identity
    assert compute_chunk_id("cs102", "v1", "audio", 0.0, 10.0, "hello world") != base_id
    # Changed modality
    assert compute_chunk_id("cs101", "v1", "visual", 0.0, 10.0, "hello world") != base_id
    # Changed start timestamp
    assert compute_chunk_id("cs101", "v1", "audio", 1.0, 10.0, "hello world") != base_id
    # Changed end timestamp
    assert compute_chunk_id("cs101", "v1", "audio", 0.0, 11.0, "hello world") != base_id
    # Changed text
    assert compute_chunk_id("cs101", "v1", "audio", 0.0, 10.0, "different text") != base_id


def test_asset_paths_are_version_isolated():
    """Requirement 2: Different versions of the same video basename produce different asset paths."""
    v1_audio = get_audio_asset_path("lecture.mp4", "cs5903-lec01", "hash_v1")
    v2_audio = get_audio_asset_path("lecture.mp4", "cs5903-lec01", "hash_v2")

    assert v1_audio != v2_audio
    assert "hash_v1" in v1_audio
    assert "hash_v2" in v2_audio
    assert "cs5903-lec01" in v1_audio and "cs5903-lec01" in v2_audio

    v1_keyframes = get_keyframe_asset_dir("cs5903-lec01", "hash_v1")
    v2_keyframes = get_keyframe_asset_dir("cs5903-lec01", "hash_v2")

    assert v1_keyframes != v2_keyframes
    assert "hash_v1" in v1_keyframes
    assert "hash_v2" in v2_keyframes
    assert "cs5903-lec01" in v1_keyframes and "cs5903-lec01" in v2_keyframes


def test_same_version_uses_same_asset_namespace():
    """Requirement 2: Reprocessing the same version resolves to the same asset location."""
    audio_path1 = get_audio_asset_path("lecture.mp4", "cs5903-lec01", "hash_v1")
    audio_path2 = get_audio_asset_path("lecture.mp4", "cs5903-lec01", "hash_v1")
    assert audio_path1 == audio_path2

    keyframe_dir1 = get_keyframe_asset_dir("cs5903-lec01", "hash_v1")
    keyframe_dir2 = get_keyframe_asset_dir("cs5903-lec01", "hash_v1")
    assert keyframe_dir1 == keyframe_dir2


def test_long_transcript_segment_is_split():
    """Requirement 3: A single transcript segment longer than max_chunk_duration_sec is split
    without inventing word-level timestamps, preserving text ordering and avoiding data loss."""
    # 45 second segment with max duration 30.0s
    seg = TranscriptSegment(
        start_sec=0.0,
        end_sec=45.0,
        text="The quick brown fox jumps over the lazy dog repeatedly during this extended lecture excerpt",
    )
    sub_segments = split_long_segment(seg, max_duration=30.0)

    assert len(sub_segments) == 2
    # Verify duration of each sub-segment <= 30.0
    for sub in sub_segments:
        assert (sub.end_sec - sub.start_sec) <= 30.0
        assert sub.end_sec > sub.start_sec  # no zero-length chunks

    # Contiguous bounds
    assert sub_segments[0].start_sec == 0.0
    assert sub_segments[0].end_sec == sub_segments[1].start_sec
    assert sub_segments[-1].end_sec == 45.0

    # Text ordering intact and no text lost
    words_original = seg.text.split()
    words_combined = (sub_segments[0].text + " " + sub_segments[1].text).split()
    assert words_combined == words_original


def test_all_chunks_respect_max_duration():
    """Requirement 3: build_chunks enforces max_chunk_duration_sec across all audio chunks,
    even with segments exceeding 30s."""
    transcript = [
        TranscriptSegment(0.0, 45.0, "A very long introductory segment exceeding thirty seconds limit by fifteen seconds"),
        TranscriptSegment(45.0, 95.0, "Another huge segment that spans fifty full seconds and must be subdivided cleanly"),
        TranscriptSegment(95.0, 100.0, "Short concluding segment"),
    ]
    chunks = build_chunks("cs5903-lec01", "hash1", transcript, ocr_results=[])

    assert len(chunks) > 0
    for c in chunks:
        assert c.modality == "audio"
        duration = c.end_sec - c.start_sec
        assert duration <= CONFIG.max_chunk_duration_sec
        assert duration > 0.0  # no zero-length chunks
        assert len(c.text.strip()) > 0  # no empty text


def test_v1_to_v2_successful_replacement_lifecycle():
    """Requirement 4: Explicit step-by-step verification of V1 -> V2 replacement:
    1. V1 is active.
    2. V2 ingestion completes successfully.
    3. V2 chunks are inserted.
    4. V2 is activated.
    5. V1 becomes stale.
    6. V2 is returned by active_chunks.
    Delayed superseded writes cannot become active.
    """
    v1 = SourceVersion(source_id="cs5903-lec01", content_hash="hash_v1", course_edition="Fall2026", title="Lecture 1")
    v2 = SourceVersion(source_id="cs5903-lec01", content_hash="hash_v2", course_edition="Fall2026", title="Lecture 1")

    chunk_v1 = EvidenceChunk(
        chunk_id="chunk_v1", source_id="cs5903-lec01", content_hash="hash_v1",
        modality="audio", start_sec=0.0, end_sec=10.0, text="V1 content",
    )
    chunk_v2 = EvidenceChunk(
        chunk_id="chunk_v2", source_id="cs5903-lec01", content_hash="hash_v2",
        modality="audio", start_sec=0.0, end_sec=10.0, text="V2 content",
    )
    delayed_v1_chunk = EvidenceChunk(
        chunk_id="chunk_v1_late", source_id="cs5903-lec01", content_hash="hash_v1",
        modality="audio", start_sec=10.0, end_sec=20.0, text="V1 late content",
    )

    # 1. V1 is active
    insert_chunks([chunk_v1])
    upsert_source(v1)
    active = active_chunks()
    assert len(active) == 1
    assert active[0]["chunk_id"] == "chunk_v1"
    assert active[0]["content_hash"] == "hash_v1"

    # 2. V2 ingestion completes & 3. V2 chunks are inserted
    insert_chunks([chunk_v2])
    # Before V2 activation, V1 remains active and V2 is not in active_chunks
    active_before = active_chunks()
    assert len(active_before) == 1
    assert active_before[0]["chunk_id"] == "chunk_v1"

    # 4. V2 is activated
    activated = upsert_source(v2)
    assert activated is True

    # 5. V1 becomes stale (verify in database directly)
    with sqlite3.connect(CONFIG.corpus_db_path) as conn:
        v1_stale = conn.execute("SELECT is_stale FROM chunks WHERE chunk_id = 'chunk_v1'").fetchone()[0]
        v2_stale = conn.execute("SELECT is_stale FROM chunks WHERE chunk_id = 'chunk_v2'").fetchone()[0]
        assert v1_stale == 1
        assert v2_stale == 0

    # 6. V2 is returned by active_chunks()
    active_after = active_chunks()
    assert len(active_after) == 1
    assert active_after[0]["chunk_id"] == "chunk_v2"
    assert active_after[0]["content_hash"] == "hash_v2"

    # Invariant: Delayed superseded write cannot become active
    insert_chunks([delayed_v1_chunk])
    with sqlite3.connect(CONFIG.corpus_db_path) as conn:
        late_stale = conn.execute("SELECT is_stale FROM chunks WHERE chunk_id = 'chunk_v1_late'").fetchone()[0]
        assert late_stale == 1

    active_final = active_chunks()
    assert len(active_final) == 1
    assert active_final[0]["chunk_id"] == "chunk_v2"

