"""Splits a lecture video into an audio track (for ASR) and timestamped
keyframes (for OCR / visual evidence). Feeds the M1 versioned corpus and
directly enables M4 (multimodal evidence)."""
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from config import CONFIG
from ingestion.versioning import file_content_hash


@dataclass
class Keyframe:
    timestamp_sec: float
    image_path: str


def get_audio_asset_dir(source_id: str, content_hash: str, base_dir: Optional[str] = None) -> str:
    """Returns the version-isolated audio directory:
    <base_dir or CONFIG.audio_dir>/<source_id>/<content_hash>
    """
    root = base_dir or CONFIG.audio_dir
    return os.path.join(root, source_id, content_hash)


def get_audio_asset_path(
    video_path: str,
    source_id: str,
    content_hash: str,
    base_dir: Optional[str] = None,
) -> str:
    """Returns the version-isolated audio file path."""
    audio_dir = get_audio_asset_dir(source_id, content_hash, base_dir)
    base = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(audio_dir, f"{base}.wav")


def get_keyframe_asset_dir(
    source_id: str,
    content_hash: str,
    base_dir: Optional[str] = None,
) -> str:
    """Returns the version-isolated keyframe directory:
    <base_dir or CONFIG.keyframes_dir>/<source_id>/<content_hash>
    """
    root = base_dir or CONFIG.keyframes_dir
    return os.path.join(root, source_id, content_hash)


def extract_audio(
    video_path: str,
    out_dir: Optional[str] = None,
    source_id: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> str:
    base = os.path.splitext(os.path.basename(video_path))[0]
    sid = source_id or base
    chash = content_hash or file_content_hash(video_path)
    audio_path = get_audio_asset_path(video_path, sid, chash, base_dir=out_dir)
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", audio_path],
        check=True, capture_output=True,
    )
    return audio_path


def extract_keyframes(
    video_path: str,
    out_dir: Optional[str] = None,
    source_id: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> List[Keyframe]:
    """Scene-change keyframes first (catches slide transitions and new code
    appearing on screen). If ffmpeg finds too few scenes -- e.g. a static
    talking-head segment with code on screen the whole time -- fall back to
    fixed-interval sampling so visual evidence is never silently missed."""
    base = os.path.splitext(os.path.basename(video_path))[0]
    sid = source_id or base
    chash = content_hash or file_content_hash(video_path)
    frame_dir = get_keyframe_asset_dir(sid, chash, base_dir=out_dir)
    os.makedirs(frame_dir, exist_ok=True)

    scene_pattern = os.path.join(frame_dir, "scene_%05d.jpg")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"select='gt(scene,{CONFIG.scene_change_threshold})',showinfo",
            "-vsync", "vfr", scene_pattern,
        ],
        check=True, capture_output=True,
    )
    frames = _scene_timestamps(video_path, frame_dir, "scene_")

    if len(frames) < 2:
        frames = _fixed_interval_keyframes(video_path, frame_dir)

    return frames


def _scene_timestamps(video_path: str, frame_dir: str, prefix: str) -> List[Keyframe]:
    """Re-run the same select filter with showinfo -> stderr to recover the
    pts_time of each selected frame, then pair those timestamps in order
    with the saved frame files (ffmpeg numbers output frames sequentially)."""
    proc = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", f"select='gt(scene,{CONFIG.scene_change_threshold})',showinfo",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    timestamps = []
    for line in proc.stderr.splitlines():
        if "pts_time:" in line:
            token = line.split("pts_time:")[1].split()[0]
            timestamps.append(float(token))

    files = sorted(f for f in os.listdir(frame_dir) if f.startswith(prefix))
    return [
        Keyframe(timestamp_sec=ts, image_path=os.path.join(frame_dir, fn))
        for ts, fn in zip(timestamps, files)
    ]


def _fixed_interval_keyframes(video_path: str, frame_dir: str) -> List[Keyframe]:
    duration = _probe_duration(video_path)
    pattern = os.path.join(frame_dir, "fixed_%05d.jpg")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vf", f"fps=1/{CONFIG.keyframe_interval_sec}", pattern],
        check=True, capture_output=True,
    )
    files = sorted(f for f in os.listdir(frame_dir) if f.startswith("fixed_"))
    return [
        Keyframe(timestamp_sec=i * CONFIG.keyframe_interval_sec, image_path=os.path.join(frame_dir, fn))
        for i, fn in enumerate(files)
        if i * CONFIG.keyframe_interval_sec <= duration
    ]


def _probe_duration(video_path: str) -> float:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(proc.stdout.strip())
