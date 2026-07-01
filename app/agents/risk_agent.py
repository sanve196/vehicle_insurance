"""Agent 5 — Risk & Pricing Agent.

Takes vehicle profile, condition report, and fraud score from other agents,
calculates an estimated premium range.
"""
from app.agents import BaseAgent, AgentResult, AgentStatus


# Base premium lookup (annual, INR) — simplified demo pricing
_BASE_PREMIUM = {
    "Motor Cycle": 1800,
    "Scooter": 1500,
    "Motor Car": 6500,
}
_DEFAULT_BASE = 3500


class RiskPricingAgent(BaseAgent):
    name = "risk_pricing_agent"
    role = "Calculate estimated premium and risk tier based on vehicle profile, condition, and fraud signals."

    def run(self, context: dict) -> AgentResult:
        vehicle = context.get("vehicle_data", {})
        inspection = context.get("inspection_result")
        fraud = context.get("fraud_result")

        if not vehicle:
            return AgentResult(
                agent=self.name, status=AgentStatus.SKIPPED,
                verdict="NO_DATA", summary="No vehicle data available for pricing.",
            )

        # Base premium by vehicle class
        v_class = vehicle.get("vehicle_class", "")
        base = _BASE_PREMIUM.get(v_class, _DEFAULT_BASE)

        factors = []
        multiplier = 1.0

        # Age factor
        age = vehicle.get("vehicle_age_years", 0)
        if isinstance(age, int):
            if age <= 2:
                multiplier *= 1.15
                factors.append(f"New vehicle (≤2 yrs): +15%")
            elif age <= 5:
                factors.append("Vehicle 3–5 years: base rate")
            elif age <= 10:
                multiplier *= 0.90
                factors.append(f"Vehicle 6–10 years: -10%")
            else:
                multiplier *= 0.80
                factors.append(f"Vehicle >10 years: -20%")

        # Damage factor from inspection
        if inspection and inspection.status == AgentStatus.DONE:
            worst = inspection.details.get("worst_damage_signal", "none")
            if worst == "none":
                multiplier *= 0.95
                factors.append("No damage detected: -5%")
            elif worst == "minor":
                multiplier *= 1.05
                factors.append("Minor damage detected: +5%")
            elif worst in ("moderate", "severe"):
                multiplier *= 1.25
                factors.append(f"{worst.title()} damage detected: +25%")

        # Fraud risk factor
        if fraud and fraud.status == AgentStatus.DONE:
            risk_score = fraud.details.get("risk_score", 0)
            if risk_score >= 50:
                multiplier *= 1.30
                factors.append("High fraud risk: +30%")
            elif risk_score >= 25:
                multiplier *= 1.10
                factors.append("Moderate fraud risk: +10%")
            else:
                factors.append("Low fraud risk: no adjustment")

        # Fuel type factor
        fuel = vehicle.get("fuel_type", "").upper()
        if fuel == "ELECTRIC":
            multiplier *= 0.90
            factors.append("Electric vehicle: -10%")
        elif fuel == "CNG":
            multiplier *= 0.95
            factors.append("CNG vehicle: -5%")

        estimated = round(base * multiplier)
        premium_range = (max(estimated - 300, 500), estimated + 500)

        # Risk tier
        if multiplier > 1.20:
            tier = "HIGH_RISK"
        elif multiplier > 1.05:
            tier = "STANDARD"
        else:
            tier = "PREFERRED"

        return AgentResult(
            agent=self.name,
            status=AgentStatus.DONE,
            verdict=tier,
            confidence=75,
            summary=f"Estimated annual premium: ₹{estimated:,} (range ₹{premium_range[0]:,}–₹{premium_range[1]:,}). Risk tier: {tier.replace('_', ' ').title()}.",
            details={
                "base_premium": base,
                "multiplier": round(multiplier, 3),
                "estimated_premium": estimated,
                "premium_range": {"min": premium_range[0], "max": premium_range[1]},
                "risk_tier": tier,
                "vehicle_class": v_class,
                "factors": factors,
            },
            issues=[],
            suggestions=[f"Consider {tier.replace('_', ' ').lower()} underwriting guidelines."],
        )
