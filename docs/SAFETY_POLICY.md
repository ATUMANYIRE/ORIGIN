# ORIGIN Operational Safety Policy Engine (`docs/SAFETY_POLICY.md`)

**Milestone:** `04/05 — Verified Autonomous Recovery, Agent Orchestration & Operational Safety`  
**Module:** [`backend/app/modules/recovery/policy.py`](file:///E:/Projects/ORIGIN/backend/app/modules/recovery/policy.py)

---

## 1. Fail-Closed Architectural Philosophy

The `SafetyPolicyEngine` operates as an unconditional fail-closed gatekeeper. Any ambiguity, missing prerequisite, uncalibrated state, expired credential, or parameter anomaly results in an immediate rejection (`allowed = False`) and records a persistent evaluation record in `safety_policy_evaluations`.

Execution is strictly forbidden unless all eleven verification checks pass simultaneously.

---

## 2. Eleven Evaluated Safety Policy Dimensions

1. **Environment Confinement**:
   - Only `synthetic-lab` is permitted for autonomous recovery actions.
   - Any target environment specifying `production`, `staging`, or `live` is rejected with `HTTP 403 Forbidden` (`PROD_DISABLED`).
2. **Allowlisted Remediation Actions**:
   - Actions must be in `ALLOWLISTED_REMEDIATION_ACTIONS`:
     - `restart_synthetic_service`
     - `adjust_service_replicas`
     - `modify_concurrency_limit`
     - `toggle_circuit_breaker`
     - `apply_rate_limiting`
     - `adjust_db_contention_controls`
     - `restore_safe_lab_configuration`
   - Arbitrary shell commands, unsanitized strings, and external webhooks are rejected with `HTTP 422 Unprocessable Content`.
3. **Parameter Safety Bounds**:
   - `replicas`: Integer $\in [1, 8]$
   - `concurrency_limit`: Integer $\in [10, 100]$
   - `rate_limit_factor`: Float $\in [0.1, 1.0]$
   - `threshold_ms`: Float $\in [50.0, 1000.0]$
   - `db_connection_capacity`: Float $\in [20.0, 300.0]$
4. **Execution Duration Bounds**:
   - Sandbox trials bounded by $\le 30.0$ seconds.
   - Live recovery executions bounded by $\le 60.0$ seconds.
5. **Maximum Recovery Attempts & Blast Radius**:
   - A recovery plan cannot exceed `max_recovery_attempts` (default $3$). Exceeding attempts terminates the workflow to prevent cyclic thrashing.
6. **Causal Evidence Grounding Requirement**:
   - Proposing or executing remediation requires verified causal evidence:
     - Linked investigation status must be `CONCLUDED`.
     - Causal confidence score must be $\ge 0.55$.
     - Minimum evidence count $\ge 1$.
7. **Operational Guardrails**:
   - Maximum allowable post-execution error rate: $\le 8.0\%$.
   - Maximum allowable post-execution latency: must improve by at least $22\%$ against degraded baseline ($< \text{baseline} \times 0.78$) or reach $< 260.0$ ms.
8. **Cryptographic Plan Hash & Version Binding**:
   - SHA-256 canonical hash binding `plan_id`, `plan_version`, `target_environment`, `candidate_id`, `action_type`, `target_service_key`, and parameters.
   - Modifying any parameter bumps `plan_version`, revokes prior approvals, and forces re-evaluation.
9. **Single-Use Authorization Token & Nonce Protocol**:
   - Human approval generates a single-use token (`origin-appr-...`).
   - Stored in hashed form (`SHA-256`); upon execution, `token_used` is set to `True`. Replay attempts return `HTTP 403 Forbidden`.
10. **Per-System Concurrency Mutex Lock**:
    - Only one recovery plan may execute on a given system simultaneously (`_ACTIVE_SYSTEM_EXECUTION_LOCKS`). Conflicting concurrent requests return `HTTP 409 Conflict`.
11. **Mandatory Rollback Strategy**:
    - Every candidate must specify a verified rollback mechanism (`rollback_strategy_json`). Candidates lacking a rollback strategy are rejected.
