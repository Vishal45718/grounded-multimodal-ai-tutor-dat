"""Unit tests for modality evaluation, perturbation checks, and evidence alignment (M4 Phase 3)."""
import json
import os
import pytest

from benchmark.evaluate_modalities import (
    VISUAL_CASE_IDS,
    MockRetrievalNode,
    TargetedRetriever,
    check_answer_correctness,
    create_intelligent_mock_vision_adapter,
    run_modality_evaluation,
    run_perturbation_evaluation,
)
from generation.answer import generate_grounded_answer
from generation.vqa import VisualPayload
from storage.corpus_store import active_chunks


def _create_dummy_jpeg(path: str) -> str:
    """Create a minimal valid JPEG image on disk."""
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


def test_evidence_alignment_report_schema_and_completeness():
    """Verify evidence_alignment_report.json exists, covers all 20 cases, and contains required fields."""
    report_path = "benchmark/evidence_alignment_report.json"
    assert os.path.exists(report_path), "benchmark/evidence_alignment_report.json must exist"

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    assert len(report) == 20, "Alignment report must cover all 20 benchmark cases"

    required_keys = {
        "case_id", "question", "category", "answerability",
        "visual_required", "previous_expected_evidence_ids",
        "proposed_current_evidence_ids", "source_version_info",
        "verification_status", "explanation"
    }

    chunks = active_chunks()
    active_chunk_ids = {c["chunk_id"] for c in chunks}

    for item in report:
        missing = required_keys - set(item.keys())
        assert not missing, f"Report item {item.get('case_id')} missing keys: {missing}"
        assert item["verification_status"] == "verified"

        # If answerable, all proposed IDs must exist in active chunks
        if item["answerability"] in ["answerable", "partial"]:
            assert len(item["proposed_current_evidence_ids"]) > 0
            for eid in item["proposed_current_evidence_ids"]:
                assert eid in active_chunk_ids, f"Proposed ID {eid} for {item['case_id']} not active"
        else:
            assert len(item["proposed_current_evidence_ids"]) == 0


def test_transcript_only_condition_abstains_on_visual_question(tmp_path):
    """Transcript-only evidence must abstain when visual evidence is mandated."""
    node = MockRetrievalNode(
        text="The instructor talks about writing hello world in C.",
        metadata={
            "chunk_id": "audio_chunk_1",
            "source_id": "cs50-lec01",
            "asset_id": "cs50-2024-lec01-video",
            "modality": "audio",
            "start_sec": 100.0,
            "end_sec": 130.0,
        },
    )
    retriever = TargetedRetriever({})
    retriever.set_override_nodes([node])

    mock_vision = create_intelligent_mock_vision_adapter()

    answer, citations = generate_grounded_answer(
        query="In the first C code example for 'hello, world', which keyword is highlighted in purple?",
        retriever=retriever,
        vision_model=mock_vision,
        visual_required=True,
    )

    assert "abstain" in answer.lower()
    assert citations == []


def test_ocr_only_condition_without_image_payload_abstains(tmp_path):
    """OCR text alone without image payload must abstain when visual evidence is mandated."""
    node = MockRetrievalNode(
        text='#include <stdio.h>\nint main(void)\n{\n    printf("hello, world\\n");\n}',
        metadata={
            "chunk_id": "visual_chunk_1",
            "source_id": "cs50-lec01",
            "asset_id": "cs50-2024-lec01-slides",
            "modality": "visual",
            "page_number": 11,
            "image_path": None,  # No image supplied
        },
    )
    retriever = TargetedRetriever({})
    retriever.set_override_nodes([node])

    mock_vision = create_intelligent_mock_vision_adapter()

    answer, citations = generate_grounded_answer(
        query="In the first C code example for 'hello, world', which keyword is highlighted in purple?",
        retriever=retriever,
        vision_model=mock_vision,
        visual_required=True,
    )

    assert "abstain" in answer.lower()
    assert citations == []


def test_visual_input_condition_succeeds_with_valid_image(tmp_path):
    """Providing the actual slide JPEG image produces a grounded answer citing the evidence."""
    img_path = str(tmp_path / "slide_00011.jpg")
    _create_dummy_jpeg(img_path)

    node = MockRetrievalNode(
        text='#include <stdio.h>\nint main(void)\n{\n    printf("hello, world\\n");\n}',
        metadata={
            "chunk_id": "26e6a09bdeb383a528ef7a4709ebd707",
            "source_id": "cs50-lec01",
            "asset_id": "cs50-2024-lec01-slides",
            "modality": "visual",
            "page_number": 11,
            "image_path": img_path,
        },
    )
    retriever = TargetedRetriever({})
    retriever.set_override_nodes([node])

    mock_vision = create_intelligent_mock_vision_adapter()

    answer, citations = generate_grounded_answer(
        query="In the first C code example for 'hello, world', which keyword is highlighted in purple?",
        retriever=retriever,
        vision_model=mock_vision,
        visual_required=True,
    )

    assert "printf" in answer
    assert "purple" in answer
    assert len(citations) == 1
    assert citations[0]["citation_label"] == "[Evidence 1]"
    assert citations[0]["chunk_id"] == "26e6a09bdeb383a528ef7a4709ebd707"


def test_image_swap_perturbation_prevents_silent_acceptance(tmp_path):
    """Swapping the required slide with an unrelated slide prevents false grounding."""
    # Create an unrelated slide (Slide 193: binary 1s)
    swapped_img = str(tmp_path / "slide_00193.jpg")
    _create_dummy_jpeg(swapped_img)

    node = MockRetrievalNode(
        text='#include <stdio.h>\nint main(void)\n{\n    printf("hello, world\\n");\n}',
        metadata={
            "chunk_id": "26e6a09bdeb383a528ef7a4709ebd707",
            "source_id": "cs50-lec01",
            "asset_id": "cs50-2024-lec01-slides",
            "modality": "visual",
            "page_number": 193,  # Swapped slide page
            "image_path": swapped_img,
        },
    )
    retriever = TargetedRetriever({})
    retriever.set_override_nodes([node])

    mock_vision = create_intelligent_mock_vision_adapter()

    answer, citations = generate_grounded_answer(
        query="In the first C code example for 'hello, world', which keyword is highlighted in purple?",
        retriever=retriever,
        vision_model=mock_vision,
        visual_required=True,
    )

    # The adapter reports that the image is unrelated and cannot answer the question
    status, explanation = check_answer_correctness("cs50-2024-lec01-vis-01", answer, "swapped_image")
    assert status == "abstained" or status == "incorrect"
    assert status != "correct", "Swapped image must not be silently accepted as correct"


def test_missing_image_perturbation_causes_safe_abstention():
    """An image path pointing to a non-existent file causes safe abstention."""
    node = MockRetrievalNode(
        text='#include <stdio.h>\nint main(void)\n{\n    printf("hello, world\\n");\n}',
        metadata={
            "chunk_id": "26e6a09bdeb383a528ef7a4709ebd707",
            "source_id": "cs50-lec01",
            "asset_id": "cs50-2024-lec01-slides",
            "modality": "visual",
            "page_number": 11,
            "image_path": "data/keyframes/cs50-lec01/nonexistent.jpg",
        },
    )
    retriever = TargetedRetriever({})
    retriever.set_override_nodes([node])

    mock_vision = create_intelligent_mock_vision_adapter()

    answer, citations = generate_grounded_answer(
        query="In the first C code example for 'hello, world', which keyword is highlighted in purple?",
        retriever=retriever,
        vision_model=mock_vision,
        visual_required=True,
    )

    assert "abstain" in answer.lower()
    assert citations == []
