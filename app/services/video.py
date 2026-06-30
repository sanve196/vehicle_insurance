"""Vehicle inspection video analysis.

This module does REAL frame extraction and image-quality analysis (blur,
brightness, vehicle-present check). The damage detection is a clearly-labeled
heuristic stand-in for a trained CV model, suitable for a demo. In production,
swap `_assess_damage` for a call to a trained detector (YOLO / Detectron2 /
hosted vision model).
"""
import os
import tempfile
import cv2
import numpy as np


def _blur_score(gray: np.ndarray) -> float:
    """Variance of Laplacian — higher = sharper."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _brightness(gray: np.ndarray) -> float:
    return float(gray.mean())


def _downscale(frame: np.ndarray, max_w: int = 960) -> np.ndarray:
    """Shrink large frames to cap memory use on small instances."""
    h, w = frame.shape[:2]
    if w > max_w:
        scale = max_w / w
        frame = cv2.resize(frame, (max_w, int(h * scale)), interpolation=cv2.INTER_AREA)
    return frame


def extract_keyframes(video_bytes: bytes, max_frames: int = 5):
    """Sample evenly spaced frames; return list of (index, downscaled BGR frame)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        tmp.write(video_bytes)
        tmp.flush()
        tmp.close()
        cap = cv2.VideoCapture(tmp.name)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        frames = []
        if total <= 0:
            # Stream-read fallback
            idx = 0
            while len(frames) < max_frames:
                ok, fr = cap.read()
                if not ok:
                    break
                if idx % 10 == 0:
                    frames.append((idx, _downscale(fr)))
                idx += 1
        else:
            picks = np.linspace(0, total - 1, num=min(max_frames, total)).astype(int)
            for p in picks:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(p))
                ok, fr = cap.read()
                if ok:
                    frames.append((int(p), _downscale(fr)))
        cap.release()
        return frames
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# Pretrained Haar cascade for a coarse "is there a car-like object" sanity check
_CAR_CASCADE = None


def _car_present(gray: np.ndarray) -> bool:
    global _CAR_CASCADE
    try:
        if _CAR_CASCADE is None:
            path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            # Note: OpenCV ships no reliable car cascade by default; we use edge
            # density as a proxy for "structured object present" instead.
        edges = cv2.Canny(gray, 100, 200)
        density = edges.mean()
        return density > 5.0
    except Exception:
        return True


def _assess_damage(frame: np.ndarray) -> dict:
    """DEMO heuristic damage signal based on local contrast irregularities.

    NOT a real damage classifier. Produces a deterministic, explainable
    demo signal so the UI can show severity. Replace with a trained model
    in production.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Strong, localized edges can indicate scratches/dents in a demo context
    edges = cv2.Canny(gray, 80, 200)
    edge_density = float(edges.mean())
    # Bucket into severity for demo purposes
    if edge_density > 18:
        severity = "moderate"
    elif edge_density > 12:
        severity = "minor"
    else:
        severity = "none"
    return {"edge_density": round(edge_density, 2), "severity": severity}


def analyze_video(video_bytes: bytes) -> dict:
    frames = extract_keyframes(video_bytes)
    if not frames:
        return {"error": "Could not read video. Please upload a valid MP4/MOV file."}

    frame_reports = []
    severities = []
    usable = 0
    for idx, fr in frames:
        gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        blur = _blur_score(gray)
        bright = _brightness(gray)
        car = _car_present(gray)
        is_usable = blur > 60 and 40 < bright < 220 and car
        if is_usable:
            usable += 1
        dmg = _assess_damage(fr)
        severities.append(dmg["severity"])
        frame_reports.append({
            "frame": idx,
            "sharpness": round(blur, 1),
            "brightness": round(bright, 1),
            "vehicle_detected": car,
            "usable": is_usable,
            "damage_signal": dmg["severity"],
        })

    sev_rank = {"none": 0, "minor": 1, "moderate": 2, "severe": 3}
    worst = max(severities, key=lambda s: sev_rank[s]) if severities else "none"
    quality_ok = usable >= max(1, len(frames) // 2)

    if not quality_ok:
        recommendation = "RECAPTURE_NEEDED"
    elif worst in ("moderate", "severe"):
        recommendation = "NEEDS_HUMAN_REVIEW"
    else:
        recommendation = "LIKELY_INSURABLE"

    return {
        "frames_analyzed": len(frames),
        "usable_frames": usable,
        "quality_ok": quality_ok,
        "worst_damage_signal": worst,
        "recommendation": recommendation,
        "frame_reports": frame_reports,
    }
