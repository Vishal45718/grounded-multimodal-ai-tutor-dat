"""Smoke and helper unit tests for DAT Tutor M8 Interactive Demo (demo/).

Ensures:
1. demo/helpers.py: Formatting, URL generation, path validation, backend status,
   and memory CRUD wrappers are completely verified offline using tmp_path.
2. demo/app.py: FastAPI routes (index, status, query, memory endpoints, media)
   function properly with zero external API calls.
3. Zero mutation of tracked production databases in data/.
"""
import os
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from config import CONFIG
from storage.corpus_store import init_db
from demo.app import app
from demo.helpers import (
    add_learner_memory_item,
    build_jump_url,
    correct_learner_memory_item,
    delete_learner_memory_item,
    detect_backend_status,
    format_citation_card,
    format_citation_time_bounds,
    format_time_seconds,
    get_learner_memory_data,
    purge_learner_memory_items,
    run_tutor_query,
    validate_media_path,
)


@pytest.fixture
def isolated_corpus_and_memory_db(tmp_path, monkeypatch):
    """Ensure all tests run with isolated temporary SQLite databases."""
    test_corpus = str(tmp_path / "test_corpus.db")
    test_memory = str(tmp_path / "test_memory.db")
    monkeypatch.setattr(CONFIG, "corpus_db_path", test_corpus)
    monkeypatch.setattr(CONFIG, "memory_db_path", test_memory)
    init_db()
    return {"corpus_db": test_corpus, "memory_db": test_memory, "tmp_path": tmp_path}


# ----------------------------------------------------------------------
# 1. Helper Unit Tests: Formatting, URLs & Media Validation
# ----------------------------------------------------------------------

def test_format_time_seconds():
    assert format_time_seconds(None) == "00:00"
    assert format_time_seconds(0.0) == "00:00"
    assert format_time_seconds(59.4) == "00:59"
    assert format_time_seconds(60.0) == "01:00"
    assert format_time_seconds(125.6) == "02:06"
    assert format_time_seconds(3600.0) == "60:00"


def test_format_citation_time_bounds():
    assert format_citation_time_bounds(10.0, 25.0) == "[00:10] - [00:25]"
    assert format_citation_time_bounds(15.0, None) == "[00:15]"
    assert format_citation_time_bounds(None, None, page_number=4) == "Slide Page 4"
    assert format_citation_time_bounds(None, None, page_number=None) == "Unknown"


def test_build_jump_url():
    assert build_jump_url(None, 10.0) is None
    assert build_jump_url("https://example.com/video", None) is None

    # Clean URL without query params
    url1 = build_jump_url("https://youtu.be/abc", 45.2)
    assert url1 == "https://youtu.be/abc?t=45s"

    # URL with existing query param
    url2 = build_jump_url("https://cs50.harvard.edu/x/2024/weeks/1/?v=1", 120.0)
    assert url2 == "https://cs50.harvard.edu/x/2024/weeks/1/?v=1&t=120s"


def test_validate_media_path(tmp_path):
    # Missing / None
    res_none = validate_media_path(None, base_dir=str(tmp_path))
    assert res_none["valid"] is False
    assert res_none["exists"] is False

    # Existing file
    dummy_img = tmp_path / "slide.jpg"
    dummy_img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    res_valid = validate_media_path(str(dummy_img), base_dir=str(tmp_path))
    assert res_valid["valid"] is True
    assert res_valid["exists"] is True
    assert res_valid["error"] is None

    # Non-existent file
    res_missing = validate_media_path("nonexistent.jpg", base_dir=str(tmp_path))
    assert res_missing["valid"] is True
    assert res_missing["exists"] is False
    assert "File not found" in res_missing["error"]

    # Traversal escape
    res_escape = validate_media_path("../../secret.txt", base_dir=str(tmp_path / "sub"))
    assert res_escape["valid"] is False
    assert "escapes" in res_escape["error"]


