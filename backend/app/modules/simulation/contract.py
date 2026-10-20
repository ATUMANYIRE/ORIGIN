"""Architecture contract and status for Living Digital Twin & Simulation (Milestone 03/05)."""

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
    """Return truthful implementation status for Milestone 03/05."""
    return {
        "module": "simulation",
        "boundary_number": 6,
        "status": "implemented",
        "target_milestone": (
            "03/05 — Living Digital Twin, Counterfactual Intelligence & Scientific Memory"
        ),
        "database_tables_provisioned": [
            "digital_twin_models",
            "calibration_runs",
            "simulation_snapshots",
            "simulation_branches",
            "scientific_memory_entries",
        ],
        "execution_enabled": True,
        "capabilities": [
            (
                "Discrete-event + discrete-step queueing, concurrency & shared DB "
                "lock contention simulator"
            ),
            (
                "Evidence-based parameter calibration with strict train vs held-out "
                "validation split (MAE, RMSE, NRMSE)"
            ),
            "Serializable simulation state snapshots and bit-exact RNG/event deterministic rewind",
            "Parallel counterfactual branching with Monte Carlo 95% prediction intervals",
            (
                "Persistent Scientific Memory distinguishing observations, "
                "experiments, and predictions"
            ),
        ],
    }
