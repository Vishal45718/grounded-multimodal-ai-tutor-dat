"""Visual question-answering adapter and image validation helpers (M4 Phase 2).

Provides modular, pluggable vision-model backends (Google GenAI / Gemini, OpenAI,
or offline Mock adapters) that load real JPEG/PNG images from disk, validate
their integrity, and deliver them alongside structured evidence context to vision models.
"""
from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import CONFIG


@dataclass
class VisualPayload:
    """Represents a validated local visual evidence image delivered to a vision model."""

    label: str  # e.g. "[Evidence 1]"
    image_path: str
    image_bytes: bytes
    page_number: Optional[int] = None
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def base64_data(self) -> str:
        """Return base64-encoded string of the image bytes."""
        return base64.b64encode(self.image_bytes).decode("utf-8")

    @property
    def pil_image(self):
        """Lazily load and return a PIL Image object."""
        import io
        from PIL import Image
        return Image.open(io.BytesIO(self.image_bytes))


def load_and_validate_image(image_path: Optional[str]) -> Tuple[bool, Optional[bytes], Optional[str]]:
    """Load an image from disk and verify it is a valid, readable, non-empty image file.

    Returns:
        (is_valid, image_bytes, error_message)
    """
    if not image_path:
        return False, None, "No image path provided"

    if not os.path.exists(image_path):
        return False, None, f"Image file not found: {image_path}"

    if not os.path.isfile(image_path):
        return False, None, f"Image path is not a regular file: {image_path}"

    try:
        with open(image_path, "rb") as f:
            data = f.read()

        if len(data) == 0:
            return False, None, f"Image file is empty (0 bytes): {image_path}"

        # Check image magic bytes for common formats (JPEG: \xff\xd8\xff, PNG: \x89PNG)
        is_jpeg = data.startswith(b"\xff\xd8\xff")
        is_png = data.startswith(b"\x89PNG\r\n\x1a\n")
        if not (is_jpeg or is_png):
            return False, None, f"Unrecognized image header in: {image_path}"

        return True, data, None
    except Exception as exc:
        return False, None, f"Error reading image {image_path}: {type(exc).__name__} ({exc})"


class BaseVisionAdapter(ABC):
    """Abstract base class for vision model adapters."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if model credentials and required dependencies are available."""
        pass

    @abstractmethod
    def generate(self, prompt: str, images: List[VisualPayload]) -> str:
        """Call the vision model with text prompt and actual image payloads."""
        pass


class GoogleGenAIVisionAdapter(BaseVisionAdapter):
    """Adapter for Google GenAI SDK (gemini-2.5-flash or configured model)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        self.model_name = model_name or getattr(CONFIG, "vision_model_name", "gemini-2.5-flash")
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate(self, prompt: str, images: List[VisualPayload]) -> str:
        if not self.is_available():
            raise RuntimeError(
                "Google GenAI API key not configured. Set GEMINI_API_KEY or GOOGLE_API_KEY."
            )

        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(f"google-genai package is not installed: {exc}")

        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)

        # Build contents array interleaving text prompt and PIL images with evidence labels
        contents: List[Any] = [prompt]
        for img_payload in images:
            contents.append(f"\n--- Attached Image for {img_payload.label} ---")
            contents.append(img_payload.pil_image)

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=contents,
        )
        return response.text or ""


class OpenAIVisionAdapter(BaseVisionAdapter):
    """Adapter for OpenAI Vision API (e.g. gpt-4o, gpt-4o-mini)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4o",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model_name = model_name
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate(self, prompt: str, images: List[VisualPayload]) -> str:
        if not self.is_available():
            raise RuntimeError("OpenAI API key not configured. Set OPENAI_API_KEY.")

        try:
            import openai
        except ImportError as exc:
            raise RuntimeError(f"openai package is not installed: {exc}")

        if self._client is None:
            self._client = openai.OpenAI(api_key=self.api_key)

        content_parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img_payload in images:
            content_parts.append({
                "type": "text",
                "text": f"Attached Image for {img_payload.label}:",
            })
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_payload.base64_data}",
                },
            })

        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": content_parts}],
        )
        return response.choices[0].message.content or ""


class MockVisionAdapter(BaseVisionAdapter):
    """Offline test adapter that records image payloads and returns controlled responses."""

    def __init__(
        self,
        response_text: str = "Mock vision answer citing [Evidence 1].",
        available: bool = True,
        side_effect: Optional[Exception] = None,
        handler: Optional[Callable[[str, List[VisualPayload]], str]] = None,
    ):
        self.response_text = response_text
        self.available = available
        self.side_effect = side_effect
        self.handler = handler
        self.call_count = 0
        self.last_prompt: Optional[str] = None
        self.last_images: List[VisualPayload] = []

    def is_available(self) -> bool:
        return self.available

    def generate(self, prompt: str, images: List[VisualPayload]) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_images = list(images)

        if self.side_effect is not None:
            raise self.side_effect

        if self.handler is not None:
            return self.handler(prompt, images)

        return self.response_text


class CallableVisionAdapter(BaseVisionAdapter):
    """Wraps a callable (prompt, images) -> str as a vision adapter."""

    def __init__(self, fn: Callable[[str, List[VisualPayload]], str]):
        self.fn = fn
        self.call_count = 0
        self.last_images: List[VisualPayload] = []

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, images: List[VisualPayload]) -> str:
        self.call_count += 1
        self.last_images = list(images)
        return self.fn(prompt, images)


class LlamaIndexVisionAdapter(BaseVisionAdapter):
    """Wraps an existing LlamaIndex LLM instance that supports multimodal completion."""

    def __init__(self, llm: Any):
        self.llm = llm

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, images: List[VisualPayload]) -> str:
        # Check if llm accepts images argument
        try:
            pil_images = [img.pil_image for img in images]
            resp = self.llm.complete(prompt, images=pil_images)
            return getattr(resp, "text", str(resp))
        except TypeError:
            # Fallback if model only takes prompt
            resp = self.llm.complete(prompt)
            return getattr(resp, "text", str(resp))


def get_vision_adapter(vision_model: Any = None) -> Optional[BaseVisionAdapter]:
    """Resolve or construct the appropriate vision adapter."""
    if vision_model is not None:
        if isinstance(vision_model, BaseVisionAdapter):
            return vision_model
        if isinstance(vision_model, str):
            backend = vision_model.lower().strip()
            if backend == "gemini":
                return GoogleGenAIVisionAdapter()
            if backend == "openai":
                return OpenAIVisionAdapter()
            if backend == "mock":
                return MockVisionAdapter()
        if callable(vision_model):
            return CallableVisionAdapter(vision_model)
        if hasattr(vision_model, "complete"):
            return LlamaIndexVisionAdapter(vision_model)

    backend = getattr(CONFIG, "vision_backend", "gemini").lower().strip()
    if backend == "gemini":
        return GoogleGenAIVisionAdapter(
            model_name=getattr(CONFIG, "vision_model_name", "gemini-2.5-flash")
        )
    if backend == "openai":
        return OpenAIVisionAdapter()
    if backend == "mock":
        return MockVisionAdapter()

    return None
