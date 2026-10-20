"""Autonomous Recovery, Sandbox Verification, Approvals, Rollbacks, and Safety Policy schema.

Revision ID: 0004_recovery_safety
Revises: 0003_digital_twin_memory
Create Date: 2026-10-20 14:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_recovery_safety"
down_revision: str | None = "0003_digital_twin_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Milestone 04/05 Autonomous Recovery & Operational Safety tables."""
    op.create_table(
        "recovery_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
        sa.Column("twin_model_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("target_environment", sa.String(length=64), nullable=False),
        sa.Column("root_cause_service_key", sa.String(length=120), nullable=True),
        sa.Column("root_cause_mechanism", sa.String(length=160), nullable=True),
        sa.Column("selected_candidate_id", sa.String(length=36), nullable=True),
        sa.Column("active_approval_id", sa.String(length=36), nullable=True),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("plan_hash", sa.String(length=128), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("recovery_attempts", sa.Integer(), nullable=False),
        sa.Column("max_recovery_attempts", sa.Integer(), nullable=False),
        sa.Column("baseline_metrics_json", sa.JSON(), nullable=False),
        sa.Column("evidence_summary_json", sa.JSON(), nullable=False),
        sa.Column("lifecycle_history_json", sa.JSON(), nullable=False),
        sa.Column("agent_decision_history_json", sa.JSON(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recovery_plans_system_id", "recovery_plans", ["system_id"])
    op.create_index("ix_recovery_plans_investigation_id", "recovery_plans", ["investigation_id"])
    op.create_index("ix_recovery_plans_status", "recovery_plans", ["status"])
    op.create_index("ix_recovery_plans_idempotency_key", "recovery_plans", ["idempotency_key"])

    op.create_table(
        "remediation_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recovery_plan_id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("target_service_key", sa.String(length=120), nullable=False),
        sa.Column("suspected_root_cause", sa.String(length=240), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("preconditions_json", sa.JSON(), nullable=False),
        sa.Column("expected_effect_json", sa.JSON(), nullable=False),
        sa.Column("adverse_effects_json", sa.JSON(), nullable=False),
        sa.Column("rollback_strategy_json", sa.JSON(), nullable=False),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False),
        sa.Column("simulation_branch_id", sa.String(length=36), nullable=True),
        sa.Column("simulation_prediction_json", sa.JSON(), nullable=False),
        sa.Column("sandbox_verification_id", sa.String(length=36), nullable=True),
        sa.Column("verification_status", sa.String(length=40), nullable=False),
        sa.Column("risk_classification", sa.String(length=32), nullable=False),
        sa.Column("approval_requirements_json", sa.JSON(), nullable=False),
        sa.Column("rank_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recovery_plan_id"], ["recovery_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_remediation_candidates_recovery_plan_id",
        "remediation_candidates",
        ["recovery_plan_id"],
    )
    op.create_index(
        "ix_remediation_candidates_verification_status",
        "remediation_candidates",
        ["verification_status"],
    )

    op.create_table(
        "sandbox_verification_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recovery_plan_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("initial_config_json", sa.JSON(), nullable=False),
        sa.Column("baseline_metrics_json", sa.JSON(), nullable=False),
        sa.Column("treatment_metrics_json", sa.JSON(), nullable=False),
        sa.Column("post_restore_config_json", sa.JSON(), nullable=False),
        sa.Column("post_restore_metrics_json", sa.JSON(), nullable=False),
        sa.Column("statistical_comparison_json", sa.JSON(), nullable=False),
        sa.Column("regressions_detected_json", sa.JSON(), nullable=False),
        sa.Column("simulation_disagreement_json", sa.JSON(), nullable=False),
        sa.Column("passed_thresholds", sa.Boolean(), nullable=False),
        sa.Column("restoration_verified", sa.Boolean(), nullable=False),
        sa.Column("evidence_trail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["remediation_candidates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["recovery_plan_id"], ["recovery_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sandbox_verification_runs_recovery_plan_id",
        "sandbox_verification_runs",
        ["recovery_plan_id"],
    )
    op.create_index(
        "ix_sandbox_verification_runs_candidate_id",
        "sandbox_verification_runs",
        ["candidate_id"],
    )

    op.create_table(
        "recovery_approvals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recovery_plan_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("plan_hash", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("action_parameters_json", sa.JSON(), nullable=False),
        sa.Column("target_environment", sa.String(length=64), nullable=False),
        sa.Column("evidence_summary_json", sa.JSON(), nullable=False),
        sa.Column("risk_classification", sa.String(length=32), nullable=False),
        sa.Column("approver_identity", sa.String(length=120), nullable=False),
        sa.Column("approver_role", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("approval_token_hash", sa.String(length=128), nullable=False),
        sa.Column("token_used", sa.Boolean(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["remediation_candidates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["recovery_plan_id"], ["recovery_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recovery_approvals_recovery_plan_id",
        "recovery_approvals",
        ["recovery_plan_id"],
    )

    op.create_table(
        "recovery_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recovery_plan_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("approval_id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("lock_key", sa.String(length=120), nullable=False),
        sa.Column("previous_config_json", sa.JSON(), nullable=False),
        sa.Column("applied_config_json", sa.JSON(), nullable=False),
        sa.Column("pre_execution_metrics_json", sa.JSON(), nullable=False),
        sa.Column("observed_metrics_json", sa.JSON(), nullable=False),
        sa.Column("guardrail_evaluation_json", sa.JSON(), nullable=False),
        sa.Column("verification_passed", sa.Boolean(), nullable=False),
        sa.Column("rollback_triggered", sa.Boolean(), nullable=False),
        sa.Column("rollback_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["recovery_approvals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["remediation_candidates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["recovery_plan_id"], ["recovery_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recovery_executions_recovery_plan_id",
        "recovery_executions",
        ["recovery_plan_id"],
    )
    op.create_index(
        "ix_recovery_executions_idempotency_key",
        "recovery_executions",
        ["idempotency_key"],
    )

    op.create_table(
        "recovery_rollbacks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recovery_plan_id", sa.String(length=36), nullable=False),
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.Column("target_config_json", sa.JSON(), nullable=False),
        sa.Column("restored_config_json", sa.JSON(), nullable=False),
        sa.Column("post_rollback_metrics_json", sa.JSON(), nullable=False),
        sa.Column("rollback_verified", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["recovery_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recovery_plan_id"], ["recovery_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recovery_rollbacks_recovery_plan_id",
        "recovery_rollbacks",
        ["recovery_plan_id"],
    )

    op.create_table(
        "safety_policy_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recovery_plan_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_id", sa.String(length=36), nullable=True),
        sa.Column("system_id", sa.String(length=36), nullable=False),
        sa.Column("policy_stage", sa.String(length=64), nullable=False),
        sa.Column("target_environment", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("risk_classification", sa.String(length=32), nullable=False),
        sa.Column("violations_json", sa.JSON(), nullable=False),
        sa.Column("evaluated_rules_json", sa.JSON(), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["system_id"], ["registered_systems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_safety_policy_evaluations_recovery_plan_id",
        "safety_policy_evaluations",
        ["recovery_plan_id"],
    )


def downgrade() -> None:
    """Drop Milestone 04/05 Autonomous Recovery & Operational Safety tables."""
    op.drop_table("safety_policy_evaluations")
    op.drop_table("recovery_rollbacks")
    op.drop_table("recovery_executions")
    op.drop_table("recovery_approvals")
    op.drop_table("sandbox_verification_runs")
    op.drop_table("remediation_candidates")
    op.drop_table("recovery_plans")
