"""OCR over keyframes -- captures slide text, on-screen code, and diagram
labels that the audio transcript alone would miss. This is what makes M4
(multimodal evidence) possible: without it, a question like "what does the
function signature on screen at 12:40 say?" is unanswerable from transcript
text alone."""
from dataclasses import dataclass
from typing import List

from ingestion.video_processor import Keyframe


@dataclass
class OcrResult:
    timestamp_sec: float
    image_path: str
    text: str


def ocr_keyframes(keyframes: List[Keyframe]) -> List[OcrResult]:
    import pytesseract
    from PIL import Image

    results = []
    for kf in keyframes:
        try:
            text = pytesseract.image_to_string(Image.open(kf.image_path)).strip()
        except Exception:
            text = ""
        if text:  # skip frames with no on-screen text (e.g. talking-head shots)
            results.append(OcrResult(timestamp_sec=kf.timestamp_sec, image_path=kf.image_path, text=text))
    return results
