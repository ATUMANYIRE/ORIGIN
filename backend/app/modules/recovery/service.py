"""Autonomous Recovery Engine, Sandbox Verifier & 8-Role Agent Orchestrator (M04/05).

Implements:
- Explicit recovery lifecycle state machine:
  DETECTED -> INVESTIGATING -> SIMULATING -> PROPOSING -> SANDBOX_VERIFYING
  -> AWAITING_APPROVAL -> APPROVED -> EXECUTING -> OBSERVING
  -> RECOVERED / ROLLED_BACK / REJECTED / FAILED / CANCELLED / MANUAL_INTERVENTION_REQUIRED
- 8 bounded deterministic software agent roles:
  Observer, Investigator, Simulator, RecoveryPlanner, Verifier, SafetyGovernor,
  ExecutionController, EvidenceAuditor.
- Real Sandbox Verification with before/after measurements, Welch's t-test, simulation
  disagreement detection, and mandatory laboratory restoration verification.
- Cryptographically bound (plan_hash + version), single-use token human approval enforcement.
- Saga-like execution with concurrency lock, idempotency, post-action observation,
  automatic rollback on guardrail violation, and MANUAL_INTERVENTION_REQUIRED on rollback failure.
"""

import hashlib
import json
import secrets
import statistics
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ApprovalRecord,
    EvidenceRecord,
    HypothesisRecord,
    RecoveryExecutionRecord,
    RecoveryPlanRecord,
    RemediationCandidateRecord,
    RollbackRecord,
    SafetyPolicyEvaluationRecord,
    SandboxVerificationRunRecord,
    ScientificMemoryEntryRecord,
    SpanObservation,
)
from app.modules.agents.investigator import AutonomousInvestigatorService
from app.modules.agents.schemas import InvestigationCreateRequest
from app.modules.experimentation.engine import compute_experiment_statistics
from app.modules.laboratory.orchestrator import (
    LAB_SYSTEM_SLUG,
    LabTransactionRequest,
    SyntheticLabOrchestrator,
    apply_lab_remediation_action,
    capture_lab_configuration,
    restore_lab_configuration,
)
from app.modules.recovery.policy import SafetyPolicyEngine
from app.modules.recovery.schemas import (
    ApprovalRecordRead,
    CandidateGenerationRequest,
    ManualRollbackRequest,
    PlanMutationRequest,
    RecoveryApprovalRequest,
    RecoveryExecutionRead,
    RecoveryExecutionRequest,
    RecoveryPlanDetailRead,
    RecoveryPlanRead,
    RecoveryWorkflowCreateRequest,
    RemediationCandidateRead,
    RollbackRecordRead,
    SafetyPolicyEvaluationRead,
    SandboxVerificationRunRead,
    SandboxVerifyRequest,
)
from app.modules.registry.service import RegistryService
from app.modules.safety.service import AuditService
from app.modules.simulation.schemas import (
    SimulationBranchCreateRequest,
    TwinCalibrationRequest,
    TwinInterventionSpec,
)
from app.modules.simulation.service import DigitalTwinService

VALID_RECOVERY_TRANSITIONS: dict[str, set[str]] = {
    "DETECTED": {"INVESTIGATING", "SIMULATING", "PROPOSING", "FAILED", "CANCELLED"},
    "INVESTIGATING": {"SIMULATING", "PROPOSING", "FAILED", "CANCELLED"},
    "SIMULATING": {"PROPOSING", "SANDBOX_VERIFYING", "FAILED", "CANCELLED"},
    "PROPOSING": {"SIMULATING", "SANDBOX_VERIFYING", "FAILED", "CANCELLED"},
    "SANDBOX_VERIFYING": {
        "AWAITING_APPROVAL",
        "PROPOSING",
        "FAILED",
        "CANCELLED",
    },
    "AWAITING_APPROVAL": {
        "APPROVED",
        "REJECTED",
        "SANDBOX_VERIFYING",
        "PROPOSING",
        "CANCELLED",
        "FAILED",
    },
    "APPROVED": {
        "EXECUTING",
        "AWAITING_APPROVAL",
        "REJECTED",
        "CANCELLED",
        "FAILED",
    },
    "EXECUTING": {
        "OBSERVING",
        "ROLLED_BACK",
        "MANUAL_INTERVENTION_REQUIRED",
        "FAILED",
        "CANCELLED",
    },
    "OBSERVING": {
        "RECOVERED",
        "ROLLED_BACK",
        "MANUAL_INTERVENTION_REQUIRED",
        "FAILED",
        "CANCELLED",
    },
    "RECOVERED": {"ROLLED_BACK", "MANUAL_INTERVENTION_REQUIRED"},
    "ROLLED_BACK": {"PROPOSING", "SANDBOX_VERIFYING", "AWAITING_APPROVAL", "APPROVED"},
    "REJECTED": {"PROPOSING", "SANDBOX_VERIFYING", "AWAITING_APPROVAL", "APPROVED"},
    "FAILED": {"PROPOSING", "SANDBOX_VERIFYING"},
    "CANCELLED": set(),
    "MANUAL_INTERVENTION_REQUIRED": set(),
}

# Process-level concurrency locks keyed by system_id
_ACTIVE_SYSTEM_EXECUTION_LOCKS: set[str] = set()


class RecoveryExplanationGatewayProtocol(Protocol):
    """Optional constrained LLM explanation gateway (cannot grant permissions or override)."""

    def summarize_candidate_rationale(
        self, root_cause_service: str, mechanism: str, action_type: str
    ) -> str:
        """Generate a human-readable explanation of a candidate remediation."""


class DeterministicRecoveryExplanationGateway:
    """Default deterministic explanation generator requiring zero external paid LLM APIs."""

    def summarize_candidate_rationale(
        self, root_cause_service: str, mechanism: str, action_type: str
    ) -> str:
        return (
            f"Deterministic Planner selected '{action_type}' targeting '{root_cause_service}' "
            f"to remediate verified causal mechanism '{mechanism}' under fail-closed bounds."
        )


