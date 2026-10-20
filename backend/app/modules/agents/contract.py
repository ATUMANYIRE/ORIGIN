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
    """Return truthful implementation status for Milestone 04/05."""
    return {
        "module": "agents",
        "boundary_number": 7,
        "status": "implemented",
        "target_milestone": "04/05 — Multi-Role Agent Orchestration & Autonomous Recovery",
        "database_tables_provisioned": [
            "investigations",
            "recovery_plans",
            "remediation_candidates",
            "sandbox_verification_runs",
            "recovery_approvals",
            "recovery_executions",
            "recovery_rollbacks",
        ],
        "execution_enabled": True,
        "capabilities": [
            (
                "8-Role Bounded Deterministic Agent Orchestrator (Observer, Investigator, "
                "Simulator, RecoveryPlanner, Verifier, SafetyGovernor, "
                "ExecutionController, EvidenceAuditor)"
            ),
            (
                "Full investigation lifecycle (CREATED -> OBSERVING -> HYPOTHESIZING "
                "-> PLANNING -> EXPERIMENTING -> EVALUATING -> CONCLUDED / INCONCLUSIVE)"
            ),
            (
                "Full recovery lifecycle (DETECTED -> INVESTIGATING -> SIMULATING -> PROPOSING "
                "-> SANDBOX_VERIFYING -> AWAITING_APPROVAL -> APPROVED -> EXECUTING -> OBSERVING "
                "-> RECOVERED / ROLLED_BACK / REJECTED / FAILED / CANCELLED "
                "/ MANUAL_INTERVENTION_REQUIRED)"
            ),
            "Optional constrained ModelGatewayProtocol with topology & allowlist validation",
            "Reproducible JSON & Markdown scientific investigation and recovery report exports",
        ],
    }
