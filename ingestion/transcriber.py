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

def parse_srt(srt_path: str) -> List[TranscriptSegment]:
    segments = []
    with open(srt_path, 'r', encoding='utf-8') as f:
        blocks = f.read().strip().split('\n\n')
        for block in blocks:
            lines = block.split('\n')
            if len(lines) >= 3:
                time_range = lines[1]
                text = " ".join(lines[2:]).replace('\n', ' ').strip()
                if ' --> ' in time_range:
                    start_str, end_str = time_range.split(' --> ')
                    def time_to_sec(t_str):
                        h, m, s = t_str.replace(',', '.').split(':')
                        return float(h)*3600 + float(m)*60 + float(s)
                    start_sec = time_to_sec(start_str)
                    end_sec = time_to_sec(end_str)
                    segments.append(TranscriptSegment(start_sec, end_sec, text))
    return segments
