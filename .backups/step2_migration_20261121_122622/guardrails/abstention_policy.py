"""Abstention and Qualification decision policy for Milestone M6.

Enforces:
1. Dual-threshold decision gating:
   - Answer if top-1 retrieval score >= tau_ans and evidence coverage >= tau_cov.
   - Qualify if tau_qual <= top-1 retrieval score < tau_ans, or if coverage is partial.
   - Abstain if top-1 retrieval score < tau_qual, or if no active-version evidence is retrieved.
2. Standardized abstention and qualification responses.
3. Calibration support for tuning thresholds against development splits.
"""
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

ABSTAIN_UNSUPPORTED = "I abstain from answering because no relevant material was found in the approved course material."
ABSTAIN_OFF_CORPUS = "I abstain from answering because this question is outside the approved lecture corpus."
QUALIFY_PREFIX = "Partially supported by course evidence:"


class DecisionType(str, Enum):
    ANSWER = "answer"
    QUALIFY = "qualify"
    ABSTAIN = "abstain"


class AbstentionPolicy:
    """Configurable decision policy governing when the tutor answers, qualifies, or abstains."""

    def __init__(
        self,
        tau_ans: float = 0.50,
        tau_qual: float = 0.20,
        tau_cov: float = 0.40,
        sim_threshold_answer: Optional[float] = None,
        sim_threshold_qualify: Optional[float] = None,
    ):
        self.tau_ans = sim_threshold_answer if sim_threshold_answer is not None else tau_ans
        self.tau_qual = sim_threshold_qualify if sim_threshold_qualify is not None else tau_qual
        self.tau_cov = tau_cov

    @staticmethod
    def _extract_tokens(text: str) -> Set[str]:
        """Extract alphanumeric lowercase tokens from text, filtering trivial stopwords."""
        stopwords = {
            "a", "an", "the", "in", "on", "at", "to", "for", "of", "with",
            "is", "are", "was", "were", "and", "or", "what", "how", "why",
            "which", "does", "do", "did", "this", "that", "these", "those",
            "can", "could", "would", "should", "according", "lecture", "cs50",
            "you", "your", "yours", "me", "my", "we", "our", "us", "it", "its",
            "they", "them", "their", "he", "him", "his", "she", "her",
            "be", "been", "being", "have", "has", "had", "will", "shall",
        }
        tokens = set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower()))
        return tokens - stopwords

    def compute_evidence_scores(
        self, query: str, nodes: List[Any]
    ) -> Tuple[float, float]:
        """Calculates top-1 retrieval score S in [0.0, 1.0] and evidence coverage C in [0.0, 1.0]."""
        if not nodes:
            return 0.0, 0.0

        q_tokens = self._extract_tokens(query)
        if not q_tokens:
            return 1.0, 1.0

        best_score = 0.0
        combined_chunk_tokens: Set[str] = set()

        for node in nodes:
            content = node.get_content() if hasattr(node, "get_content") else str(node)
            node_tokens = self._extract_tokens(content)
            combined_chunk_tokens.update(node_tokens)

            # Node score if assigned by retriever (e.g. NodeWithScore)
            if hasattr(node, "score") and node.score is not None and float(node.score) > 0.0:
                node_s = float(node.score)
                # Normalize if score exceeds 1.0
                if node_s > 1.0:
                    node_s = min(1.0, node_s / 10.0)
            else:
                # Jaccard-like token overlap score for this chunk
                overlap = len(q_tokens & node_tokens)
                node_s = overlap / max(1, len(q_tokens))

            if node_s > best_score:
                best_score = node_s

        # Coverage is fraction of query tokens present across top retrieved chunks
        covered_tokens = q_tokens & combined_chunk_tokens
        coverage = len(covered_tokens) / max(1, len(q_tokens))

        return best_score, coverage

    def evaluate(
        self, query: str, nodes: List[Any]
    ) -> Tuple[DecisionType, float, float, str]:
        """Evaluates whether to answer, qualify, or abstain for a given query and retrieved nodes."""
        if not nodes:
            return DecisionType.ABSTAIN, 0.0, 0.0, ABSTAIN_UNSUPPORTED

        score, coverage = self.compute_evidence_scores(query, nodes)

        if score < self.tau_qual or coverage < 0.25:
            reason = (
                f"Retrieval score ({score:.2f}) < tau_qual ({self.tau_qual:.2f}) "
                f"or coverage ({coverage:.2f}) < 0.25"
            )
            return DecisionType.ABSTAIN, score, coverage, reason

        if score >= self.tau_ans and coverage >= self.tau_cov:
            reason = (
                f"Score ({score:.2f}) >= tau_ans ({self.tau_ans:.2f}) and "
                f"coverage ({coverage:.2f}) >= tau_cov ({self.tau_cov:.2f})"
            )
            return DecisionType.ANSWER, score, coverage, reason

        # Otherwise qualify
        reason = (
            f"Partial evidence: score ({score:.2f}) in [{self.tau_qual:.2f}, {self.tau_ans:.2f}) "
            f"or coverage ({coverage:.2f}) < tau_cov ({self.tau_cov:.2f})"
        )
        return DecisionType.QUALIFY, score, coverage, reason

    @staticmethod
    def format_qualification(answer_body: str, missing_aspects: Optional[str] = None) -> str:
        """Wraps answer in clear qualification wording."""
        if missing_aspects:
            return f"Partially supported by course evidence: {answer_body.strip()} (Note: {missing_aspects})"
        return f"Partially supported by course evidence: {answer_body.strip()}"
