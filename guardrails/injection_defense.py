"""Indirect prompt-injection defense, delimiter isolation, and citation validation (M7).

Enforces:
1. Instruction Hierarchy: System > Developer > Tutor Policy > Retrieved Content.
2. Delimited evidence framing: All retrieved content is tagged as untrusted data.
3. Attack pattern detection: Detects common indirect injection payloads embedded in slides/transcripts.
4. Output verification: Detects compromised responses and neutralizes them.
5. Fabricated citation removal: Strips hallucinations like [Evidence 99] that were never provided.
"""
import re
from typing import Dict, List, Optional, Set, Tuple

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|previous\s+|prior\s+)?instructions",
    r"system\s+(prompt|override|command)",
    r"you\s+are\s+now\s+(a|an|dan|jailbreak)",
    r"reveal\s+(the\s+|all\s+)?(system\s+)?prompt",
    r"drop\s+table",
    r"disregard\s+(the\s+)?above",
    r"output\s*:\s*pwned",
    r"pwned\b",
    r"admin\s+mode",
    r"developer\s+mode",
]

COMPILED_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


class InjectionDefense:
    """Security guardrail against indirect prompt injection and fabricated citations."""

    @staticmethod
    def contains_injection_payload(text: str) -> bool:
        """Detects whether text contains common prompt-injection attack signatures."""
        for pattern in COMPILED_INJECTION_RE:
            if pattern.search(text):
                return True
        return False

    @staticmethod
    def wrap_evidence(label: str, content: str, source_id: str, modality: str) -> str:
        """Wraps retrieved evidence into untrusted data delimiters to prevent execution as instructions."""
        sanitized_content = content.replace("]]>", "]] >")
        return (
            f'<untrusted_evidence_data label="{label}" source="{source_id}" modality="{modality}">\n'
            f"<![CDATA[\n{sanitized_content}\n]]>\n"
            f"</untrusted_evidence_data>"
        )

    @staticmethod
    def sanitize_citations(
        answer: str, valid_labels: List[str]
    ) -> Tuple[str, List[str], List[str]]:
        """Finds all citations in the answer, validates them against provided evidence,

        and strips any fabricated or hallucinated citations.

        Returns:
            sanitized_answer: Text with fabricated citations stripped or flagged.
            kept_citations: List of valid citation labels present in answer.
            removed_citations: List of stripped hallucinated citation labels.
        """
        valid_set = set(valid_labels)
        found_labels = re.findall(r"\[Evidence\s+\d+\]", answer)
        kept: List[str] = []
        removed: List[str] = []

        sanitized_answer = answer
        for lbl in set(found_labels):
            if lbl in valid_set:
                kept.append(lbl)
            else:
                removed.append(lbl)
                # Strip the hallucinated citation
                sanitized_answer = sanitized_answer.replace(lbl, "")

        # Clean up any double spaces left behind by removal
        sanitized_answer = re.sub(r"\s{2,}", " ", sanitized_answer).strip()
        return sanitized_answer, kept, removed

    @staticmethod
    def verify_output(
        answer: str,
        prohibited_phrases: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Validates that the generated answer has not obeyed an injected instruction.

        Returns:
            (is_safe, sanitized_or_original_text)
        """
        bad_phrases = prohibited_phrases or [
            "system prompt",
            "pwned",
            "developer mode enabled",
            "jailbreak successful",
            "you are now an unrestricted",
        ]

        lower = answer.lower()
        for phrase in bad_phrases:
            if phrase in lower:
                # The model followed an attacker's instruction
                return False, "I abstain from answering because the evidence contains untrusted instructions."

        return True, answer
