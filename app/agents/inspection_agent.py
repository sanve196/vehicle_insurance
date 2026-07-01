"""Agent 3 — Vehicle Inspection Agent.

Receives uploaded vehicle photos, assesses quality and condition,
identifies missing angles, and produces a condition report.
"""
from app.agents import BaseAgent, AgentResult, AgentStatus
from app.services.photo import analyze_photos


REQUIRED_ANGLES = {"front / rear", "side view"}


class InspectionAgent(BaseAgent):
    name = "inspection_agent"
    role = "Assess vehicle condition from uploaded photos: quality, damage, and coverage."

    def run(self, context: dict) -> AgentResult:
        photo_list = context.get("photo_bytes_list", [])
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

        # Check photo count
        if result["photos_analyzed"] < 3:
            issues.append(f"Only {result['photos_analyzed']} photo(s) uploaded — minimum 3 recommended for thorough assessment.")

        # Check quality
        if not result["quality_ok"]:
            issues.append(f"Only {result['usable_photos']}/{result['photos_analyzed']} photos are usable — too many quality issues.")

        # Check angle coverage
        detected_angles = set()
        for pr in result.get("photo_reports", []):
            if pr.get("estimated_angle"):
                detected_angles.add(pr["estimated_angle"])
        missing = REQUIRED_ANGLES - detected_angles
        if missing:
            suggestions.append(f"Missing angles: {', '.join(missing)}. Ask the customer to retake from these views.")

        # Damage issues
        for pr in result.get("photo_reports", []):
            dmg = pr.get("damage", {})
            if dmg.get("severity") in ("moderate", "severe"):
                issues.append(f"Photo {pr.get('photo')}: {dmg.get('severity')} damage detected — {dmg.get('details', '')}")

        if result["worst_damage_signal"] in ("moderate", "severe"):
            suggestions.append("Significant damage detected — recommend human inspector review before issuing policy.")

        return AgentResult(
            agent=self.name,
            status=AgentStatus.DONE,
            verdict=result.get("recommendation", "UNKNOWN"),
            confidence=round((result["usable_photos"] / max(result["photos_analyzed"], 1)) * 100),
            summary=result.get("summary", ""),
            details={
                "photos_analyzed": result["photos_analyzed"],
                "usable_photos": result["usable_photos"],
                "worst_damage_signal": result["worst_damage_signal"],
                "photo_reports": result.get("photo_reports", []),
            },
            issues=issues,
            suggestions=suggestions,
        )
