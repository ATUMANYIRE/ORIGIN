"""Architecture contract for Scientific Evidence & Causal Hypotheses (Milestone 02/05)."""

from typing import Any, Protocol

from pydantic import BaseModel, Field


class HypothesisSubmissionContract(BaseModel):
    """Contract for recording a falsifiable causal hypothesis."""

    system_id: str
    statement: str
    root_cause_service_key: str | None = None
    affected_service_key: str | None = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ScientificEvidenceLedgerProtocol(Protocol):
    """Protocol for causal discovery and evidence linking (Milestone 02/05)."""

    async def register_hypothesis(
        self, submission: HypothesisSubmissionContract
    ) -> dict[str, Any]:
        """Record a causal hypothesis for falsification."""


def get_module_contract_status() -> dict[str, Any]:
    """Return truthful implementation status for Milestone 01/05."""
    return {
        "module": "evidence",
        "boundary_number": 8,
        "status": "architecture_contract_only",
        "target_milestone": "02/05 — Causal Discovery & Hypothesis Generation Engine",
        "database_tables_provisioned": ["hypotheses", "evidence_records"],
        "execution_enabled": False,
        "notice": (
            "Database tables (hypotheses, evidence_records) and contracts are migrated "
            "and ready for Milestone 02/05 Causal Discovery Engine."
        ),
    }
