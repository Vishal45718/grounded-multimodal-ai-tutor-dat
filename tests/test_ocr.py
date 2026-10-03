import pytest
import sys
from unittest.mock import patch, MagicMock

# Mock dependencies before they are imported in the function
mock_pytesseract = MagicMock()
mock_pil = MagicMock()
mock_image = MagicMock()
mock_pil.Image = mock_image
sys.modules['pytesseract'] = mock_pytesseract
sys.modules['PIL'] = mock_pil

from ingestion.ocr import ocr_keyframes, OcrResult
from ingestion.video_processor import Keyframe

def test_ocr_success_records_success_status():
    kf = Keyframe(timestamp_sec=1.5, image_path="/dummy/path.jpg")
    
    mock_pytesseract.image_to_string.return_value = "Some text on screen"
    mock_image.open.return_value = MagicMock()
    
    results = ocr_keyframes([kf])
        
    assert len(results) == 1
    assert results[0].status == "success"
    assert results[0].text == "Some text on screen"
    assert results[0].error_message is None

def test_ocr_failure_is_recorded():
    kf = Keyframe(timestamp_sec=2.0, image_path="/dummy/error.jpg")
    
    mock_pytesseract.image_to_string.side_effect = RuntimeError("Tesseract failed")
    mock_image.open.return_value = MagicMock()
    
    results = ocr_keyframes([kf])
        
    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].text == ""
    assert results[0].error_message == "RuntimeError"
    
    # reset side effect for other tests
    mock_pytesseract.image_to_string.side_effect = None

def test_ocr_failure_preserves_visual_asset():
    kf = Keyframe(timestamp_sec=3.0, image_path="/dummy/preserved.jpg")
    
    mock_pytesseract.image_to_string.side_effect = Exception("Timeout")
    mock_image.open.return_value = MagicMock()
    
    results = ocr_keyframes([kf])
        
    assert len(results) == 1
    assert results[0].image_path == "/dummy/preserved.jpg"
    assert results[0].timestamp_sec == 3.0
    
    # reset side effect for other tests
    mock_pytesseract.image_to_string.side_effect = None

def test_text_free_image_is_not_treated_as_ocr_failure():
    kf = Keyframe(timestamp_sec=4.0, image_path="/dummy/empty.jpg")
    
    mock_pytesseract.image_to_string.return_value = "   \n   "
    mock_image.open.return_value = MagicMock()
    
    results = ocr_keyframes([kf])
        
    assert len(results) == 1
    assert results[0].status == "success"
    assert results[0].text == ""
    assert results[0].error_message is None