def test_format_citation_card(tmp_path):
    dummy_img = tmp_path / "slide_test.jpg"
    dummy_img.write_bytes(b"\xff\xd8\xff\xe0")

    raw_citation = {
        "citation_label": "[Evidence 1]",
        "chunk_id": "c_audio_1",
        "source_id": "cs50-lec01",
        "asset_id": "cs50-2024-lec01-video",
        "content_hash": "hash123",
        "edition_id": "2024",
        "modality": "audio",
        "start_sec": 30.0,
        "end_sec": 45.0,
        "page_number": None,
        "source_url": "https://cs50.harvard.edu/x/2024/weeks/1/",
        "image_path": None,
        "text": "printf outputs text to the screen in C.",
    }

    card = format_citation_card(raw_citation, base_dir=str(tmp_path))
    assert card["citation_label"] == "[Evidence 1]"
    assert card["time_bounds_str"] == "[00:30] - [00:45]"
    assert card["jump_url"] == "https://cs50.harvard.edu/x/2024/weeks/1/?t=30s"
    assert card["image_exists"] is False

    # Visual citation
    raw_visual = {
        "citation_label": "[Evidence 2]",
        "chunk_id": "c_vis_1",
        "source_id": "cs50-lec01",
        "modality": "visual",
        "page_number": 5,
        "image_path": str(dummy_img),
        "text": "Memory layout diagram",
    }
    v_card = format_citation_card(raw_visual, base_dir=str(tmp_path))
    assert v_card["time_bounds_str"] == "Slide Page 5"
    assert v_card["image_exists"] is True


