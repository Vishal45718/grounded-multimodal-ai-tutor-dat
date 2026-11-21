"""Answer generation with grounded multimodal and text citation pathways (M4 Phase 2).

Dispatches visual questions with real local images to vision-capable models (e.g. Gemini, OpenAI),
preserves text-only workflows for audio transcripts, enforces mandatory visual abstentions,
and validates citations against active retrieved evidence.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from config import CONFIG
from generation.vqa import (
    VisualPayload,
    get_vision_adapter,
    load_and_validate_image,
)

try:
    from llama_index.llms.openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from retrieval.retriever import TutorRetriever
except ImportError:
    TutorRetriever = Any  # type: ignore


def generate_grounded_answer(
    query: str,
    retriever: Any,
    llm: Any = None,
    vision_model: Any = None,
    visual_required: bool = False,
    max_images: Optional[int] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Generate an evidence-grounded answer to a query using retrieved multimodal context.

    Args:
        query: User question to answer.
        retriever: TutorRetriever instance or mock retriever supporting .retrieve(query).
        llm: Optional text-only LLM instance (default OpenAI if available).
        vision_model: Optional vision adapter, model name, or callable for visual Q&A.
        visual_required: If True, mandates verified visual evidence; abstains if missing.
        max_images: Maximum number of visual images to supply per request (default from CONFIG).

    Returns:
        (answer_text, validated_citations_list)
    """
    effective_max_images = max_images or getattr(CONFIG, "max_visual_images", 5)

    # 1. Retrieve evidence nodes
    nodes = retriever.retrieve(query, fusion=True) if hasattr(retriever, "retrieve") else []
    if not nodes:
        return "I abstain from answering because no relevant material was found.", []

    # 2. Inspect retrieved evidence and load local images
    visual_payloads: List[VisualPayload] = []
    missing_or_invalid_images: List[Tuple[str, str, str]] = []
    has_visual_node = False

    for idx, node in enumerate(nodes):
        label = f"[Evidence {idx + 1}]"
        meta = getattr(node, "metadata", {}) or {}
        modality = meta.get("modality", "audio")

        if modality == "visual":
            has_visual_node = True
            image_path = meta.get("image_path")
            is_valid, img_bytes, err = load_and_validate_image(image_path)

            if not is_valid or img_bytes is None:
                missing_or_invalid_images.append((label, image_path or "", err or "Invalid file"))
            else:
                if len(visual_payloads) < effective_max_images:
                    visual_payloads.append(
                        VisualPayload(
                            label=label,
                            image_path=image_path,
                            image_bytes=img_bytes,
                            page_number=meta.get("page_number"),
                            start_sec=meta.get("start_sec"),
                            end_sec=meta.get("end_sec"),
                            metadata=dict(meta),
                        )
                    )

    # 3. Enforce mandatory visual evidence requirement
    if visual_required:
        if not has_visual_node:
            return (
                "I abstain from answering because required visual evidence was not found in retrieved material.",
                [],
            )
        if missing_or_invalid_images:
            details = "; ".join(f"{lbl}: {err}" for lbl, _, err in missing_or_invalid_images)
            return (
                f"I abstain from answering because required visual evidence is missing or invalid ({details}).",
                [],
            )

        vision_adapter = get_vision_adapter(vision_model)
        if vision_adapter is None or not vision_adapter.is_available():
            return (
                "I abstain from answering because no vision model is available to inspect the required visual evidence.",
                [],
            )

    # 4. Resolve vision adapter if visual images are present
    vision_adapter = get_vision_adapter(vision_model)
    use_vision = bool(visual_payloads and vision_adapter and vision_adapter.is_available())

    # 5. Format evidence context string
    context_lines = []
    for idx, node in enumerate(nodes):
        label = f"[Evidence {idx + 1}]"
        meta = getattr(node, "metadata", {}) or {}
        modality = meta.get("modality", "audio")
        start_sec = meta.get("start_sec")
        end_sec = meta.get("end_sec")
        time_str = f"{start_sec}s - {end_sec}s" if (start_sec is not None and end_sec is not None) else "Unknown"

        text_content = (
            node.get_content()
            if hasattr(node, "get_content")
            else getattr(node, "text", "")
        )

        line = (
            f"--- {label} ({modality.capitalize()} Evidence) ---\n"
            f"Source ID: {meta.get('source_id')}\n"
            f"Asset ID: {meta.get('asset_id')}\n"
            f"Time Bounds: {time_str}\n"
        )
        if meta.get("page_number"):
            line += f"Slide Page: {meta.get('page_number')}\n"
        if modality == "visual":
            line += f"Visual Asset: Attached image {label}\n"
            line += f"Extracted Slide Text: {text_content}\n"
        else:
            line += f"Transcript Text: {text_content}\n"

        context_lines.append(line)

    context_str = "\n".join(context_lines)

    # 6. Execute vision model or text LLM
    if use_vision and vision_adapter:
        prompt = (
            "You are an AI tutor. You must answer the user's query ONLY using the provided evidence "
            "(both the attached visual images and the textual context).\n"
            "If the evidence does not clearly support answering the query, explicitly abstain by saying 'I abstain...'.\n"
            "When making any factual claim, you MUST cite the exact evidence label (e.g. [Evidence 1]) inline immediately following the claim.\n"
            "Only cite evidence labels that you actually consulted and that directly support your statement.\n\n"
            f"Query: {query}\n\n"
            f"Evidence Context:\n{context_str}\n\n"
            "Answer:"
        )
        try:
            answer_text = vision_adapter.generate(prompt, visual_payloads)
        except Exception as exc:
            return (
                f"I abstain from answering due to an error executing the vision model: {type(exc).__name__}.",
                [],
            )
    else:
        # Text-only answering workflow
        if visual_required:
            return (
                "I abstain from answering because no vision model is available to inspect the required visual evidence.",
                [],
            )

        prompt = (
            "You are an AI tutor. You must answer the user's query ONLY using the provided evidence.\n"
            "If the evidence does not support answering the query, explicitly abstain by saying 'I abstain...'.\n"
            "When making a claim, you MUST cite the exact evidence number [Evidence X] inline.\n\n"
            f"Query: {query}\n\n"
            f"Evidence Context:\n{context_str}\n\n"
            "Answer:"
        )

        if llm is None:
            if OpenAI is not None:
                try:
                    llm = OpenAI(model="gpt-4o-mini")
                except Exception:
                    llm = None

        if llm is None:
            return (
                "I abstain from answering because no text generation model is available.",
                [],
            )

        try:
            if hasattr(llm, "complete"):
                resp = llm.complete(prompt)
                answer_text = getattr(resp, "text", str(resp))
            elif callable(llm):
                resp = llm(prompt)
                answer_text = getattr(resp, "text", str(resp))
            else:
                answer_text = str(llm)
        except Exception as exc:
            return (
                f"I abstain from answering due to an error executing the language model: {type(exc).__name__}.",
                [],
            )

    # 7. Extract and validate citations
    if not answer_text or answer_text.strip().lower().startswith("i abstain"):
        return answer_text or "I abstain from answering.", []

    cited_indices = []
    # Find all [Evidence X] references in the generated answer text
    for match in re.finditer(r"\[Evidence\s+(\d+)\]", answer_text):
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(nodes):
            if idx not in cited_indices:
                cited_indices.append(idx)
        # Note: unknown evidence labels (idx out of range) are intentionally ignored/rejected

    citations: List[Dict[str, Any]] = []
    for idx in cited_indices:
        node = nodes[idx]
        meta = getattr(node, "metadata", {}) or {}

        # Exclude inactive or superseded chunks
        if meta.get("is_stale") == 1:
            continue

        citations.append({
            "citation_label": f"[Evidence {idx + 1}]",
            "chunk_id": meta.get("chunk_id"),
            "source_id": meta.get("source_id"),
            "asset_id": meta.get("asset_id"),
            "content_hash": meta.get("content_hash"),
            "course_edition": meta.get("course_edition") or meta.get("edition_id"),
            "edition_id": meta.get("edition_id"),
            "modality": meta.get("modality"),
            "start_sec": meta.get("start_sec"),
            "end_sec": meta.get("end_sec"),
            "image_path": meta.get("image_path"),
            "page_number": meta.get("page_number"),
            "source_url": meta.get("source_url"),
        })

    return answer_text, citations
