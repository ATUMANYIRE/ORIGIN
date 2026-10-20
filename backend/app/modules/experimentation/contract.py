"""Architecture contract and status for Controlled Experimentation (Boundary 5/9)."""

from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.modules.safety.service import SafetyEnvelopeContract


class ExperimentProposalContract(BaseModel):
    """Contract for proposing a bounded perturbation experiment."""

    system_id: str
    hypothesis_id: str
    target_service_key: str
    perturbation_type: str
    safety_envelope: SafetyEnvelopeContract = Field(default_factory=SafetyEnvelopeContract)


class ExperimentEngineProtocol(Protocol):
    """Protocol implemented in Milestone 02/05 (Controlled Experimentation Engine)."""

    async def schedule_experiment(self, proposal: ExperimentProposalContract) -> dict[str, Any]:
        """Schedule a bounded experiment within a safety envelope."""


def get_module_contract_status() -> dict[str, Any]:
    """Return truthful implementation status for Milestone 02/05."""
    return {
        "module": "experimentation",
        "boundary_number": 5,
        "status": "implemented",
        "target_milestone": "02/05 — Controlled Experimentation & Statistical Discovery",
        "database_tables_provisioned": ["experiment_definitions", "experiment_runs"],
        "execution_enabled": True,
        "capabilities": [
            "Allowlisted intervention planner & validator",
            "Seeded block-randomized treatment/control assignment",
            "Welch two-sample t-test, 95% CI, and Cohen's d effect sizes",
            "Experiment budget & cancellation enforcement",
        ],
    }
