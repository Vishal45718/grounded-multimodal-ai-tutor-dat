"""Central configuration for the multimodal tutor ingestion and live inference pipeline."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def load_dotenv(dotenv_path: str = ".env") -> None:
    """Load environment variables from .env if present, without overwriting existing environment.
    Skips auto-loading during automated pytest execution to keep test suites hermetic and offline.
    """
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    # Try python-dotenv if installed
    try:
        from dotenv import load_dotenv as _sys_load_dotenv
        _sys_load_dotenv(dotenv_path, override=False)
        return
    except ImportError:
        pass

    # Built-in lightweight parser fallback
    path = Path(dotenv_path)
    if not path.is_file():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


load_dotenv()


@dataclass
class Config:
    # Storage & DB paths
    corpus_db_path: str = os.environ.get("CORPUS_DB_PATH", "data/corpus.db")
    keyframes_dir: str = os.environ.get("KEYFRAMES_DIR", "data/keyframes")
    audio_dir: str = os.environ.get("AUDIO_DIR", "data/audio")
    manifest_path: str = os.environ.get("MANIFEST_PATH", "data/source_manifest.json")
    memory_db_path: str = os.environ.get("MEMORY_DB_PATH", "data/learner_memory.db")

    # Ingestion settings
    whisper_model_size: str = os.environ.get("WHISPER_MODEL", "base")
    keyframe_interval_sec: float = 8.0     # fallback fixed-interval sampling
    scene_change_threshold: float = 0.35   # ffmpeg scene-detect sensitivity
    min_chunk_duration_sec: float = 3.0
    max_chunk_duration_sec: float = 30.0

    # Vision & Multimodal settings (legacy & general)
    vision_backend: str = os.environ.get("VISION_BACKEND", "gemini")
    vision_model_name: str = os.environ.get("VISION_MODEL_NAME", "gemini-2.5-flash")
    max_visual_images: int = int(os.environ.get("MAX_VISUAL_IMAGES", "5"))

    # Mentor Model Stack — Dynamic properties resolving environment variables
    _llm_api_key: Optional[str] = None
    _llm_base_url: Optional[str] = None
    _llm_model: Optional[str] = None

    _vision_api_key: Optional[str] = None
    _vision_base_url: Optional[str] = None
    _vision_model: Optional[str] = None

    _ocr_api_key: Optional[str] = None
    _ocr_base_url: Optional[str] = None
    _ocr_model: Optional[str] = None

    # 1. Main Text LLM: Gemma4-12B (FP8)
    @property
    def llm_api_key(self) -> str:
        if self._llm_api_key is not None:
            return self._llm_api_key
        return os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

    @llm_api_key.setter
    def llm_api_key(self, val: Optional[str]) -> None:
        self._llm_api_key = val

    @property
    def llm_base_url(self) -> str:
        if self._llm_base_url is not None:
            return self._llm_base_url
        return os.environ.get("LLM_BASE_URL", "")

    @llm_base_url.setter
    def llm_base_url(self, val: Optional[str]) -> None:
        self._llm_base_url = val

    @property
    def llm_model(self) -> str:
        if self._llm_model is not None:
            return self._llm_model
        return os.environ.get("LLM_MODEL", "google/gemma-4-12b-it-fp8")

    @llm_model.setter
    def llm_model(self, val: Optional[str]) -> None:
        self._llm_model = val

    # 2. Vision-Language Model (VLM): zai-org/GLM-4.6V-Flash
    @property
    def vision_api_key(self) -> str:
        if self._vision_api_key is not None:
            return self._vision_api_key
        return os.environ.get("VISION_API_KEY", os.environ.get("OPENAI_API_KEY", os.environ.get("GEMINI_API_KEY", "")))

    @vision_api_key.setter
    def vision_api_key(self, val: Optional[str]) -> None:
        self._vision_api_key = val

    @property
    def vision_base_url(self) -> str:
        if self._vision_base_url is not None:
            return self._vision_base_url
        return os.environ.get("VISION_BASE_URL", "")

    @vision_base_url.setter
    def vision_base_url(self, val: Optional[str]) -> None:
        self._vision_base_url = val

    @property
    def vision_model(self) -> str:
        if self._vision_model is not None:
            return self._vision_model
        return os.environ.get("VISION_MODEL", "zai-org/GLM-4.6V-Flash")

    @vision_model.setter
    def vision_model(self, val: Optional[str]) -> None:
        self._vision_model = val

    # 3. OCR VLM: PaddlePaddle/PaddleOCR-VL-1.6
    @property
    def ocr_api_key(self) -> str:
        if self._ocr_api_key is not None:
            return self._ocr_api_key
        return os.environ.get("OCR_API_KEY", "")

    @ocr_api_key.setter
    def ocr_api_key(self, val: Optional[str]) -> None:
        self._ocr_api_key = val

    @property
    def ocr_base_url(self) -> str:
        if self._ocr_base_url is not None:
            return self._ocr_base_url
        return os.environ.get("OCR_BASE_URL", "")

    @ocr_base_url.setter
    def ocr_base_url(self, val: Optional[str]) -> None:
        self._ocr_base_url = val

    @property
    def ocr_model(self) -> str:
        if self._ocr_model is not None:
            return self._ocr_model
        return os.environ.get("OCR_MODEL", "PaddlePaddle/PaddleOCR-VL-1.6")

    @ocr_model.setter
    def ocr_model(self, val: Optional[str]) -> None:
        self._ocr_model = val


CONFIG = Config()
