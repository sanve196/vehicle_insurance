"""Cross-verify user-entered application data against OCR-extracted fields."""
from rapidfuzz import fuzz


# How each form field maps to an extracted field + match strategy
_FIELD_MAP = {
    "registration_number": ("registration_number", "exact_norm"),
    "chassis_number": ("chassis_number", "exact_norm"),
    "engine_number": ("engine_number", "exact_norm"),
    "owner_name": ("owner_name", "fuzzy"),
    "fuel_type": ("fuel_type", "fuzzy"),
}

_THRESHOLDS = {"fuzzy": 80}


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s).upper() if ch.isalnum())


def verify(form_data: dict, extracted: dict) -> dict:
    """Return per-field comparison + overall confidence."""
    fields = []
    matched, comparable = 0, 0

    for form_key, (ext_key, strategy) in _FIELD_MAP.items():
        form_val = (form_data.get(form_key) or "").strip()
        ext_val = (extracted.get(ext_key) or "").strip()

        if not form_val:
            continue

        if not ext_val:
            fields.append({
                "field": form_key,
                "entered": form_val,
                "extracted": None,
                "status": "NOT_FOUND",
                "score": 0,
            })
            continue

        comparable += 1
        if strategy == "exact_norm":
            score = 100 if _norm(form_val) == _norm(ext_val) else fuzz.ratio(_norm(form_val), _norm(ext_val))
            ok = _norm(form_val) == _norm(ext_val)
        else:  # fuzzy
            score = fuzz.token_sort_ratio(form_val.upper(), ext_val.upper())
            ok = score >= _THRESHOLDS["fuzzy"]

        if ok:
            matched += 1
        fields.append({
            "field": form_key,
            "entered": form_val,
            "extracted": ext_val,
            "status": "MATCH" if ok else "MISMATCH",
            "score": round(score),
        })

    confidence = round((matched / comparable) * 100) if comparable else 0
    if confidence >= 80:
        verdict = "AUTO_VERIFIED"
    elif confidence >= 50:
        verdict = "NEEDS_REVIEW"
    else:
        verdict = "FLAGGED"

    return {
        "fields": fields,
        "matched": matched,
        "comparable": comparable,
        "confidence": confidence,
        "verdict": verdict,
    }


def classify_document(text: str) -> dict:
    """Very lightweight document-type detection by keyword presence."""
    up = text.upper()
    signals = {
        "RC_BOOK": ["REGISTRATION CERTIFICATE", "CHASSIS", "ENGINE NO", "REGN", "RC"],
        "DRIVING_LICENSE": ["DRIVING LICENCE", "DRIVING LICENSE", "DL NO", "VALID TILL"],
        "INSURANCE": ["POLICY NO", "INSURED", "PREMIUM", "INSURANCE"],
        "PUC": ["POLLUTION", "PUC", "EMISSION"],
    }
    scores = {k: sum(1 for kw in kws if kw in up) for k, kws in signals.items()}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return {"type": "UNKNOWN", "confidence": 0, "scores": scores}
    total = sum(scores.values()) or 1
    return {
        "type": best,
        "confidence": round((scores[best] / total) * 100),
        "scores": scores,
    }
