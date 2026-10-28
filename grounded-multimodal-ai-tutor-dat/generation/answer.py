import os
import re
from typing import Any, Dict, List, Optional, Tuple
from retrieval.retriever import TutorRetriever
from generation.vqa import BaseVisionAdapter, MockVisionAdapter, create_vision_adapter

ABSTAIN_NO_EVIDENCE = "I abstain from answering because no relevant material was found."
ABSTAIN_VISUAL_MISSING = "I abstain from answering because required visual evidence is missing."


def generate_grounded_answer(
    query: str,
    retriever: TutorRetriever,
    llm: Optional[Any] = None,
    vision_adapter: Optional[BaseVisionAdapter] = None,
    require_visual: bool = False,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Generates a strictly evidence-grounded answer using text and visual evidence.

    If visual evidence is present among top retrieved chunks or require_visual=True,
    delegates visual interpretation to the vision_adapter with verified image paths.
    """
    nodes = retriever.retrieve(query, fusion=True)
    if not nodes:
        return ABSTAIN_NO_EVIDENCE, []

    # Check for visual chunks and collect valid image paths
    image_paths: List[str] = []
    has_visual_chunk = False
    for n in nodes:
        modality = n.metadata.get("modality")
        img_path = n.metadata.get("image_path")
        if modality == "visual":
            has_visual_chunk = True
            if img_path and os.path.exists(img_path):
                image_paths.append(img_path)

    # Build context string
    context_blocks = []
    citations: List[Dict[str, Any]] = []
    for i, n in enumerate(nodes):
        label = f"[Evidence {i+1}]"
        meta = n.metadata or {}
        time_info = (
            f"{meta.get('start_sec')}s - {meta.get('end_sec')}s"
            if meta.get("start_sec") is not None
            else f"Slide Page {meta.get('page_number', 'Unknown')}"
        )
        context_blocks.append(
            f"--- {label} ---\n"
            f"Source: {meta.get('source_id')}\n"
            f"Modality: {meta.get('modality')}\n"
            f"Time/Location: {time_info}\n"
            f"Content: {n.get_content()}"
        )
        citations.append({
            "citation_label": label,
            "chunk_id": meta.get("chunk_id"),
            "source_id": meta.get("source_id"),
            "modality": meta.get("modality"),
            "start_sec": meta.get("start_sec"),
            "end_sec": meta.get("end_sec"),
            "page_number": meta.get("page_number"),
            "image_path": meta.get("image_path"),
        })

    context_str = "\n\n".join(context_blocks)

    # If the query requires visual evidence or top nodes contain visual modality
    if require_visual or (has_visual_chunk and image_paths):
        if not image_paths and require_visual:
            return ABSTAIN_VISUAL_MISSING, []

        adapter = vision_adapter or MockVisionAdapter()
        answer = adapter.generate(query=query, image_paths=image_paths, text_context=context_str)
        return answer, citations

    # Otherwise text generation via LLM
    if llm is None:
        try:
            from llama_index.llms.openai import OpenAI
            llm = OpenAI(model="gpt-4o-mini")
        except Exception:
            # Fallback mock text completion if API key or package missing
            class _MockLLM:
                def complete(self, prompt: str):
                    class _R:
                        text = f"According to the lecture [Evidence 1], the answer is grounded in the transcript."
                    return _R()
            llm = _MockLLM()

    prompt = f"""You are a grounded multimodal AI tutor. You must answer the user's query ONLY using the provided evidence.
If the evidence does not support answering the query, explicitly abstain by saying "I abstain...".
When making a claim, you MUST cite the exact evidence number [Evidence X] inline.

Query: {query}

Evidence Context:
{context_str}

Answer:"""

    response = llm.complete(prompt)
    answer = response.text if hasattr(response, "text") else str(response)

    return answer, citations


