"""Vision adapter layer and Multimodal Visual Question Answering (VQA) support for M4.

Provides adapters for:
- MockVisionAdapter: offline rule-based and perturbation testing.
- GoogleGenAIVisionAdapter: Google Gemini multimodal API.
- OpenAIVisionAdapter: OpenAI GPT-4o / GPT-4o-mini vision API.
- CallableVisionAdapter: user-supplied callable for testing.

Enforces:
1. Actual image payload loading and delivery.
2. Explicit visual requirement & safe abstention when visual evidence is missing or corrupted.
3. Maximum image budget (max_images).
4. Perturbation handling (image removal, image swap detection).
"""
import base64
import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from PIL import Image

from config import CONFIG

ABSTAIN_VISUAL_MISSING = "I abstain from answering because required visual evidence is missing."
ABSTAIN_VISUAL_UNSUPPORTED = "I abstain from answering because the visual evidence is unsupported or contradictory."


class BaseVisionAdapter(ABC):
    """Abstract base class for vision-language model adapters."""

    def __init__(self, max_images: int = 5):
        self.max_images = max_images

    @abstractmethod
    def generate(self, query: str, image_paths: List[str], text_context: str = "") -> str:
        """Generate a grounded answer given query, image paths, and text context."""
        pass

    def validate_and_load_images(self, image_paths: List[str]) -> List[str]:
        """Validates that image paths exist, are non-empty, and respects max_images limit."""
        valid_paths = []
        for p in image_paths:
            if p and os.path.exists(p) and os.path.isfile(p) and os.path.getsize(p) > 0:
                valid_paths.append(p)
            if len(valid_paths) >= self.max_images:
                break
        return valid_paths


class MockVisionAdapter(BaseVisionAdapter):
    """Offline mock vision adapter for deterministic test execution and perturbation checks."""

    def __init__(
        self,
        canned_answers: Optional[Dict[str, str]] = None,
        default_answer: Optional[str] = None,
        max_images: int = 5,
        verify_content: bool = True,
    ):
        super().__init__(max_images=max_images)
        self.canned_answers = canned_answers or {}
        self.default_answer = default_answer or "Based on the visual evidence shown in the slide [Evidence 1], the answer is confirmed."
        self.verify_content = verify_content
        self.last_payload_bytes: List[bytes] = []

    def generate(self, query: str, image_paths: List[str], text_context: str = "") -> str:
        valid_paths = self.validate_and_load_images(image_paths)
        self.last_payload_bytes = []

        # If visual evidence was expected/passed as an empty or invalid list
        if not valid_paths and image_paths:
            return ABSTAIN_VISUAL_MISSING

        if not valid_paths:
            # No images at all
            return ABSTAIN_VISUAL_MISSING

        # Read actual bytes to confirm image payload integrity
        for p in valid_paths:
            with open(p, "rb") as f:
                self.last_payload_bytes.append(f.read())

        # Check for swap/perturbation flags in test filenames
        for p in valid_paths:
            if "swapped" in os.path.basename(p).lower():
                return ABSTAIN_VISUAL_UNSUPPORTED

        for q_sub, ans in self.canned_answers.items():
            if q_sub.lower() in query.lower():
                return ans

        return self.default_answer


class CallableVisionAdapter(BaseVisionAdapter):
    """Adapter wrapping a custom Python callable for testing."""

    def __init__(self, callback: Callable[[str, List[str], str], str], max_images: int = 5):
        super().__init__(max_images=max_images)
        self.callback = callback

    def generate(self, query: str, image_paths: List[str], text_context: str = "") -> str:
        valid_paths = self.validate_and_load_images(image_paths)
        if not valid_paths and image_paths:
            return ABSTAIN_VISUAL_MISSING
        return self.callback(query, valid_paths, text_context)


class GoogleGenAIVisionAdapter(BaseVisionAdapter):
    """Vision adapter using Google Generative AI / Gemini."""

    def __init__(self, model_name: str = "gemini-1.5-flash", api_key: Optional[str] = None, max_images: int = 5):
        super().__init__(max_images=max_images)
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def generate(self, query: str, image_paths: List[str], text_context: str = "") -> str:
        valid_paths = self.validate_and_load_images(image_paths)
        if not valid_paths and image_paths:
            return ABSTAIN_VISUAL_MISSING

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is not set.")

        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_name)

        contents: List[Any] = []
        for p in valid_paths:
            contents.append(Image.open(p))

        prompt = f"""You are a grounded multimodal AI tutor.
Answer the following query using ONLY the provided visual images and text context.
Cite each claim with [Evidence X] matching the visual/text source.
If the images and context do not sufficiently support the answer, explicitly state:
'{ABSTAIN_VISUAL_MISSING}'

Context:
{text_context}

Query: {query}
"""
        contents.append(prompt)
        response = model.generate_content(contents)
        return response.text if response and response.text else ABSTAIN_VISUAL_MISSING


class OpenAIVisionAdapter(BaseVisionAdapter):
    """Vision adapter using OpenAI multimodal API (gpt-4o / gpt-4o-mini)."""

    def __init__(self, model_name: str = "gpt-4o-mini", api_key: Optional[str] = None, max_images: int = 5):
        super().__init__(max_images=max_images)
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def generate(self, query: str, image_paths: List[str], text_context: str = "") -> str:
        valid_paths = self.validate_and_load_images(image_paths)
        if not valid_paths and image_paths:
            return ABSTAIN_VISUAL_MISSING

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")

        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)

        user_content: List[Dict[str, Any]] = [
            {"type": "text", "text": f"Context:\n{text_context}\n\nQuery: {query}\nAnswer with inline citations like [Evidence 1]. If unsupported, state '{ABSTAIN_VISUAL_MISSING}'."}
        ]

        for p in valid_paths:
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })

        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a grounded tutor. Assert only claims directly visible in the evidence."},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content or ABSTAIN_VISUAL_MISSING


def create_vision_adapter(backend: str = "mock", **kwargs) -> BaseVisionAdapter:
    """Factory creating the appropriate vision adapter."""
    b = backend.lower()
    if b == "mock":
        return MockVisionAdapter(**kwargs)
    elif b in ("gemini", "google"):
        return GoogleGenAIVisionAdapter(**kwargs)
    elif b == "openai":
        return OpenAIVisionAdapter(**kwargs)
    elif b == "callable":
        return CallableVisionAdapter(**kwargs)
    else:
        raise ValueError(f"Unknown vision backend: {backend}")
