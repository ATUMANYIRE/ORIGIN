"""Optional constrained Model Gateway interface for hypothesis proposal and explanation.

Core investigations run deterministically without requiring any external or paid AI API.
If an external model is registered, all outputs are strictly validated against topology
reachability and allowlisted interventions, and can never fabricate evidence or bypass safety.
"""

from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.modules.laboratory.orchestrator import ALLOWLISTED_INTERVENTIONS


class CandidateHypothesisProposal(BaseModel):
    """Constrained schema for a candidate hypothesis proposal."""

    root_cause_service_key: str = Field(..., min_length=2, max_length=120)
    affected_service_key: str = Field(..., min_length=2, max_length=120)
    suspected_mechanism: str = Field(..., min_length=3, max_length=160)
    statement: str = Field(..., min_length=10, max_length=500)
    recommended_intervention: str = Field(..., min_length=2, max_length=120)
    alternative_explanations: list[str] = Field(default_factory=list)


class ModelGatewayProtocol(Protocol):
    """Protocol for optional constrained AI assistance in hypothesis proposal."""

    async def propose_additional_hypotheses(
        self,
        *,
        target_service_key: str,
        reachable_services: set[str],
        baseline_metrics: dict[str, Any],
    ) -> list[CandidateHypothesisProposal]:
        """Propose candidate hypotheses constrained by topology and allowlisted interventions."""


def validate_candidate_proposal(
    proposal: CandidateHypothesisProposal,
    reachable_services: set[str],
) -> bool:
    """Enforce topology reachability and allowlisted intervention feasibility."""
    if proposal.root_cause_service_key not in reachable_services:
        return False
    if proposal.recommended_intervention not in ALLOWLISTED_INTERVENTIONS:
        return False
    return proposal.recommended_intervention != "none"
