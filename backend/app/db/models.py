"""SQLAlchemy 2.0 async declarative models for ORIGIN."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


def new_uuid() -> str:
    """Generate a new UUIDv4 string."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base for all ORIGIN tables."""


class RegisteredSystem(Base):
    """Represents a software system observed and studied by ORIGIN."""

    __tablename__ = "registered_systems"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    environment: Mapped[str] = mapped_column(String(64), nullable=False, default="synthetic-lab")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_synthetic_lab: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    services: Mapped[list["ServiceRecord"]] = relationship(
        "ServiceRecord", back_populates="system", cascade="all, delete-orphan"
    )
    dependencies: Mapped[list["ServiceDependency"]] = relationship(
        "ServiceDependency", back_populates="system", cascade="all, delete-orphan"
    )
    telemetry_sources: Mapped[list["TelemetrySource"]] = relationship(
        "TelemetrySource", back_populates="system", cascade="all, delete-orphan"
    )


class ServiceRecord(Base):
    """Represents a registered or discovered service node within a system."""

    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("system_id", "service_key", name="uq_services_system_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    service_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_type: Mapped[str] = mapped_column(String(64), nullable=False, default="microservice")
    tier: Mapped[str] = mapped_column(String(64), nullable=False, default="tier-1")
    owner_team: Mapped[str] = mapped_column(String(120), nullable=False, default="platform")
    registration_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="registered"
    )  # "registered" | "observed" | "registered_and_observed"
    health_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )  # "healthy" | "degraded" | "critical" | "unknown"
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    system: Mapped["RegisteredSystem"] = relationship("RegisteredSystem", back_populates="services")


class ServiceDependency(Base):
    """Represents a directed relationship between two services in a system.

    Provenance is strictly tracked via `discovery_source`:
    - 'registered': explicitly declared via API/manifest
    - 'observed': directly established from parent->child span observations
    - 'registered_and_observed': both declared and confirmed via live telemetry
    """

    __tablename__ = "service_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "system_id",
            "source_service_key",
            "target_service_key",
            name="uq_dependency_edge",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    source_service_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_service_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False, default="http")
    discovery_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="registered"
    )  # "registered" | "observed" | "registered_and_observed"
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    system: Mapped["RegisteredSystem"] = relationship(
        "RegisteredSystem", back_populates="dependencies"
    )


class TelemetrySource(Base):
    """Metadata describing an active OpenTelemetry / instrumentation source."""

    __tablename__ = "telemetry_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    exporter_protocol: Mapped[str] = mapped_column(
        String(64), nullable=False, default="otlp-http-json"
    )
    sdk_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="opentelemetry-python-1.27"
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_batches_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    system: Mapped["RegisteredSystem"] = relationship(
        "RegisteredSystem", back_populates="telemetry_sources"
    )


