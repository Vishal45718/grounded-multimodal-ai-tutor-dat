"""Offline unit tests for modality isolation and image-perturbation harness (M4).

Covers 6 conditions matching benchmark modality evaluation:
1. Transcript-only condition -> visual question safely abstains.
2. OCR-text-only condition -> transcript-insufficient question safely abstains.
3. Actual visual input condition -> returns expected grounded answer.
4. Correct image condition -> accepted with evidence citation.
5. Image-removal perturbation -> rejected / safely abstained.
6. Image-swap perturbation -> rejected as visually unsupported.
"""
import os
import pytest
from PIL import Image

from generation.vqa import (
    MockVisionAdapter,
    ABSTAIN_VISUAL_MISSING,
    ABSTAIN_VISUAL_UNSUPPORTED,
)
from generation.answer import generate_grounded_answer


class MockNode:
    def __init__(self, text, metadata):
        self.text = text
        self.metadata = metadata

    def get_content(self):
        return self.text


class FixedRetriever:
    def __init__(self, nodes):
        self.nodes = nodes

    def retrieve(self, query, fusion=True):
        return self.nodes


@pytest.fixture
def slide_assets(tmp_path):
    correct_img = tmp_path / "correct_diagram.jpg"
    swapped_img = tmp_path / "swapped_diagram.jpg"

    im1 = Image.new("RGB", (120, 120), color="blue")
    im1.save(str(correct_img))

    im2 = Image.new("RGB", (120, 120), color="red")
    im2.save(str(swapped_img))

    return str(correct_img), str(swapped_img)


def test_condition_1_transcript_only_abstains():
    node = MockNode("The professor speaks about functions in C without mentioning the slide number.", {
        "source_id": "cs50-lec01",
        "modality": "audio",
        "chunk_id": "chunk_audio_01",
        "start_sec": 100.0,
        "end_sec": 120.0,
    })
    retriever = FixedRetriever([node])
    adapter = MockVisionAdapter()

    # Visual-required question with only transcript in retriever
    ans, _ = generate_grounded_answer(
        "What exact hexadecimal overflow value is shown on the slide diagram?",
        retriever,
        vision_adapter=adapter,
        require_visual=True,
    )
    assert ans == ABSTAIN_VISUAL_MISSING


def test_condition_2_ocr_text_only_abstains():
    # Only OCR text available, no valid image on disk
    node = MockNode("Some ambiguous text snippet without diagram layout", {
        "source_id": "cs50-lec01",
        "modality": "visual",
        "chunk_id": "chunk_ocr_01",
        "page_number": 5,
        "image_path": None,  # image file missing
    })
    retriever = FixedRetriever([node])
    adapter = MockVisionAdapter()

    ans, _ = generate_grounded_answer(
        "What is the spatial relationship between the input and output boxes in the diagram?",
        retriever,
        vision_adapter=adapter,
        require_visual=True,
    )
    assert ans == ABSTAIN_VISUAL_MISSING


def test_condition_3_actual_visual_input(slide_assets):
    correct_img, _ = slide_assets
    node = MockNode("Slide 12: Compilation pipeline", {
        "source_id": "cs50-lec01",
        "modality": "visual",
        "chunk_id": "chunk_vis_12",
        "page_number": 12,
        "image_path": correct_img,
    })
    retriever = FixedRetriever([node])
    adapter = MockVisionAdapter(
        canned_answers={"compilation": "The diagram displays source code -> clang -> assembly [Evidence 1]"}
    )

    ans, citations = generate_grounded_answer(
        "Explain the compilation stages in the slide diagram",
        retriever,
        vision_adapter=adapter,
    )
    assert "clang" in ans
    assert "[Evidence 1]" in ans
    assert citations[0]["page_number"] == 12


def test_condition_4_correct_image_accepted(slide_assets):
    correct_img, _ = slide_assets
    adapter = MockVisionAdapter()
    ans = adapter.generate("Explain the slide layout", [correct_img])
    assert ans != ABSTAIN_VISUAL_MISSING
    assert ans != ABSTAIN_VISUAL_UNSUPPORTED
    assert len(adapter.last_payload_bytes) == 1


def test_condition_5_image_removed_perturbation(tmp_path):
    deleted_path = str(tmp_path / "deleted_frame.jpg")
    adapter = MockVisionAdapter()
    ans = adapter.generate("What is on this slide?", [deleted_path])
    assert ans == ABSTAIN_VISUAL_MISSING


def test_condition_6_image_swapped_perturbation(slide_assets):
    _, swapped_img = slide_assets
    adapter = MockVisionAdapter()
    ans = adapter.generate("Confirm the binary search diagram", [swapped_img])
    assert ans == ABSTAIN_VISUAL_UNSUPPORTED
