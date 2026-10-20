"""Pydantic v2 schemas for Autonomous Recovery, Sandbox Verification, Approvals & Rollbacks."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RecoveryStatusType = Literal[
    "DETECTED",
    "INVESTIGATING",
    "SIMULATING",
    "PROPOSING",
    "SANDBOX_VERIFYING",
    "AWAITING_APPROVAL",
    "APPROVED",
    "EXECUTING",
    "OBSERVING",
    "RECOVERED",
    "ROLLED_BACK",
    "REJECTED",
    "FAILED",
    "CANCELLED",
    "MANUAL_INTERVENTION_REQUIRED",
]

RemediationActionType = Literal[
    "adjust_service_replicas",
    "modify_concurrency_limit",
    "toggle_circuit_breaker",
    "apply_rate_limiting",
    "adjust_db_contention_controls",
    "restore_safe_lab_configuration",
    "restart_synthetic_service",
]

RiskClassificationType = Literal["low", "medium", "high", "critical"]


class RecoveryWorkflowCreateRequest(BaseModel):
    """Request payload to create and optionally run a recovery workflow up to AWAITING_APPROVAL."""

    system_slug: str = Field(default="origin-synthetic-lab", min_length=2, max_length=120)
    title: str = Field(default="Autonomous Recovery Workflow", min_length=2, max_length=240)
    target_environment: str = Field(default="synthetic-lab", min_length=2, max_length=64)
    investigation_id: str | None = None
    operator_root_cause_service_key: str | None = None
    operator_root_cause_mechanism: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)
    auto_prepare_to_approval: bool = Field(default=True)
    sandbox_trials_per_arm: int = Field(default=4, ge=2, le=12)
    random_seed: int = Field(default=42, ge=1, le=999999)


class CandidateGenerationRequest(BaseModel):
    """Request payload to generate or add bounded remediation candidates."""

    custom_action_type: str | None = None
    custom_target_service_key: str | None = None
    custom_parameters: dict[str, Any] = Field(default_factory=dict)


class SandboxVerifyRequest(BaseModel):
    """Request payload to run real sandbox verification on a remediation candidate."""

    candidate_id: str | None = None
    trials_per_arm: int = Field(default=4, ge=2, le=12)
    duration_seconds: float = Field(default=10.0, gt=0.0)
    random_seed: int = Field(default=42, ge=1, le=999999)
    simulate_restore_failure: bool = Field(default=False)


class RecoveryApprovalRequest(BaseModel):
    """Request payload for a human operator to approve or reject a verified recovery plan."""

    candidate_id: str | None = None
    decision: Literal["APPROVED", "REJECTED"] = "APPROVED"
    approver_identity: str = Field(default="human-sre-commander", min_length=2, max_length=120)
    approver_role: str = Field(default="reliability-commander", min_length=2, max_length=64)
    rationale: str = Field(
        default=(
            "Sandbox verification confirmed statistically significant latency recovery "
            "and clean restoration."
        ),
        min_length=3,
        max_length=1000,
    )
    ttl_seconds: int = Field(default=900, ge=-3600, le=86400)


class RecoveryExecutionRequest(BaseModel):
    """Request payload to execute an approved recovery plan inside the Synthetic Laboratory."""

    approval_id: str
    approval_token: str = Field(min_length=8, max_length=256)
    idempotency_key: str | None = Field(default=None, max_length=128)
    observation_iterations: int = Field(default=4, ge=2, le=12)
    timeout_seconds: float = Field(default=15.0, gt=0.0)
    simulate_timeout: bool = Field(default=False)
    simulate_execution_regression: bool = Field(default=False)
    simulate_rollback_failure: bool = Field(default=False)


class ManualRollbackRequest(BaseModel):
    """Request payload to trigger an immediate rollback of an executed recovery plan."""

    execution_id: str | None = None
    reason: str = Field(default="Operator-initiated manual rollback.", min_length=3, max_length=500)
    simulate_rollback_failure: bool = Field(default=False)


class PlanMutationRequest(BaseModel):
    """Request payload to update a recovery plan's candidate or parameters."""

    selected_candidate_id: str | None = None
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="Updated remediation parameters", max_length=300)


