"""Pydantic v2 schemas for the Living Digital Twin and Scientific Memory (Milestone 03/05)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

InterventionKind = Literal[
    "increase_replicas",
    "reduce_incoming_traffic",
    "adjust_concurrency_limit",
    "enable_circuit_breaker",
    "reduce_downstream_latency",
    "adjust_db_connection_capacity",
    "simulate_dependency_failure",
    "restore_configuration",
]

EpistemicLabelType = Literal[
    "historical_observation",
    "experimental_evidence",
    "calibrated_model",
    "counterfactual_prediction",
    "prediction_validation",
]


class TwinInterventionSpec(BaseModel):
    """Specification of a counterfactual intervention applied to a Digital Twin branch."""

    intervention_type: InterventionKind
    target_service_key: str = Field(default="checkout-service", min_length=2, max_length=120)
    value: float = Field(default=1.0)
    apply_at_sec: float = Field(default=0.0, ge=0.0, le=300.0)
    description: str = Field(default="")


class TwinCalibrationRequest(BaseModel):
    """Request payload to calibrate a new Digital Twin model version from stored evidence."""

    system_slug: str = Field(default="origin-synthetic-lab", min_length=2, max_length=120)
    investigation_id: str | None = None
    version_tag: str | None = None
    min_required_observations: int = Field(default=12, ge=4, le=500)
    validation_split_ratio: float = Field(default=0.25, ge=0.1, le=0.5)
    strict_rejection: bool = Field(default=False)


class SnapshotCreateRequest(BaseModel):
    """Request payload to capture a serializable simulation state snapshot."""

    twin_model_id: str
    branch_id: str | None = None
    step_index: int = Field(default=0, ge=0, le=300)
    label: str = Field(default="Initial System Snapshot (t=0s)", min_length=2, max_length=160)
    random_seed: int = Field(default=42, ge=1, le=999999)


class SimulationBranchCreateRequest(BaseModel):
    """Request payload to run a baseline or counterfactual simulation branch."""

    twin_model_id: str
    name: str = Field(default="Baseline Future Trajectory", min_length=2, max_length=200)
    branch_type: Literal["baseline", "counterfactual", "hypothesis_test", "benchmark"] = (
        "baseline"
    )
    parent_branch_id: str | None = None
    initial_snapshot_id: str | None = None
    investigation_id: str | None = None
    hypothesis_id: str | None = None
    random_seed: int = Field(default=42, ge=1, le=999999)
    horizon_seconds: float = Field(default=30.0, ge=5.0, le=300.0)
    dt_seconds: float = Field(default=1.0, ge=0.5, le=5.0)
    incoming_traffic_rps: float | None = Field(default=None, ge=1.0, le=500.0)
    monte_carlo_runs: int = Field(default=5, ge=1, le=20)
    interventions: list[TwinInterventionSpec] = Field(default_factory=list)


class HypothesisSimulationRequest(BaseModel):
    """Request payload for the Causal Investigator to simulate a hypothesis in the Digital Twin."""

    hypothesis_id: str | None = None
    target_service_key: str = Field(default="checkout-service")
    suspected_service_key: str = Field(default="payment-simulator")
    intervention_type: InterventionKind = "reduce_downstream_latency"
    intervention_value: float = Field(default=0.15)
    random_seed: int = Field(default=42, ge=1, le=999999)
    horizon_seconds: float = Field(default=25.0, ge=5.0, le=120.0)


class DigitalTwinModelRead(BaseModel):
    """Serialized representation of a versioned Digital Twin model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    investigation_id: str | None
    version_number: int
    version_tag: str
    status: str
    calibration_method: str
    parameters_json: dict[str, Any]
    parameter_uncertainty_json: dict[str, Any]
    validity_bounds_json: dict[str, Any]
    calibration_summary_json: dict[str, Any]
    assumptions_json: list[str]
    warnings_json: list[str]
    evidence_sources_json: dict[str, Any]
    created_at: datetime


