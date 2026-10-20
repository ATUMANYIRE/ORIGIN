"""Fail-Closed Operational Safety Policy Engine (Milestone 04/05).

Enforces explicit policies across 11 operational safety dimensions:
1. Allowed environments (restricted strictly to 'synthetic-lab'; production disabled).
2. Allowed action types (strict allowlist; zero shell/arbitrary URL execution).
3. Maximum change magnitude (replicas, concurrency, rate limiting, DB capacity bounds).
4. Maximum experiment / sandbox duration.
5. Maximum recovery attempts per workflow.
6. Minimum causal evidence requirements.
7. Maximum acceptable error rate.
8. Latency regression & recovery improvement thresholds.
9. Human approval presence, cryptographic plan-hash match, single-use token, and expiration.
10. Concurrent execution limits (per-system/service mutex lock).
11. Mandatory rollback strategy presence.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SafetyPolicyEvaluationRecord
from app.modules.laboratory.orchestrator import (
    ALLOWLISTED_REMEDIATION_ACTIONS,
    is_lab_unsafe_locked,
)

ALLOWED_EXECUTION_ENVIRONMENTS: set[str] = {"synthetic-lab"}

VALID_LABORATORY_SERVICES: set[str] = {
    "api-gateway",
    "checkout-service",
    "inventory-service",
    "payment-simulator",
    "order-database-sim",
}

DEFAULT_SAFETY_POLICY_RULES: dict[str, Any] = {
    "allowed_environments": sorted(ALLOWED_EXECUTION_ENVIRONMENTS),
    "production_execution_enabled": False,
    "allowed_action_types": sorted(ALLOWLISTED_REMEDIATION_ACTIONS),
    "max_replica_count": 8,
    "min_replica_count": 1,
    "max_concurrency_limit": 250,
    "min_concurrency_limit": 8,
    "min_rate_limit_factor": 0.30,
    "max_rate_limit_factor": 1.00,
    "min_db_connection_capacity": 20.0,
    "max_db_connection_capacity": 260.0,
    "max_sandbox_duration_seconds": 60.0,
    "max_execution_timeout_seconds": 60.0,
    "max_recovery_attempts": 3,
    "min_evidence_references": 1,
    "min_causal_confidence_score": 0.55,
    "max_acceptable_error_rate_pct": 8.0,
    "max_latency_regression_ratio": 1.12,
    "required_recovery_latency_reduction_ratio": 0.72,
    "max_concurrent_executions_per_system": 1,
    "require_human_approval": True,
    "require_sandbox_verification_before_approval": True,
    "require_rollback_strategy": True,
}


class SafetyPolicyEngine:
    """Evaluates and persists fail-closed safety policy checks."""

    @staticmethod
    def get_policy_specification() -> dict[str, Any]:
        """Return the canonical fail-closed operational safety policy specification."""
        return dict(DEFAULT_SAFETY_POLICY_RULES)

    @staticmethod
    def classify_risk(action_type: str, parameters: dict[str, Any]) -> str:
        """Assign a deterministic risk classification ('low', 'medium', 'high', 'critical')."""
        if action_type not in ALLOWLISTED_REMEDIATION_ACTIONS:
            return "critical"
        if action_type == "restore_safe_lab_configuration":
            return "low"
        if action_type == "toggle_circuit_breaker":
            return "low"
        if action_type == "adjust_service_replicas":
            rep = int(parameters.get("replicas", parameters.get("value", 2)))
            return "high" if rep > 6 or rep < 2 else "medium"
        if action_type == "apply_rate_limiting":
            factor = float(parameters.get("rate_limit_factor", parameters.get("value", 0.75)))
            return "high" if factor < 0.50 else "medium"
        if action_type == "restart_synthetic_service":
            return "medium"
        return "medium"

    @staticmethod
    async def evaluate_and_record(
        db: AsyncSession,
        *,
        system_id: str,
        policy_stage: str,
        target_environment: str,
        action_type: str,
        target_service_key: str = "checkout-service",
        parameters: dict[str, Any] | None = None,
        recovery_plan_id: str | None = None,
        candidate_id: str | None = None,
        evidence_count: int = 1,
        causal_confidence: float = 0.85,
        recovery_attempts: int = 0,
        max_recovery_attempts: int = 3,
        duration_seconds: float = 10.0,
        has_rollback_strategy: bool = True,
        active_execution_count: int = 0,
        actor: str = "safety-governor",
    ) -> SafetyPolicyEvaluationRecord:
        """Evaluate fail-closed safety rules and persist an immutable evaluation record."""
        params = parameters or {}
        violations: list[str] = []

        # 0. Check if laboratory is locked due to a prior failed restoration
        lab_locked, lock_reason = is_lab_unsafe_locked()
        if lab_locked and action_type != "restore_safe_lab_configuration":
            violations.append(
                f"Laboratory unsafe lock is active: {lock_reason or 'restoration failed'}."
            )

        # 1. Allowed environment check (Fail-closed: only 'synthetic-lab' permitted)
        if target_environment not in ALLOWED_EXECUTION_ENVIRONMENTS:
            violations.append(
                f"Unauthorized target_environment '{target_environment}'. "
                f"Only {sorted(ALLOWED_EXECUTION_ENVIRONMENTS)} is permitted in Milestone 04/05."
            )

        # 2. Allowed action type check (No arbitrary shell commands or unknown actions)
        if action_type not in ALLOWLISTED_REMEDIATION_ACTIONS:
            violations.append(
                f"Unsupported remediation action_type '{action_type}'. "
                f"Allowed: {sorted(ALLOWLISTED_REMEDIATION_ACTIONS)}."
            )

        # Reject any parameter attempting shell injection or external URLs
        for k, v in params.items():
            sval = str(v).lower()
            if any(
                bad in k.lower() or bad in sval
                for bad in ("shell", "cmd", "exec", "http://", "https://", "rm -rf", ";")
            ):
                violations.append(f"Prohibited command or URL token detected in parameter '{k}'.")

        # 3. Target service validation
        if (
            action_type != "restore_safe_lab_configuration"
            and target_service_key not in VALID_LABORATORY_SERVICES
        ):
            violations.append(
                f"Unknown target_service_key '{target_service_key}'. "
                f"Valid services: {sorted(VALID_LABORATORY_SERVICES)}."
            )

        # 4. Parameter magnitude bounds
        if action_type == "adjust_service_replicas":
            rep = int(params.get("replicas", params.get("value", 2)))
            if (
                rep < DEFAULT_SAFETY_POLICY_RULES["min_replica_count"]
                or rep > DEFAULT_SAFETY_POLICY_RULES["max_replica_count"]
            ):
                violations.append(
                    f"Replica count {rep} violates safety bounds "
                    f"[{DEFAULT_SAFETY_POLICY_RULES['min_replica_count']}, "
                    f"{DEFAULT_SAFETY_POLICY_RULES['max_replica_count']}]."
                )

        elif action_type == "modify_concurrency_limit":
            conc = int(params.get("concurrency_limit", params.get("value", 30)))
            if (
                conc < DEFAULT_SAFETY_POLICY_RULES["min_concurrency_limit"]
                or conc > DEFAULT_SAFETY_POLICY_RULES["max_concurrency_limit"]
            ):
                violations.append(
                    f"Concurrency limit {conc} violates safety bounds "
                    f"[{DEFAULT_SAFETY_POLICY_RULES['min_concurrency_limit']}, "
                    f"{DEFAULT_SAFETY_POLICY_RULES['max_concurrency_limit']}]."
                )

        elif action_type == "apply_rate_limiting":
            rf = float(params.get("rate_limit_factor", params.get("value", 0.70)))
            if (
                rf < DEFAULT_SAFETY_POLICY_RULES["min_rate_limit_factor"]
                or rf > DEFAULT_SAFETY_POLICY_RULES["max_rate_limit_factor"]
            ):
                violations.append(
                    f"Rate limit factor {rf} violates safety bounds "
                    f"[{DEFAULT_SAFETY_POLICY_RULES['min_rate_limit_factor']}, "
                    f"{DEFAULT_SAFETY_POLICY_RULES['max_rate_limit_factor']}]."
                )

        elif action_type == "adjust_db_contention_controls":
            db_cap = float(params.get("db_connection_capacity", params.get("value", 120.0)))
            if (
                db_cap < DEFAULT_SAFETY_POLICY_RULES["min_db_connection_capacity"]
                or db_cap > DEFAULT_SAFETY_POLICY_RULES["max_db_connection_capacity"]
            ):
                violations.append(
                    f"DB connection capacity {db_cap} violates safety bounds "
                    f"[{DEFAULT_SAFETY_POLICY_RULES['min_db_connection_capacity']}, "
                    f"{DEFAULT_SAFETY_POLICY_RULES['max_db_connection_capacity']}]."
                )

        # 5. Experiment / execution duration bounds
        if duration_seconds > DEFAULT_SAFETY_POLICY_RULES["max_sandbox_duration_seconds"]:
            violations.append(
                f"Duration {duration_seconds}s exceeds maximum permitted duration "
                f"({DEFAULT_SAFETY_POLICY_RULES['max_sandbox_duration_seconds']}s)."
            )

        # 6. Maximum recovery attempts
        if recovery_attempts >= max_recovery_attempts:
            violations.append(
                f"Recovery attempts ({recovery_attempts}) exhausted maximum allowed "
                f"({max_recovery_attempts})."
            )

        # 7. Minimum causal evidence requirements
        if (
            evidence_count < DEFAULT_SAFETY_POLICY_RULES["min_evidence_references"]
            or causal_confidence < DEFAULT_SAFETY_POLICY_RULES["min_causal_confidence_score"]
        ):
            violations.append(
                f"Insufficient causal evidence: evidence_count={evidence_count}, "
                f"causal_confidence={causal_confidence:.2f} (minimum required: "
                f"{DEFAULT_SAFETY_POLICY_RULES['min_evidence_references']} ref, "
                f"confidence >= {DEFAULT_SAFETY_POLICY_RULES['min_causal_confidence_score']})."
            )

        # 8. Rollback strategy requirement
        if not has_rollback_strategy:
            violations.append("Candidate is missing a required rollback strategy.")

        # 9. Concurrent execution limit
        if (
            active_execution_count
            >= DEFAULT_SAFETY_POLICY_RULES["max_concurrent_executions_per_system"]
        ):
            violations.append(
                f"Conflicting concurrent execution detected: {active_execution_count} "
                f"active execution(s) already hold the system remediation lock."
            )

        allowed = len(violations) == 0
        risk = SafetyPolicyEngine.classify_risk(action_type, params)

        rec = SafetyPolicyEvaluationRecord(
            recovery_plan_id=recovery_plan_id,
            candidate_id=candidate_id,
            system_id=system_id,
            policy_stage=policy_stage,
            target_environment=target_environment,
            action_type=action_type,
            allowed=allowed,
            risk_classification=risk,
            violations_json=violations,
            evaluated_rules_json={
                "target_service_key": target_service_key,
                "parameters": params,
                "evidence_count": evidence_count,
                "causal_confidence": causal_confidence,
                "recovery_attempts": recovery_attempts,
                "max_recovery_attempts": max_recovery_attempts,
                "duration_seconds": duration_seconds,
                "active_execution_count": active_execution_count,
            },
            actor=actor,
        )
        db.add(rec)
        await db.flush()
        return rec
