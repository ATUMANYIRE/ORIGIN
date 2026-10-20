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


class ExperimentDefinition(Base):
    """Controlled scientific experiment specification (Schema active; execution in Prompt 3)."""

    __tablename__ = "experiment_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_service_key: Mapped[str] = mapped_column(String(120), nullable=False)
    perturbation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    safety_envelope_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ExperimentRun(Base):
    """Execution record of a controlled experiment (Schema active; execution in Prompt 3)."""

    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    experiment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiment_definitions.id", ondelete="CASCADE"), index=True
    )
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    AbortReason: Mapped[str | None] = mapped_column("abort_reason", Text, nullable=True)
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
    """Falsifiable scientific hypothesis about system behavior (Prompt 2 engine)."""

    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_service_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    affected_service_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="proposed"
    )  # "proposed" | "testing" | "supported" | "refuted"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EvidenceRecord(Base):
    """Immutable scientific evidence linking telemetry observations to a hypothesis."""

    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_systems.id", ondelete="CASCADE"), index=True
    )
    hypothesis_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("hypotheses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    artifact_payload_json: Mapped[dict[str, Any]] = mapped_column(
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
