"""Merges ASR segments and OCR events into a single stream of time-aligned,
modality-tagged evidence chunks -- the atomic unit that M2's retriever will
index and M3's citer will point students back to."""
import uuid
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


def build_chunks(
    source_id: str,
    content_hash: str,
    transcript: List[TranscriptSegment],
    ocr_results: List[OcrResult],
) -> List[EvidenceChunk]:
    chunks: List[EvidenceChunk] = []

    # Audio chunks: merge consecutive short ASR segments up to
    # max_chunk_duration so we aren't indexing a chunk per two-second
    # utterance, while never letting a chunk drift so long that a citation
    # stops being a useful pointer.
    buf: List[TranscriptSegment] = []
    for seg in transcript:
        prospective_span = seg.end_sec - (buf[0].start_sec if buf else seg.start_sec)
        if buf and prospective_span > CONFIG.max_chunk_duration_sec:
            # Adding this segment would overshoot the cap -- flush what we
            # have first, so long ASR segments don't silently blow the
            # citation window out past what's still a useful [mm:ss] pointer.
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
    for ocr in ocr_results:
        chunks.append(
            EvidenceChunk(
                chunk_id=str(uuid.uuid4()),
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
    return EvidenceChunk(
        chunk_id=str(uuid.uuid4()),
        source_id=source_id,
        content_hash=content_hash,
        modality="audio",
        start_sec=buf[0].start_sec,
        end_sec=buf[-1].end_sec,
        text=" ".join(s.text for s in buf),
    )