class RemediationCandidateRead(BaseModel):
    """Serialized representation of a remediation candidate."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str
    system_id: str
    target_service_key: str
    suspected_root_cause: str
    action_type: str
    parameters_json: dict[str, Any]
    preconditions_json: list[str]
    expected_effect_json: dict[str, Any]
    adverse_effects_json: list[str]
    rollback_strategy_json: dict[str, Any]
    evidence_refs_json: list[str]
    simulation_branch_id: str | None
    simulation_prediction_json: dict[str, Any]
    sandbox_verification_id: str | None
    verification_status: str
    risk_classification: str
    approval_requirements_json: dict[str, Any]
    rank_score: float
    created_at: datetime


class SandboxVerificationRunRead(BaseModel):
    """Serialized representation of a sandbox verification run."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str
    candidate_id: str
    system_id: str
    status: str
    initial_config_json: dict[str, Any]
    baseline_metrics_json: dict[str, Any]
    treatment_metrics_json: dict[str, Any]
    post_restore_config_json: dict[str, Any]
    post_restore_metrics_json: dict[str, Any]
    statistical_comparison_json: dict[str, Any]
    regressions_detected_json: list[str]
    simulation_disagreement_json: dict[str, Any]
    passed_thresholds: bool
    restoration_verified: bool
    evidence_trail_json: dict[str, Any]
    created_at: datetime


class ApprovalRecordRead(BaseModel):
    """Serialized representation of a human approval record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str
    candidate_id: str
    system_id: str
    plan_version: int
    plan_hash: str
    action_type: str
    action_parameters_json: dict[str, Any]
    target_environment: str
    evidence_summary_json: dict[str, Any]
    risk_classification: str
    approver_identity: str
    approver_role: str
    decision: str
    rationale: str
    token_used: bool
    approved_at: datetime
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime
    issued_single_use_token: str | None = None


class RecoveryExecutionRead(BaseModel):
    """Serialized representation of a recovery execution attempt."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str
    candidate_id: str
    approval_id: str
    system_id: str
    status: str
    idempotency_key: str | None
    lock_key: str
    previous_config_json: dict[str, Any]
    applied_config_json: dict[str, Any]
    pre_execution_metrics_json: dict[str, Any]
    observed_metrics_json: dict[str, Any]
    guardrail_evaluation_json: dict[str, Any]
    verification_passed: bool
    rollback_triggered: bool
    rollback_id: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class RollbackRecordRead(BaseModel):
    """Serialized representation of a rollback record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str
    execution_id: str
    system_id: str
    trigger_reason: str
    target_config_json: dict[str, Any]
    restored_config_json: dict[str, Any]
    post_rollback_metrics_json: dict[str, Any]
    rollback_verified: bool
    status: str
    created_at: datetime


class SafetyPolicyEvaluationRead(BaseModel):
    """Serialized representation of a safety policy evaluation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str | None
    candidate_id: str | None
    system_id: str
    policy_stage: str
    target_environment: str
    action_type: str
    allowed: bool
    risk_classification: str
    violations_json: list[str]
    evaluated_rules_json: dict[str, Any]
    actor: str
    created_at: datetime


class RecoveryPlanRead(BaseModel):
    """Serialized representation of a recovery plan."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    investigation_id: str | None
    twin_model_id: str | None
    title: str
    status: str
    target_environment: str
    root_cause_service_key: str | None
    root_cause_mechanism: str | None
    selected_candidate_id: str | None
    active_approval_id: str | None
    plan_version: int
    plan_hash: str
    cancel_requested: bool
    idempotency_key: str | None
    recovery_attempts: int
    max_recovery_attempts: int
    baseline_metrics_json: dict[str, Any]
    evidence_summary_json: dict[str, Any]
    lifecycle_history_json: list[dict[str, Any]]
    agent_decision_history_json: list[dict[str, Any]]
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class RecoveryPlanDetailRead(RecoveryPlanRead):
    """Complete view of a recovery plan including candidates, sandbox runs, and audit logs."""

    candidates: list[RemediationCandidateRead] = Field(default_factory=list)
    sandbox_runs: list[SandboxVerificationRunRead] = Field(default_factory=list)
    approvals: list[ApprovalRecordRead] = Field(default_factory=list)
    executions: list[RecoveryExecutionRead] = Field(default_factory=list)
    rollbacks: list[RollbackRecordRead] = Field(default_factory=list)
    policy_evaluations: list[SafetyPolicyEvaluationRead] = Field(default_factory=list)
