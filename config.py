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


CONFIG = Config()
