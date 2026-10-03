"""OCR over keyframes -- captures slide text, on-screen code, and diagram
labels that the audio transcript alone would miss. This is what makes M4
(multimodal evidence) possible: without it, a question like "what does the
function signature on screen at 12:40 say?" is unanswerable from transcript
text alone."""
from dataclasses import dataclass
from typing import List, Optional

from ingestion.video_processor import Keyframe


@dataclass
class OcrResult:
    timestamp_sec: Optional[float]
    image_path: str
    text: str
    status: str = "success"
    error_message: Optional[str] = None


def ocr_keyframes(keyframes: List[Keyframe]) -> List[OcrResult]:
    import pytesseract
    from PIL import Image

    results = []
    for kf in keyframes:
        try:
            text = pytesseract.image_to_string(Image.open(kf.image_path)).strip()
            results.append(OcrResult(timestamp_sec=kf.timestamp_sec, image_path=kf.image_path, text=text, status="success"))
        except Exception as e:
            results.append(OcrResult(timestamp_sec=kf.timestamp_sec, image_path=kf.image_path, text="", status="failed", error_message=type(e).__name__))
    return results
