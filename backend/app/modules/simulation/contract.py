"""Architecture contract for Counterfactual & Topology Simulation (Milestone 03/05)."""

from typing import Any, Protocol

from pydantic import BaseModel


class SimulationScenarioContract(BaseModel):
    """Contract for simulating topology or latency perturbations offline."""

    system_id: str
    focal_service_key: str
    latency_multiplier: float = 1.0
    horizon_seconds: int = 60


class SimulationEngineProtocol(Protocol):
    """Protocol for offline counterfactual simulation prior to live experimentation."""

    async def run_counterfactual(
        self, scenario: SimulationScenarioContract
    ) -> dict[str, Any]:
        """Simulate propagation across the observed dependency graph."""


def get_module_contract_status() -> dict[str, Any]:
    """Return truthful implementation status for Milestone 01/05."""
    return {
        "module": "simulation",
        "boundary_number": 6,
        "status": "architecture_contract_only",
        "target_milestone": "03/05 — Counterfactual Simulation & Pre-flight Validation",
        "database_tables_provisioned": [],
        "execution_enabled": False,
        "notice": (
            "Simulation interface contracts are defined in Milestone 01/05. "
            "Counterfactual propagation solvers will be implemented in Milestone 03/05."
        ),
    }
