"""Pydantic v2 schemas for Hypotheses, Scientific Evidence, and Investigations."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

InvestigationStatusType = Literal[
    "CREATED",
    "OBSERVING",
    "HYPOTHESIZING",
    "PLANNING",
    "EXPERIMENTING",
    "EVALUATING",
    "CONCLUDED",
    "INCONCLUSIVE",
    "FAILED",
    "CANCELLED",
]

HypothesisStatusType = Literal[
    "proposed",
    "testing",
    "supported",
    "refuted",
    "inconclusive",
]


class ObservationReference(BaseModel):
    """Reference to a real stored observation supporting or contradicting a hypothesis."""

    service_key: str
    metric_name: str
    observed_value: float
    baseline_reference: float
    unit: str = "ms"
    correlation_ids: list[str] = Field(default_factory=list)
    note: str


class ExpectedInterventionEffect(BaseModel):
    """Predicted outcome if the suspected causal mechanism is intervened upon."""

    intervention_type: str
    target_service_key: str
    target_metric: str
    expected_direction: Literal["decrease", "increase", "stabilize"] = "decrease"
    min_expected_reduction_pct: float = 25.0
    rationale: str


class HypothesisRead(BaseModel):
    """Full serialized representation of a competing causal hypothesis."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    investigation_id: str | None
    statement: str
    suspected_mechanism: str
    root_cause_service_key: str | None
    affected_service_key: str | None
    target_metric: str
    recommended_intervention: str
    supporting_observations_json: list[dict[str, Any]]
    contradicting_observations_json: list[dict[str, Any]]
    expected_intervention_effect_json: dict[str, Any]
    alternative_explanations_json: list[str]
    confidence_score: float
    score_interpretation: str
    status: str
    revision_history_json: list[dict[str, Any]]
    created_at: datetime


class EvidenceRead(BaseModel):
    """Full serialized representation of an immutable scientific evidence record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    investigation_id: str | None
    experiment_run_id: str | None
    hypothesis_id: str | None
    evidence_type: str
    direction: str
    summary: str
    correlation_id: str | None
    effect_size: float | None
    ci_lower: float | None
    ci_upper: float | None
    sample_size: int
    artifact_payload_json: dict[str, Any]
    created_at: datetime