def _hash_token(raw_token: str) -> str:
    """Return SHA-256 hex digest of an approval token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def compute_recovery_plan_hash(
    *,
    plan_id: str,
    plan_version: int,
    target_environment: str,
    candidate_id: str | None,
    action_type: str,
    target_service_key: str,
    parameters: dict[str, Any],
) -> str:
    """Compute a deterministic SHA-256 hash binding plan version, action, and parameters."""
    canonical = json.dumps(
        {
            "plan_id": plan_id,
            "plan_version": plan_version,
            "target_environment": target_environment,
            "candidate_id": candidate_id or "",
            "action_type": action_type,
            "target_service_key": target_service_key,
            "parameters": parameters,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def acquire_test_execution_lock(system_id: str) -> None:
    """Helper to acquire a system execution lock (used by concurrency safety tests)."""
    _ACTIVE_SYSTEM_EXECUTION_LOCKS.add(system_id)


def release_test_execution_lock(system_id: str) -> None:
    """Helper to release a system execution lock."""
    _ACTIVE_SYSTEM_EXECUTION_LOCKS.discard(system_id)


class AutonomousRecoveryService:
    """Orchestrates the 8-role autonomous recovery lifecycle with fail-closed safety."""

    @staticmethod
    def _record_transition(
        plan: RecoveryPlanRecord,
        to_state: str,
        *,
        actor: str,
        agent_role: str,
        rationale: str,
        evidence_refs: list[str] | None = None,
    ) -> None:
        """Validate and append a lifecycle state transition."""
        from_state = plan.status
        if from_state != to_state:
            allowed = VALID_RECOVERY_TRANSITIONS.get(from_state, set())
            if to_state not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Invalid recovery lifecycle transition: {from_state} -> {to_state}. "
                        f"Permitted from {from_state}: {sorted(allowed)}"
                    ),
                )
        history = list(plan.lifecycle_history_json or [])
        history.append(
            {
                "from_state": from_state,
                "to_state": to_state,
                "timestamp": datetime.now(UTC).isoformat(),
                "actor": actor,
                "agent_role": agent_role,
                "rationale": rationale,
                "evidence_refs": evidence_refs or [],
            }
        )
        plan.status = to_state
        plan.lifecycle_history_json = history
        plan.updated_at = datetime.now(UTC)

    @staticmethod
    def _record_agent_decision(
        plan: RecoveryPlanRecord,
        *,
        agent_role: str,
        phase: str,
        decision: str,
        rationale: str,
        artifacts: dict[str, Any] | None = None,
    ) -> None:
        """Append a structured decision entry from one of the 8 deterministic agent roles."""
        decisions = list(plan.agent_decision_history_json or [])
        decisions.append(
            {
                "step": len(decisions) + 1,
                "timestamp": datetime.now(UTC).isoformat(),
                "agent_role": agent_role,
                "phase": phase,
                "decision": decision,
                "rationale": rationale,
                "artifacts": artifacts or {},
            }
        )
        plan.agent_decision_history_json = decisions

    @staticmethod
    async def get_plan_model(db: AsyncSession, plan_id: str) -> RecoveryPlanRecord:
        """Fetch a RecoveryPlanRecord or raise 404."""
        stmt = select(RecoveryPlanRecord).where(RecoveryPlanRecord.id == plan_id)
        plan = (await db.execute(stmt)).scalar_one_or_none()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recovery plan '{plan_id}' not found.",
            )
        return plan

    @staticmethod
    async def get_plan_detail(db: AsyncSession, plan_id: str) -> RecoveryPlanDetailRead:
        """Return full RecoveryPlanDetailRead with all child records."""
        plan = await AutonomousRecoveryService.get_plan_model(db, plan_id)
        cands = list(
            (
                await db.execute(
                    select(RemediationCandidateRecord)
                    .where(RemediationCandidateRecord.recovery_plan_id == plan.id)
                    .order_by(RemediationCandidateRecord.rank_score.desc())
                )
            )
            .scalars()
            .all()
        )
        sruns = list(
            (
                await db.execute(
                    select(SandboxVerificationRunRecord)
                    .where(SandboxVerificationRunRecord.recovery_plan_id == plan.id)
                    .order_by(SandboxVerificationRunRecord.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        apps = list(
            (
                await db.execute(
                    select(ApprovalRecord)
                    .where(ApprovalRecord.recovery_plan_id == plan.id)
                    .order_by(ApprovalRecord.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        execs = list(
            (
                await db.execute(
                    select(RecoveryExecutionRecord)
                    .where(RecoveryExecutionRecord.recovery_plan_id == plan.id)
                    .order_by(RecoveryExecutionRecord.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        rbacks = list(
            (
                await db.execute(
                    select(RollbackRecord)
                    .where(RollbackRecord.recovery_plan_id == plan.id)
                    .order_by(RollbackRecord.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        pols = list(
            (
                await db.execute(
                    select(SafetyPolicyEvaluationRecord)
                    .where(SafetyPolicyEvaluationRecord.recovery_plan_id == plan.id)
                    .order_by(SafetyPolicyEvaluationRecord.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        base_read = RecoveryPlanRead.model_validate(plan)
        return RecoveryPlanDetailRead(
            **base_read.model_dump(),
            candidates=[RemediationCandidateRead.model_validate(c) for c in cands],
            sandbox_runs=[SandboxVerificationRunRead.model_validate(s) for s in sruns],
            approvals=[ApprovalRecordRead.model_validate(a) for a in apps],
            executions=[RecoveryExecutionRead.model_validate(e) for e in execs],
            rollbacks=[RollbackRecordRead.model_validate(r) for r in rbacks],
            policy_evaluations=[SafetyPolicyEvaluationRead.model_validate(p) for p in pols],
        )

    @staticmethod
    async def list_plans(
        db: AsyncSession, system_id: str | None = None, limit: int = 50
    ) -> list[RecoveryPlanRead]:
        """List recent recovery plans ordered newest first."""
        stmt = (
            select(RecoveryPlanRecord).order_by(RecoveryPlanRecord.created_at.desc()).limit(limit)
        )
        if system_id:
            stmt = stmt.where(RecoveryPlanRecord.system_id == system_id)
        rows = list((await db.execute(stmt)).scalars().all())
        return [RecoveryPlanRead.model_validate(r) for r in rows]

    @staticmethod
    async def create_recovery_workflow(
        db: AsyncSession,
        request: RecoveryWorkflowCreateRequest,
        *,
        actor: str = "autonomous-operator",
        correlation_id: str | None = None,
    ) -> RecoveryPlanDetailRead:
        """Create a recovery workflow, validate causal evidence, and optionally run sandbox."""
        if request.system_slug == LAB_SYSTEM_SLUG:
            await SyntheticLabOrchestrator.ensure_lab_registered(db)
        system = await RegistryService.get_system_by_id_or_slug(db, request.system_slug)

        # Idempotency check on workflow creation
        if request.idempotency_key:
            existing_stmt = select(RecoveryPlanRecord).where(
                RecoveryPlanRecord.idempotency_key == request.idempotency_key
            )
            existing_plan = (await db.execute(existing_stmt)).scalar_one_or_none()
            if existing_plan:
                return await AutonomousRecoveryService.get_plan_detail(db, existing_plan.id)

        # Fail-closed environment policy check via SafetyGovernor
        env_eval = await SafetyPolicyEngine.evaluate_and_record(
            db,
            system_id=system.id,
            policy_stage="workflow_creation",
            target_environment=request.target_environment,
            action_type="restore_safe_lab_configuration",
            actor="SafetyGovernor",
        )
        if not env_eval.allowed:
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Safety Policy Violation: {'; '.join(env_eval.violations_json)}",
            )

        # 1. Observer Role: Collect recent telemetry baseline
        recent_spans = list(
            (
                await db.execute(
                    select(SpanObservation)
                    .where(SpanObservation.system_id == system.id)
                    .order_by(SpanObservation.started_at.desc())
                    .limit(40)
                )
            )
            .scalars()
            .all()
        )
        if len(recent_spans) < 5:
            await SyntheticLabOrchestrator.run_workload(
                db,
                LabTransactionRequest(iterations=4),
                actor="Observer",
            )
            recent_spans = list(
                (
                    await db.execute(
                        select(SpanObservation)
                        .where(SpanObservation.system_id == system.id)
                        .order_by(SpanObservation.started_at.desc())
                        .limit(40)
                    )
                )
                .scalars()
                .all()
            )

        gw_lats = [
            float(s.duration_ms)
            for s in recent_spans
            if s.service_key in ("api-gateway", "checkout-service")
        ]
        baseline_mean_ms = round(statistics.fmean(gw_lats), 2) if gw_lats else 120.0
        baseline_err_pct = (
            round(
                (sum(1 for s in recent_spans if s.http_status >= 500) / max(1, len(recent_spans)))
                * 100.0,
                2,
            )
            if recent_spans
            else 0.0
        )

        plan = RecoveryPlanRecord(
            system_id=system.id,
            investigation_id=request.investigation_id,
            title=request.title,
            status="DETECTED",
            target_environment=request.target_environment,
            idempotency_key=request.idempotency_key,
            baseline_metrics_json={
                "mean_latency_ms": baseline_mean_ms,
                "error_rate_pct": baseline_err_pct,
                "observed_span_count": len(recent_spans),
            },
            lifecycle_history_json=[
                {
                    "from_state": None,
                    "to_state": "DETECTED",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "actor": actor,
                    "agent_role": "Observer",
                    "rationale": (
                        f"Observer detected system baseline mean_latency_ms={baseline_mean_ms}ms "
                        f"across {len(recent_spans)} recent spans."
                    ),
                    "evidence_refs": [s.correlation_id for s in recent_spans[:4]],
                }
            ],
            agent_decision_history_json=[],
        )
        db.add(plan)
        await db.flush()
        env_eval.recovery_plan_id = plan.id

        AutonomousRecoveryService._record_agent_decision(
            plan,
            agent_role="Observer",
            phase="DETECTED",
            decision="telemetry_validated",
            rationale=(
                f"Collected {len(recent_spans)} spans; baseline latency={baseline_mean_ms}ms."
            ),
            artifacts={"baseline_mean_latency_ms": baseline_mean_ms},
        )

        # 2. Investigator Role: Validate or run causal investigation
        AutonomousRecoveryService._record_transition(
            plan,
            "INVESTIGATING",
            actor=actor,
            agent_role="Investigator",
            rationale="Validating causal root-cause evidence before proposing recovery candidates.",
        )

        evidence_refs: list[str] = []
        causal_confidence = 0.0
        root_service = request.operator_root_cause_service_key
        root_mech = request.operator_root_cause_mechanism

        if request.investigation_id:
            inv = await AutonomousInvestigatorService.get_investigation_model(
                db, request.investigation_id
            )
            if inv.status == "CREATED":
                await AutonomousInvestigatorService.run_investigation(
                    db, inv.id, actor="Investigator"
                )
                await db.refresh(inv)

            ev_rows = list(
                (
                    await db.execute(
                        select(EvidenceRecord).where(EvidenceRecord.investigation_id == inv.id)
                    )
                )
                .scalars()
                .all()
            )
            hyp_rows = list(
                (
                    await db.execute(
                        select(HypothesisRecord)
                        .where(HypothesisRecord.investigation_id == inv.id)
                        .order_by(HypothesisRecord.confidence_score.desc())
                    )
                )
                .scalars()
                .all()
            )
            evidence_refs = [e.id for e in ev_rows]
            top_hyp = hyp_rows[0] if hyp_rows else None
            causal_confidence = float(top_hyp.confidence_score) if top_hyp else 0.0
            root_service = inv.concluded_cause_service_key or (
                top_hyp.root_cause_service_key if top_hyp else None
            )
            root_mech = inv.concluded_mechanism or (
                top_hyp.suspected_mechanism if top_hyp else None
            )
            if inv.status != "CONCLUDED" or causal_confidence < 0.55 or not ev_rows:
                pol_fail = await SafetyPolicyEngine.evaluate_and_record(
                    db,
                    system_id=system.id,
                    recovery_plan_id=plan.id,
                    policy_stage="causal_evidence_validation",
                    target_environment=plan.target_environment,
                    action_type="restore_safe_lab_configuration",
                    evidence_count=len(ev_rows),
                    causal_confidence=causal_confidence,
                    actor="SafetyGovernor",
                )
                AutonomousRecoveryService._record_transition(
                    plan,
                    "FAILED",
                    actor="SafetyGovernor",
                    agent_role="SafetyGovernor",
                    rationale=(
                        f"Rejected recovery planning due to insufficient causal evidence "
                        f"(investigation status={inv.status}, confidence={causal_confidence:.2f})."
                    ),
                )
                plan.failure_reason = "; ".join(pol_fail.violations_json) or (
                    f"Investigation {inv.id} is {inv.status} without sufficient causal proof."
                )
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=plan.failure_reason,
                )
        elif root_service and root_mech:
            # Operator-identified root cause with telemetry correlation references
            evidence_refs = list({s.correlation_id for s in recent_spans[:4]})
            causal_confidence = 0.80
        else:
            # Launch an autonomous causal investigation automatically!
            inv_created = await AutonomousInvestigatorService.create_investigation(
                db,
                InvestigationCreateRequest(
                    system_slug=system.slug,
                    title=f"Causal Investigation for {request.title}",
                    target_service_key="checkout-service",
                    experiment_budget=3,
                    sample_size_per_arm=4,
                    random_seed=request.random_seed,
                    auto_run=True,
                ),
                actor="Investigator",
                correlation_id=correlation_id,
            )
            inv_detail = await AutonomousInvestigatorService.run_investigation(
                db, inv_created.id, actor="Investigator"
            )
            plan.investigation_id = inv_detail.id
            evidence_refs = [e.id for e in inv_detail.evidence_records]
            top_hyp_read = inv_detail.hypotheses[0] if inv_detail.hypotheses else None
            causal_confidence = float(top_hyp_read.confidence_score) if top_hyp_read else 0.0
            root_service = inv_detail.concluded_cause_service_key
            root_mech = inv_detail.concluded_mechanism

            if inv_detail.status != "CONCLUDED" or not root_service or causal_confidence < 0.55:
                await SafetyPolicyEngine.evaluate_and_record(
                    db,
                    system_id=system.id,
                    recovery_plan_id=plan.id,
                    policy_stage="causal_evidence_validation",
                    target_environment=plan.target_environment,
                    action_type="restore_safe_lab_configuration",
                    evidence_count=len(evidence_refs),
                    causal_confidence=causal_confidence,
                    actor="SafetyGovernor",
                )
                AutonomousRecoveryService._record_transition(
                    plan,
                    "FAILED",
                    actor="Investigator",
                    agent_role="Investigator",
                    rationale=(
                        f"Autonomous investigation {inv_detail.id} ended in {inv_detail.status}; "
                        f"refusing to guess remediation without causal proof."
                    ),
                )
                plan.failure_reason = (
                    f"Insufficient causal evidence: investigation status={inv_detail.status}, "
                    f"confidence={causal_confidence:.2f}."
                )
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=plan.failure_reason,
                )

        plan.root_cause_service_key = root_service
        plan.root_cause_mechanism = root_mech
        plan.evidence_summary_json = {
            "investigation_id": plan.investigation_id,
            "root_cause_service_key": root_service,
            "root_cause_mechanism": root_mech,
            "causal_confidence_score": causal_confidence,
            "evidence_reference_ids": evidence_refs,
        }

        AutonomousRecoveryService._record_agent_decision(
            plan,
            agent_role="Investigator",
            phase="INVESTIGATING",
            decision="causal_root_cause_confirmed",
            rationale=(
                f"Confirmed root cause service='{root_service}' ({root_mech}) "
                f"with confidence={causal_confidence:.2f} and {len(evidence_refs)} evidence refs."
            ),
            artifacts=plan.evidence_summary_json,
        )
        await db.commit()

        if request.auto_prepare_to_approval:
            await AutonomousRecoveryService.generate_and_simulate_candidates(
                db, plan.id, actor=actor
            )
            await AutonomousRecoveryService.run_sandbox_verification(
                db,
                plan.id,
                SandboxVerifyRequest(
                    trials_per_arm=request.sandbox_trials_per_arm,
                    random_seed=request.random_seed,
                ),
                actor=actor,
            )

        return await AutonomousRecoveryService.get_plan_detail(db, plan.id)

    @staticmethod
    async def generate_and_simulate_candidates(
        db: AsyncSession,
        plan_id: str,
        request: CandidateGenerationRequest | None = None,
        *,
        actor: str = "RecoveryPlanner",
    ) -> RecoveryPlanDetailRead:
        """Generate bounded remediation candidates and simulate each in the Digital Twin."""
        plan = await AutonomousRecoveryService.get_plan_model(db, plan_id)
        if plan.cancel_requested or plan.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Recovery plan is cancelled.",
            )

        req = request or CandidateGenerationRequest()
        ev_refs = list(plan.evidence_summary_json.get("evidence_reference_ids", ["ev-1"]))
        causal_conf = float(plan.evidence_summary_json.get("causal_confidence_score", 0.85))

        # If custom candidate requested, validate via SafetyGovernor first
        if req.custom_action_type:
            target_svc = (
                req.custom_target_service_key or plan.root_cause_service_key or "checkout-service"
            )
            pol = await SafetyPolicyEngine.evaluate_and_record(
                db,
                system_id=plan.system_id,
                recovery_plan_id=plan.id,
                policy_stage="candidate_generation",
                target_environment=plan.target_environment,
                action_type=req.custom_action_type,
                target_service_key=target_svc,
                parameters=req.custom_parameters,
                evidence_count=len(ev_refs),
                causal_confidence=causal_conf,
                recovery_attempts=plan.recovery_attempts,
                max_recovery_attempts=plan.max_recovery_attempts,
                actor="SafetyGovernor",
            )
            if not pol.allowed:
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Safety Policy rejected candidate: {'; '.join(pol.violations_json)}",
                )

        # 3. Simulator Role: Calibrate Digital Twin from current evidence
        AutonomousRecoveryService._record_transition(
            plan,
            "SIMULATING",
            actor=actor,
            agent_role="Simulator",
            rationale="Calibrating Digital Twin and simulating candidate remediation trajectories.",
            evidence_refs=ev_refs,
        )
        twin_bundle = await DigitalTwinService.create_or_calibrate_twin(
            db,
            TwinCalibrationRequest(
                system_slug=LAB_SYSTEM_SLUG,
                investigation_id=plan.investigation_id,
                min_required_observations=8,
            ),
            actor="Simulator",
        )
        twin_id = twin_bundle["twin_model"]["id"]
        plan.twin_model_id = twin_id

        # 4. RecoveryPlanner Role: Generate competing candidate strategies for the root cause
        AutonomousRecoveryService._record_transition(
            plan,
            "PROPOSING",
            actor=actor,
            agent_role="RecoveryPlanner",
            rationale="Proposing bounded remediation candidates ranked by simulated outcome.",
            evidence_refs=ev_refs,
        )

        root_svc = plan.root_cause_service_key or "payment-simulator"
        root_mech = plan.root_cause_mechanism or "payment_gateway_latency_propagation"
        explainer = DeterministicRecoveryExplanationGateway()

        specs: list[dict[str, Any]] = []
        if req.custom_action_type:
            specs.append(
                {
                    "target_service_key": req.custom_target_service_key or root_svc,
                    "action_type": req.custom_action_type,
                    "parameters": req.custom_parameters,
                    "twin_intervention": TwinInterventionSpec(
                        intervention_type="restore_configuration",
                        target_service_key=req.custom_target_service_key or root_svc,
                        value=1.0,
                    ),
                    "expected_effect": {
                        "expected_latency_reduction_pct": 55.0,
                        "target_metric": "request_latency_ms",
                    },
                    "adverse_effects": [
                        "Potential transient state reset during configuration change."
                    ],
                }
            )
        elif root_svc == "payment-simulator":
            specs = [
                {
                    "target_service_key": "payment-simulator",
                    "action_type": "restart_synthetic_service",
                    "parameters": {"fastpath_isolation": True, "graceful_drain_ms": 200},
                    "twin_intervention": TwinInterventionSpec(
                        intervention_type="reduce_downstream_latency",
                        target_service_key="payment-simulator",
                        value=0.10,
                        description="Restart payment-simulator onto isolated clearing fast-path",
                    ),
                    "expected_effect": {
                        "expected_latency_reduction_pct": 75.0,
                        "target_metric": "request_latency_ms",
                    },
                    "adverse_effects": [
                        "Brief connection pool drain (~200ms) during synthetic service restart."
                    ],
                },
                {
                    "target_service_key": "checkout-service",
                    "action_type": "toggle_circuit_breaker",
                    "parameters": {"enabled": True, "threshold_ms": 240.0},
                    "twin_intervention": TwinInterventionSpec(
                        intervention_type="enable_circuit_breaker",
                        target_service_key="checkout-service",
                        value=1.0,
                        description="Enable checkout circuit breaker to fast-fail slow calls",
                    ),
                    "expected_effect": {
                        "expected_latency_reduction_pct": 65.0,
                        "target_metric": "request_latency_ms",
                    },
                    "adverse_effects": [
                        "Introduces bounded fast-fail fallback error rate (~4–9%) while recovering."
                    ],
                },
                {
                    "target_service_key": "api-gateway",
                    "action_type": "apply_rate_limiting",
                    "parameters": {"rate_limit_factor": 0.65},
                    "twin_intervention": TwinInterventionSpec(
                        intervention_type="reduce_incoming_traffic",
                        target_service_key="api-gateway",
                        value=0.65,
                        description="Throttle incoming gateway traffic to 65%",
                    ),
                    "expected_effect": {
                        "expected_latency_reduction_pct": 35.0,
                        "target_metric": "request_latency_ms",
                    },
                    "adverse_effects": ["Sheds 35% of incoming order throughput at api-gateway."],
                },
            ]
        elif root_svc == "order-database-sim":
            specs = [
                {
                    "target_service_key": "order-database-sim",
                    "action_type": "adjust_db_contention_controls",
                    "parameters": {
                        "db_connection_capacity": 160.0,
                        "snapshot_isolation": True,
                    },
                    "twin_intervention": TwinInterventionSpec(
                        intervention_type="adjust_db_connection_capacity",
                        target_service_key="order-database-sim",
                        value=160.0,
                        description="Expand DB connection capacity to 160 and enable lock relief",
                    ),
                    "expected_effect": {
                        "expected_latency_reduction_pct": 72.0,
                        "target_metric": "request_latency_ms",
                    },
                    "adverse_effects": [
                        "Increases database memory footprint for expanded connection pool."
                    ],
                },
                {
                    "target_service_key": "checkout-service",
                    "action_type": "adjust_service_replicas",
                    "parameters": {"replicas": 6},
                    "twin_intervention": TwinInterventionSpec(
                        intervention_type="increase_replicas",
                        target_service_key="checkout-service",
                        value=6.0,
                        description="Scale checkout-service replicas 2 -> 6 (naive scaling)",
                    ),
                    "expected_effect": {
                        "expected_latency_reduction_pct": 5.0,
                        "target_metric": "request_latency_ms",
                    },
                    "adverse_effects": [
                        "Amplifies downstream row-lock contention on order-database-sim!"
                    ],
                },
            ]
        else:
            # inventory-service or checkout-service
            specs = [
                {
                    "target_service_key": "inventory-service",
                    "action_type": "adjust_service_replicas",
                    "parameters": {"replicas": 4},
                    "twin_intervention": TwinInterventionSpec(
                        intervention_type="increase_replicas",
                        target_service_key="inventory-service",
                        value=4.0,
                        description="Scale inventory-service replicas 2 -> 4",
                    ),
                    "expected_effect": {
                        "expected_latency_reduction_pct": 70.0,
                        "target_metric": "request_latency_ms",
                    },
                    "adverse_effects": [
                        "Higher container compute allocation in synthetic laboratory."
                    ],
                },
                {
                    "target_service_key": "checkout-service",
                    "action_type": "modify_concurrency_limit",
                    "parameters": {"concurrency_limit": 65},
                    "twin_intervention": TwinInterventionSpec(
                        intervention_type="adjust_concurrency_limit",
                        target_service_key="checkout-service",
                        value=65.0,
                        description="Adjust checkout-service worker concurrency limit to 65",
                    ),
                    "expected_effect": {
                        "expected_latency_reduction_pct": 30.0,
                        "target_metric": "request_latency_ms",
                    },
                    "adverse_effects": ["Slightly higher memory utilization per replica."],
                },
            ]

        # Run baseline branch in Digital Twin for comparison
        base_branch = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_id,
                name=f"Recovery Plan Baseline ({root_svc})",
                branch_type="baseline",
                investigation_id=plan.investigation_id,
                random_seed=42,
                horizon_seconds=15.0,
            ),
            actor="Simulator",
        )
        base_sim_lat = float(base_branch.outcome_summary_json.get("mean_latency_ms", 400.0))

        created_candidates: list[RemediationCandidateRecord] = []
        for idx, sp in enumerate(specs):
            pol_eval = await SafetyPolicyEngine.evaluate_and_record(
                db,
                system_id=plan.system_id,
                recovery_plan_id=plan.id,
                policy_stage="candidate_generation",
                target_environment=plan.target_environment,
                action_type=sp["action_type"],
                target_service_key=sp["target_service_key"],
                parameters=sp["parameters"],
                evidence_count=len(ev_refs),
                causal_confidence=causal_conf,
                actor="SafetyGovernor",
            )

            sim_branch = await DigitalTwinService.create_and_run_branch(
                db,
                SimulationBranchCreateRequest(
                    twin_model_id=twin_id,
                    name=f"Candidate {idx + 1}: {sp['action_type']} on {sp['target_service_key']}",
                    branch_type="counterfactual",
                    parent_branch_id=base_branch.id,
                    investigation_id=plan.investigation_id,
                    random_seed=42,
                    horizon_seconds=15.0,
                    interventions=[sp["twin_intervention"]],
                ),
                actor="Simulator",
            )
            cand_sim_lat = float(
                sim_branch.outcome_summary_json.get("mean_latency_ms", base_sim_lat)
            )
            cand_sim_err = float(sim_branch.outcome_summary_json.get("mean_error_rate_pct", 0.5))
            cand_sim_tp = float(sim_branch.outcome_summary_json.get("mean_throughput_rps", 44.0))
            sim_red_pct = round(((base_sim_lat - cand_sim_lat) / max(1.0, base_sim_lat)) * 100.0, 2)

            risk_penalty = {"low": 0.0, "medium": 5.0, "high": 18.0, "critical": 90.0}[
                pol_eval.risk_classification
            ]
            rank_score = round(sim_red_pct - cand_sim_err * 1.5 - risk_penalty, 2)

            cand = RemediationCandidateRecord(
                recovery_plan_id=plan.id,
                system_id=plan.system_id,
                target_service_key=sp["target_service_key"],
                suspected_root_cause=f"{root_svc}: {root_mech}",
                action_type=sp["action_type"],
                parameters_json=sp["parameters"],
                preconditions_json=[
                    "Target environment must be 'synthetic-lab'",
                    "Laboratory unsafe lock must be False",
                    f"Causal investigation evidence count >= 1 (actual={len(ev_refs)})",
                ],
                expected_effect_json={
                    **sp["expected_effect"],
                    "rationale": explainer.summarize_candidate_rationale(
                        root_svc, root_mech, sp["action_type"]
                    ),
                },
                adverse_effects_json=sp["adverse_effects"],
                rollback_strategy_json={
                    "strategy": "automatic_state_snapshot_restore",
                    "fallback_action": "restore_safe_lab_configuration",
                    "target_service_key": sp["target_service_key"],
                    "verification_required": True,
                },
                evidence_refs_json=ev_refs,
                simulation_branch_id=sim_branch.id,
                simulation_prediction_json={
                    "epistemic_label": "counterfactual_prediction",
                    "baseline_simulated_latency_ms": base_sim_lat,
                    "predicted_mean_latency_ms": cand_sim_lat,
                    "predicted_latency_reduction_pct": sim_red_pct,
                    "predicted_error_rate_pct": cand_sim_err,
                    "predicted_throughput_rps": cand_sim_tp,
                    "uncertainty_95_ms": [
                        sim_branch.uncertainty_json.get("latency_ci_lower_95_ms"),
                        sim_branch.uncertainty_json.get("latency_ci_upper_95_ms"),
                    ],
                    "note": (
                        "SIMULATED ONLY: Digital Twin prediction does NOT authorize execution "
                        "or mark candidate verified until real sandbox verification completes."
                    ),
                },
                verification_status=("simulated_only" if pol_eval.allowed else "policy_rejected"),
                risk_classification=pol_eval.risk_classification,
                approval_requirements_json={
                    "require_human_approval": True,
                    "require_sandbox_verification": True,
                    "required_role": "reliability-commander",
                    "single_use_token_binding": True,
                },
                rank_score=rank_score,
            )
            db.add(cand)
            await db.flush()
            pol_eval.candidate_id = cand.id
            created_candidates.append(cand)

        created_candidates.sort(key=lambda c: c.rank_score, reverse=True)
        best = created_candidates[0]
        plan.selected_candidate_id = best.id
        plan.plan_hash = compute_recovery_plan_hash(
            plan_id=plan.id,
            plan_version=plan.plan_version,
            target_environment=plan.target_environment,
            candidate_id=best.id,
            action_type=best.action_type,
            target_service_key=best.target_service_key,
            parameters=best.parameters_json,
        )

        best_pred_pct = best.simulation_prediction_json["predicted_latency_reduction_pct"]
        AutonomousRecoveryService._record_agent_decision(
            plan,
            agent_role="Simulator",
            phase="SIMULATING",
            decision="counterfactual_candidates_evaluated",
            rationale=(
                f"Simulated {len(created_candidates)} candidates in Digital Twin {twin_id}; "
                f"top candidate '{best.action_type}' predicted {best_pred_pct}% latency "
                f"reduction (status=simulated_only)."
            ),
            artifacts={"selected_candidate_id": best.id, "twin_model_id": twin_id},
        )
        await db.commit()
        return await AutonomousRecoveryService.get_plan_detail(db, plan.id)

    @staticmethod
    async def run_sandbox_verification(
        db: AsyncSession,
        plan_id: str,
        request: SandboxVerifyRequest,
        *,
        actor: str = "Verifier",
    ) -> RecoveryPlanDetailRead:
        """Execute real isolated laboratory sandbox verification with restoration check."""
        plan = await AutonomousRecoveryService.get_plan_model(db, plan_id)
        if plan.cancel_requested or plan.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Recovery plan is cancelled.",
            )

        cand_id = request.candidate_id or plan.selected_candidate_id
        if not cand_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No remediation candidate selected for sandbox verification.",
            )

        cand = (
            await db.execute(
                select(RemediationCandidateRecord).where(
                    RemediationCandidateRecord.id == cand_id,
                    RemediationCandidateRecord.recovery_plan_id == plan.id,
                )
            )
        ).scalar_one_or_none()
        if not cand:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidate '{cand_id}' not found on recovery plan '{plan.id}'.",
            )

        # SafetyGovernor pre-check for sandbox duration & lab lock
        pol = await SafetyPolicyEngine.evaluate_and_record(
            db,
            system_id=plan.system_id,
            recovery_plan_id=plan.id,
            candidate_id=cand.id,
            policy_stage="sandbox_precheck",
            target_environment=plan.target_environment,
            action_type=cand.action_type,
            target_service_key=cand.target_service_key,
            parameters=cand.parameters_json,
            evidence_count=len(cand.evidence_refs_json),
            duration_seconds=request.duration_seconds,
            has_rollback_strategy=bool(cand.rollback_strategy_json),
            actor="SafetyGovernor",
        )
        if not pol.allowed:
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Sandbox verification blocked by SafetyPolicyEngine: "
                    f"{'; '.join(pol.violations_json)}"
                ),
            )

        AutonomousRecoveryService._record_transition(
            plan,
            "SANDBOX_VERIFYING",
            actor=actor,
            agent_role="Verifier",
            rationale=(
                f"Executing real sandbox verification for candidate '{cand.action_type}' "
                f"on '{cand.target_service_key}'."
            ),
        )

        # 1. Capture initial laboratory configuration
        initial_config = capture_lab_configuration()

        # 2. Measure baseline performance (Control Arm)
        baseline_traces = []
        for i in range(request.trials_per_arm):
            tr = await SyntheticLabOrchestrator.execute_instrumented_transaction(
                db,
                profile=None,
                intervention="none",
                experiment_arm="sandbox_baseline",
                rng_seed=request.random_seed + i,
            )
            baseline_traces.append(tr)

        base_lats = [float(t.total_duration_ms) for t in baseline_traces]
        base_errs = [1 if t.gateway_status >= 500 else 0 for t in baseline_traces]
        base_mean_ms = round(statistics.fmean(base_lats), 2)
        base_err_pct = round(statistics.fmean(base_errs) * 100.0, 2)

        # 3. Apply candidate remediation in isolated laboratory
        apply_lab_remediation_action(
            cand.action_type,
            cand.target_service_key,
            cand.parameters_json,
        )

        # 4. Measure treatment performance (Treatment Arm)
        treatment_traces = []
        for i in range(request.trials_per_arm):
            tr = await SyntheticLabOrchestrator.execute_instrumented_transaction(
                db,
                profile=None,
                intervention="none",
                experiment_arm="sandbox_treatment",
                rng_seed=request.random_seed + 100 + i,
            )
            treatment_traces.append(tr)

        treat_lats = [float(t.total_duration_ms) for t in treatment_traces]
        treat_errs = [1 if t.gateway_status >= 500 else 0 for t in treatment_traces]
        treat_mean_ms = round(statistics.fmean(treat_lats), 2)
        treat_err_pct = round(statistics.fmean(treat_errs) * 100.0, 2)

        all_corrs = [t.correlation_id for t in baseline_traces + treatment_traces]
        stats_comp = compute_experiment_statistics(
            control_values=base_lats,
            treatment_values=treat_lats,
            trial_correlation_ids=all_corrs,
            measurement_unit="ms",
        )

        # 5. Restore laboratory to initial configuration & verify restoration!
        restored_ok, post_restore_config = restore_lab_configuration(
            initial_config,
            simulate_restore_failure=request.simulate_restore_failure,
        )

        restore_trace = await SyntheticLabOrchestrator.execute_instrumented_transaction(
            db,
            profile=None,
            intervention="none",
            experiment_arm="sandbox_post_restore_check",
            rng_seed=request.random_seed + 500,
        )

        # 6. Check for regressions and simulation disagreement
        regressions: list[str] = []
        if treat_mean_ms > base_mean_ms * 1.05:
            regressions.append(
                f"Latency regression detected: treatment mean ({treat_mean_ms}ms) "
                f"> baseline ({base_mean_ms}ms)."
            )
        if treat_err_pct > 8.0 and treat_err_pct > base_err_pct:
            regressions.append(
                f"Error rate regression detected: treatment error rate {treat_err_pct}% "
                f"exceeds 8.0% threshold."
            )

        observed_reduction_pct = round(
            ((base_mean_ms - treat_mean_ms) / max(1.0, base_mean_ms)) * 100.0, 2
        )
        predicted_reduction_pct = float(
            cand.simulation_prediction_json.get("predicted_latency_reduction_pct", 0.0)
        )
        sim_disagreement = abs(predicted_reduction_pct - observed_reduction_pct) > 35.0
        disagreement_info = {
            "predicted_latency_reduction_pct": predicted_reduction_pct,
            "observed_latency_reduction_pct": observed_reduction_pct,
            "disagreement_detected": sim_disagreement,
            "note": (
                "Significant divergence between Digital Twin prediction and sandbox outcome!"
                if sim_disagreement
                else "Observed sandbox effect matches Digital Twin directional prediction."
            ),
        }

        passed_thresholds = len(regressions) == 0 and (
            treat_mean_ms <= base_mean_ms * 0.75 or treat_mean_ms < 160.0
        )

        run_status = (
            "RESTORATION_FAILED"
            if not restored_ok
            else ("COMPLETED" if passed_thresholds else "FAILED")
        )

        srun = SandboxVerificationRunRecord(
            recovery_plan_id=plan.id,
            candidate_id=cand.id,
            system_id=plan.system_id,
            status=run_status,
            initial_config_json=initial_config,
            baseline_metrics_json={
                "mean_latency_ms": base_mean_ms,
                "error_rate_pct": base_err_pct,
                "sample_count": len(base_lats),
                "correlation_ids": [t.correlation_id for t in baseline_traces],
            },
            treatment_metrics_json={
                "mean_latency_ms": treat_mean_ms,
                "error_rate_pct": treat_err_pct,
                "sample_count": len(treat_lats),
                "correlation_ids": [t.correlation_id for t in treatment_traces],
            },
            post_restore_config_json=post_restore_config,
            post_restore_metrics_json={
                "post_restore_latency_ms": restore_trace.total_duration_ms,
                "correlation_id": restore_trace.correlation_id,
            },
            statistical_comparison_json=stats_comp,
            regressions_detected_json=regressions,
            simulation_disagreement_json=disagreement_info,
            passed_thresholds=passed_thresholds and restored_ok,
            restoration_verified=restored_ok,
            evidence_trail_json={
                "epistemic_label": "sandbox_experimental_verification",
                "all_correlation_ids": all_corrs + [restore_trace.correlation_id],
            },
        )
        db.add(srun)
        await db.flush()
        cand.sandbox_verification_id = srun.id

        if not restored_ok:
            cand.verification_status = "sandbox_failed"
            AutonomousRecoveryService._record_transition(
                plan,
                "FAILED",
                actor=actor,
                agent_role="Verifier",
                rationale="Sandbox restoration failed! Laboratory marked unsafe and locked.",
                evidence_refs=all_corrs,
            )
            plan.failure_reason = (
                "Sandbox configuration restoration failed verification; "
                "laboratory locked as unsafe."
            )
            await AuditService.record_event(
                db,
                system_id=plan.system_id,
                actor="Verifier",
                action="recovery.sandbox_restoration_failed",
                resource_type="sandbox_verification_run",
                resource_id=srun.id,
                severity="critical",
                details={"recovery_plan_id": plan.id, "candidate_id": cand.id},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=plan.failure_reason,
            )

        if not passed_thresholds:
            cand.verification_status = "sandbox_failed"
            AutonomousRecoveryService._record_transition(
                plan,
                "FAILED",
                actor=actor,
                agent_role="Verifier",
                rationale=(
                    f"Sandbox verification failed thresholds: baseline={base_mean_ms}ms, "
                    f"treatment={treat_mean_ms}ms, regressions={regressions}."
                ),
                evidence_refs=all_corrs,
            )
            plan.failure_reason = (
                f"Sandbox verification failed thresholds (baseline={base_mean_ms}ms -> "
                f"treatment={treat_mean_ms}ms). {'; '.join(regressions)}"
            )
            await db.commit()
            return await AutonomousRecoveryService.get_plan_detail(db, plan.id)

        # Sandbox verification succeeded and restoration is verified!
        cand.verification_status = "sandbox_verified"
        plan.selected_candidate_id = cand.id
        plan.plan_hash = compute_recovery_plan_hash(
            plan_id=plan.id,
            plan_version=plan.plan_version,
            target_environment=plan.target_environment,
            candidate_id=cand.id,
            action_type=cand.action_type,
            target_service_key=cand.target_service_key,
            parameters=cand.parameters_json,
        )
        AutonomousRecoveryService._record_transition(
            plan,
            "AWAITING_APPROVAL",
            actor=actor,
            agent_role="Verifier",
            rationale=(
                f"Sandbox verification passed ({base_mean_ms}ms -> {treat_mean_ms}ms, "
                f"-{observed_reduction_pct}%) and laboratory restoration verified. "
                f"Awaiting human approval (plan_hash={plan.plan_hash[:12]})."
            ),
            evidence_refs=all_corrs,
        )
        AutonomousRecoveryService._record_agent_decision(
            plan,
            agent_role="Verifier",
            phase="SANDBOX_VERIFYING",
            decision="sandbox_verified_and_restored",
            rationale=(
                f"Measured {base_mean_ms}ms -> {treat_mean_ms}ms in sandbox; "
                f"restoration_verified={restored_ok}."
            ),
            artifacts={
                "sandbox_verification_id": srun.id,
                "observed_reduction_pct": observed_reduction_pct,
                "simulation_disagreement": disagreement_info,
            },
        )
        await db.commit()
        return await AutonomousRecoveryService.get_plan_detail(db, plan.id)

    @staticmethod
    async def mutate_recovery_plan(
        db: AsyncSession,
        plan_id: str,
        request: PlanMutationRequest,
        *,
        actor: str = "operator",
    ) -> RecoveryPlanDetailRead:
        """Mutate a recovery plan's candidate or parameters, invalidating prior approvals."""
        plan = await AutonomousRecoveryService.get_plan_model(db, plan_id)
        cand_id = request.selected_candidate_id or plan.selected_candidate_id
        cand = (
            await db.execute(
                select(RemediationCandidateRecord).where(
                    RemediationCandidateRecord.id == cand_id,
                    RemediationCandidateRecord.recovery_plan_id == plan.id,
                )
            )
        ).scalar_one_or_none()
        if not cand:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected candidate not found.",
            )

        if request.parameter_overrides:
            updated_params = dict(cand.parameters_json)
            updated_params.update(request.parameter_overrides)
            cand.parameters_json = updated_params

        plan.selected_candidate_id = cand.id
        plan.plan_version += 1
        plan.plan_hash = compute_recovery_plan_hash(
            plan_id=plan.id,
            plan_version=plan.plan_version,
            target_environment=plan.target_environment,
            candidate_id=cand.id,
            action_type=cand.action_type,
            target_service_key=cand.target_service_key,
            parameters=cand.parameters_json,
        )
        # Invalidate any active approval when the plan changes!
        if plan.active_approval_id:
            old_app = (
                await db.execute(
                    select(ApprovalRecord).where(ApprovalRecord.id == plan.active_approval_id)
                )
            ).scalar_one_or_none()
            if old_app and old_app.decision == "APPROVED":
                old_app.decision = "REVOKED"
                old_app.rationale += " [Auto-revoked due to post-approval plan mutation]"
            plan.active_approval_id = None

        if plan.status == "APPROVED":
            AutonomousRecoveryService._record_transition(
                plan,
                "AWAITING_APPROVAL",
                actor=actor,
                agent_role="SafetyGovernor",
                rationale=(
                    f"Plan mutated to version {plan.plan_version} (hash={plan.plan_hash[:12]}); "
                    f"previous approval revoked."
                ),
            )
        await db.commit()
        return await AutonomousRecoveryService.get_plan_detail(db, plan.id)

    @staticmethod
    async def submit_human_approval(
        db: AsyncSession,
        plan_id: str,
        request: RecoveryApprovalRequest,
        *,
        actor: str = "human-sre-commander",
    ) -> ApprovalRecordRead:
        """Record a human approval or rejection, issuing a cryptographically bound token."""
        plan = await AutonomousRecoveryService.get_plan_model(db, plan_id)
        cand_id = request.candidate_id or plan.selected_candidate_id
        cand = (
            await db.execute(
                select(RemediationCandidateRecord).where(
                    RemediationCandidateRecord.id == cand_id,
                    RemediationCandidateRecord.recovery_plan_id == plan.id,
                )
            )
        ).scalar_one_or_none()
        if not cand:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Remediation candidate not found for approval.",
            )

        if request.decision == "REJECTED":
            now = datetime.now(UTC)
            rej = ApprovalRecord(
                recovery_plan_id=plan.id,
                candidate_id=cand.id,
                system_id=plan.system_id,
                plan_version=plan.plan_version,
                plan_hash=plan.plan_hash,
                action_type=cand.action_type,
                action_parameters_json=cand.parameters_json,
                target_environment=plan.target_environment,
                evidence_summary_json=plan.evidence_summary_json,
                risk_classification=cand.risk_classification,
                approver_identity=request.approver_identity,
                approver_role=request.approver_role,
                decision="REJECTED",
                rationale=request.rationale,
                approval_token_hash="rejected-no-token",
                token_used=True,
                approved_at=now,
                expires_at=now,
            )
            db.add(rej)
            AutonomousRecoveryService._record_transition(
                plan,
                "REJECTED",
                actor=request.approver_identity,
                agent_role="SafetyGovernor",
                rationale=f"Human operator rejected recovery plan: {request.rationale}",
            )
            await db.commit()
            return ApprovalRecordRead.model_validate(rej)

        # Require sandbox verification before human approval can be granted!
        if cand.verification_status != "sandbox_verified":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Cannot approve candidate '{cand.id}' with "
                    f"verification_status='{cand.verification_status}'. "
                    f"Real sandbox verification ('sandbox_verified') is mandatory before approval."
                ),
            )

        plan.selected_candidate_id = cand.id
        plan.plan_hash = compute_recovery_plan_hash(
            plan_id=plan.id,
            plan_version=plan.plan_version,
            target_environment=plan.target_environment,
            candidate_id=cand.id,
            action_type=cand.action_type,
            target_service_key=cand.target_service_key,
            parameters=cand.parameters_json,
        )

        raw_token = f"origin-appr-{secrets.token_urlsafe(24)}"
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=request.ttl_seconds)

        app_rec = ApprovalRecord(
            recovery_plan_id=plan.id,
            candidate_id=cand.id,
            system_id=plan.system_id,
            plan_version=plan.plan_version,
            plan_hash=plan.plan_hash,
            action_type=cand.action_type,
            action_parameters_json=cand.parameters_json,
            target_environment=plan.target_environment,
            evidence_summary_json=plan.evidence_summary_json,
            risk_classification=cand.risk_classification,
            approver_identity=request.approver_identity,
            approver_role=request.approver_role,
            decision="APPROVED",
            rationale=request.rationale,
            approval_token_hash=_hash_token(raw_token),
            token_used=False,
            approved_at=now,
            expires_at=expires_at,
        )
        db.add(app_rec)
        await db.flush()
        plan.active_approval_id = app_rec.id

        AutonomousRecoveryService._record_transition(
            plan,
            "APPROVED",
            actor=request.approver_identity,
            agent_role="SafetyGovernor",
            rationale=(
                f"Human approver '{request.approver_identity}' ({request.approver_role}) "
                f"approved plan v{plan.plan_version} (hash={plan.plan_hash[:12]})."
            ),
        )
        await AuditService.record_event(
            db,
            system_id=plan.system_id,
            actor=request.approver_identity,
            action="recovery.plan_approved",
            resource_type="recovery_approval",
            resource_id=app_rec.id,
            severity="info",
            details={
                "recovery_plan_id": plan.id,
                "candidate_id": cand.id,
                "plan_version": plan.plan_version,
                "plan_hash": plan.plan_hash,
                "expires_at": expires_at.isoformat(),
            },
        )
        await db.commit()
        read_obj = ApprovalRecordRead.model_validate(app_rec)
        read_obj.issued_single_use_token = raw_token
        return read_obj

    @staticmethod
    async def execute_approved_recovery(
        db: AsyncSession,
        plan_id: str,
        request: RecoveryExecutionRequest,
        *,
        actor: str = "ExecutionController",
    ) -> RecoveryPlanDetailRead:
        """Execute an approved recovery action, observe telemetry, and auto-rollback."""
        plan = await AutonomousRecoveryService.get_plan_model(db, plan_id)

        # Idempotent retry check: if idempotency_key already executed, return current state
        if request.idempotency_key:
            existing_exec = (
                await db.execute(
                    select(RecoveryExecutionRecord).where(
                        RecoveryExecutionRecord.recovery_plan_id == plan.id,
                        RecoveryExecutionRecord.idempotency_key == request.idempotency_key,
                    )
                )
            ).scalar_one_or_none()
            if existing_exec:
                return await AutonomousRecoveryService.get_plan_detail(db, plan.id)

        if plan.cancel_requested or plan.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot execute a cancelled recovery plan.",
            )

        # 1. Fetch and strictly verify the ApprovalRecord
        approval = (
            await db.execute(select(ApprovalRecord).where(ApprovalRecord.id == request.approval_id))
        ).scalar_one_or_none()
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Execution denied: approval record not found.",
            )

        if approval.recovery_plan_id != plan.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Execution denied: approval '{approval.id}' belongs to recovery plan "
                    f"'{approval.recovery_plan_id}', not '{plan.id}'."
                ),
            )

        if approval.decision != "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Execution denied: approval status is '{approval.decision}'.",
            )

        if approval.token_used:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Execution denied: single-use approval token has already been consumed "
                    "(replay rejected)."
                ),
            )

        now = datetime.now(UTC)
        exp_ts = (
            approval.expires_at
            if approval.expires_at.tzinfo is not None
            else approval.expires_at.replace(tzinfo=UTC)
        )
        if now > exp_ts:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Execution denied: human approval has expired.",
            )

        supplied_hash = _hash_token(request.approval_token)
        if not secrets.compare_digest(supplied_hash, approval.approval_token_hash):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Execution denied: invalid single-use approval_token.",
            )

        cand = (
            await db.execute(
                select(RemediationCandidateRecord).where(
                    RemediationCandidateRecord.id == plan.selected_candidate_id,
                    RemediationCandidateRecord.recovery_plan_id == plan.id,
                )
            )
        ).scalar_one_or_none()
        if not cand:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected candidate not found.",
            )

        current_hash = compute_recovery_plan_hash(
            plan_id=plan.id,
            plan_version=plan.plan_version,
            target_environment=plan.target_environment,
            candidate_id=cand.id,
            action_type=cand.action_type,
            target_service_key=cand.target_service_key,
            parameters=cand.parameters_json,
        )
        if approval.plan_hash != current_hash or approval.plan_version != plan.plan_version:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Execution denied: recovery plan was mutated after approval "
                    "(plan_hash or plan_version mismatch)."
                ),
            )

        # 2. Check concurrent execution lock & safety policy
        active_lock_count = 1 if plan.system_id in _ACTIVE_SYSTEM_EXECUTION_LOCKS else 0
        pol = await SafetyPolicyEngine.evaluate_and_record(
            db,
            system_id=plan.system_id,
            recovery_plan_id=plan.id,
            candidate_id=cand.id,
            policy_stage="execution_precheck",
            target_environment=plan.target_environment,
            action_type=cand.action_type,
            target_service_key=cand.target_service_key,
            parameters=cand.parameters_json,
            evidence_count=len(cand.evidence_refs_json),
            recovery_attempts=plan.recovery_attempts,
            max_recovery_attempts=plan.max_recovery_attempts,
            duration_seconds=request.timeout_seconds,
            active_execution_count=active_lock_count,
            actor="SafetyGovernor",
        )
        if not pol.allowed:
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT
                if active_lock_count > 0
                else status.HTTP_403_FORBIDDEN,
                detail=f"Execution blocked by SafetyPolicyEngine: {'; '.join(pol.violations_json)}",
            )

        # Consume single-use token & acquire system execution lock
        _ACTIVE_SYSTEM_EXECUTION_LOCKS.add(plan.system_id)
        try:
            approval.token_used = True
            approval.used_at = now
            plan.recovery_attempts += 1

            AutonomousRecoveryService._record_transition(
                plan,
                "EXECUTING",
                actor=actor,
                agent_role="ExecutionController",
                rationale=(
                    f"Executing approved remediation '{cand.action_type}' on "
                    f"'{cand.target_service_key}' in '{plan.target_environment}'."
                ),
            )

            previous_config = capture_lab_configuration()
            exec_params = dict(cand.parameters_json)
            if request.simulate_execution_regression:
                exec_params["induce_regression"] = True
                exec_params["regression_penalty_ms"] = 680.0

            applied_config = apply_lab_remediation_action(
                cand.action_type,
                cand.target_service_key,
                exec_params,
            )

            exec_rec = RecoveryExecutionRecord(
                recovery_plan_id=plan.id,
                candidate_id=cand.id,
                approval_id=approval.id,
                system_id=plan.system_id,
                status="OBSERVING",
                idempotency_key=request.idempotency_key,
                lock_key=f"mutex:{plan.system_id}",
                previous_config_json=previous_config,
                applied_config_json=applied_config,
                pre_execution_metrics_json=plan.baseline_metrics_json,
                observed_metrics_json={},
                guardrail_evaluation_json={},
            )
            db.add(exec_rec)
            await db.flush()

            # 3. Transition to OBSERVING and measure real post-execution telemetry
            AutonomousRecoveryService._record_transition(
                plan,
                "OBSERVING",
                actor=actor,
                agent_role="Observer",
                rationale=(
                    "Observing post-execution laboratory latency, error rate, and guardrails."
                ),
            )

            obs_traces = []
            for i in range(request.observation_iterations):
                tr = await SyntheticLabOrchestrator.execute_instrumented_transaction(
                    db,
                    profile=None,
                    intervention="none",
                    experiment_arm="post_recovery_observation",
                    rng_seed=900 + i,
                )
                obs_traces.append(tr)

            obs_lats = [float(t.total_duration_ms) for t in obs_traces]
            obs_errs = [1 if t.gateway_status >= 500 else 0 for t in obs_traces]
            obs_mean_ms = round(statistics.fmean(obs_lats), 2)
            obs_p95_ms = round(max(obs_lats), 2)
            obs_err_pct = round(statistics.fmean(obs_errs) * 100.0, 2)
            base_mean_ms = float(plan.baseline_metrics_json.get("mean_latency_ms", 420.0))

            exec_rec.observed_metrics_json = {
                "mean_latency_ms": obs_mean_ms,
                "p95_latency_ms": obs_p95_ms,
                "error_rate_pct": obs_err_pct,
                "sample_count": len(obs_traces),
                "correlation_ids": [t.correlation_id for t in obs_traces],
            }

            guardrail_violations: list[str] = []
            if request.simulate_timeout:
                guardrail_violations.append(
                    f"Post-execution observation exceeded timeout ({request.timeout_seconds}s)."
                )
            if plan.cancel_requested:
                guardrail_violations.append(
                    "Operator requested cancellation during execution observation."
                )
            if obs_err_pct > 8.0:
                guardrail_violations.append(
                    f"Observed error rate ({obs_err_pct}%) exceeded maximum guardrail (8.0%)."
                )
            if obs_mean_ms > base_mean_ms * 0.78 or obs_mean_ms > 260.0:
                guardrail_violations.append(
                    f"Post-execution latency ({obs_mean_ms}ms) failed recovery threshold "
                    f"against baseline ({base_mean_ms}ms)."
                )

            exec_rec.guardrail_evaluation_json = {
                "baseline_mean_latency_ms": base_mean_ms,
                "observed_mean_latency_ms": obs_mean_ms,
                "observed_error_rate_pct": obs_err_pct,
                "violations": guardrail_violations,
                "passed": len(guardrail_violations) == 0,
            }

            if len(guardrail_violations) > 0:
                # Trigger Automatic Saga Rollback!
                await AutonomousRecoveryService._execute_rollback_internal(
                    db,
                    plan=plan,
                    exec_rec=exec_rec,
                    trigger_reason="; ".join(guardrail_violations),
                    simulate_rollback_failure=request.simulate_rollback_failure,
                    actor="ExecutionController",
                )
            else:
                exec_rec.verification_passed = True
                exec_rec.status = "RECOVERED"
                exec_rec.completed_at = datetime.now(UTC)

                AutonomousRecoveryService._record_transition(
                    plan,
                    "RECOVERED",
                    actor="EvidenceAuditor",
                    agent_role="EvidenceAuditor",
                    rationale=(
                        f"Verified recovery: latency improved from {base_mean_ms}ms to "
                        f"{obs_mean_ms}ms (error_rate={obs_err_pct}%)."
                    ),
                    evidence_refs=[t.correlation_id for t in obs_traces],
                )
                AutonomousRecoveryService._record_agent_decision(
                    plan,
                    agent_role="EvidenceAuditor",
                    phase="OBSERVING",
                    decision="recovery_verified_and_committed",
                    rationale=(
                        f"Post-execution telemetry confirmed recovery "
                        f"({base_mean_ms}ms -> {obs_mean_ms}ms)."
                    ),
                    artifacts=exec_rec.observed_metrics_json,
                )
                db.add(
                    ScientificMemoryEntryRecord(
                        system_id=plan.system_id,
                        epistemic_kind="historical_observation",
                        title=(
                            f"Verified Autonomous Recovery: {cand.action_type} "
                            f"on {cand.target_service_key}"
                        ),
                        summary=(
                            f"Approved remediation reduced laboratory latency from "
                            f"{base_mean_ms}ms to {obs_mean_ms}ms across "
                            f"{len(obs_traces)} post-execution traces."
                        ),
                        investigation_id=plan.investigation_id,
                        twin_model_id=plan.twin_model_id,
                        branch_id=cand.simulation_branch_id,
                        predicted_outcome_json=cand.simulation_prediction_json,
                        observed_outcome_json=exec_rec.observed_metrics_json,
                        validation_metrics_json=exec_rec.guardrail_evaluation_json,
                        provenance_json={
                            "recovery_plan_id": plan.id,
                            "execution_id": exec_rec.id,
                        },
                    )
                )
                await AuditService.record_event(
                    db,
                    system_id=plan.system_id,
                    actor=actor,
                    action="recovery.execution_recovered",
                    resource_type="recovery_execution",
                    resource_id=exec_rec.id,
                    severity="info",
                    details={
                        "recovery_plan_id": plan.id,
                        "baseline_mean_latency_ms": base_mean_ms,
                        "observed_mean_latency_ms": obs_mean_ms,
                    },
                )

            await db.commit()
            return await AutonomousRecoveryService.get_plan_detail(db, plan.id)
        finally:
            _ACTIVE_SYSTEM_EXECUTION_LOCKS.discard(plan.system_id)

    @staticmethod
    async def _execute_rollback_internal(
        db: AsyncSession,
        *,
        plan: RecoveryPlanRecord,
        exec_rec: RecoveryExecutionRecord,
        trigger_reason: str,
        simulate_rollback_failure: bool = False,
        actor: str = "ExecutionController",
    ) -> RollbackRecord:
        """Restore previous lab config, verify rollback, or enter MANUAL_INTERVENTION_REQUIRED."""
        restored_ok, restored_cfg = restore_lab_configuration(
            exec_rec.previous_config_json,
            simulate_restore_failure=simulate_rollback_failure,
        )
        post_rb_trace = await SyntheticLabOrchestrator.execute_instrumented_transaction(
            db,
            profile=None,
            intervention="none",
            experiment_arm="post_rollback_verification",
            rng_seed=999,
        )

        rb_status = "COMPLETED" if restored_ok else "MANUAL_INTERVENTION_REQUIRED"
        rb = RollbackRecord(
            recovery_plan_id=plan.id,
            execution_id=exec_rec.id,
            system_id=plan.system_id,
            trigger_reason=trigger_reason,
            target_config_json=exec_rec.previous_config_json,
            restored_config_json=restored_cfg,
            post_rollback_metrics_json={
                "post_rollback_latency_ms": post_rb_trace.total_duration_ms,
                "correlation_id": post_rb_trace.correlation_id,
            },
            rollback_verified=restored_ok,
            status=rb_status,
        )
        db.add(rb)
        await db.flush()

        exec_rec.rollback_triggered = True
        exec_rec.rollback_id = rb.id
        exec_rec.completed_at = datetime.now(UTC)

        if restored_ok:
            exec_rec.status = "ROLLED_BACK"
            AutonomousRecoveryService._record_transition(
                plan,
                "ROLLED_BACK",
                actor=actor,
                agent_role="ExecutionController",
                rationale=f"Automatic rollback completed and verified: {trigger_reason}",
                evidence_refs=[post_rb_trace.correlation_id],
            )
            await AuditService.record_event(
                db,
                system_id=plan.system_id,
                actor=actor,
                action="recovery.execution_rolled_back",
                resource_type="recovery_rollback",
                resource_id=rb.id,
                severity="warning",
                details={
                    "recovery_plan_id": plan.id,
                    "execution_id": exec_rec.id,
                    "trigger_reason": trigger_reason,
                },
            )
        else:
            exec_rec.status = "MANUAL_INTERVENTION_REQUIRED"
            plan.failure_reason = (
                f"Rollback verification failed after guardrail violation ({trigger_reason}). "
                f"Entered MANUAL_INTERVENTION_REQUIRED."
            )
            AutonomousRecoveryService._record_transition(
                plan,
                "MANUAL_INTERVENTION_REQUIRED",
                actor=actor,
                agent_role="SafetyGovernor",
                rationale=plan.failure_reason,
                evidence_refs=[post_rb_trace.correlation_id],
            )
            await AuditService.record_event(
                db,
                system_id=plan.system_id,
                actor=actor,
                action="recovery.manual_intervention_required",
                resource_type="recovery_rollback",
                resource_id=rb.id,
                severity="critical",
                details={
                    "recovery_plan_id": plan.id,
                    "execution_id": exec_rec.id,
                    "trigger_reason": trigger_reason,
                },
            )
        return rb

    @staticmethod
    async def trigger_manual_rollback(
        db: AsyncSession,
        plan_id: str,
        request: ManualRollbackRequest,
        *,
        actor: str = "human-sre-commander",
    ) -> RecoveryPlanDetailRead:
        """Trigger an explicit rollback of the most recent execution on a recovery plan."""
        plan = await AutonomousRecoveryService.get_plan_model(db, plan_id)
        stmt = (
            select(RecoveryExecutionRecord)
            .where(RecoveryExecutionRecord.recovery_plan_id == plan.id)
            .order_by(RecoveryExecutionRecord.created_at.desc())
        )
        if request.execution_id:
            stmt = stmt.where(RecoveryExecutionRecord.id == request.execution_id)
        exec_rec = (await db.execute(stmt)).scalars().first()
        if not exec_rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No execution record found to roll back.",
            )

        await AutonomousRecoveryService._execute_rollback_internal(
            db,
            plan=plan,
            exec_rec=exec_rec,
            trigger_reason=request.reason,
            simulate_rollback_failure=request.simulate_rollback_failure,
            actor=actor,
        )
        await db.commit()
        return await AutonomousRecoveryService.get_plan_detail(db, plan.id)

    @staticmethod
    async def cancel_recovery_plan(
        db: AsyncSession,
        plan_id: str,
        *,
        actor: str = "operator",
    ) -> RecoveryPlanDetailRead:
        """Cancel a recovery plan and roll back if currently executing."""
        plan = await AutonomousRecoveryService.get_plan_model(db, plan_id)
        plan.cancel_requested = True
        if plan.status in ("EXECUTING", "OBSERVING"):
            exec_rec = (
                (
                    await db.execute(
                        select(RecoveryExecutionRecord)
                        .where(RecoveryExecutionRecord.recovery_plan_id == plan.id)
                        .order_by(RecoveryExecutionRecord.created_at.desc())
                    )
                )
                .scalars()
                .first()
            )
            if exec_rec:
                await AutonomousRecoveryService._execute_rollback_internal(
                    db,
                    plan=plan,
                    exec_rec=exec_rec,
                    trigger_reason="Cancelled by operator during active execution.",
                    actor=actor,
                )
        elif plan.status not in ("RECOVERED", "ROLLED_BACK", "MANUAL_INTERVENTION_REQUIRED"):
            AutonomousRecoveryService._record_transition(
                plan,
                "CANCELLED",
                actor=actor,
                agent_role="SafetyGovernor",
                rationale="Recovery plan cancelled by operator.",
            )
        await db.commit()
        return await AutonomousRecoveryService.get_plan_detail(db, plan.id)

    @staticmethod
    async def export_recovery_report(
        db: AsyncSession,
        plan_id: str,
        report_format: Literal["markdown", "json"] = "markdown",
    ) -> dict[str, Any]:
        """Export a complete, reproducible Markdown & JSON scientific recovery & audit report."""
        detail = await AutonomousRecoveryService.get_plan_detail(db, plan_id)
        lines: list[str] = [
            f"# ORIGIN Verified Autonomous Recovery Report: {detail.title}",
            "",
            f"- **Recovery Plan ID:** `{detail.id}`",
            f"- **Lifecycle Status:** `{detail.status}`",
            (
                f"- **Target Environment:** `{detail.target_environment}` "
                f"(Production Execution Disabled)"
            ),
            (
                f"- **Plan Version & Cryptographic Hash:** "
                f"`v{detail.plan_version}` · `{detail.plan_hash}`"
            ),
            (
                f"- **Suspected Root Cause:** `{detail.root_cause_service_key}` "
                f"(`{detail.root_cause_mechanism}`)"
            ),
            f"- **Linked Investigation ID:** `{detail.investigation_id}`",
            f"- **Linked Digital Twin Model ID:** `{detail.twin_model_id}`",
            "",
            "## 1. Epistemic Separation & Remediation Candidates",
        ]
        for c in detail.candidates:
            sim_red = c.simulation_prediction_json.get("predicted_latency_reduction_pct")
            lines.append(
                f"- **Candidate `{c.action_type}` on `{c.target_service_key}`** "
                f"(Risk: `{c.risk_classification}`, Status: `{c.verification_status}`, "
                f"Simulated Reduction: `{sim_red}%`)"
            )

        lines.extend(["", "## 2. Isolated Laboratory Sandbox Verification Runs"])
        for s in detail.sandbox_runs:
            b_lat = s.baseline_metrics_json.get("mean_latency_ms")
            t_lat = s.treatment_metrics_json.get("mean_latency_ms")
            lines.append(
                f"- **Sandbox Run `{s.id}`**: Status=`{s.status}` · Baseline=`{b_lat}ms` -> "
                f"Treatment=`{t_lat}ms` · Restoration Verified=`{s.restoration_verified}`"
            )

        lines.extend(["", "## 3. Human Approval Records"])
        for a in detail.approvals:
            lines.append(
                f"- **Approval `{a.id}`**: Decision=`{a.decision}` by `{a.approver_identity}` "
                f"(`{a.approver_role}`) · Plan Hash=`{a.plan_hash[:16]}...` "
                f"· Token Used=`{a.token_used}`"
            )

        lines.extend(["", "## 4. Execution & Rollback Audit Trail"])
        for e in detail.executions:
            o_lat = e.observed_metrics_json.get("mean_latency_ms")
            lines.append(
                f"- **Execution `{e.id}`**: Status=`{e.status}` · Observed Latency=`{o_lat}ms` · "
                f"Verification Passed=`{e.verification_passed}` · "
                f"Rollback Triggered=`{e.rollback_triggered}`"
            )
        for r in detail.rollbacks:
            lines.append(
                f"- **Rollback `{r.id}`**: Status=`{r.status}` · "
                f"Verified=`{r.rollback_verified}` · Reason: {r.trigger_reason}"
            )

        lines.extend(["", "## 5. Multi-Role Agent Decision Ledger"])
        for d in detail.agent_decision_history_json:
            lines.append(
                f"- **Step {d.get('step')} [{d.get('agent_role')}] ({d.get('phase')})**: "
                f"`{d.get('decision')}` — {d.get('rationale')}"
            )

        markdown_text = "\n".join(lines)
        return {
            "recovery_plan_id": detail.id,
            "status": detail.status,
            "format": report_format,
            "markdown": markdown_text,
            "report": detail.model_dump(mode="json"),
        }
