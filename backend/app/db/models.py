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
    __table_args__ = (
        UniqueConstraint("system_id", "service_key", name="uq_services_system_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    service_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="microservice"
    )
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

    system: Mapped["RegisteredSystem"] = relationship(
        "RegisteredSystem", back_populates="services"
    )


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
    parent_service_key: Mapped[str | None] = mapped_column(
        String(120), nullable=True, index=True
    )
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
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="CREATED", index=True
    )
    # Lifecycle: CREATED -> OBSERVING -> HYPOTHESIZING -> PLANNING -> EXPERIMENTING
    #            -> EVALUATING -> CONCLUDED / INCONCLUSIVE / FAILED / CANCELLED
    experiment_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    experiments_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_size_per_arm: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    concluded_cause_service_key: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
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
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    investigation_id: Mapped[str | None] = mapped_column(
        String(36), index=True, nullable=True
    )
    hypothesis_id: Mapped[str | None] = mapped_column(
        String(36), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_service_key: Mapped[str] = mapped_column(String(120), nullable=False)
    target_metric: Mapped[str] = mapped_column(
        String(120), nullable=False, default="request_latency_ms"
    )
    measurement_unit: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ms"
    )
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
    safety_envelope_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
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
    investigation_id: Mapped[str | None] = mapped_column(
        String(36), index=True, nullable=True
    )
    hypothesis_id: Mapped[str | None] = mapped_column(
        String(36), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    AbortReason: Mapped[str | None] = mapped_column("abort_reason", Text, nullable=True)
    assignment_order_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    trial_observations_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    metrics_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    investigation_id: Mapped[str | None] = mapped_column(
        String(36), index=True, nullable=True
    )
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
    investigation_id: Mapped[str | None] = mapped_column(
        String(36), index=True, nullable=True
    )
    experiment_run_id: Mapped[str | None] = mapped_column(
        String(36), index=True, nullable=True
    )
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
    expected_root_cause_service: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    expected_mechanism: Mapped[str | None] = mapped_column(String(160), nullable=True)
    investigator_concluded_service: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    investigator_concluded_mechanism: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    investigation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    experiments_performed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_trials: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elapsed_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    conclusion_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_inconclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
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