class CalibrationRunRead(BaseModel):
    """Serialized representation of an evidence-based calibration and held-out validation run."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    twin_model_id: str
    investigation_id: str | None
    status: str
    train_sample_count: int
    validation_sample_count: int
    train_correlation_ids_json: list[str]
    validation_correlation_ids_json: list[str]
    mae_ms: float
    rmse_ms: float
    normalized_error_pct: float
    residuals_json: list[dict[str, Any]]
    parameter_estimates_json: dict[str, Any]
    validity_envelope_json: dict[str, Any]
    warnings_json: list[str]
    created_at: datetime


class SimulationSnapshotRead(BaseModel):
    """Serialized representation of a simulation snapshot for deterministic rewind."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    twin_model_id: str
    branch_id: str | None
    label: str
    sim_clock_sec: float
    step_index: int
    random_seed: int
    rng_state_json: dict[str, Any]
    pending_events_json: list[dict[str, Any]]
    service_states_json: dict[str, Any]
    active_interventions_json: list[dict[str, Any]]
    created_at: datetime


class SimulationBranchRead(BaseModel):
    """Serialized representation of a baseline or counterfactual simulation branch."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    twin_model_id: str
    investigation_id: str | None
    hypothesis_id: str | None
    parent_branch_id: str | None
    initial_snapshot_id: str | None
    name: str
    branch_type: str
    status: str
    random_seed: int
    horizon_seconds: float
    dt_seconds: float
    monte_carlo_runs: int
    interventions_json: list[dict[str, Any]]
    simulation_params_json: dict[str, Any]
    trajectory_json: list[dict[str, Any]]
    event_log_json: list[dict[str, Any]]
    outcome_summary_json: dict[str, Any]
    uncertainty_json: dict[str, Any]
    warnings_json: list[str]
    created_at: datetime


class BranchComparisonResponse(BaseModel):
    """Side-by-side comparison of two simulation branches (e.g., Baseline vs. Counterfactual)."""

    epistemic_label: str = "counterfactual_prediction"
    epistemic_notice: str = (
        "Simulated counterfactual comparison generated by the ORIGIN Digital Twin. "
        "Predictions are conditioned on calibrated model parameters and stated assumptions, "
        "and do not constitute independent experimental proof."
    )
    baseline_branch: SimulationBranchRead
    alternative_branch: SimulationBranchRead
    delta_metrics: dict[str, Any]
    tradeoff_analysis: list[str]
    shared_bottleneck_warnings: list[str]


class ScientificMemoryEntryRead(BaseModel):
    """Serialized record from the persistent Scientific Memory Engine."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    epistemic_kind: str
    title: str
    summary: str
    investigation_id: str | None
    hypothesis_id: str | None
    twin_model_id: str | None
    branch_id: str | None
    experiment_run_id: str | None
    predicted_outcome_json: dict[str, Any]
    observed_outcome_json: dict[str, Any]
    validation_metrics_json: dict[str, Any]
    provenance_json: dict[str, Any]
    created_at: datetime


class SimulationBenchmarkScenarioResult(BaseModel):
    """Result of executing one of the 4 canonical Milestone 03/05 simulation benchmarks."""

    benchmark_key: str
    title: str
    description: str
    twin_model_id: str
    model_version_tag: str
    calibration_mae_ms: float
    calibration_rmse_ms: float
    baseline_branch_id: str
    intervention_branch_ids: list[str]
    baseline_outcome: dict[str, Any]
    intervention_outcomes: list[dict[str, Any]]
    uncertainty_summary: dict[str, Any]
    key_scientific_finding: str
    limitations: list[str]
    passed_verification: bool


class SimulationBenchmarkSuiteResponse(BaseModel):
    """Summary of running all 4 Milestone 03/05 Digital Twin benchmarks."""

    total_benchmarks: int
    passed_count: int
    executed_at: str
    benchmarks: list[SimulationBenchmarkScenarioResult]
