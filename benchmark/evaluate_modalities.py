"""Controlled Modality and Image Perturbation Evaluation (M4 Phase 3).

Evaluates visual-required and multimodal benchmark questions under controlled conditions:
1. Transcript-only (no visual evidence provided)
2. OCR-only (slide text provided without image payload)
3. Visual input (actual JPEG slide image delivered to vision model)

Also performs image-removal and image-swap perturbation checks to verify:
- Missing required visual evidence causes safe abstention.
- Answers are not accepted as visually grounded when images are absent.
- Citations do not claim support from unprovided images.
- Swapped images do not silently preserve unsupported answers.

Supports offline deterministic mock evaluation and optional live API evaluation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CONFIG
from generation.answer import generate_grounded_answer
from generation.vqa import (
    BaseVisionAdapter,
    MockVisionAdapter,
    VisualPayload,
    get_vision_adapter,
    load_and_validate_image,
)
from storage.corpus_store import active_chunks


# The 5 verified visual-required cases
VISUAL_CASE_IDS = [
    "cs50-2024-lec01-vis-01",
    "cs50-2024-lec01-vis-02",
    "cs50-2024-lec01-vis-03",
    "cs50-2024-lec01-vis-04",
    "cs50-2024-lec01-vis-05",
]


class MockRetrievalNode:
    """Mock node mimicking LlamaIndex NodeWithScore / Document for testing."""

    def __init__(self, text: str, metadata: Dict[str, Any]):
        self.text = text
        self.metadata = metadata

    def get_content(self) -> str:
        return self.text


class TargetedRetriever:
    """Retriever wrapper that provides targeted evidence subsets for controlled conditions."""

    def __init__(self, active_chunk_map: Dict[str, dict]):
        self.active_chunk_map = active_chunk_map
        self.override_nodes: Optional[List[MockRetrievalNode]] = None

    def set_override_nodes(self, nodes: List[MockRetrievalNode]):
        self.override_nodes = nodes

    def retrieve(self, query: str, fusion: bool = True) -> List[MockRetrievalNode]:
        if self.override_nodes is not None:
            return self.override_nodes
        return []


def create_intelligent_mock_vision_adapter() -> MockVisionAdapter:
    """Creates a mock vision adapter that inspects the delivered image payload."""

    def mock_handler(prompt: str, images: List[VisualPayload]) -> str:
        if not images:
            return "I abstain from answering because no visual images were provided."

        img = images[0]
        page = img.page_number
        label = img.label or "[Evidence 1]"

        # Check image validity
        if not img.image_bytes or len(img.image_bytes) < 10:
            return f"I abstain from answering because the image in {label} is corrupt or empty."

        # Case 1: Slide 11 - hello world in C with purple printf
        if page == 11 or "slide_00011" in img.image_path:
            return f"In the C code shown in {label}, the function 'printf' is highlighted in purple."

        # Case 2: Slide 16 - input/output diagram with empty central box
        if page == 16 or "slide_00016" in img.image_path:
            return f"In the block diagram in {label}, the central box between input and output is empty; there is no text written inside it."

        # Case 3: Slide 20 - compilation diagram with compiler inside central box
        if page == 20 or "slide_00020" in img.image_path:
            return f"In the block diagram in {label}, the word 'compiler' is positioned inside the central box, between 'source code' and 'machine code'."

        # Case 4: Slide 30 - function with side effects
        if page == 30 or "slide_00030" in img.image_path:
            return f"In the block diagram in {label}, the text positioned inside the central box is 'function'."

        # Case 5: Slide 51 - function returning a value
        if page == 51 or "slide_00051" in img.image_path:
            return f"In {label}, the word 'function' is located inside a box between the incoming 'arguments' arrow and outgoing 'return value' arrow."

        # Swapped / Unrelated image handler
        return (
            f"The image provided in {label} (Slide {page}) does not display the requested diagram or syntax highlighting. "
            "It shows an unrelated slide from the lecture; therefore, the question cannot be answered from this image."
        )

    return MockVisionAdapter(handler=mock_handler, available=True)


def check_answer_correctness(case_id: str, answer_text: str, condition: str) -> Tuple[str, str]:
    """Deterministically check if an answer is correct, abstained, or incorrect.

    Returns:
        (status, explanation) where status in {'correct', 'abstained', 'incorrect', 'manual_review'}
    """
    ans_lower = answer_text.lower()

    # Check for safe abstention
    if (
        "abstain" in ans_lower
        or "cannot be answered" in ans_lower
        or "no visual evidence" in ans_lower
        or "unrelated slide" in ans_lower
    ):
        return "abstained", "Model safely abstained or reported unsupported visual evidence."

    # Case-specific objective checks
    if case_id == "cs50-2024-lec01-vis-01":
        if "printf" in ans_lower and "purple" in ans_lower:
            return "correct", "Correctly identified printf highlighted in purple."
        if "printf" in ans_lower and "purple" not in ans_lower:
            return "incorrect", "Identified printf but failed to identify purple highlighting."
        return "incorrect", "Did not identify printf with purple highlighting."

    if case_id == "cs50-2024-lec01-vis-02":
        if "empty" in ans_lower or "nothing" in ans_lower or "no text" in ans_lower:
            return "correct", "Correctly identified the central box is empty."
        return "incorrect", "Failed to identify that the central box is empty."

    if case_id == "cs50-2024-lec01-vis-03":
        if "compiler" in ans_lower and ("inside" in ans_lower or "box" in ans_lower):
            return "correct", "Correctly identified compiler inside the central box."
        return "incorrect", "Failed to identify compiler inside the central box."

    if case_id == "cs50-2024-lec01-vis-04":
        if "function" in ans_lower and ("inside" in ans_lower or "box" in ans_lower or "central" in ans_lower):
            return "correct", "Correctly identified function inside central box."
        return "incorrect", "Failed to identify function inside central box."

    if case_id == "cs50-2024-lec01-vis-05":
        if "function" in ans_lower and ("inside" in ans_lower or "box" in ans_lower or "between" in ans_lower):
            return "correct", "Correctly identified function inside box between arrows."
        return "incorrect", "Failed to identify function inside box between arrows."

    return "manual_review", "Subjective or non-templated answer requiring manual review."


def run_modality_evaluation(
    cases: List[Dict[str, Any]],
    active_chunk_map: Dict[str, dict],
    vision_adapter: BaseVisionAdapter,
    text_llm: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Runs the 3-condition modality evaluation on visual benchmark cases."""
    results = []
    retriever = TargetedRetriever(active_chunk_map)

    for case in cases:
        case_id = case["id"]
        question = case["question"]
        expected_ans = case["expected_answer"]
        visual_required = case.get("visual_required", False)
        gold_eids = case.get("expected_evidence_ids", [])

        if not visual_required or not gold_eids:
            continue

        gold_chunk = active_chunk_map.get(gold_eids[0])
        if not gold_chunk:
            continue

        # Condition 1: Transcript-only
        # Provide an audio chunk instead of visual slide
        # Find an audio chunk from the lecture
        audio_chunk = next((c for c in active_chunk_map.values() if c["modality"] == "audio"), None)
        transcript_node = MockRetrievalNode(
            text=audio_chunk["text"] if audio_chunk else "General lecture transcript.",
            metadata={
                "chunk_id": audio_chunk["chunk_id"] if audio_chunk else "audio_dummy",
                "source_id": "cs50-lec01",
                "asset_id": "cs50-2024-lec01-video",
                "modality": "audio",
                "start_sec": audio_chunk.get("start_sec") if audio_chunk else 0.0,
                "end_sec": audio_chunk.get("end_sec") if audio_chunk else 30.0,
            },
        )
        retriever.set_override_nodes([transcript_node])
        raw_ans_t, cites_t = generate_grounded_answer(
            query=question,
            retriever=retriever,
            llm=text_llm,
            vision_model=vision_adapter,
            visual_required=True,
        )
        status_t, exp_t = check_answer_correctness(case_id, raw_ans_t, "transcript_only")
        results.append({
            "case_id": case_id,
            "question": question,
            "expected_answer": expected_ans,
            "condition": "transcript_only",
            "image_supplied": False,
            "raw_answer": raw_ans_t,
            "citations": cites_t,
            "status": status_t,
            "explanation": exp_t,
            "evidence_used": [transcript_node.metadata["chunk_id"]],
        })

        # Condition 2: OCR-only (slide text present, image omitted/suppressed)
        ocr_node = MockRetrievalNode(
            text=gold_chunk.get("text", ""),
            metadata={
                "chunk_id": gold_chunk["chunk_id"],
                "source_id": gold_chunk["source_id"],
                "asset_id": gold_chunk.get("asset_id"),
                "modality": "visual",
                "page_number": gold_chunk.get("page_number"),
                "image_path": None,  # Suppressed image path
                "status": "success",
            },
        )
        retriever.set_override_nodes([ocr_node])
        raw_ans_ocr, cites_ocr = generate_grounded_answer(
            query=question,
            retriever=retriever,
            llm=text_llm,
            vision_model=vision_adapter,
            visual_required=True,
        )
        status_ocr, exp_ocr = check_answer_correctness(case_id, raw_ans_ocr, "ocr_only")
        results.append({
            "case_id": case_id,
            "question": question,
            "expected_answer": expected_ans,
            "condition": "ocr_only",
            "image_supplied": False,
            "raw_answer": raw_ans_ocr,
            "citations": cites_ocr,
            "status": status_ocr,
            "explanation": exp_ocr,
            "evidence_used": [ocr_node.metadata["chunk_id"]],
        })

        # Condition 3: Visual input (actual JPEG delivered)
        visual_node = MockRetrievalNode(
            text=gold_chunk.get("text", ""),
            metadata=dict(gold_chunk),
        )
        retriever.set_override_nodes([visual_node])
        raw_ans_v, cites_v = generate_grounded_answer(
            query=question,
            retriever=retriever,
            llm=text_llm,
            vision_model=vision_adapter,
            visual_required=True,
        )
        status_v, exp_v = check_answer_correctness(case_id, raw_ans_v, "visual_input")
        results.append({
            "case_id": case_id,
            "question": question,
            "expected_answer": expected_ans,
            "condition": "visual_input",
            "image_supplied": True,
            "image_path": gold_chunk.get("image_path"),
            "page_number": gold_chunk.get("page_number"),
            "raw_answer": raw_ans_v,
            "citations": cites_v,
            "status": status_v,
            "explanation": exp_v,
            "evidence_used": [visual_node.metadata["chunk_id"]],
        })

    return results


