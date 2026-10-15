import os
import pytest
from unittest.mock import MagicMock, patch

from config import CONFIG
from generation.answer import generate_grounded_answer
from generation.vqa import (
    BaseVisionAdapter,
    MockVisionAdapter,
    VisualPayload,
    load_and_validate_image,
)
from scripts.ingest_official import resolve_citation
from storage.corpus_store import init_db, insert_chunks, upsert_source
from ingestion.chunker import EvidenceChunk


class MockNode:
    """Mock retrieved evidence node."""
    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata

    def get_content(self) -> str:
        return self.text


class MockRetriever:
    """Mock retriever returning a fixed list of nodes."""
    def __init__(self, nodes: list):
        self.nodes = nodes

    def retrieve(self, query: str, fusion: bool = False, top_k: int = 5):
        return self.nodes


def _create_dummy_jpeg(path: str) -> str:
    """Create a minimal valid JPEG image on disk."""
    # Smallest valid 1x1 JPEG bytes
    jpeg_bytes = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    )
    with open(path, "wb") as f:
        f.write(jpeg_bytes)
    return path


def test_visual_question_sends_actual_image_payload(tmp_path):
    """Test 1: A visual question sends the actual image payload to the vision-model adapter."""
    img_file = str(tmp_path / "slide_00011.jpg")
    _create_dummy_jpeg(img_file)

    node = MockNode(
        text='#include <stdio.h>\nprintf("hello, world");',
        metadata={
            "chunk_id": "chunk_vis_01",
            "source_id": "cs50-lec01",
            "asset_id": "cs50-2024-lec01-video",
            "modality": "visual",
            "image_path": img_file,
            "page_number": 11,
            "start_sec": None,
            "end_sec": None,
        },
    )
    retriever = MockRetriever([node])

    mock_vision = MockVisionAdapter(
        response_text="printf is highlighted in purple [Evidence 1]."
    )

    answer, citations = generate_grounded_answer(
        query="Which keyword is purple?",
        retriever=retriever,
        vision_model=mock_vision,
    )

    # Verify adapter was called with real image payload
    assert mock_vision.call_count == 1
    assert len(mock_vision.last_images) == 1
    payload = mock_vision.last_images[0]
    assert payload.label == "[Evidence 1]"
    assert payload.image_path == img_file
    assert payload.image_bytes == open(img_file, "rb").read()
    assert payload.page_number == 11

    # Verify citation
    assert len(citations) == 1
    assert citations[0]["citation_label"] == "[Evidence 1]"
    assert citations[0]["chunk_id"] == "chunk_vis_01"
    assert citations[0]["image_path"] == img_file


def test_ocr_text_alone_not_treated_as_visual_understanding_when_visual_required(tmp_path):
    """Test 2: OCR text alone does not suffice when visual evidence is required."""
    missing_img = str(tmp_path / "missing_slide.jpg")
    node = MockNode(
        text='printf("hello, world");',
        metadata={
            "chunk_id": "chunk_ocr_only",
            "source_id": "cs50-lec01",
            "modality": "visual",
            "image_path": missing_img,
            "page_number": 11,
        },
    )
    retriever = MockRetriever([node])

    mock_vision = MockVisionAdapter(response_text="printf is purple [Evidence 1].")

    answer, citations = generate_grounded_answer(
        query="Which keyword is highlighted in purple?",
        retriever=retriever,
        vision_model=mock_vision,
        visual_required=True,
    )

    # Must abstain because real image is missing, despite OCR text being available
    assert answer.startswith("I abstain")
    assert "missing" in answer.lower()
    assert citations == []
    assert mock_vision.call_count == 0


def test_answer_cites_correct_evidence_id_and_asset_metadata(tmp_path):
    """Test 3: The answer cites the correct evidence ID and preserves asset provenance metadata."""
    img_file = str(tmp_path / "slide_00015.jpg")
    _create_dummy_jpeg(img_file)

    node = MockNode(
        text="Input -> [ ] -> Output",
        metadata={
            "chunk_id": "3d5dc8044490f63ea809f8790a713a71",
            "source_id": "cs50-lec01",
            "asset_id": "cs50-2024-lec01-video",
            "content_hash": "44469ebd8de3e045",
            "course_edition": "2024",
            "modality": "visual",
            "image_path": img_file,
            "page_number": 15,
            "start_sec": None,
            "end_sec": None,
            "source_url": "https://cs50.harvard.edu/x/2024/weeks/1/",
        },
    )
    retriever = MockRetriever([node])

    mock_vision = MockVisionAdapter(
        response_text="The central box is empty [Evidence 1]."
    )

    answer, citations = generate_grounded_answer(
        query="What is written inside the central box?",
        retriever=retriever,
        vision_model=mock_vision,
    )

    assert len(citations) == 1
    c = citations[0]
    assert c["citation_label"] == "[Evidence 1]"
    assert c["chunk_id"] == "3d5dc8044490f63ea809f8790a713a71"
    assert c["source_id"] == "cs50-lec01"
    assert c["asset_id"] == "cs50-2024-lec01-video"
    assert c["content_hash"] == "44469ebd8de3e045"
    assert c["course_edition"] == "2024"
    assert c["page_number"] == 15
    assert c["image_path"] == img_file
    assert c["start_sec"] is None
    assert c["end_sec"] is None
    assert c["source_url"] == "https://cs50.harvard.edu/x/2024/weeks/1/"


