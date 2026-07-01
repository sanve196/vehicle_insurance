"""Agent 3 — Vehicle Inspection Agent.

Receives uploaded vehicle photos, assesses quality and condition,
enforces required angles, extracts number plate and cross-checks
against declared registration, and produces a condition report.
"""
from app.agents import BaseAgent, AgentResult, AgentStatus
from app.services.photo import analyze_photos
from app.services.plate import match_plate_to_registration


# These angles MUST be covered for a complete inspection
REQUIRED_ANGLES = {
    "front / rear": "Front or rear view of the vehicle",
    "side view": "Left or right side view",
}
MINIMUM_PHOTOS = 4
RECOMMENDED_PHOTOS = 6


class InspectionAgent(BaseAgent):
    name = "inspection_agent"
    role = "Assess vehicle condition from photos: quality, damage, angle coverage, and number plate verification."

    def run(self, context: dict) -> AgentResult:
        photo_list = context.get("photo_bytes_list", [])
        reg_number = context.get("registration_number", "")

        if not photo_list:
            return AgentResult(
                agent=self.name, status=AgentStatus.SKIPPED,
                verdict="NO_PHOTOS",
                summary="No vehicle photos uploaded — skipping condition assessment.",
            )

        result = analyze_photos(photo_list)
        if "error" in result:
            return AgentResult(
                agent=self.name, status=AgentStatus.FAILED,
                verdict="ANALYSIS_FAILED", summary=result["error"],
            )

        issues = []
        suggestions = []

        # --- Check 1: Minimum photo count ---
        if result["photos_analyzed"] < MINIMUM_PHOTOS:
            issues.append(
                f"Only {result['photos_analyzed']} photo(s) uploaded — minimum {MINIMUM_PHOTOS} required "
                f"(recommended {RECOMMENDED_PHOTOS}: front, rear, left side, right side, odometer, close-up of any damage)."
            )
        elif result["photos_analyzed"] < RECOMMENDED_PHOTOS:
            suggestions.append(
                f"{result['photos_analyzed']} photos uploaded. For best coverage, upload {RECOMMENDED_PHOTOS}: "
                f"front, rear, left side, right side, odometer, and close-up of any existing damage."
            )

        # --- Check 2: Quality ---
        if not result["quality_ok"]:
            issues.append(f"Only {result['usable_photos']}/{result['photos_analyzed']} photos are usable — too many quality issues.")

        # --- Check 3: Required angle coverage ---
        detected_angles = set()
        for pr in result.get("photo_reports", []):
            if pr.get("estimated_angle"):
                detected_angles.add(pr["estimated_angle"])
                # Also map sub-angles to parent
                angle = pr["estimated_angle"]
                if "left" in angle or "right" in angle:
                    detected_angles.add("side view")

        missing_angles = []
        for angle, desc in REQUIRED_ANGLES.items():
            if angle not in detected_angles:
                missing_angles.append(f"{angle} ({desc})")

        if missing_angles:
            issues.append(
                f"Missing required angles: {', '.join(missing_angles)}. "
                f"Please capture the vehicle from these views."
            )

        # --- Check 4: Damage ---
        for pr in result.get("photo_reports", []):
            dmg = pr.get("damage", {})
            if dmg.get("severity") in ("moderate", "severe"):
                issues.append(f"Photo {pr.get('photo')}: {dmg.get('severity')} damage — {dmg.get('details', '')}")

        if result["worst_damage_signal"] in ("moderate", "severe"):
            suggestions.append("Significant damage detected — recommend human inspector review before issuing policy.")

        # --- Check 5: Number plate matching ---
        plate_results = []
        plate_match_found = False
        plate_mismatch_found = False

        if reg_number:
            for i, photo_bytes in enumerate(photo_list):
                plate_check = match_plate_to_registration(photo_bytes, reg_number)
                plate_check["photo"] = i + 1
                plate_results.append(plate_check)

                if plate_check["plate_found"]:
                    if plate_check["match"] is True:
                        plate_match_found = True
                    elif plate_check["match"] is False:
                        plate_mismatch_found = True
                        issues.append(
                            f"Photo {i+1}: Number plate '{plate_check['plate_number']}' "
                            f"does NOT match declared registration '{plate_check['expected']}' — "
                            f"possible wrong vehicle or fraudulent submission."
                        )
                    elif plate_check["match"] is None:
                        # Partial match — uncertain
                        suggestions.append(
                            f"Photo {i+1}: Plate '{plate_check['plate_number']}' partially matches "
                            f"'{plate_check['expected']}' — verify manually."
                        )

            if not plate_match_found and not plate_mismatch_found:
                suggestions.append(
                    "Could not detect the number plate in any photo. "
                    "For stronger verification, include a clear photo showing the plate."
                )

        # --- Determine verdict ---
        if plate_mismatch_found:
            recommendation = "PLATE_MISMATCH"
            summary_text = "Number plate in photos does not match the declared registration — possible wrong vehicle."
        elif not result["quality_ok"]:
            recommendation = "RECAPTURE_NEEDED"
            summary_text = result.get("summary", "Too many quality issues.")
        elif result["worst_damage_signal"] in ("moderate", "severe"):
            recommendation = "NEEDS_HUMAN_REVIEW"
            summary_text = result.get("summary", "Damage detected.")
        elif missing_angles:
            recommendation = "INCOMPLETE_COVERAGE"
            summary_text = f"Missing {len(missing_angles)} required angle(s) — ask customer to retake."
        else:
            recommendation = "LIKELY_INSURABLE"
            summary_text = result.get("summary", "Vehicle condition acceptable.")

        # Confidence
        confidence_factors = [
            (result["usable_photos"] / max(result["photos_analyzed"], 1)) * 40,  # quality weight
            (1 if not missing_angles else 0.5) * 20,  # angle coverage weight
            (1 if plate_match_found else (0 if plate_mismatch_found else 0.5)) * 25,  # plate match weight
            (1 if result["worst_damage_signal"] == "none" else 0.7) * 15,  # damage weight
        ]
        confidence = round(sum(confidence_factors))

        return AgentResult(
            agent=self.name,
            status=AgentStatus.DONE,
            verdict=recommendation,
            confidence=confidence,
            summary=summary_text,
            details={
                "photos_analyzed": result["photos_analyzed"],
                "usable_photos": result["usable_photos"],
                "worst_damage_signal": result["worst_damage_signal"],
                "photo_reports": result.get("photo_reports", []),
                "missing_angles": missing_angles,
                "plate_results": plate_results,
                "plate_match_found": plate_match_found,
                "plate_mismatch_found": plate_mismatch_found,
            },
            issues=issues,
            suggestions=suggestions,
        )