def run_perturbation_evaluation(
    cases: List[Dict[str, Any]],
    active_chunk_map: Dict[str, dict],
    vision_adapter: BaseVisionAdapter,
    text_llm: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Runs image removal and image swap perturbation checks."""
    results = []
    retriever = TargetedRetriever(active_chunk_map)

    # Pick an unrelated real visual slide from the corpus for swapping (Slide 193: 32 bits slide)
    unrelated_slide = next(
        (c for c in active_chunk_map.values() if c.get("page_number") == 193 and c["modality"] == "visual"),
        next((c for c in active_chunk_map.values() if c.get("page_number") == 1 and c["modality"] == "visual"), None),
    )

    for case in cases:
        case_id = case["id"]
        question = case["question"]
        expected_ans = case["expected_answer"]
        visual_required = case.get("visual_required", False)
        gold_eids = case.get("expected_evidence_ids", [])

        if not visual_required or not gold_eids:
            continue

        gold_chunk = active_chunk_map.get(gold_eids[0])
        if not gold_chunk:
            continue

        # Perturbation 1: Correct Image
        correct_node = MockRetrievalNode(
            text=gold_chunk.get("text", ""),
            metadata=dict(gold_chunk),
        )
        retriever.set_override_nodes([correct_node])
        raw_corr, cites_corr = generate_grounded_answer(
            query=question,
            retriever=retriever,
            llm=text_llm,
            vision_model=vision_adapter,
            visual_required=True,
        )
        stat_corr, exp_corr = check_answer_correctness(case_id, raw_corr, "correct_image")
        results.append({
            "case_id": case_id,
            "question": question,
            "test_type": "correct_image",
            "image_path": gold_chunk.get("image_path"),
            "image_supplied": True,
            "raw_answer": raw_corr,
            "citations": cites_corr,
            "status": stat_corr,
            "explanation": exp_corr,
        })

        # Perturbation 2: Missing / Removed Image
        removed_meta = dict(gold_chunk)
        removed_meta["image_path"] = "data/keyframes/nonexistent_missing_slide.jpg"
        removed_node = MockRetrievalNode(
            text=gold_chunk.get("text", ""),
            metadata=removed_meta,
        )
        retriever.set_override_nodes([removed_node])
        raw_rem, cites_rem = generate_grounded_answer(
            query=question,
            retriever=retriever,
            llm=text_llm,
            vision_model=vision_adapter,
            visual_required=True,
        )
        stat_rem, exp_rem = check_answer_correctness(case_id, raw_rem, "removed_image")
        results.append({
            "case_id": case_id,
            "question": question,
            "test_type": "removed_image",
            "image_path": removed_meta["image_path"],
            "image_supplied": False,
            "raw_answer": raw_rem,
            "citations": cites_rem,
            "status": stat_rem,
            "explanation": exp_rem,
            "safe_abstention_verified": bool("abstain" in raw_rem.lower() and len(cites_rem) == 0),
        })

        # Perturbation 3: Swapped Image (with unrelated real slide from corpus)
        if unrelated_slide:
            swapped_meta = dict(gold_chunk)
            swapped_meta["image_path"] = unrelated_slide.get("image_path")
            swapped_meta["page_number"] = unrelated_slide.get("page_number")
            swapped_node = MockRetrievalNode(
                text=gold_chunk.get("text", ""),
                metadata=swapped_meta,
            )
            retriever.set_override_nodes([swapped_node])
            raw_swap, cites_swap = generate_grounded_answer(
                query=question,
                retriever=retriever,
                llm=text_llm,
                vision_model=vision_adapter,
                visual_required=True,
            )
            stat_swap, exp_swap = check_answer_correctness(case_id, raw_swap, "swapped_image")
            results.append({
                "case_id": case_id,
                "question": question,
                "test_type": "swapped_image",
                "original_slide_page": gold_chunk.get("page_number"),
                "swapped_slide_page": unrelated_slide.get("page_number"),
                "image_path": unrelated_slide.get("image_path"),
                "image_supplied": True,
                "raw_answer": raw_swap,
                "citations": cites_swap,
                "status": stat_swap,
                "explanation": exp_swap,
                "silent_acceptance_prevented": bool(stat_swap != "correct"),
            })

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate visual QA modalities and image perturbations.")
    parser.add_argument("--mode", choices=["mock", "real"], default="mock", help="Evaluation execution mode.")
    parser.add_argument("--backend", default=None, help="Vision backend ('mock', 'gemini', 'openai').")
    parser.add_argument("--cases", default="benchmark/cases.jsonl", help="Path to benchmark cases.")
    parser.add_argument("--output-dir", default="benchmark/results", help="Directory to save evaluation results.")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 1. Load active chunks from DB
    chunks = active_chunks()
    chunk_map = {c["chunk_id"]: c for c in chunks}
    print(f"Loaded {len(chunk_map)} active chunks from corpus.db ({sum(1 for c in chunks if c['modality']=='visual')} visual).")

    # 2. Load cases
    cases = []
    with open(args.cases, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    print(f"Loaded {len(cases)} cases from {args.cases}.")

    # 3. Determine vision adapter
    if args.mode == "real":
        backend_name = args.backend or CONFIG.vision_backend
        vision_adapter = get_vision_adapter(backend_name)
        if vision_adapter is None or not vision_adapter.is_available():
            print(f"\n[NOTICE] Real vision backend '{backend_name}' is not configured with a valid API key.")
            print("Marking real-model evaluation as NOT RUN (no API key configured).")
            not_run_summary = {
                "execution_mode": "real",
                "backend": backend_name,
                "status": "not_run",
                "reason": f"API key not set for backend '{backend_name}'. Set GEMINI_API_KEY or OPENAI_API_KEY to execute real model evaluation.",
            }
            with open(os.path.join(args.output_dir, "real_model_evaluation_status.json"), "w") as f:
                json.dump(not_run_summary, f, indent=2)
            return
    else:
        vision_adapter = create_intelligent_mock_vision_adapter()

    # 4. Run Modality Evaluation
    print("\n--- Running 3-Condition Modality Evaluation ---")
    modality_results = run_modality_evaluation(cases, chunk_map, vision_adapter)
    modality_path = os.path.join(args.output_dir, f"modality_evaluation_{args.mode}.json")
    with open(modality_path, "w", encoding="utf-8") as f:
        json.dump(modality_results, f, indent=2)
    print(f"Saved modality results to {modality_path} ({len(modality_results)} condition trials).")

    # 5. Run Perturbation Evaluation
    print("\n--- Running Image Perturbation Evaluation (Removal & Swap) ---")
    perturbation_results = run_perturbation_evaluation(cases, chunk_map, vision_adapter)
    perturbation_path = os.path.join(args.output_dir, f"perturbation_evaluation_{args.mode}.json")
    with open(perturbation_path, "w", encoding="utf-8") as f:
        json.dump(perturbation_results, f, indent=2)
    print(f"Saved perturbation results to {perturbation_path} ({len(perturbation_results)} trials).")

    # 6. Summarize results
    print("\n================== MODALITY EVALUATION SUMMARY ==================")
    cond_counts: Dict[str, Dict[str, int]] = {}
    for r in modality_results:
        cond = r["condition"]
        st = r["status"]
        cond_counts.setdefault(cond, {})
        cond_counts[cond][st] = cond_counts[cond].get(st, 0) + 1

    for cond, counts in cond_counts.items():
        print(f"Condition: {cond.upper():<16} -> Correct: {counts.get('correct', 0)} | Abstained: {counts.get('abstained', 0)} | Incorrect: {counts.get('incorrect', 0)}")

    print("\n================ PERTURBATION EVALUATION SUMMARY ================")
    pert_counts: Dict[str, Dict[str, int]] = {}
    for r in perturbation_results:
        tt = r["test_type"]
        st = r["status"]
        pert_counts.setdefault(tt, {})
        pert_counts[tt][st] = pert_counts[tt].get(st, 0) + 1

    for tt, counts in pert_counts.items():
        print(f"Test: {tt.upper():<16} -> Correct: {counts.get('correct', 0)} | Abstained: {counts.get('abstained', 0)} | Incorrect: {counts.get('incorrect', 0)}")

    # Generate Markdown Summary
    summary_md = f"""# Modality and Perturbation Evaluation Report

- **Execution Mode**: `{args.mode}`
- **Vision Backend**: `{getattr(vision_adapter, 'model_name', args.mode)}`
- **Total Visual Cases**: {len(VISUAL_CASE_IDS)}
- **Modality Conditions Evaluated**: Transcript-only, OCR-only, Visual-input
- **Perturbation Tests Evaluated**: Correct image, Removed image, Swapped image

## 1. Modality Breakdown

| Condition | Cases Tested | Correct | Abstained | Incorrect |
|-----------|--------------|---------|-----------|-----------|
"""
    for cond, counts in cond_counts.items():
        tot = sum(counts.values())
        summary_md += f"| {cond} | {tot} | {counts.get('correct', 0)} | {counts.get('abstained', 0)} | {counts.get('incorrect', 0)} |\n"

    summary_md += """
## 2. Image Perturbation Results

| Perturbation Test | Cases Tested | Safe Abstention / Rejection | Silent False Acceptance |
|-------------------|--------------|-----------------------------|-------------------------|
"""
    for tt, counts in pert_counts.items():
        tot = sum(counts.values())
        safe_count = counts.get('abstained', 0) if tt != "correct_image" else counts.get('correct', 0)
        silent_count = counts.get('correct', 0) if tt != "correct_image" else 0
        summary_md += f"| {tt} | {tot} | {safe_count} | {silent_count} |\n"

    summary_path = os.path.join(args.output_dir, f"summary_{args.mode}.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_md)
    print(f"\nWrote markdown summary to {summary_path}")


if __name__ == "__main__":
    main()
