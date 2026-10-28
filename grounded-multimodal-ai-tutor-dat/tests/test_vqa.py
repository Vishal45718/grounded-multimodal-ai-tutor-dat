"""Offline automated unit tests for Multimodal Visual Question Answering (VQA) in M4.

Covers:
1. Mock vision adapter payload delivery (verifies actual byte loading).
2. Safe abstention when required visual evidence is missing.
3. Safe abstention when visual evidence list is empty.
4. Enforcement of max_images budget constraint.
5. Grounded citation emission matching visual slide evidence.
6. Image perturbation: image removal triggers safe abstention.
7. Image perturbation: image swap triggers unsupported / contradictory refusal.
8. Custom callable vision adapter execution.
9. Multiple visual evidence chunks handling.
10. Fallback when text-only retriever results are provided.
11. Provenance preservation in multimodal citation records.
12. Validation of non-empty image bytes on disk.
"""
import os
import pytest
from PIL import Image

from generation.vqa import (
    BaseVisionAdapter,
    MockVisionAdapter,
    CallableVisionAdapter,
    create_vision_adapter,
    ABSTAIN_VISUAL_MISSING,
    ABSTAIN_VISUAL_UNSUPPORTED,
)
from generation.answer import generate_grounded_answer


@pytest.fixture
def sample_images(tmp_path):
    img1 = tmp_path / "slide_00001.jpg"
    img2 = tmp_path / "slide_00002.jpg"
    swapped = tmp_path / "slide_swapped.jpg"

    # Create real image files
    im1 = Image.new("RGB", (100, 100), color="blue")
    im1.save(str(img1))

    im2 = Image.new("RGB", (100, 100), color="red")
    im2.save(str(img2))

    im_s = Image.new("RGB", (100, 100), color="yellow")
    im_s.save(str(swapped))

    return str(img1), str(img2), str(swapped)


class DummyNode:
    def __init__(self, text, metadata):
        self.text = text
        self.metadata = metadata

    def get_content(self):
        return self.text


class DummyRetriever:
    def __init__(self, nodes):
        self.nodes = nodes

    def retrieve(self, query, fusion=True):
        return self.nodes


def test_mock_adapter_loads_actual_image_bytes(sample_images):
    img1, _, _ = sample_images
    adapter = MockVisionAdapter()
    ans = adapter.generate("What color is this slide?", [img1])
    assert len(adapter.last_payload_bytes) == 1
    assert len(adapter.last_payload_bytes[0]) > 0
    assert "[Evidence 1]" in ans


def test_missing_image_file_triggers_abstention(tmp_path):
    missing_path = str(tmp_path / "non_existent.jpg")
    adapter = MockVisionAdapter()
    ans = adapter.generate("Explain the diagram", [missing_path])
    assert ans == ABSTAIN_VISUAL_MISSING


def test_empty_images_list_triggers_abstention():
    adapter = MockVisionAdapter()
    ans = adapter.generate("Explain the diagram", [])
    assert ans == ABSTAIN_VISUAL_MISSING


def test_max_images_budget_enforced(sample_images):
    img1, img2, _ = sample_images
    adapter = MockVisionAdapter(max_images=1)
    paths = adapter.validate_and_load_images([img1, img2])
    assert len(paths) == 1
    assert paths[0] == img1


def test_multimodal_answer_citations_mapped(sample_images):
    img1, _, _ = sample_images
    node = DummyNode("Code for printf", {
        "source_id": "cs50-lec01",
        "modality": "visual",
        "chunk_id": "chunk_v1",
        "page_number": 42,
        "image_path": img1,
        "start_sec": None,
        "end_sec": None,
    })
    retriever = DummyRetriever([node])
    adapter = MockVisionAdapter(canned_answers={"printf": "The slide shows printf(\"hello\") [Evidence 1]"})

    ans, citations = generate_grounded_answer("How is printf used?", retriever, vision_adapter=adapter)
    assert "[Evidence 1]" in ans
    assert len(citations) == 1
    assert citations[0]["page_number"] == 42
    assert citations[0]["modality"] == "visual"


def test_image_removal_perturbation(sample_images, tmp_path):
    img1, _, _ = sample_images
    node = DummyNode("Slide diagram", {
        "source_id": "cs50-lec01",
        "modality": "visual",
        "chunk_id": "chunk_v1",
        "page_number": 1,
        "image_path": str(tmp_path / "deleted.jpg"),
    })
    retriever = DummyRetriever([node])
    adapter = MockVisionAdapter()

    ans, _ = generate_grounded_answer("What does diagram show?", retriever, vision_adapter=adapter, require_visual=True)
    assert ans == ABSTAIN_VISUAL_MISSING


def test_image_swap_perturbation(sample_images):
    _, _, swapped = sample_images
    adapter = MockVisionAdapter()
    ans = adapter.generate("What is the algorithm on slide?", [swapped])
    assert ans == ABSTAIN_VISUAL_UNSUPPORTED


def test_callable_vision_adapter(sample_images):
    img1, _, _ = sample_images
    def my_vision_fn(query, images, context):
        return f"Custom answer for {query} with {len(images)} images"

    adapter = CallableVisionAdapter(my_vision_fn)
    ans = adapter.generate("Test query", [img1])
    assert "Custom answer for Test query with 1 images" == ans


def test_multiple_visual_evidence_chunks(sample_images):
    img1, img2, _ = sample_images
    adapter = MockVisionAdapter(max_images=5)
    ans = adapter.generate("Compare slides", [img1, img2])
    assert len(adapter.last_payload_bytes) == 2


def test_text_only_retriever_fallback():
    node = DummyNode("Spoken explanation about memory", {
        "source_id": "cs50-lec01",
        "modality": "audio",
        "chunk_id": "chunk_a1",
        "start_sec": 10.0,
        "end_sec": 20.0,
    })
    retriever = DummyRetriever([node])
    ans, citations = generate_grounded_answer("What is memory?", retriever)
    assert len(citations) == 1
    assert citations[0]["modality"] == "audio"


def test_provenance_preservation_in_multimodal_citation(sample_images):
    img1, _, _ = sample_images
    node = DummyNode("Binary search diagram", {
        "source_id": "cs50-lec03",
        "modality": "visual",
        "chunk_id": "ev_bs_123",
        "page_number": 15,
        "image_path": img1,
        "start_sec": None,
        "end_sec": None,
    })
    retriever = DummyRetriever([node])
    adapter = MockVisionAdapter()
    _, citations = generate_grounded_answer("Explain binary search", retriever, vision_adapter=adapter)
    c = citations[0]
    assert c["chunk_id"] == "ev_bs_123"
    assert c["source_id"] == "cs50-lec03"
    assert c["page_number"] == 15


def test_create_vision_adapter_factory():
    m = create_vision_adapter("mock")
    assert isinstance(m, MockVisionAdapter)
    c = create_vision_adapter("callable", callback=lambda q, i, c: "test")
    assert isinstance(c, CallableVisionAdapter)
    with pytest.raises(ValueError):
        create_vision_adapter("unknown_backend")
