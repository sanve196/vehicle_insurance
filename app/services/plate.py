"""Number plate extraction from vehicle photos.

Uses OCR on detected plate regions to extract the registration number
from a vehicle photo, then cross-checks against the declared registration.
"""
import re
import io
import cv2
import numpy as np
import pytesseract
from PIL import Image


# Indian registration number pattern: XX 00 XX 0000 (with optional spaces/dashes)
_REG_PATTERN = re.compile(
    r"[A-Z]{2}[\s\-]?\d{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?\d{1,4}"
)


def _preprocess_plate(gray: np.ndarray) -> np.ndarray:
    """Enhance a plate region for better OCR."""
    # Resize up if small
    h, w = gray.shape
    if w < 200:
        scale = 200 / w
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
    # Denoise + threshold
    gray = cv2.bilateralFilter(gray, 11, 75, 75)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return thresh


def _find_plate_candidates(gray: np.ndarray) -> list[np.ndarray]:
    """Find rectangular contours that could be number plates."""
    candidates = []

    # Edge detection
    edges = cv2.Canny(gray, 100, 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h_img, w_img = gray.shape
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        aspect = w / max(h, 1)
        area = w * h
        # Indian plates are roughly 3:1 to 5:1 aspect ratio
        if 2.0 < aspect < 6.0 and area > 800 and w > 60:
            # Not too close to edges, reasonable size relative to image
            if area < (h_img * w_img * 0.4):
                roi = gray[y:y+h, x:x+w]
                candidates.append(roi)

    # Sort by area descending (largest plate-like region first)
    candidates.sort(key=lambda c: c.shape[0] * c.shape[1], reverse=True)
    return candidates[:5]  # top 5 candidates


def _normalize_reg(s: str) -> str:
    """Strip spaces, dashes, and uppercase for comparison."""
    return re.sub(r"[\s\-]", "", s.strip().upper())


def extract_plate_number(image_bytes: bytes) -> dict:
    """Attempt to extract a registration number from a vehicle photo.

    Returns:
        {
            "found": bool,
            "plate_text": str or None,  # raw OCR text from plate region
            "plate_number": str or None,  # cleaned registration number
            "confidence": str,  # "high", "medium", "low"
        }
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        # Downscale if very large
        h, w = arr.shape[:2]
        if max(h, w) > 1500:
            scale = 1500 / max(h, w)
            arr = cv2.resize(arr, (int(w * scale), int(h * scale)))
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    except Exception as e:
        return {"found": False, "plate_text": None, "plate_number": None, "confidence": "none", "error": str(e)}

    # Strategy 1: Find plate region candidates and OCR each
    candidates = _find_plate_candidates(gray)
    for roi in candidates:
        processed = _preprocess_plate(roi)
        text = pytesseract.image_to_string(processed, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ")
        text = text.strip().upper()
        match = _REG_PATTERN.search(text)
        if match:
            return {
                "found": True,
                "plate_text": text,
                "plate_number": _normalize_reg(match.group()),
                "confidence": "high",
            }

    # Strategy 2: Full image OCR fallback (plate might not have been isolated)
    full_text = pytesseract.image_to_string(gray, config="--psm 6")
    full_text_upper = full_text.upper()
    match = _REG_PATTERN.search(full_text_upper)
    if match:
        return {
            "found": True,
            "plate_text": match.group(),
            "plate_number": _normalize_reg(match.group()),
            "confidence": "medium",
        }

    return {"found": False, "plate_text": None, "plate_number": None, "confidence": "none"}


def match_plate_to_registration(image_bytes: bytes, expected_reg: str) -> dict:
    """Extract plate from photo and check if it matches the expected registration.

    Returns:
        {
            "plate_found": bool,
            "plate_number": str or None,
            "expected": str,
            "match": bool or None,  # None if plate not found
            "confidence": str,
            "detail": str,
        }
    """
    expected_norm = _normalize_reg(expected_reg)
    result = extract_plate_number(image_bytes)

    if not result["found"]:
        return {
            "plate_found": False,
            "plate_number": None,
            "expected": expected_norm,
            "match": None,
            "confidence": "none",
            "detail": "Could not detect a number plate in this photo.",
        }

    plate_norm = result["plate_number"]
    is_match = plate_norm == expected_norm

    # Partial match check (OCR might miss a character)
    partial = False
    if not is_match and len(plate_norm) >= 6 and len(expected_norm) >= 6:
        # Check if they share a significant prefix or the difference is ≤2 chars
        common = sum(1 for a, b in zip(plate_norm, expected_norm) if a == b)
        if common >= len(expected_norm) - 2:
            partial = True

    if is_match:
        detail = f"Number plate {plate_norm} matches the declared registration."
    elif partial:
        detail = f"Number plate {plate_norm} partially matches {expected_norm} — possible OCR noise, verify manually."
        is_match = None  # uncertain
    else:
        detail = f"Number plate {plate_norm} does NOT match declared registration {expected_norm} — possible wrong vehicle."

    return {
        "plate_found": True,
        "plate_number": plate_norm,
        "expected": expected_norm,
        "match": is_match,
        "confidence": result["confidence"],
        "detail": detail,
    }