class MetricObservation(Base):
    """Time-series operational metric point emitted by an instrumented service."""

    __tablename__ = "metric_observations"
    __table_args__ = (
        Index(
            "ix_metric_obs_system_service_metric_ts",
            "system_id",
            "service_key",
            "metric_name",
            "observed_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    service_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    metric_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="ms")
    value: Mapped[float] = mapped_column(Float, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attributes_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )


class SpanObservation(Base):
    """Distributed trace span observation establishing causal parent->child call flow."""

    __tablename__ = "span_observations"
    __table_args__ = (
        Index("ix_span_obs_system_trace", "system_id", "trace_id"),
        Index("ix_span_obs_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    span_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parent_span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    service_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    parent_service_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    operation_name: Mapped[str] = mapped_column(String(200), nullable=False)
    span_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="SERVER")
    status_code: Mapped[str] = mapped_column(String(32), nullable=False, default="OK")
    http_status: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attributes_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )


class InvestigationRecord(Base):
    """Autonomous scientific investigation lifecycle record (Milestone 02/05)."""

    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    target_service_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_metric: Mapped[str] = mapped_column(
        String(120), nullable=False, default="request_latency_ms"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED", index=True)
    # Lifecycle: CREATED -> OBSERVING -> HYPOTHESIZING -> PLANNING -> EXPERIMENTING
    #            -> EVALUATING -> CONCLUDED / INCONCLUSIVE / FAILED / CANCELLED
    experiment_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    experiments_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_size_per_arm: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    concluded_cause_service_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    concluded_mechanism: Mapped[str | None] = mapped_column(String(160), nullable=True)
    conclusion_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    uncertainty_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    lifecycle_history_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    decision_history_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ExperimentDefinition(Base):
    """Controlled scientific experiment specification (Active in Milestone 02/05)."""

    __tablename__ = "experiment_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    hypothesis_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_service_key: Mapped[str] = mapped_column(String(120), nullable=False)
    target_metric: Mapped[str] = mapped_column(
        String(120), nullable=False, default="request_latency_ms"
    )
    measurement_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="ms")
    perturbation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    treatment_condition_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    control_condition_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    sample_size_per_arm: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    budget_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selection_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    safety_envelope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ExperimentRun(Base):
    """Execution record of a controlled experiment with treatment/control arms."""

    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    experiment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiment_definitions.id", ondelete="CASCADE"), index=True
    )
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    hypothesis_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    AbortReason: Mapped[str | None] = mapped_column("abort_reason", Text, nullable=True)
    assignment_order_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    trial_observations_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    metrics_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class HypothesisRecord(Base):
    """Falsifiable scientific hypothesis about system behavior (Milestone 02/05)."""

    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    suspected_mechanism: Mapped[str] = mapped_column(
        String(160), nullable=False, default="downstream_latency_propagation"
    )
    root_cause_service_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    affected_service_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_metric: Mapped[str] = mapped_column(
        String(120), nullable=False, default="request_latency_ms"
    )
    recommended_intervention: Mapped[str] = mapped_column(
        String(120), nullable=False, default="none"
    )
    supporting_observations_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    contradicting_observations_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    expected_intervention_effect_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    alternative_explanations_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_interpretation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Heuristic prior based on observational correlation; requires intervention.",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="proposed"
    )  # "proposed" | "testing" | "supported" | "refuted" | "inconclusive"
    revision_history_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EvidenceRecord(Base):
    """Immutable scientific evidence linking telemetry and experiments to a hypothesis."""

    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    experiment_run_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    hypothesis_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("hypotheses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # "observational_correlation" | "controlled_experiment"
    direction: Mapped[str] = mapped_column(
        String(32), nullable=False, default="supporting"
    )  # "supporting" | "contradicting" | "inconclusive"
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    effect_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    artifact_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class BenchmarkRunRecord(Base):
    """Private Benchmark Controller evaluation record.

    NEVER queried or exposed to Investigator APIs.
    """

    __tablename__ = "benchmark_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    investigation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hidden_fault_profile: Mapped[str] = mapped_column(String(120), nullable=False)
    expected_root_cause_service: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expected_mechanism: Mapped[str | None] = mapped_column(String(160), nullable=True)
    investigator_concluded_service: Mapped[str | None] = mapped_column(String(120), nullable=True)
    investigator_concluded_mechanism: Mapped[str | None] = mapped_column(String(160), nullable=True)
    investigation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    experiments_performed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_trials: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elapsed_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    conclusion_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_inconclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evaluation_notes_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AuditEvent(Base):
    """Immutable safety and operational audit trail for all system actions."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("registered_systems.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )


class DigitalTwinModelRecord(Base):
    """Versioned calibrated Digital Twin model of a registered system (Milestone 03/05)."""

    __tablename__ = "digital_twin_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version_tag: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="calibrated", index=True
    )
    calibration_method: Mapped[str] = mapped_column(
        String(80), nullable=False, default="moments_and_heldout_validation"
    )
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    parameter_uncertainty_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    validity_bounds_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    calibration_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    assumptions_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_sources_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )


class CalibrationRunRecord(Base):
    """Immutable record of a Digital Twin calibration and held-out validation run."""

    __tablename__ = "calibration_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    twin_model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("digital_twin_models.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    train_sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    train_correlation_ids_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    validation_correlation_ids_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    mae_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rmse_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    normalized_error_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    residuals_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    parameter_estimates_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    validity_envelope_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    warnings_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SimulationSnapshotRecord(Base):
    """Serializable Digital Twin state snapshot for deterministic rewind & branching."""

    __tablename__ = "simulation_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    twin_model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("digital_twin_models.id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    sim_clock_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    rng_state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    pending_events_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    service_states_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    active_interventions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SimulationBranchRecord(Base):
    """Baseline or counterfactual Digital Twin branch execution and trajectory."""

    __tablename__ = "simulation_branches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    twin_model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("digital_twin_models.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    hypothesis_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    parent_branch_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    initial_snapshot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("simulation_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    branch_type: Mapped[str] = mapped_column(String(40), nullable=False, default="baseline")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED", index=True)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    horizon_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    dt_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    monte_carlo_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    interventions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    simulation_params_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    trajectory_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    event_log_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    outcome_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    uncertainty_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )


class ScientificMemoryEntryRecord(Base):
    """Persistent scientific memory distinguishing observations, experiments, and predictions."""

    __tablename__ = "scientific_memory_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    epistemic_kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    # "historical_observation" | "experimental_evidence" | "calibrated_model"
    # | "counterfactual_prediction" | "prediction_validation"
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    hypothesis_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    twin_model_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    branch_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    experiment_run_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    predicted_outcome_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    observed_outcome_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    validation_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )


class RecoveryPlanRecord(Base):
    """Autonomous recovery plan & lifecycle state machine (Milestone 04/05).

    Lifecycle states:
    DETECTED -> INVESTIGATING -> SIMULATING -> PROPOSING -> SANDBOX_VERIFYING
    -> AWAITING_APPROVAL -> APPROVED -> EXECUTING -> OBSERVING
    -> RECOVERED / ROLLED_BACK / REJECTED / FAILED / CANCELLED / MANUAL_INTERVENTION_REQUIRED
    """

    __tablename__ = "recovery_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    twin_model_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="DETECTED", index=True)
    target_environment: Mapped[str] = mapped_column(
        String(64), nullable=False, default="synthetic-lab"
    )
    root_cause_service_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    root_cause_mechanism: Mapped[str | None] = mapped_column(String(160), nullable=True)
    selected_candidate_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    active_approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    plan_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    recovery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_recovery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    baseline_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    evidence_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    lifecycle_history_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    agent_decision_history_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class RemediationCandidateRecord(Base):
    """Bounded remediation candidate generated from causal evidence and Digital Twin simulation."""

    __tablename__ = "remediation_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    recovery_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_plans.id", ondelete="CASCADE"), index=True
    )
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    target_service_key: Mapped[str] = mapped_column(String(120), nullable=False)
    suspected_root_cause: Mapped[str] = mapped_column(String(240), nullable=False)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    preconditions_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expected_effect_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    adverse_effects_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rollback_strategy_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    evidence_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    simulation_branch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    simulation_prediction_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    sandbox_verification_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    verification_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="unverified", index=True
    )
    # "unverified" | "simulated_only" | "sandbox_verified" | "sandbox_failed" | "policy_rejected"
    risk_classification: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    # "low" | "medium" | "high" | "critical"
    approval_requirements_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    rank_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SandboxVerificationRunRecord(Base):
    """Real isolated laboratory verification run for a remediation candidate."""

    __tablename__ = "sandbox_verification_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    recovery_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_plans.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("remediation_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED", index=True)
    initial_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    baseline_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    treatment_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    post_restore_config_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    post_restore_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    statistical_comparison_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    regressions_detected_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    simulation_disagreement_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    passed_thresholds: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    restoration_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_trail_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ApprovalRecord(Base):
    """Cryptographically bound, single-use human approval for a verified recovery plan."""

    __tablename__ = "recovery_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    recovery_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_plans.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("remediation_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    action_parameters_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    target_environment: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    risk_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    approver_identity: Mapped[str] = mapped_column(String(120), nullable=False)
    approver_role: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(
        String(32), nullable=False, default="APPROVED", index=True
    )
    # "APPROVED" | "REJECTED" | "REVOKED"
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    approval_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    token_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class RecoveryExecutionRecord(Base):
    """Saga-like controlled execution, post-action observation, and guardrail record."""

    __tablename__ = "recovery_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    recovery_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_plans.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("remediation_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    approval_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recovery_approvals.id", ondelete="CASCADE"),
        index=True,
    )
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="EXECUTING", index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    lock_key: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    applied_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    pre_execution_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    observed_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    guardrail_evaluation_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    verification_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollback_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollback_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class RollbackRecord(Base):
    """Immutable record of an automatic or operator-triggered configuration rollback."""

    __tablename__ = "recovery_rollbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    recovery_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_plans.id", ondelete="CASCADE"), index=True
    )
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_executions.id", ondelete="CASCADE"), index=True
    )
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    target_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    restored_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    post_rollback_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    rollback_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="COMPLETED", index=True)
    # "COMPLETED" | "MANUAL_INTERVENTION_REQUIRED" | "FAILED"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SafetyPolicyEvaluationRecord(Base):
    """Fail-closed operational safety policy evaluation log."""

    __tablename__ = "safety_policy_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    recovery_plan_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    candidate_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    policy_stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_environment: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    risk_classification: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    violations_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evaluated_rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
