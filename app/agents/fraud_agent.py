"""Agent 4 — Fraud Detection Agent.

Runs in parallel with other agents. Looks across all available data
(lookup, document, photos) for fraud signals and inconsistencies.
"""
from app.agents import BaseAgent, AgentResult, AgentStatus


class FraudAgent(BaseAgent):
    name = "fraud_agent"
    role = "Detect fraud signals across documents, photos, and registry data."

    def run(self, context: dict) -> AgentResult:
        flags = []
        risk_score = 0
        checks_performed = []

        vehicle = context.get("vehicle_data", {})
        doc_result = context.get("document_result")
        inspection_result = context.get("inspection_result")

        # Check 1: Document vs registry mismatch
        if doc_result and doc_result.status == AgentStatus.DONE:
            checks_performed.append("document_vs_registry")
            if doc_result.verdict == "FLAGGED":
                flags.append("Document fields significantly mismatch registry data — possible forged or wrong document.")
                risk_score += 35
            elif doc_result.verdict == "NEEDS_REVIEW":
                flags.append("Some document fields don't match registry data — could be OCR noise or minor discrepancy.")
                risk_score += 15

            # Wrong document type
            doc_type = doc_result.details.get("document_type", {}).get("type")
            if doc_type and doc_type != "RC_BOOK":
                flags.append(f"Uploaded document classified as {doc_type} instead of RC Book — possible intentional misdirection.")
                risk_score += 25

        # Check 2: Vehicle age anomaly
        if vehicle:
            checks_performed.append("vehicle_age_check")
            age = vehicle.get("vehicle_age_years", 0)
            if isinstance(age, int):
                if age > 15:
                    flags.append(f"Vehicle is {age} years old — higher risk of pre-existing undisclosed damage.")
                    risk_score += 15
                elif age == 0:
                    flags.append("Vehicle age reported as 0 — verify manufacturing date.")
                    risk_score += 10

        # Check 3: Insurance gap
        if vehicle:
            checks_performed.append("insurance_continuity")
            ins_upto = vehicle.get("insurance_valid_upto", "")
            if ins_upto:
                # Simple check: if year in insurance_valid_upto is < current year, there's a gap
                try:
                    parts = ins_upto.replace("-", "/").split("/")
                    year = int(parts[-1]) if len(parts) >= 3 else 0
                    if 0 < year < 2025:
                        flags.append(f"Previous insurance expired in {year} — gap in coverage history, higher fraud risk.")
                        risk_score += 20
                except (ValueError, IndexError):
                    pass

        # Check 4: Photo quality suspicion
        if inspection_result and inspection_result.status == AgentStatus.DONE:
            checks_performed.append("photo_integrity")
            usable = inspection_result.details.get("usable_photos", 0)
            total = inspection_result.details.get("photos_analyzed", 0)
            if total > 0 and usable < total // 2:
                flags.append("Majority of photos are unusable — could be intentional obfuscation of vehicle condition.")
                risk_score += 20

            # All photos show no damage on an old vehicle — suspicious
            worst = inspection_result.details.get("worst_damage_signal", "none")
            age = vehicle.get("vehicle_age_years", 0) if vehicle else 0
            if isinstance(age, int) and age > 10 and worst == "none":
                flags.append(f"Vehicle is {age} years old but shows zero damage — unusually clean, verify photos are current.")
                risk_score += 10

        # Check 5: Financer mismatch
        if vehicle:
            checks_performed.append("finance_check")
            financer = vehicle.get("financer", "NONE")
            if financer and financer != "NONE":
                flags.append(f"Vehicle has active financing with {financer} — verify lien holder consent for new policy.")
                risk_score += 5

        # Cap score
        risk_score = min(risk_score, 100)

        if risk_score >= 50:
            verdict = "HIGH_RISK"
            summary = f"High fraud risk ({risk_score}/100). {len(flags)} flag(s) detected — manual review strongly recommended."
        elif risk_score >= 25:
            verdict = "MEDIUM_RISK"
            summary = f"Moderate fraud risk ({risk_score}/100). {len(flags)} flag(s) detected — review advisable."
        else:
            verdict = "LOW_RISK"
            summary = f"Low fraud risk ({risk_score}/100). No significant anomalies detected."

        return AgentResult(
            agent=self.name,
            status=AgentStatus.DONE,
            verdict=verdict,
            confidence=100 - risk_score,
            summary=summary,
            details={
                "risk_score": risk_score,
                "checks_performed": checks_performed,
                "flags_count": len(flags),
            },
            issues=flags,
            suggestions=["Escalate to fraud investigation team."] if risk_score >= 50 else [],
        )
