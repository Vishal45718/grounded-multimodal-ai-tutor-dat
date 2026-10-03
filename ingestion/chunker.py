"""Merges ASR segments and OCR events into a single stream of time-aligned,
modality-tagged evidence chunks -- the atomic unit that M2's retriever will
index and M3's citer will point students back to."""
import hashlib
import math
import os
from dataclasses import dataclass
from typing import List, Optional

from config import CONFIG
from ingestion.ocr import OcrResult
from ingestion.transcriber import TranscriptSegment


@dataclass
class EvidenceChunk:
    chunk_id: str
    source_id: str
    content_hash: str
    modality: str  # "audio" | "visual"
    start_sec: float
    end_sec: float
    text: str
    image_path: Optional[str] = None


def compute_chunk_id(
    source_id: str,
    content_hash: str,
    modality: str,
    start_sec: float,
    end_sec: float,
    text: str = "",
    extra: str = "",
) -> str:
    """Computes a deterministic, collision-resistant chunk ID derived from
    stable evidence identity.

    Stable across identical rebuilds without depending on process randomness.
    """
    identity_str = (
        f"{source_id}:{content_hash}:{modality}:"
        f"{round(start_sec, 3):.3f}:{round(end_sec, 3):.3f}:"
        f"{text.strip()}:{extra.strip()}"
    )
    return hashlib.sha256(identity_str.encode("utf-8")).hexdigest()[:32]


def split_long_segment(
    seg: TranscriptSegment,
    max_duration: float = CONFIG.max_chunk_duration_sec,
) -> List[TranscriptSegment]:
    """Splits an individual transcript segment if its duration exceeds max_duration.

    Deterministic splitting method:
    When only segment-level start/end timestamps are available (no word-level timestamps),
    the segment is divided into N = ceil(duration / max_duration) equal-duration sub-intervals.
    The segment's words are partitioned proportionally across the N sub-intervals, preserving
    word ordering without hallucinating word-level timestamps or dropping text.
    """
    duration = seg.end_sec - seg.start_sec
    if duration <= max_duration:
        return [seg]

    n_parts = math.ceil(duration / max_duration)
    if n_parts <= 1:
        return [seg]

    dt = duration / n_parts
    words = seg.text.split()
    w_count = len(words)

    sub_segments: List[TranscriptSegment] = []
    for i in range(n_parts):
        sub_start = round(seg.start_sec + i * dt, 3)
        sub_end = round(seg.start_sec + (i + 1) * dt, 3) if i < n_parts - 1 else round(seg.end_sec, 3)

        if w_count > 0:
            w_start = (i * w_count) // n_parts
            w_end = ((i + 1) * w_count) // n_parts if i < n_parts - 1 else w_count
            sub_words = words[w_start:w_end]
            if not sub_words:
                sub_words = [words[min(i, w_count - 1)]]
            sub_text = " ".join(sub_words)
        else:
            sub_text = ""

        sub_segments.append(
            TranscriptSegment(
                start_sec=sub_start,
                end_sec=sub_end,
                text=sub_text,
            )
        )

    return sub_segments


def build_chunks(
    source_id: str,
    content_hash: str,
    transcript: List[TranscriptSegment],
    ocr_results: List[OcrResult],
) -> List[EvidenceChunk]:
    chunks: List[EvidenceChunk] = []

    # Audio chunks: ensure no individual segment exceeds max_chunk_duration_sec first
    normalized_transcript: List[TranscriptSegment] = []
    for seg in transcript:
        normalized_transcript.extend(split_long_segment(seg, CONFIG.max_chunk_duration_sec))

    buf: List[TranscriptSegment] = []
    for seg in normalized_transcript:
        prospective_span = seg.end_sec - (buf[0].start_sec if buf else seg.start_sec)
        if buf and prospective_span > CONFIG.max_chunk_duration_sec:
            chunks.append(_flush_audio(buf, source_id, content_hash))
            buf = []
        buf.append(seg)
        span = buf[-1].end_sec - buf[0].start_sec
        if span >= CONFIG.max_chunk_duration_sec:
            chunks.append(_flush_audio(buf, source_id, content_hash))
            buf = []
    if buf:
        chunks.append(_flush_audio(buf, source_id, content_hash))

    # Visual chunks: one per OCR'd keyframe, timestamped at that exact
    # frame so M3's citation can seek a video player straight to it.
    for idx, ocr in enumerate(ocr_results):
        image_name = os.path.basename(ocr.image_path) if ocr.image_path else str(idx)
        chunk_id = compute_chunk_id(
            source_id=source_id,
            content_hash=content_hash,
            modality="visual",
            start_sec=ocr.timestamp_sec,
            end_sec=ocr.timestamp_sec,
            text=ocr.text,
            extra=image_name,
        )
        chunks.append(
            EvidenceChunk(
                chunk_id=chunk_id,
                source_id=source_id,
                content_hash=content_hash,
                modality="visual",
                start_sec=ocr.timestamp_sec,
                end_sec=ocr.timestamp_sec,
                text=ocr.text,
                image_path=ocr.image_path,
            )
        )

    return chunks


def _flush_audio(buf: List[TranscriptSegment], source_id: str, content_hash: str) -> EvidenceChunk:
    text = " ".join(s.text for s in buf).strip()
    start_sec = buf[0].start_sec
    end_sec = buf[-1].end_sec
    chunk_id = compute_chunk_id(
        source_id=source_id,
        content_hash=content_hash,
        modality="audio",
        start_sec=start_sec,
        end_sec=end_sec,
        text=text,
    )
    return EvidenceChunk(
        chunk_id=chunk_id,
        source_id=source_id,
        content_hash=content_hash,
        modality="audio",
        start_sec=start_sec,
        end_sec=end_sec,
        text=text,
    )
