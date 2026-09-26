"""Time-aligned ASR. Produces segments with exact start/end timestamps so
M3's [mm:ss] citations point at the right moment in the lecture, not just
'somewhere in this video'."""
from dataclasses import dataclass
from typing import List

from config import CONFIG


@dataclass
class TranscriptSegment:
    start_sec: float
    end_sec: float
    text: str


def transcribe(audio_path: str) -> List[TranscriptSegment]:
    from faster_whisper import WhisperModel  # imported lazily: heavy dependency

    model = WhisperModel(CONFIG.whisper_model_size, compute_type="int8")
    segments, _info = model.transcribe(audio_path, word_timestamps=False)
    return [
        TranscriptSegment(start_sec=seg.start, end_sec=seg.end, text=seg.text.strip())
        for seg in segments
    ]
