"""OCR + field extraction for vehicle documents (RC book, etc.)."""
import re
import io
import cv2
import numpy as np
import pytesseract
from PIL import Image


def _preprocess(image_bytes: bytes) -> np.ndarray:
    """Decode image bytes and apply light preprocessing to improve OCR."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    # Upscale small images, then denoise + threshold
    h, w = gray.shape
    if max(h, w) < 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    thr = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return thr


def run_ocr(image_bytes: bytes) -> str:
    """Return raw OCR text from an image."""
    try:
        processed = _preprocess(image_bytes)
        text = pytesseract.image_to_string(processed)
        # Fallback to original if preprocessing yielded little
        if len(text.strip()) < 10:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            text = pytesseract.image_to_string(img)
        return text
    except Exception as e:  # pragma: no cover
        return f"[OCR_ERROR] {e}"


# --- Field extraction heuristics --------------------------------------------

_LABELS = {
    "registration_number": [
        r"reg(?:istration)?\.?\s*(?:no|number)\.?\s*[:\-]?\s*([A-Z]{2}[ -]?\d{1,2}[ -]?[A-Z]{0,3}[ -]?\d{1,4})",
        r"\b([A-Z]{2}[ -]?\d{1,2}[ -]?[A-Z]{1,3}[ -]?\d{3,4})\b",
    ],
    "chassis_number": [r"chassis\s*(?:no|number)?\.?\s*[:\-]?\s*([A-Z0-9]{8,20})"],
    "engine_number": [r"engine\s*(?:no|number)?\.?\s*[:\-]?\s*([A-Z0-9]{6,20})"],
    "owner_name": [
        r"(?:owner(?:'s)?\s*name|name\s*of\s*owner)\s*[:\-]?\s*([A-Z][A-Za-z .]{2,40})",
        r"\bowner\s*[:\-]?\s*([A-Z][A-Za-z .]{2,40})",
    ],
    "make_model": [
        r"(?:maker|make|model|maker\s*'?s?\s*name|m\.?\s*name)\s*[:\-/]*\s*([A-Z][A-Za-z0-9 .\-]{2,30})",
    ],
    "fuel_type": [r"\b(petrol|diesel|electric|cng|lpg|hybrid)\b"],
    "registration_date": [
        r"(?:reg(?:istration)?\s*date|date\s*of\s*reg)\s*[:\-]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
    ],
}


def extract_fields(text: str) -> dict:
    """Extract structured fields from raw OCR text using regex heuristics."""
    up = text.upper()
    result = {}
    for field, patterns in _LABELS.items():
        value = None
        for pat in patterns:
            m = re.search(pat, up, re.IGNORECASE)
            if m:
                value = m.group(1).strip()
                break
        result[field] = value
    # Normalise registration number spacing
    if result.get("registration_number"):
        result["registration_number"] = re.sub(
            r"[ \-]", "", result["registration_number"]
        ).upper()
    if result.get("fuel_type"):
        result["fuel_type"] = result["fuel_type"].title()
    return result
