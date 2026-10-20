"""Living Digital Twin, Counterfactual Branches, and Scientific Memory schema.

Revision ID: 0003_digital_twin_memory
Revises: 0002_causal_investigation_engine
Create Date: 2026-10-20 13:02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_digital_twin_memory"
down_revision: str | None = "0002_causal_investigation_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Digital Twin, Calibration, Snapshot, Branch, and Scientific Memory tables."""
    op.create_table(
        "digital_twin_models",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_tag", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("calibration_method", sa.String(length=80), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("parameter_uncertainty_json", sa.JSON(), nullable=False),
        sa.Column("validity_bounds_json", sa.JSON(), nullable=False),
        sa.Column("calibration_summary_json", sa.JSON(), nullable=False),
        sa.Column("assumptions_json", sa.JSON(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("evidence_sources_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_id"], ["registered_systems.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_digital_twin_models_system_id",
        "digital_twin_models",
        ["system_id"],
        unique=False,
    )
    op.create_index(
        "ix_digital_twin_models_investigation_id",
        "digital_twin_models",
        ["investigation_id"],
        unique=False,
    )
    op.create_index(
        "ix_digital_twin_models_status",
        "digital_twin_models",
        ["status"],
        unique=False,
    )

    op.create_table(
        "calibration_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("twin_model_id", sa.String(length=36), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("train_sample_count", sa.Integer(), nullable=False),
        sa.Column("validation_sample_count", sa.Integer(), nullable=False),
        sa.Column("train_correlation_ids_json", sa.JSON(), nullable=False),
        sa.Column("validation_correlation_ids_json", sa.JSON(), nullable=False),
        sa.Column("mae_ms", sa.Float(), nullable=False),
        sa.Column("rmse_ms", sa.Float(), nullable=False),
        sa.Column("normalized_error_pct", sa.Float(), nullable=False),
        sa.Column("residuals_json", sa.JSON(), nullable=False),
        sa.Column("parameter_estimates_json", sa.JSON(), nullable=False),
        sa.Column("validity_envelope_json", sa.JSON(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_id"], ["registered_systems.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["twin_model_id"], ["digital_twin_models.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_calibration_runs_system_id", "calibration_runs", ["system_id"], unique=False
    )
    op.create_index(
        "ix_calibration_runs_twin_model_id",
        "calibration_runs",
        ["twin_model_id"],
        unique=False,
    )

    op.create_table(
        "simulation_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("twin_model_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=True),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("sim_clock_sec", sa.Float(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("rng_state_json", sa.JSON(), nullable=False),
        sa.Column("pending_events_json", sa.JSON(), nullable=False),
        sa.Column("service_states_json", sa.JSON(), nullable=False),
        sa.Column("active_interventions_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_id"], ["registered_systems.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["twin_model_id"], ["digital_twin_models.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_snapshots_system_id",
        "simulation_snapshots",
        ["system_id"],
        unique=False,
    )
    op.create_index(
        "ix_simulation_snapshots_twin_model_id",
        "simulation_snapshots",
        ["twin_model_id"],
        unique=False,
    )

    op.create_table(
        "simulation_branches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("twin_model_id", sa.String(length=36), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
        sa.Column("hypothesis_id", sa.String(length=36), nullable=True),
        sa.Column("parent_branch_id", sa.String(length=36), nullable=True),
        sa.Column("initial_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("branch_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("horizon_seconds", sa.Float(), nullable=False),
        sa.Column("dt_seconds", sa.Float(), nullable=False),
        sa.Column("monte_carlo_runs", sa.Integer(), nullable=False),
        sa.Column("interventions_json", sa.JSON(), nullable=False),
        sa.Column("simulation_params_json", sa.JSON(), nullable=False),
        sa.Column("trajectory_json", sa.JSON(), nullable=False),
        sa.Column("event_log_json", sa.JSON(), nullable=False),
        sa.Column("outcome_summary_json", sa.JSON(), nullable=False),
        sa.Column("uncertainty_json", sa.JSON(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_id"], ["registered_systems.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["twin_model_id"], ["digital_twin_models.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["initial_snapshot_id"], ["simulation_snapshots.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_branches_system_id",
        "simulation_branches",
        ["system_id"],
        unique=False,
    )
    op.create_index(
        "ix_simulation_branches_twin_model_id",
        "simulation_branches",
        ["twin_model_id"],
        unique=False,
    )
    op.create_index(
        "ix_simulation_branches_parent_branch_id",
        "simulation_branches",
        ["parent_branch_id"],
        unique=False,
    )

    op.create_table(
        "scientific_memory_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("epistemic_kind", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
        sa.Column("hypothesis_id", sa.String(length=36), nullable=True),
        sa.Column("twin_model_id", sa.String(length=36), nullable=True),
        sa.Column("branch_id", sa.String(length=36), nullable=True),
        sa.Column("experiment_run_id", sa.String(length=36), nullable=True),
        sa.Column("predicted_outcome_json", sa.JSON(), nullable=False),
        sa.Column("observed_outcome_json", sa.JSON(), nullable=False),
        sa.Column("validation_metrics_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_id"], ["registered_systems.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scientific_memory_entries_system_id",
        "scientific_memory_entries",
        ["system_id"],
        unique=False,
    )
    op.create_index(
        "ix_scientific_memory_entries_epistemic_kind",
        "scientific_memory_entries",
        ["epistemic_kind"],
        unique=False,
    )


def downgrade() -> None:
    """Drop Milestone 03/05 Digital Twin and Scientific Memory tables."""
    op.drop_index(
        "ix_scientific_memory_entries_epistemic_kind",
        table_name="scientific_memory_entries",
    )
    op.drop_index(
        "ix_scientific_memory_entries_system_id",
        table_name="scientific_memory_entries",
    )
    op.drop_table("scientific_memory_entries")

    op.drop_index(
        "ix_simulation_branches_parent_branch_id",
        table_name="simulation_branches",
    )
    op.drop_index(
        "ix_simulation_branches_twin_model_id",
        table_name="simulation_branches",
    )
    op.drop_index(
        "ix_simulation_branches_system_id",
        table_name="simulation_branches",
    )
    op.drop_table("simulation_branches")

    op.drop_index(
        "ix_simulation_snapshots_twin_model_id",
        table_name="simulation_snapshots",
    )
    op.drop_index(
        "ix_simulation_snapshots_system_id",
        table_name="simulation_snapshots",
    )
    op.drop_table("simulation_snapshots")

    op.drop_index("ix_calibration_runs_twin_model_id", table_name="calibration_runs")
    op.drop_index("ix_calibration_runs_system_id", table_name="calibration_runs")
    op.drop_table("calibration_runs")

    op.drop_index("ix_digital_twin_models_status", table_name="digital_twin_models")
    op.drop_index(
        "ix_digital_twin_models_investigation_id",
        table_name="digital_twin_models",
    )
    op.drop_index("ix_digital_twin_models_system_id", table_name="digital_twin_models")
    op.drop_table("digital_twin_models")
