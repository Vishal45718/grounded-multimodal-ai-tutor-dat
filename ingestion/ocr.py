"""OCR over keyframes -- captures slide text, on-screen code, and diagram
labels that the audio transcript alone would miss. This is what makes M4
(multimodal evidence) possible: without it, a question like "what does the
function signature on screen at 12:40 say?" is unanswerable from transcript
text alone."""
import os
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
    page_number: Optional[int] = None


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


def extract_pdf_slides(
    pdf_path: str,
    source_id: str,
    content_hash: str,
    base_dir: Optional[str] = None,
) -> List[OcrResult]:
    """Render each PDF page into a real JPEG image and extract embedded text.

    Stores the rendered images persistently under the version-isolated directory:
    <base_dir or CONFIG.keyframes_dir>/<source_id>/<content_hash>/slide_00001.jpg

    Preserves empty-text pages and processing failures distinctly using the existing
    evidence status conventions. Video timestamps remain unknown (None) as a PDF
    page number is not a video timestamp.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    from ingestion.video_processor import get_keyframe_asset_dir

    frame_dir = get_keyframe_asset_dir(source_id, content_hash, base_dir=base_dir)
    os.makedirs(frame_dir, exist_ok=True)

    results: List[OcrResult] = []
    doc = fitz.open(pdf_path)
    try:
        for idx, page in enumerate(doc):
            page_num = idx + 1
            image_name = f"slide_{page_num:05d}.jpg"
            image_path = os.path.join(frame_dir, image_name)

            try:
                # Render page to a real JPEG image without alpha channel
                pix = page.get_pixmap(alpha=False)
                pix.save(image_path)

                # Extract embedded text from page
                raw_text = page.get_text()
                text = raw_text.strip() if raw_text else ""

                results.append(
                    OcrResult(
                        timestamp_sec=None,
                        image_path=image_path,
                        text=text,
                        status="success",
                        error_message=None,
                        page_number=page_num,
                    )
                )
            except Exception as e:
                # Preserve visual asset path and record processing failure distinctly
                results.append(
                    OcrResult(
                        timestamp_sec=None,
                        image_path=image_path,
                        text="",
                        status="failed",
                        error_message=type(e).__name__,
                        page_number=page_num,
                    )
                )
    finally:
        doc.close()

    return results

