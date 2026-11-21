"""Central configuration for the multimodal tutor ingestion pipeline (M1)."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    corpus_db_path: str = os.environ.get("CORPUS_DB_PATH", "data/corpus.db")
    keyframes_dir: str = os.environ.get("KEYFRAMES_DIR", "data/keyframes")
    audio_dir: str = os.environ.get("AUDIO_DIR", "data/audio")
    whisper_model_size: str = os.environ.get("WHISPER_MODEL", "base")
    keyframe_interval_sec: float = 8.0     # fallback fixed-interval sampling
    scene_change_threshold: float = 0.35   # ffmpeg scene-detect sensitivity
    min_chunk_duration_sec: float = 3.0
    max_chunk_duration_sec: float = 30.0
    manifest_path: str = os.environ.get("MANIFEST_PATH", "data/source_manifest.json")
    vision_backend: str = os.environ.get("VISION_BACKEND", "gemini")
    vision_model_name: str = os.environ.get("VISION_MODEL_NAME", "gemini-2.5-flash")
    max_visual_images: int = int(os.environ.get("MAX_VISUAL_IMAGES", "5"))


CONFIG = Config()
