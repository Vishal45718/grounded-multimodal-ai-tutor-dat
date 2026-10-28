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
    out_dir: Optional[str] = None,
    source_id: Optional[str] = None,
    content_hash: Optional[str] = None,
    dpi: int = 150,
) -> List[OcrResult]:
    """Renders PDF slide pages to images and extracts embedded text using PyMuPDF.

    Each page is saved as a JPEG in a version-isolated directory:
    <out_dir or CONFIG.keyframes_dir>/<source_id>/<content_hash>/slide_{page:05d}.jpg
    """
    import os
    import fitz  # PyMuPDF
    from config import CONFIG
    from ingestion.versioning import file_content_hash
    from ingestion.video_processor import get_keyframe_asset_dir

    sid = source_id or os.path.splitext(os.path.basename(pdf_path))[0]
    chash = content_hash or file_content_hash(pdf_path)
    frame_dir = get_keyframe_asset_dir(sid, chash, base_dir=out_dir)
    os.makedirs(frame_dir, exist_ok=True)

    results: List[OcrResult] = []
    doc = fitz.open(pdf_path)
    for idx, page in enumerate(doc):
        page_num = idx + 1
        img_filename = f"slide_{page_num:05d}.jpg"
        img_path = os.path.join(frame_dir, img_filename)

        try:
            pix = page.get_pixmap(dpi=dpi)
            pix.save(img_path)
            raw_text = page.get_text() or ""
            text = raw_text.strip()
            status = "success" if text else "empty"
            results.append(
                OcrResult(
                    timestamp_sec=None,
                    image_path=img_path,
                    text=text,
                    status=status,
                    page_number=page_num,
                )
            )
        except Exception as e:
            results.append(
                OcrResult(
                    timestamp_sec=None,
                    image_path=img_path,
                    text="",
                    status="failed",
                    error_message=str(e),
                    page_number=page_num,
                )
            )

    doc.close()
    return results

