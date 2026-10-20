"""Pydantic v2 schemas for Autonomous Causal Investigations and Scientific Reports."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.evidence.schemas import EvidenceRead, HypothesisRead
from app.modules.experimentation.schemas import (
    ExperimentDefinitionRead,
    ExperimentRunRead,
)


class InvestigationCreateRequest(BaseModel):
    """Request payload to create and optionally run an autonomous causal investigation."""

    system_slug: str = Field(default="origin-synthetic-lab", min_length=2, max_length=120)
    title: str = Field(
        default="Autonomous Checkout Latency Investigation",
        min_length=3,
        max_length=240,
    )
    target_service_key: str = Field(default="checkout-service", min_length=2, max_length=120)
    target_metric: str = Field(default="request_latency_ms", min_length=2, max_length=120)
    experiment_budget: int = Field(default=3, ge=1, le=10)
    sample_size_per_arm: int = Field(default=6, ge=2, le=20)
    random_seed: int = Field(default=42, ge=1, le=999999)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    auto_run: bool = Field(default=True)


class InvestigationRead(BaseModel):
    """Summary representation of an autonomous investigation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    title: str
    target_service_key: str
    target_metric: str
    status: str
    experiment_budget: int
    experiments_used: int
    sample_size_per_arm: int
    random_seed: int
    timeout_seconds: int
    cancel_requested: bool
    concluded_cause_service_key: str | None
    concluded_mechanism: str | None
    conclusion_summary: str | None
    uncertainty_summary: str | None
    failure_reason: str | None
    baseline_summary_json: dict[str, Any]
    lifecycle_history_json: list[dict[str, Any]]
    decision_history_json: list[dict[str, Any]]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InvestigationDetailRead(InvestigationRead):
    """Full investigation detail including hypotheses, experiments, runs, and evidence."""

    hypotheses: list[HypothesisRead] = Field(default_factory=list)
    experiment_plans: list[ExperimentDefinitionRead] = Field(default_factory=list)
    experiment_runs: list[ExperimentRunRead] = Field(default_factory=list)
    evidence_records: list[EvidenceRead] = Field(default_factory=list)
