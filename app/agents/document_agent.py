"""Agent 2 — Document Verification Agent.

Receives uploaded document bytes, runs OCR, extracts fields, classifies
document type, and cross-verifies against the vehicle data from the Lookup Agent.
"""
from app.agents import BaseAgent, AgentResult, AgentStatus
from app.services.ocr import run_ocr, extract_fields
from app.services.verify import verify, classify_document


class DocumentAgent(BaseAgent):
    name = "document_agent"
    role = "Read the uploaded RC document via OCR, extract fields, and cross-verify against the registry data."

    def run(self, context: dict) -> AgentResult:
        doc_bytes = context.get("document_bytes")
        if not doc_bytes:
            return AgentResult(
                agent=self.name, status=AgentStatus.SKIPPED,
                verdict="NO_DOCUMENT",
                summary="No document was uploaded — skipping document verification.",
            )

        # Step 1: OCR
        raw_text = run_ocr(doc_bytes)
        if raw_text.startswith("[OCR_ERROR]"):
            return AgentResult(
                agent=self.name, status=AgentStatus.FAILED,
                verdict="OCR_FAILED", summary=f"Could not read document: {raw_text}",
            )

        # Step 2: Classify document type
        doc_type = classify_document(raw_text)

        # Step 3: Extract fields
        extracted = extract_fields(raw_text)

        # Step 4: Build form data from lookup agent results (if available)
        vehicle = context.get("vehicle_data", {})
        form_data = {
            "registration_number": vehicle.get("registration_number", ""),
            "owner_name": vehicle.get("owner_name", ""),
            "chassis_number": vehicle.get("chassis_number", ""),
            "engine_number": vehicle.get("engine_number", ""),
            "fuel_type": vehicle.get("fuel_type", ""),
        }

        # Step 5: Cross-verify
        verification = verify(form_data, extracted)

        issues = []
        suggestions = []

        # Document type check
        if doc_type.get("type") != "RC_BOOK":
            issues.append(f"Expected RC Book but detected {doc_type.get('type', 'UNKNOWN')} — possible wrong document uploaded.")

        # Field-level issues
        for f in verification.get("fields", []):
            if f["status"] == "MISMATCH":
                issues.append(f"{f['field'].replace('_', ' ').title()}: entered '{f['entered']}' but document shows '{f['extracted']}'.")
            elif f["status"] == "NOT_FOUND":
                issues.append(f"{f['field'].replace('_', ' ').title()}: could not be located in the document.")

        if verification.get("verdict") == "FLAGGED":
            suggestions.append("Low confidence — recommend manual document review before proceeding.")
        elif verification.get("verdict") == "NEEDS_REVIEW":
            suggestions.append("Moderate confidence — a quick human glance is advisable.")

        return AgentResult(
            agent=self.name,
            status=AgentStatus.DONE,
            verdict=verification.get("verdict", "UNKNOWN"),
            confidence=verification.get("confidence", 0),
            summary=f"Document type: {doc_type.get('type')}. {verification.get('matched', 0)}/{verification.get('comparable', 0)} fields matched at {verification.get('confidence', 0)}% confidence.",
            details={
                "document_type": doc_type,
                "extracted_fields": extracted,
                "verification": verification,
                "ocr_chars": len(raw_text),
            },
            issues=issues,
            suggestions=suggestions,
        )
