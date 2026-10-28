import copy
import json
import sqlite3
import pytest

from config import CONFIG
from ingestion.chunker import build_chunks
from ingestion.manifest import (
    ManifestValidationError,
    SourceAssetRecord,
    build_source_version_from_manifest,
    get_manifest_asset,
    get_manifest_source,
    load_manifest,
    validate_manifest,
)
from ingestion.ocr import OcrResult
from ingestion.transcriber import TranscriptSegment
from ingestion.versioning import SourceVersion
from storage.corpus_store import active_chunks, init_db, insert_chunks, upsert_source


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use an isolated SQLite database for each test."""
    db_file = str(tmp_path / "test_corpus.db")
    monkeypatch.setattr(CONFIG, "corpus_db_path", db_file)
    init_db()
    return db_file


def test_manifest_loads_successfully():
    """Test 1: Manifest loads and validates the real CS50 public instructional sources."""
    records = load_manifest()
    assert len(records) >= 8

    # Verify specific real CS50 assets are loaded
    asset_ids = {r.asset_id for r in records}
    assert "cs50-2024-lec00-video" in asset_ids
    assert "cs50-2024-lec01-video" in asset_ids
    assert "cs50-2023-lec00-video" in asset_ids
    assert "cs50-2023-lec01-video" in asset_ids

    for r in records:
        assert r.source_id.startswith("cs50-lec")
        assert r.edition_id in ("2023", "2024")
        assert r.title
        assert r.source_url.startswith("https://cs50.harvard.edu/x/")
        assert r.original_asset_url.startswith("https://youtu.be/") or r.original_asset_url.startswith("https://www.youtube.com/")
        assert r.modality in ("video", "audio", "multimodal", "text", "visual")
        assert isinstance(r.duration, int) and r.duration > 0
        assert "CC BY-NC-SA 4.0" in r.licence_info.get("name", "")
        assert "David J. Malan" in r.attribution_info.get("author", "")
        assert "Harvard University" in r.attribution_info.get("institution", "")
        assert r.ingestion_status == "cataloged"
        # Content hash must be None when not yet locally downloaded
        assert r.content_hash is None


def test_malformed_manifest_is_rejected():
    """Test 2: Malformed manifest records missing required fields or containing invalid data are rejected."""
    valid_records = [r.to_dict() for r in load_manifest()]
    sample = copy.deepcopy(valid_records[0])

    # 1. Missing required field: source_id
    bad_rec = copy.deepcopy(sample)
    del bad_rec["source_id"]
    with pytest.raises(ManifestValidationError, match="missing required field 'source_id'"):
        validate_manifest([bad_rec])

    # 2. Missing required field: edition_id
    bad_rec = copy.deepcopy(sample)
    del bad_rec["edition_id"]
    with pytest.raises(ManifestValidationError, match="missing required field 'edition_id'"):
        validate_manifest([bad_rec])

    # 3. Missing required field: asset_id
    bad_rec = copy.deepcopy(sample)
    del bad_rec["asset_id"]
    with pytest.raises(ManifestValidationError, match="missing required field 'asset_id'"):
        validate_manifest([bad_rec])

    # 4. Invalid modality
    bad_rec = copy.deepcopy(sample)
    bad_rec["modality"] = "interactive_vr"
    with pytest.raises(ManifestValidationError, match="invalid modality 'interactive_vr'"):
        validate_manifest([bad_rec])

    # 5. Empty source_url
    bad_rec = copy.deepcopy(sample)
    bad_rec["source_url"] = "   "
    with pytest.raises(ManifestValidationError, match="source_url must not be empty"):
        validate_manifest([bad_rec])

    # 6. Placeholder URL: <URL>
    bad_rec = copy.deepcopy(sample)
    bad_rec["source_url"] = "<URL>"
    with pytest.raises(ManifestValidationError, match="placeholder URL detected"):
        validate_manifest([bad_rec])

    # 7. Placeholder URL: example.com
    bad_rec = copy.deepcopy(sample)
    bad_rec["source_url"] = "https://example.com/cs50"
    with pytest.raises(ManifestValidationError, match="placeholder URL detected"):
        validate_manifest([bad_rec])

    # 8. Placeholder URL: TBD
    bad_rec = copy.deepcopy(sample)
    bad_rec["original_asset_url"] = "TBD"
    with pytest.raises(ManifestValidationError, match="placeholder URL detected"):
        validate_manifest([bad_rec])

    # 9. Non-dict, non-list root
    with pytest.raises(ManifestValidationError, match="Manifest root must be a dictionary or list"):
        validate_manifest("invalid_string_root")

    # 10. Dict without sources list
    with pytest.raises(ManifestValidationError, match="Manifest must contain a non-empty 'sources' list"):
        validate_manifest({"invalid_key": "val"})


def test_duplicate_source_version_asset_identity_is_rejected():
    """Test 3: Accidental duplicate source/version/asset identities are rejected."""
    records = [r.to_dict() for r in load_manifest()]

    # Duplicate asset_id
    dup_asset = copy.deepcopy(records)
    dup_record = copy.deepcopy(records[0])
    dup_record["edition_id"] = "2025"  # even with different edition
    dup_asset.append(dup_record)
    with pytest.raises(ManifestValidationError, match="Duplicate asset_id"):
        validate_manifest(dup_asset)

    # Duplicate (source_id, edition_id) identity
    dup_source_edition = copy.deepcopy(records)
    dup_record2 = copy.deepcopy(records[0])
    dup_record2["asset_id"] = "cs50-2024-lec00-alt-asset"
    dup_source_edition.append(dup_record2)
    with pytest.raises(ManifestValidationError, match="Duplicate logical source/edition identity"):
        validate_manifest(dup_source_edition)

    # Duplicate original_asset_url under same edition
    dup_url = copy.deepcopy(records)
    dup_record3 = copy.deepcopy(records[0])
    dup_record3["asset_id"] = "cs50-2024-lec00-duplicate-url"
    dup_record3["source_id"] = "cs50-lec99"
    dup_url.append(dup_record3)
    with pytest.raises(ManifestValidationError, match="Duplicate asset URL"):
        validate_manifest(dup_url)


def test_provenance_fields_preserved_in_ingestion_record():
    """Test 4: Provenance fields (asset_id, source_url) are preserved in SourceVersion,
    EvidenceChunk, and persistent SQLite storage."""
    rec = get_manifest_asset("cs50-2024-lec00-video")
    assert rec is not None
    assert rec.asset_id == "cs50-2024-lec00-video"
    assert rec.source_url == "https://cs50.harvard.edu/x/2024/weeks/0/"

    content_hash = "mock_hash_cs50_2024_lec00"

    # 1. SourceVersion created from manifest preserves provenance
    version = build_source_version_from_manifest(rec, content_hash)
    assert version.source_id == rec.source_id
    assert version.content_hash == content_hash
    assert version.course_edition == rec.edition_id
    assert version.title == rec.title
    assert version.asset_id == "cs50-2024-lec00-video"
    assert version.source_url == "https://cs50.harvard.edu/x/2024/weeks/0/"

    # 2. Evidence chunks built with provenance preserve fields
    transcript = [
        TranscriptSegment(start_sec=0.0, end_sec=5.0, text="Welcome to CS50."),
        TranscriptSegment(start_sec=5.0, end_sec=10.0, text="This is Scratch."),
    ]
    ocr_results = [
        OcrResult(timestamp_sec=2.5, image_path="/data/frames/cs50-2024-lec00-video/0.jpg", text="CS50 Week 0: Scratch"),
    ]

    chunks = build_chunks(
        source_id=rec.source_id,
        content_hash=content_hash,
        transcript=transcript,
        ocr_results=ocr_results,
        asset_id=rec.asset_id,
        source_url=rec.source_url,
    )
    assert len(chunks) == 2  # 1 audio chunk (combined 10s) + 1 visual chunk
    for c in chunks:
        assert c.asset_id == "cs50-2024-lec00-video"
        assert c.source_url == "https://cs50.harvard.edu/x/2024/weeks/0/"

    # 3. Store in database
    upsert_source(version)
    insert_chunks(chunks)

    # 4. Check SQLite direct row storage
    with sqlite3.connect(CONFIG.corpus_db_path) as conn:
        conn.row_factory = sqlite3.Row
        s_row = conn.execute("SELECT * FROM sources WHERE source_id = ?", (rec.source_id,)).fetchone()
        assert s_row["asset_id"] == "cs50-2024-lec00-video"
        assert s_row["source_url"] == "https://cs50.harvard.edu/x/2024/weeks/0/"

        c_rows = conn.execute("SELECT * FROM chunks WHERE source_id = ?", (rec.source_id,)).fetchall()
        assert len(c_rows) == 2
        for r in c_rows:
            assert r["asset_id"] == "cs50-2024-lec00-video"
            assert r["source_url"] == "https://cs50.harvard.edu/x/2024/weeks/0/"

    # 5. Check active_chunks() serves provenance to downstream components
    active = active_chunks()
    assert len(active) == 2
    for ac in active:
        assert ac["asset_id"] == "cs50-2024-lec00-video"
        assert ac["source_url"] == "https://cs50.harvard.edu/x/2024/weeks/0/"


def test_two_editions_of_same_lecture_distinguishable():
    """Test 5: Two editions of the same logical lecture remain distinguishable."""
    rec_2024 = get_manifest_asset("cs50-2024-lec00-video")
    rec_2023 = get_manifest_asset("cs50-2023-lec00-video")

    assert rec_2024 is not None
    assert rec_2023 is not None

    # Both represent the logical lecture "cs50-lec00" (Week 0)
    assert rec_2024.source_id == "cs50-lec00"
    assert rec_2023.source_id == "cs50-lec00"

    # Distinct edition IDs
    assert rec_2024.edition_id == "2024"
    assert rec_2023.edition_id == "2023"

    # Distinct asset IDs
    assert rec_2024.asset_id == "cs50-2024-lec00-video"
    assert rec_2023.asset_id == "cs50-2023-lec00-video"

    # Distinct course website URLs
    assert rec_2024.source_url == "https://cs50.harvard.edu/x/2024/weeks/0/"
    assert rec_2023.source_url == "https://cs50.harvard.edu/x/2023/weeks/0/"

    # Distinct original media asset URLs
    assert rec_2024.original_asset_url == "https://youtu.be/3LPJfIKxwWc"
    assert rec_2023.original_asset_url == "https://youtu.be/IDDmrzzB14M"

    # Distinct verified durations
    assert rec_2024.duration == 7543
    assert rec_2023.duration == 7217

    # Distinct provenance notes
    assert "2024" in rec_2024.notes
    assert "2023" in rec_2023.notes

    # Retrieval via get_manifest_source resolves each edition unambiguously
    resolved_2024 = get_manifest_source("cs50-lec00", edition_id="2024")
    resolved_2023 = get_manifest_source("cs50-lec00", edition_id="2023")
    assert resolved_2024.asset_id == "cs50-2024-lec00-video"
    assert resolved_2023.asset_id == "cs50-2023-lec00-video"


def test_cli_ingest_resolves_manifest_metadata(tmp_path):
    """Test CLI auto-resolves title, course_edition, source_id, asset_id, source_url from manifest."""
    import argparse
    from unittest.mock import patch
    from main import ingest

    video_file = str(tmp_path / "scratch_lecture.mp4")
    with open(video_file, "w") as f:
        f.write("mock video data for cs50 2024 lecture 0")

    args = argparse.Namespace(
        video=video_file,
        asset_id="cs50-2024-lec00-video",
        source_id=None,
        title=None,
        course_edition=None,
        manifest=None,
    )

    with patch("main.extract_audio", return_value="dummy.wav"), \
         patch("main.transcribe", return_value=[TranscriptSegment(start_sec=0.0, end_sec=5.0, text="Intro to Scratch")]), \
         patch("main.extract_keyframes", return_value=[]), \
         patch("main.ocr_keyframes", return_value=[]):
        ingest(args)

    with sqlite3.connect(CONFIG.corpus_db_path) as conn:
        conn.row_factory = sqlite3.Row
        s_row = conn.execute("SELECT * FROM sources WHERE source_id = 'cs50-lec00'").fetchone()
        assert s_row is not None
        assert s_row["course_edition"] == "2024"
        assert s_row["title"] == "Lecture 0: Scratch"
        assert s_row["asset_id"] == "cs50-2024-lec00-video"
        assert s_row["source_url"] == "https://cs50.harvard.edu/x/2024/weeks/0/"

        c_rows = conn.execute("SELECT * FROM chunks WHERE source_id = 'cs50-lec00'").fetchall()
        assert len(c_rows) >= 1
        assert c_rows[0]["asset_id"] == "cs50-2024-lec00-video"
        assert c_rows[0]["source_url"] == "https://cs50.harvard.edu/x/2024/weeks/0/"

