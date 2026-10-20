"""Initial ORIGIN platform schema.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-10-20 09:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all core and future research contract tables for ORIGIN."""
    op.create_table(
        "registered_systems",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_synthetic_lab", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_registered_systems_slug", "registered_systems", ["slug"], unique=True)

    op.create_table(
        "services",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("service_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("service_type", sa.String(length=64), nullable=False),
        sa.Column("tier", sa.String(length=64), nullable=False),
        sa.Column("owner_team", sa.String(length=120), nullable=False),
        sa.Column("registration_source", sa.String(length=32), nullable=False),
        sa.Column("health_status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system_id", "service_key", name="uq_services_system_key"),
    )
    op.create_index("ix_services_system_id", "services", ["system_id"], unique=False)
    op.create_index("ix_services_service_key", "services", ["service_key"], unique=False)

    op.create_table(
        "service_dependencies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("source_service_key", sa.String(length=120), nullable=False),
        sa.Column("target_service_key", sa.String(length=120), nullable=False),
        sa.Column("protocol", sa.String(length=32), nullable=False),
        sa.Column("discovery_source", sa.String(length=32), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("last_latency_ms", sa.Float(), nullable=True),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "system_id",
            "source_service_key",
            "target_service_key",
            name="uq_dependency_edge",
        ),
    )
    op.create_index(
        "ix_service_dependencies_system_id", "service_dependencies", ["system_id"], unique=False
    )

    op.create_table(
        "telemetry_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("exporter_protocol", sa.String(length=64), nullable=False),
        sa.Column("sdk_version", sa.String(length=64), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("total_batches_ingested", sa.Integer(), nullable=False),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telemetry_sources_system_id", "telemetry_sources", ["system_id"], unique=False
    )

    op.create_table(
        "metric_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("service_key", sa.String(length=120), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column("metric_unit", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_metric_obs_system_service_metric_ts",
        "metric_observations",
        ["system_id", "service_key", "metric_name", "observed_at"],
        unique=False,
    )

    op.create_table(
        "span_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("span_id", sa.String(length=64), nullable=False),
        sa.Column("parent_span_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=False),
        sa.Column("service_key", sa.String(length=120), nullable=False),
        sa.Column("parent_service_key", sa.String(length=120), nullable=True),
        sa.Column("operation_name", sa.String(length=200), nullable=False),
        sa.Column("span_kind", sa.String(length=32), nullable=False),
        sa.Column("status_code", sa.String(length=32), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_span_obs_system_trace",
        "span_observations",
        ["system_id", "trace_id"],
        unique=False,
    )
    op.create_index(
        "ix_span_obs_correlation",
        "span_observations",
        ["correlation_id"],
        unique=False,
    )

    op.create_table(
        "experiment_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_service_key", sa.String(length=120), nullable=False),
        sa.Column("perturbation_type", sa.String(length=80), nullable=False),
        sa.Column("safety_envelope_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "experiment_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("experiment_id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("abort_reason", sa.Text(), nullable=True),
        sa.Column("metrics_summary_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["experiment_id"], ["experiment_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "hypotheses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("root_cause_service_key", sa.String(length=120), nullable=True),
        sa.Column("affected_service_key", sa.String(length=120), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("hypothesis_id", sa.String(length=36), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("artifact_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["hypotheses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=True),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_system_id", "audit_events", ["system_id"], unique=False)
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)


def downgrade() -> None:
    """Drop all ORIGIN schema tables."""
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_system_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("evidence_records")
    op.drop_table("hypotheses")
    op.drop_table("experiment_runs")
    op.drop_table("experiment_definitions")
    op.drop_index("ix_span_obs_correlation", table_name="span_observations")
    op.drop_index("ix_span_obs_system_trace", table_name="span_observations")
    op.drop_table("span_observations")
    op.drop_index("ix_metric_obs_system_service_metric_ts", table_name="metric_observations")
    op.drop_table("metric_observations")
    op.drop_index("ix_telemetry_sources_system_id", table_name="telemetry_sources")
    op.drop_table("telemetry_sources")
    op.drop_index("ix_service_dependencies_system_id", table_name="service_dependencies")
    op.drop_table("service_dependencies")
    op.drop_index("ix_services_service_key", table_name="services")
    op.drop_index("ix_services_system_id", table_name="services")
    op.drop_table("services")
    op.drop_index("ix_registered_systems_slug", table_name="registered_systems")
    op.drop_table("registered_systems")