def test_missing_required_image_causes_abstention(tmp_path):
    """Test 4: A required image that is missing causes explicit abstention."""
    node = MockNode(
        text="Visual slide text",
        metadata={
            "chunk_id": "c1",
            "source_id": "cs50-lec01",
            "modality": "visual",
            "image_path": str(tmp_path / "absent.jpg"),
        },
    )
    retriever = MockRetriever([node])

    answer, citations = generate_grounded_answer(
        query="Describe the slide",
        retriever=retriever,
        visual_required=True,
    )

    assert answer.startswith("I abstain")
    assert citations == []


def test_unavailable_vision_backend_causes_safe_failure_when_visual_required(tmp_path, monkeypatch):
    """Test 5: An unavailable vision backend causes safe abstention when visual evidence is mandatory."""
    img_file = str(tmp_path / "valid.jpg")
    _create_dummy_jpeg(img_file)

    node = MockNode(
        text="Visual content",
        metadata={
            "chunk_id": "c1",
            "source_id": "cs50-lec01",
            "modality": "visual",
            "image_path": img_file,
        },
    )
    retriever = MockRetriever([node])

    # Unset API keys so adapter is unavailable
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    answer, citations = generate_grounded_answer(
        query="What is depicted?",
        retriever=retriever,
        vision_model=None,
        visual_required=True,
    )

    assert answer.startswith("I abstain")
    assert "no vision model is available" in answer.lower()
    assert citations == []


def test_unknown_citation_labels_rejected(tmp_path):
    """Test 6: Unknown citation labels are rejected and excluded from citations list."""
    img_file = str(tmp_path / "slide.jpg")
    _create_dummy_jpeg(img_file)

    node1 = MockNode("Content 1", {"chunk_id": "c1", "source_id": "s1", "modality": "visual", "image_path": img_file})
    node2 = MockNode("Content 2", {"chunk_id": "c2", "source_id": "s1", "modality": "audio"})
    retriever = MockRetriever([node1, node2])

    # Model hallucinated [Evidence 99] and [Evidence 5]
    mock_vision = MockVisionAdapter(
        response_text="Fact from [Evidence 1] and invalid [Evidence 99] and [Evidence 5]."
    )

    answer, citations = generate_grounded_answer(
        query="Test query",
        retriever=retriever,
        vision_model=mock_vision,
    )

    # Only [Evidence 1] is valid; [Evidence 99] and [Evidence 5] are rejected
    assert len(citations) == 1
    assert citations[0]["citation_label"] == "[Evidence 1]"
    assert citations[0]["chunk_id"] == "c1"


def test_pdf_citations_retain_unknown_time_bounds(tmp_path, capsys):
    """Test 7: PDF citations retain unknown video time bounds rather than inventing timestamps."""
    init_db()
    img_file = str(tmp_path / "slide_00019.jpg")
    _create_dummy_jpeg(img_file)

    node = MockNode(
        text="Compiler block diagram",
        metadata={
            "chunk_id": "chunk_pdf_diag",
            "source_id": "cs50-lec01",
            "modality": "visual",
            "image_path": img_file,
            "page_number": 19,
            "start_sec": None,
            "end_sec": None,
            "source_url": "https://cs50.harvard.edu/x/2024/weeks/1/",
        },
    )
    retriever = MockRetriever([node])

    mock_vision = MockVisionAdapter(
        response_text="Compiler is positioned inside the central box [Evidence 1]."
    )

    answer, citations = generate_grounded_answer(
        query="Where is compiler positioned?",
        retriever=retriever,
        vision_model=mock_vision,
    )

    assert len(citations) == 1
    assert citations[0]["start_sec"] is None
    assert citations[0]["end_sec"] is None

    # Insert into database and verify resolve_citation
    chunk = EvidenceChunk(
        chunk_id=citations[0]["chunk_id"],
        source_id=citations[0]["source_id"],
        content_hash="testhash",
        modality="visual",
        start_sec=None,
        end_sec=None,
        text=node.text,
        image_path=img_file,
        page_number=19,
    )
    insert_chunks([chunk])
    resolve_citation(chunk.chunk_id)

    captured = capsys.readouterr()
    assert "Time Bounds: Unknown" in captured.out
    assert "Video Nav:" not in captured.out
    assert "Visual Nav:  " in captured.out


