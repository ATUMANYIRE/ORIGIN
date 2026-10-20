"""Architecture contract for Controlled Experimentation (Milestone 03/05)."""

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
    """Protocol to be implemented in Milestone 03/05 (Active Experimentation)."""

    async def schedule_experiment(
        self, proposal: ExperimentProposalContract
    ) -> dict[str, Any]:
        """Schedule a bounded experiment within a safety envelope."""


def get_module_contract_status() -> dict[str, Any]:
    """Return truthful implementation status for Milestone 01/05."""
    return {
        "module": "experimentation",
        "boundary_number": 5,
        "status": "architecture_contract_only",
        "target_milestone": "03/05 — Controlled Perturbation & Active Experimentation",
        "database_tables_provisioned": ["experiment_definitions", "experiment_runs"],
        "execution_enabled": False,
        "notice": (
            "Database schema and safety envelope contracts are provisioned in Milestone 01/05. "
            "Autonomous experiment execution is intentionally disabled until Milestone 03/05."
        ),
    }