def test_detect_backend_status(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    status_offline = detect_backend_status()
    assert status_offline["mode"] == "Mock / Offline"
    assert status_offline["is_live"] is False

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test123")
    status_live = detect_backend_status()
    assert status_live["mode"] == "Live"
    assert status_live["is_live"] is True


# ----------------------------------------------------------------------
# 2. Learner Memory CRUD Unit Tests (Isolated DB)
# ----------------------------------------------------------------------

def test_learner_memory_crud_flow(tmp_path):
    db_file = str(tmp_path / "test_learner_memory.db")
    learner_id = "test_learner_101"

    # 1. Add memory
    added = add_learner_memory_item(
        learner_id=learner_id,
        memory_type="struggle",
        topic="pointers",
        content="Confused about pointer dereferencing with * and &.",
        confidence=0.9,
        db_path=db_file,
    )
    assert added["memory_id"] is not None
    assert added["topic"] == "pointers"

    # 2. Retrieve memories
    data = get_learner_memory_data(learner_id=learner_id, db_path=db_file)
    assert data["total_memories"] == 1
    assert "POINTERS" in data["pedagogical_context"] or "pointers" in data["pedagogical_context"]

    # 3. Correct memory
    mem_id = added["memory_id"]
    corrected = correct_learner_memory_item(
        memory_id=mem_id,
        new_content="Understands & is address-of, still practicing * dereferencing.",
        reason="Learner clarified progress",
        db_path=db_file,
    )
    assert corrected is not None
    assert "address-of" in corrected["content"]

    # 4. Soft delete
    deleted = delete_learner_memory_item(learner_id=learner_id, memory_id=mem_id, db_path=db_file)
    assert deleted is True

    data_after_del = get_learner_memory_data(learner_id=learner_id, db_path=db_file)
    assert data_after_del["total_memories"] == 0

    # 5. Purge
    add_learner_memory_item(learner_id, "goal", "python", "Learn python", db_path=db_file)
    purged_count = purge_learner_memory_items(learner_id=learner_id, db_path=db_file)
    assert purged_count >= 1


# ----------------------------------------------------------------------
# 3. Tutor Query Execution (Mock / Offline Mode)
# ----------------------------------------------------------------------

class MockNode:
    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata

    def get_content(self) -> str:
        return self.text


class MockRetriever:
    def __init__(self, nodes):
        self.nodes = nodes

    def retrieve(self, query: str, fusion: bool = False, top_k: int = 5):
        return self.nodes


def test_run_tutor_query_mock_mode(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_memory.db")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    node = MockNode(
        text="CS50 uses printf for standard output.",
        metadata={
            "chunk_id": "c1",
            "source_id": "cs50-lec01",
            "modality": "audio",
            "start_sec": 10.0,
            "end_sec": 20.0,
            "source_url": "https://cs50.harvard.edu/x/2024/weeks/1/",
        },
    )
    mock_retriever = MockRetriever([node])

    result = run_tutor_query(
        query="What function does CS50 use for standard output?",
        retriever=mock_retriever,
        memory_db_path=db_file,
        base_dir=str(tmp_path),
    )

    assert result["status"] == "Answered"
    assert result["is_abstained"] is False
    assert len(result["citations"]) == 1
    assert result["citations"][0]["chunk_id"] == "c1"
    assert result["citations"][0]["time_bounds_str"] == "[00:10] - [00:20]"


# ----------------------------------------------------------------------
# 4. FastAPI Endpoint Integration Tests (Starlette TestClient)
# ----------------------------------------------------------------------

def test_fastapi_endpoints_smoke(isolated_corpus_and_memory_db):
    client = TestClient(app)

    # 1. Index page
    resp_index = client.get("/")
    assert resp_index.status_code == 200
    assert "DAT Tutor — M8 Interactive Demo" in resp_index.text

    # 2. Status endpoint
    resp_status = client.get("/api/status")
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert "mode" in status_data
    assert "vision_backend" in status_data

    # 3. Memory endpoints (using isolated DB)
    mem_db = isolated_corpus_and_memory_db["memory_db"]

    # Add memory
    resp_add = client.post(
        "/api/memory/add",
        json={
            "learner_id": "fastapi_learner",
            "memory_type": "goal",
            "topic": "recursion",
            "content": "Master base cases in recursive algorithms.",
            "confidence": 0.95,
            "memory_db_path": mem_db,
        },
    )
    assert resp_add.status_code == 200
    item = resp_add.json()
    assert item["topic"] == "recursion"

    # Get memory
    resp_get = client.get(f"/api/memory?learner_id=fastapi_learner&db_path={mem_db}")
    assert resp_get.status_code == 200
    get_data = resp_get.json()
    assert get_data["total_memories"] == 1
    assert "RECURSION" in get_data["pedagogical_context"] or "recursion" in get_data["pedagogical_context"]

    # Correct memory
    resp_corr = client.post(
        "/api/memory/correct",
        json={
            "memory_id": item["memory_id"],
            "new_content": "Understands base case, working on recursive step.",
            "reason": "TestClient update",
            "memory_db_path": mem_db,
        },
    )
    assert resp_corr.status_code == 200
    assert "recursive step" in resp_corr.json()["content"]

    # Delete memory
    resp_del = client.post(
        "/api/memory/delete",
        json={
            "learner_id": "fastapi_learner",
            "memory_id": item["memory_id"],
            "memory_db_path": mem_db,
        },
    )
    assert resp_del.status_code == 200
    assert resp_del.json()["success"] is True

    # Purge memory
    resp_purge = client.post(
        "/api/memory/purge",
        json={
            "learner_id": "fastapi_learner",
            "memory_db_path": mem_db,
        },
    )
    assert resp_purge.status_code == 200


def test_fastapi_media_endpoint(tmp_path, monkeypatch):
    client = TestClient(app)

    # Valid media inside current directory
    img_file = tmp_path / "valid_slide.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 30)

    # Request with existing file
    resp = client.get(f"/media?path={img_file}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"

    # Request with missing file
    resp_missing = client.get("/media?path=missing_slide_never_exists.jpg")
    assert resp_missing.status_code == 404
