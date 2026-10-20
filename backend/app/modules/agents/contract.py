"""Architecture contract and status for Scientific Agent Orchestration (Boundary 7/9)."""

from typing import Any, Protocol

from pydantic import BaseModel


class ScientificInvestigationTaskContract(BaseModel):
    """Contract for multi-agent scientific investigation loops."""

    system_id: str
    trigger_correlation_id: str
    objective: str


class AgentOrchestratorProtocol(Protocol):
    """Protocol for coordinating autonomous causal investigation loops."""

    async def dispatch_investigation(
        self, task: ScientificInvestigationTaskContract
    ) -> dict[str, Any]:
        """Coordinate hypothesis generation and falsification."""


def get_module_contract_status() -> dict[str, Any]:
    """Return truthful implementation status for Milestone 02/05."""
    return {
        "module": "agents",
        "boundary_number": 7,
        "status": "implemented",
        "target_milestone": "02/05 — Autonomous Causal Scientist & Reasoning Loop",
        "database_tables_provisioned": ["investigations"],
        "execution_enabled": True,
        "capabilities": [
            (
                "Full lifecycle state machine (CREATED -> OBSERVING -> HYPOTHESIZING "
                "-> PLANNING -> EXPERIMENTING -> EVALUATING -> CONCLUDED / INCONCLUSIVE)"
            ),
            "Bounded autonomous reasoning loop without requiring paid LLM APIs",
            "Optional constrained ModelGatewayProtocol with topology & allowlist validation",
            "Reproducible JSON & Markdown scientific report export",
        ],
    }
