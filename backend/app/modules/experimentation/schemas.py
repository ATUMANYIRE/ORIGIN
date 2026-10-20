"""Pydantic v2 schemas for Controlled Experiments and Statistical Comparisons."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TrialObservationSchema(BaseModel):
    """Single trial measurement within a controlled experiment run."""

    trial_index: int
    arm: str  # "control" | "treatment"
    intervention: str
    correlation_id: str
    trace_id: str
    target_service_key: str
    target_metric_value_ms: float
    focal_service_key: str
    focal_service_latency_ms: float
    gateway_status: int
    observed_at: str


class StatisticalComparisonSchema(BaseModel):
    """Rigorous statistical comparison between Treatment and Control arms."""

    measurement_unit: str = "ms"
    control_n: int
    treatment_n: int
    control_mean_ms: float
    control_median_ms: float
    control_std_ms: float
    treatment_mean_ms: float
    treatment_median_ms: float
    treatment_std_ms: float
    absolute_effect_size_ms: float
    median_effect_size_ms: float
    relative_effect_pct: float
    standard_error_ms: float
    welch_t_stat: float
    degrees_of_freedom: float
    ci_lower_95_ms: float
    ci_upper_95_ms: float
    cohens_d: float
    is_statistically_significant: bool
    trial_correlation_ids: list[str]
    methodology_note: str


class ExperimentDefinitionRead(BaseModel):
    """Serialized controlled experiment plan."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    investigation_id: str | None
    hypothesis_id: str | None
    name: str
    target_service_key: str
    target_metric: str
    measurement_unit: str
    perturbation_type: str
    treatment_condition_json: dict[str, Any]
    control_condition_json: dict[str, Any]
    sample_size_per_arm: int
    random_seed: int
    budget_cost: int
    selection_score: float
    selection_reason: str
    safety_envelope_json: dict[str, Any]
    status: str
    created_at: datetime


class ExperimentRunRead(BaseModel):
    """Serialized controlled experiment execution run."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    experiment_id: str
    system_id: str
    investigation_id: str | None
    hypothesis_id: str | None
    status: str
    AbortReason: str | None
    assignment_order_json: list[str]
    trial_observations_json: list[dict[str, Any]]
    metrics_summary_json: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
