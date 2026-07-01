"""Agent 1 — Vehicle Lookup Agent.

Takes a registration number, fetches vehicle profile from the RC registry,
validates the response, and passes structured data downstream.
"""
import asyncio
from app.agents import BaseAgent, AgentResult, AgentStatus
from app.services.rc_lookup import lookup_vehicle


class LookupAgent(BaseAgent):
    name = "lookup_agent"
    role = "Fetch and validate vehicle details from the RC registry using the registration number."

    def run(self, context: dict) -> AgentResult:
        reg = context.get("registration_number", "").strip()
        if not reg or len(reg) < 6:
            return AgentResult(
                agent=self.name, status=AgentStatus.FAILED,
                verdict="INVALID_INPUT",
                summary="Registration number is missing or too short.",
            )

        result = asyncio.get_event_loop().run_until_complete(lookup_vehicle(reg))

        if not result.get("success"):
            return AgentResult(
                agent=self.name, status=AgentStatus.FAILED,
                verdict="LOOKUP_FAILED",
                summary=result.get("error", "Could not fetch vehicle details."),
            )

        data = result["data"]
        issues = []
        if not data.get("owner_name"):
            issues.append("Owner name missing from registry response.")
        if not data.get("maker_model"):
            issues.append("Vehicle make/model missing from registry response.")

        vehicle_age = data.get("vehicle_age_years", 0)
        if isinstance(vehicle_age, int) and vehicle_age > 15:
            issues.append(f"Vehicle is {vehicle_age} years old — may have age-based restrictions.")

        return AgentResult(
            agent=self.name,
            status=AgentStatus.DONE,
            verdict="VEHICLE_FOUND",
            confidence=95 if result.get("source") != "mock" else 80,
            summary=f"Found {data.get('maker_model', 'vehicle')} ({data.get('manufacturing_year', '?')}) registered to {data.get('owner_name', 'unknown')}.",
            details={"vehicle": data, "source": result.get("source")},
            issues=issues,
        )
