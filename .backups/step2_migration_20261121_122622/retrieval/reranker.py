"""Reranker layer for Milestone M8: Hybrid Fusion and Reranking Architecture.

Takes top-M candidate nodes from fused retrieval and produces a high-precision,
reranked top-K ordering using semantic and exact-match keyword scoring.
"""
import re
from typing import Any, List, Optional, Set


class TutorReranker:
    """High-precision reranker for ambiguous or high-recall instructional queries."""

    def __init__(self, exact_boost: float = 1.5, code_boost: float = 1.3):
        self.exact_boost = exact_boost
        self.code_boost = code_boost

    @staticmethod
    def _extract_tokens(text: str) -> Set[str]:
        return set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower()))

    def score_node(self, query: str, node: Any) -> float:
        """Calculates a composite relevance score for a retrieved evidence node."""
        content = node.get_content() if hasattr(node, "get_content") else str(node)
        q_tokens = self._extract_tokens(query)
        c_tokens = self._extract_tokens(content)

        if not q_tokens:
            return 0.0

        # Base token overlap (Jaccard similarity)
        intersection = q_tokens & c_tokens
        base_score = len(intersection) / max(1, len(q_tokens | c_tokens))

        # Check for exact code/symbol token matches (e.g. printf, get_string, clang)
        meta = getattr(node, "metadata", {}) or {}
        modality = meta.get("modality", "")

        exact_matches = 0
        for token in q_tokens:
            if "_" in token or "(" in query or token.isupper() or token in ["printf", "make", "clang", "int", "char"]:
                if token in c_tokens:
                    exact_matches += 1

        score = base_score + (exact_matches * 0.25 * self.exact_boost)

        # Modality boost for code or visual
        if modality == "visual" and ("slide" in query.lower() or "diagram" in query.lower()):
            score *= self.code_boost

        return float(score)

    def rerank(self, query: str, nodes: List[Any], top_k: int = 5) -> List[Any]:
        """Reranks candidate nodes and returns top_k highest scoring nodes."""
        if not nodes:
            return []

        scored_nodes = []
        for node in nodes:
            s = self.score_node(query, node)
            # If the node allows score assignment, update it
            if hasattr(node, "score"):
                node.score = s
            scored_nodes.append((s, node))

        # Sort descending by score
        scored_nodes.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in scored_nodes[:top_k]]
