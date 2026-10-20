"""Autonomous Causal Investigation, Experimentation, and Benchmark schema.

Revision ID: 0002_causal_investigation_engine
Revises: 0001_initial_schema
Create Date: 2026-10-20 11:18:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_causal_investigation_engine"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create investigations and benchmark_runs tables and extend research tables."""
    op.create_table(
        "investigations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("target_service_key", sa.String(length=120), nullable=False),
        sa.Column("target_metric", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("experiment_budget", sa.Integer(), nullable=False),
        sa.Column("experiments_used", sa.Integer(), nullable=False),
        sa.Column("sample_size_per_arm", sa.Integer(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("concluded_cause_service_key", sa.String(length=120), nullable=True),
        sa.Column("concluded_mechanism", sa.String(length=160), nullable=True),
        sa.Column("conclusion_summary", sa.Text(), nullable=True),
        sa.Column("uncertainty_summary", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("baseline_summary_json", sa.JSON(), nullable=False),
        sa.Column("lifecycle_history_json", sa.JSON(), nullable=False),
        sa.Column("decision_history_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigations_system_id", "investigations", ["system_id"], unique=False)
    op.create_index("ix_investigations_status", "investigations", ["status"], unique=False)

    op.create_table(
        "benchmark_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_name", sa.String(length=120), nullable=False),
        sa.Column("hidden_fault_profile", sa.String(length=120), nullable=False),
        sa.Column("expected_root_cause_service", sa.String(length=120), nullable=True),
        sa.Column("expected_mechanism", sa.String(length=160), nullable=True),
        sa.Column("investigator_concluded_service", sa.String(length=120), nullable=True),
        sa.Column("investigator_concluded_mechanism", sa.String(length=160), nullable=True),
        sa.Column("investigation_status", sa.String(length=32), nullable=False),
        sa.Column("experiments_performed", sa.Integer(), nullable=False),
        sa.Column("total_trials", sa.Integer(), nullable=False),
        sa.Column("elapsed_ms", sa.Float(), nullable=False),
        sa.Column("conclusion_correct", sa.Boolean(), nullable=False),
        sa.Column("is_inconclusive", sa.Boolean(), nullable=False),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("evaluation_notes_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_benchmark_runs_system_id", "benchmark_runs", ["system_id"], unique=False)
    op.create_index(
        "ix_benchmark_runs_investigation_id",
        "benchmark_runs",
        ["investigation_id"],
        unique=False,
    )

    # Extend experiment_definitions
    op.add_column(
        "experiment_definitions",
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column("hypothesis_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column(
            "target_metric",
            sa.String(length=120),
            nullable=False,
            server_default="request_latency_ms",
        ),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column("measurement_unit", sa.String(length=32), nullable=False, server_default="ms"),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column("treatment_condition_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column("control_condition_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column("sample_size_per_arm", sa.Integer(), nullable=False, server_default="6"),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column("random_seed", sa.Integer(), nullable=False, server_default="42"),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column("budget_cost", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column("selection_score", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "experiment_definitions",
        sa.Column("selection_reason", sa.Text(), nullable=False, server_default=""),
    )

    # Extend experiment_runs
    op.add_column(
        "experiment_runs",
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "experiment_runs",
        sa.Column("hypothesis_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "experiment_runs",
        sa.Column("assignment_order_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "experiment_runs",
        sa.Column("trial_observations_json", sa.JSON(), nullable=False, server_default="[]"),
    )

    # Extend hypotheses
    op.add_column(
        "hypotheses",
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "hypotheses",
        sa.Column(
            "suspected_mechanism",
            sa.String(length=160),
            nullable=False,
            server_default="downstream_latency_propagation",
        ),
    )
    op.add_column(
        "hypotheses",
        sa.Column(
            "target_metric",
            sa.String(length=120),
            nullable=False,
            server_default="request_latency_ms",
        ),
    )
    op.add_column(
        "hypotheses",
        sa.Column(
            "recommended_intervention",
            sa.String(length=120),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "hypotheses",
        sa.Column("supporting_observations_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "hypotheses",
        sa.Column(
            "contradicting_observations_json", sa.JSON(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "hypotheses",
        sa.Column(
            "expected_intervention_effect_json", sa.JSON(), nullable=False, server_default="{}"
        ),
    )
    op.add_column(
        "hypotheses",
        sa.Column(
            "alternative_explanations_json", sa.JSON(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "hypotheses",
        sa.Column(
            "score_interpretation",
            sa.Text(),
            nullable=False,
            server_default="Observational prior; requires controlled experimental intervention.",
        ),
    )
    op.add_column(
        "hypotheses",
        sa.Column("revision_history_json", sa.JSON(), nullable=False, server_default="[]"),
    )

    # Extend evidence_records
    op.add_column(
        "evidence_records",
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "evidence_records",
        sa.Column("experiment_run_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "evidence_records",
        sa.Column("direction", sa.String(length=32), nullable=False, server_default="supporting"),
    )
    op.add_column(
        "evidence_records",
        sa.Column("effect_size", sa.Float(), nullable=True),
    )
    op.add_column(
        "evidence_records",
        sa.Column("ci_lower", sa.Float(), nullable=True),
    )
    op.add_column(
        "evidence_records",
        sa.Column("ci_upper", sa.Float(), nullable=True),
    )
    op.add_column(
        "evidence_records",
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Revert Milestone 02/05 schema extensions."""
    for col in (
        "sample_size",
        "ci_upper",
        "ci_lower",
        "effect_size",
        "direction",
        "experiment_run_id",
        "investigation_id",
    ):
        op.drop_column("evidence_records", col)

    for col in (
        "revision_history_json",
        "score_interpretation",
        "alternative_explanations_json",
        "expected_intervention_effect_json",
        "contradicting_observations_json",
        "supporting_observations_json",
        "recommended_intervention",
        "target_metric",
        "suspected_mechanism",
        "investigation_id",
    ):
        op.drop_column("hypotheses", col)

    for col in (
        "trial_observations_json",
        "assignment_order_json",
        "hypothesis_id",
        "investigation_id",
    ):
        op.drop_column("experiment_runs", col)

    for col in (
        "selection_reason",
        "selection_score",
        "budget_cost",
        "random_seed",
        "sample_size_per_arm",
        "control_condition_json",
        "treatment_condition_json",
        "measurement_unit",
        "target_metric",
        "hypothesis_id",
        "investigation_id",
    ):
        op.drop_column("experiment_definitions", col)

    op.drop_index("ix_benchmark_runs_investigation_id", table_name="benchmark_runs")
    op.drop_index("ix_benchmark_runs_system_id", table_name="benchmark_runs")
    op.drop_table("benchmark_runs")

    op.drop_index("ix_investigations_status", table_name="investigations")
    op.drop_index("ix_investigations_system_id", table_name="investigations")
    op.drop_table("investigations")