def test_existing_text_only_queries_still_work():
    """Test 8: Existing text-only queries continue to work through the text LLM."""
    node = MockNode(
        text="A compiler converts source code into machine code.",
        metadata={
            "chunk_id": "chunk_audio_01",
            "source_id": "cs50-lec01",
            "modality": "audio",
            "start_sec": 300.0,
            "end_sec": 320.0,
        },
    )
    retriever = MockRetriever([node])

    mock_text_llm = MagicMock()
    mock_text_llm.complete.return_value = MagicMock(
        text="A compiler translates source code into machine code [Evidence 1]."
    )

    answer, citations = generate_grounded_answer(
        query="What is a compiler?",
        retriever=retriever,
        llm=mock_text_llm,
    )

    assert mock_text_llm.complete.called
    assert "A compiler translates" in answer
    assert len(citations) == 1
    assert citations[0]["citation_label"] == "[Evidence 1]"
    assert citations[0]["modality"] == "audio"
    assert citations[0]["start_sec"] == 300.0
    assert citations[0]["end_sec"] == 320.0


def test_max_images_limit_respected(tmp_path):
    """Test 9: The number of images passed to the vision model is capped by max_images."""
    nodes = []
    for i in range(7):
        p = str(tmp_path / f"slide_{i+1:05d}.jpg")
        _create_dummy_jpeg(p)
        nodes.append(
            MockNode(
                f"Slide {i+1}",
                {"chunk_id": f"c_{i+1}", "source_id": "s1", "modality": "visual", "image_path": p},
            )
        )

    retriever = MockRetriever(nodes)
    mock_vision = MockVisionAdapter(response_text="Summary [Evidence 1].")

    generate_grounded_answer(
        query="Analyze these slides",
        retriever=retriever,
        vision_model=mock_vision,
        max_images=3,
    )

    assert mock_vision.call_count == 1
    # Only 3 images should have been sent despite 7 visual nodes
    assert len(mock_vision.last_images) == 3


def test_vision_model_runtime_error_handled_gracefully(tmp_path):
    """Test 10: Vision model runtime errors are handled gracefully without fabricating answers."""
    img_file = str(tmp_path / "slide.jpg")
    _create_dummy_jpeg(img_file)

    node = MockNode("Slide", {"chunk_id": "c1", "source_id": "s1", "modality": "visual", "image_path": img_file})
    retriever = MockRetriever([node])

    mock_vision = MockVisionAdapter(side_effect=RuntimeError("QuotaExceeded"))

    answer, citations = generate_grounded_answer(
        query="Analyze",
        retriever=retriever,
        vision_model=mock_vision,
        visual_required=True,
    )

    assert answer.startswith("I abstain")
    assert "RuntimeError" in answer
    assert citations == []


def test_only_actually_cited_evidence_returned(tmp_path):
    """Test 11: Only citations that genuinely appear in the answer text are returned."""
    node1 = MockNode("Irrelevant audio chunk", {"chunk_id": "c1", "source_id": "s1", "modality": "audio"})
    node2 = MockNode("Relevant audio chunk", {"chunk_id": "c2", "source_id": "s1", "modality": "audio"})
    node3 = MockNode("Third audio chunk", {"chunk_id": "c3", "source_id": "s1", "modality": "audio"})
    retriever = MockRetriever([node1, node2, node3])

    # Model only cites [Evidence 2]
    mock_llm = MagicMock()
    mock_llm.complete.return_value = MagicMock(
        text="The answer is found exclusively in [Evidence 2]."
    )

    answer, citations = generate_grounded_answer(
        query="Specific question",
        retriever=retriever,
        llm=mock_llm,
    )

    assert len(citations) == 1
    assert citations[0]["citation_label"] == "[Evidence 2]"
    assert citations[0]["chunk_id"] == "c2"


def test_stale_evidence_excluded_from_citations():
    """Test 12: Superseded / stale evidence chunks are excluded from citations."""
    stale_node = MockNode("Old version content", {"chunk_id": "c_stale", "source_id": "s1", "modality": "audio", "is_stale": 1})
    active_node = MockNode("Active version content", {"chunk_id": "c_active", "source_id": "s1", "modality": "audio", "is_stale": 0})
    retriever = MockRetriever([stale_node, active_node])

    mock_llm = MagicMock()
    mock_llm.complete.return_value = MagicMock(
        text="Cited both [Evidence 1] and [Evidence 2]."
    )

    answer, citations = generate_grounded_answer(
        query="Question",
        retriever=retriever,
        llm=mock_llm,
    )

    # [Evidence 1] is stale, so only [Evidence 2] should be returned in citations
    assert len(citations) == 1
    assert citations[0]["citation_label"] == "[Evidence 2]"
    assert citations[0]["chunk_id"] == "c_active"
