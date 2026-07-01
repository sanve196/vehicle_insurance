"""Orchestrator Agent — the brain.

Receives the full application (registration number, document, photos),
dispatches agents in the right order, collects all results, and produces
the final underwriting recommendation.

Flow:
  1. Lookup Agent (fetch vehicle data)
  2. Document Agent + Inspection Agent (in parallel)
  3. Fraud Agent (needs outputs from 1+2+3)
  4. Risk & Pricing Agent (needs all above)
  5. Compile final decision
"""
import time
from concurrent.futures import ThreadPoolExecutor
from app.agents import AgentResult, AgentStatus
from app.agents.lookup_agent import LookupAgent
from app.agents.document_agent import DocumentAgent
from app.agents.inspection_agent import InspectionAgent
from app.agents.fraud_agent import FraudAgent
from app.agents.risk_agent import RiskPricingAgent


class Orchestrator:
    """Coordinates all agents and produces a unified underwriting report."""

    def __init__(self):
        self.lookup = LookupAgent()
        self.document = DocumentAgent()
        self.inspection = InspectionAgent()
        self.fraud = FraudAgent()
        self.risk = RiskPricingAgent()

    def run(self, registration_number: str, document_bytes: bytes = None,
            photo_bytes_list: list[bytes] = None) -> dict:
        """Execute the full agentic pipeline and return a consolidated report."""
        start = time.time()
        results = {}
        agent_log = []

        def log(agent_name, status):
            agent_log.append({"agent": agent_name, "status": status, "time": round(time.time() - start, 2)})

        # --- Phase 1: Vehicle Lookup ---
        log("lookup_agent", "running")
        lookup_result = self.lookup.safe_run({"registration_number": registration_number})
        results["lookup"] = lookup_result
        log("lookup_agent", lookup_result.status.value)

        vehicle_data = lookup_result.details.get("vehicle", {}) if lookup_result.status == AgentStatus.DONE else {}

        # --- Phase 2: Document + Inspection (parallel) ---
        context_doc = {
            "document_bytes": document_bytes,
            "vehicle_data": vehicle_data,
        }
        context_inspect = {
            "photo_bytes_list": photo_bytes_list or [],
        }

        log("document_agent", "running")
        log("inspection_agent", "running")

        with ThreadPoolExecutor(max_workers=2) as pool:
            doc_future = pool.submit(self.document.safe_run, context_doc)
            inspect_future = pool.submit(self.inspection.safe_run, context_inspect)
            doc_result = doc_future.result()
            inspect_result = inspect_future.result()

        results["document"] = doc_result
        results["inspection"] = inspect_result
        log("document_agent", doc_result.status.value)
        log("inspection_agent", inspect_result.status.value)

        # --- Phase 3: Fraud Detection ---
        log("fraud_agent", "running")
        fraud_context = {
            "vehicle_data": vehicle_data,
            "document_result": doc_result,
            "inspection_result": inspect_result,
        }
        fraud_result = self.fraud.safe_run(fraud_context)
        results["fraud"] = fraud_result
        log("fraud_agent", fraud_result.status.value)

        # --- Phase 4: Risk & Pricing ---
        log("risk_pricing_agent", "running")
        risk_context = {
            "vehicle_data": vehicle_data,
            "inspection_result": inspect_result,
            "fraud_result": fraud_result,
        }
        risk_result = self.risk.safe_run(risk_context)
        results["risk"] = risk_result
        log("risk_pricing_agent", risk_result.status.value)

        # --- Phase 5: Final Decision ---
        decision = self._decide(results)
        total_ms = int((time.time() - start) * 1000)

        return {
            "decision": decision,
            "agents": {k: self._serialize(v) for k, v in results.items()},
            "agent_log": agent_log,
            "total_duration_ms": total_ms,
        }

    def _decide(self, results: dict) -> dict:
        """Compile the final underwriting recommendation from all agent outputs."""
        all_issues = []
        all_suggestions = []
        for r in results.values():
            all_issues.extend(r.issues)
            all_suggestions.extend(r.suggestions)

        lookup = results.get("lookup")
        doc = results.get("document")
        inspection = results.get("inspection")
        fraud = results.get("fraud")
        risk = results.get("risk")

        # Decision logic
        blockers = []

        if lookup.status == AgentStatus.FAILED:
            blockers.append("Vehicle not found in registry.")

        if doc.status == AgentStatus.DONE and doc.verdict == "FLAGGED":
            blockers.append("Document verification failed — high mismatch.")

        if fraud.status == AgentStatus.DONE and fraud.verdict == "HIGH_RISK":
            blockers.append("High fraud risk detected.")

        if inspection.status == AgentStatus.DONE and inspection.verdict == "RECAPTURE_NEEDED":
            blockers.append("Vehicle photos are unusable — recapture required.")

        if blockers:
            verdict = "REJECTED"
            action = "Do not issue policy. Address the following blockers before re-evaluation."
            summary = f"Application rejected. {len(blockers)} blocking issue(s) found."
        elif (fraud.status == AgentStatus.DONE and fraud.verdict == "MEDIUM_RISK") or \
             (doc.status == AgentStatus.DONE and doc.verdict == "NEEDS_REVIEW") or \
             (inspection.status == AgentStatus.DONE and inspection.verdict == "NEEDS_HUMAN_REVIEW"):
            verdict = "MANUAL_REVIEW"
            action = "Route to senior underwriter for manual review with AI-highlighted areas of concern."
            summary = f"Application needs human review. {len(all_issues)} issue(s) flagged across agents."
        else:
            verdict = "APPROVED"
            action = "Application may proceed to policy issuance. All checks passed within acceptable thresholds."
            summary = "All agents passed. Vehicle verified, documents matched, condition acceptable, low fraud risk."

        premium = risk.details.get("estimated_premium") if risk.status == AgentStatus.DONE else None

        return {
            "verdict": verdict,
            "action": action,
            "summary": summary,
            "blockers": blockers,
            "total_issues": len(all_issues),
            "total_suggestions": len(all_suggestions),
            "issues": all_issues,
            "suggestions": all_suggestions,
            "estimated_premium": premium,
            "risk_tier": risk.details.get("risk_tier") if risk.status == AgentStatus.DONE else None,
        }

    @staticmethod
    def _serialize(r: AgentResult) -> dict:
        return {
            "agent": r.agent,
            "status": r.status.value,
            "verdict": r.verdict,
            "confidence": r.confidence,
            "summary": r.summary,
            "details": r.details,
            "duration_ms": r.duration_ms,
            "issues": r.issues,
            "suggestions": r.suggestions,
        }
