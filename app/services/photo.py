"""Vehicle condition assessment from uploaded photos.

Accepts one or more vehicle images, runs quality checks, vehicle detection,
and damage-signal analysis per image. Returns a consolidated condition report.

Like the video service, the damage detection is a DEMO heuristic — clearly
labeled. Swap `_assess_damage` for a trained model in production.
"""
import io
import cv2
import numpy as np
from PIL import Image


def _decode(image_bytes: bytes) -> np.ndarray:
    """Decode image bytes to a BGR numpy array, downscaled for memory safety."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img)
    arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    h, w = arr.shape[:2]
    if max(h, w) > 1200:
        scale = 1200 / max(h, w)
        arr = cv2.resize(arr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return arr


def _blur_score(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _brightness(gray: np.ndarray) -> float:
    return float(gray.mean())


def _vehicle_present(gray: np.ndarray) -> bool:
    """Heuristic: structured-object detection via edge density."""
    edges = cv2.Canny(gray, 100, 200)
    return float(edges.mean()) > 5.0


def _assess_damage(frame: np.ndarray) -> dict:
    """DEMO heuristic — edge/texture irregularity as a damage proxy.

    In production replace with a trained damage-detection model
    (YOLO-based, Detectron2, or a multimodal LLM vision call).
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Edge density
    edges = cv2.Canny(gray, 80, 200)
    edge_density = float(edges.mean())

    # Texture irregularity via local standard deviation
    blur = cv2.GaussianBlur(gray, (21, 21), 0)
    diff = cv2.absdiff(gray, blur)
    texture_score = float(diff.mean())

    # Color variance in small patches (scratches often show bare metal / paint contrast)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    sat_std = float(hsv[:, :, 1].std())

    # Combine signals
    combined = edge_density * 0.4 + texture_score * 0.35 + sat_std * 0.25

    if combined > 22:
        severity = "moderate"
        details = "Visible surface irregularities detected — recommend closer inspection."
    elif combined > 14:
        severity = "minor"
        details = "Minor surface variations noted — within normal wear range."
    else:
        severity = "none"
        details = "Vehicle surface appears clean with no significant irregularities."

    return {
        "severity": severity,
        "details": details,
        "signals": {
            "edge_density": round(edge_density, 2),
            "texture_score": round(texture_score, 2),
            "saturation_std": round(sat_std, 2),
            "combined": round(combined, 2),
        },
    }


def _detect_vehicle_angle(frame: np.ndarray) -> str:
    """Very rough angle estimation from aspect ratio and edge distribution.
    For demo labeling only.
    """
    h, w = frame.shape[:2]
    ratio = w / h
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 200)

    # Split into quadrants and check edge mass
    mid_h, mid_w = h // 2, w // 2
    top = edges[:mid_h, :].mean()
    bot = edges[mid_h:, :].mean()
    left = edges[:, :mid_w].mean()
    right = edges[:, mid_w:].mean()

    if ratio > 1.4:
        return "side view" if abs(left - right) < 3 else ("left side" if left > right else "right side")
    elif ratio < 0.8:
        return "close-up / detail"
    else:
        if top > bot * 1.3:
            return "front / rear"
        return "general view"


def analyze_photo(image_bytes: bytes) -> dict:
    """Analyze a single vehicle photo and return a condition report."""
    try:
        frame = _decode(image_bytes)
    except Exception as e:
        return {"error": f"Could not read image: {e}"}

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = _blur_score(gray)
    bright = _brightness(gray)
    vehicle = _vehicle_present(gray)
    angle = _detect_vehicle_angle(frame)
    h, w = frame.shape[:2]

    quality_issues = []
    if blur < 60:
        quality_issues.append("Image is blurry — retake with steadier hands")
    if bright < 40:
        quality_issues.append("Image is too dark — use better lighting")
    if bright > 220:
        quality_issues.append("Image is overexposed — reduce glare or flash")
    if not vehicle:
        quality_issues.append("No vehicle detected in frame")

    is_usable = len(quality_issues) == 0
    damage = _assess_damage(frame) if is_usable else {"severity": "unknown", "details": "Cannot assess — image quality insufficient.", "signals": {}}

    return {
        "resolution": f"{w}x{h}",
        "sharpness": round(blur, 1),
        "brightness": round(bright, 1),
        "vehicle_detected": vehicle,
        "estimated_angle": angle,
        "usable": is_usable,
        "quality_issues": quality_issues,
        "damage": damage,
    }


def analyze_photos(photo_list: list[bytes]) -> dict:
    """Analyze multiple vehicle photos and return a consolidated report."""
    if not photo_list:
        return {"error": "No photos provided."}

    reports = []
    severities = []
    usable_count = 0

    for i, img_bytes in enumerate(photo_list):
        r = analyze_photo(img_bytes)
        if "error" in r:
            reports.append({"photo": i + 1, "error": r["error"]})
            continue

        r["photo"] = i + 1
        reports.append(r)

        if r["usable"]:
            usable_count += 1
            severities.append(r["damage"]["severity"])

    sev_rank = {"none": 0, "minor": 1, "moderate": 2, "severe": 3, "unknown": -1}
    worst = max(severities, key=lambda s: sev_rank.get(s, -1)) if severities else "unknown"

    quality_ok = usable_count >= max(1, len(photo_list) // 2)

    if not quality_ok:
        recommendation = "RECAPTURE_NEEDED"
        summary = "Too many photos have quality issues. Please retake in better conditions."
    elif worst in ("moderate", "severe"):
        recommendation = "NEEDS_HUMAN_REVIEW"
        summary = "Surface irregularities detected. A human reviewer should inspect the flagged areas."
    elif worst == "minor":
        recommendation = "LIKELY_INSURABLE"
        summary = "Minor wear detected, within normal range. Vehicle appears insurable."
    else:
        recommendation = "LIKELY_INSURABLE"
        summary = "Vehicle surfaces appear clean. No significant damage signals detected."

    return {
        "photos_analyzed": len(reports),
        "usable_photos": usable_count,
        "quality_ok": quality_ok,
        "worst_damage_signal": worst,
        "recommendation": recommendation,
        "summary": summary,
        "photo_reports": reports,
    }
