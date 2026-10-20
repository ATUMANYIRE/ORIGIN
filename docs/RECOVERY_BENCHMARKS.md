# ORIGIN Milestone 04/05 Verification & Safety Benchmarks (`docs/RECOVERY_BENCHMARKS.md`)

**Milestone:** `04/05 — Verified Autonomous Recovery, Agent Orchestration & Operational Safety`  
**Test Suite:** [`backend/tests/test_milestone4_recovery_and_safety.py`](file:///E:/Projects/ORIGIN/backend/tests/test_milestone4_recovery_and_safety.py)

---

## 1. Twenty Adversarial & Safety Test Cases (Section 12)

Every one of the twenty safety requirements is verified with automated tests:

1. **Unapproved Execution Rejection**: `POST /execute` without an approval record returns `HTTP 403 Forbidden`.
2. **Expired Approval Rejection**: Executing with an expired human approval token returns `HTTP 403 Forbidden`.
3. **Plan Mismatch Rejection**: Presenting an approval issued for Plan A to execute Plan B returns `HTTP 403 Forbidden`.
4. **Post-Approval Mutation Invalidation**: Mutating parameters on an approved plan revokes prior approval and causes plan hash mismatch (`HTTP 403 Forbidden`).
5. **Single-Use Token Replay Rejection**: Executing twice with the exact same approval token returns `HTTP 403 Forbidden`.
6. **Disallowed Action Type Rejection**: Supplying an arbitrary command or shell script returns `HTTP 422 Unprocessable Content`.
7. **Unauthorized Target Environment Rejection**: Targeting `production` returns `HTTP 403 Forbidden`.
8. **Parameter Safety Bounds Rejection**: Requesting out-of-bound parameters (e.g. `replicas = 999`) returns `HTTP 422 Unprocessable Content`.
9. **Conflicting Concurrency Mutex Lock**: Simultaneous execution on the same system returns `HTTP 409 Conflict`.
10. **Sandbox Restoration Failure Handling**: Restoration failure marks laboratory unsafe (`HTTP 500`) and locks future sandbox trials (`HTTP 422`).
11. **Sandbox Threshold Failure Blocks Approval**: A candidate failing sandbox recovery thresholds transitions to `FAILED` and cannot be approved (`HTTP 422`).
12. **Automatic Rollback on Post-Execution Regression**: Simulated post-execution regression triggers automatic rollback and transitions plan to `ROLLED_BACK`.
13. **Rollback Failure Enters `MANUAL_INTERVENTION_REQUIRED`**: Rollback failure marks execution and plan as `MANUAL_INTERVENTION_REQUIRED`.
14. **Cancellation Enforcement**: Calling `POST /cancel` during observation rolls back and marks plan `CANCELLED`.
15. **Execution Timeout Handling**: Exceeding timeout triggers automatic rollback to `ROLLED_BACK`.
16. **Insufficient Causal Evidence Rejection**: Creating a recovery plan with an inconclusive investigation or missing root cause returns `HTTP 422`.
17. **Digital Twin vs. Sandbox Disagreement Detection**: Divergence between Twin prediction and sandbox measurements is explicitly flagged in `simulation_disagreement_json`.
18. **Audit & Safety Policy Completeness**: All policy evaluations and execution transitions are recorded in `safety_policy_evaluations` and `audit_events`.
19. **Idempotent Retry Safety**: Repeating `POST /recovery/plans` or `POST /execute` with an `idempotency_key` returns the existing record without duplicate side-effects.
20. **Resumable Recovery Across Process Interruption**: Step-by-step orchestrator execution resumes safely across process restarts.

---

## 2. Full 17-Step End-to-End Recovery Demonstration (Section 13)

The complete end-to-end loop verified in `test_full_17_step_end_to_end_autonomous_recovery_and_export`:
- **Step 1–2**: Injected `payment_latency_spike` and collected telemetry baseline.
- **Step 3–6**: Concluded causal investigation confirming `payment-simulator` root cause.
- **Step 7–9**: Created recovery workflow, calibrated living digital twin, simulated competing candidates, and proposed ranked remediation options.
- **Step 10–11**: Real isolated laboratory sandbox verification with before/after Welch's $t$-test and laboratory restoration verification.
- **Step 12–13**: Human approval recorded with cryptographic SHA-256 `plan_hash` and single-use token issuance.
- **Step 14–16**: Approved remediation executed in laboratory, post-execution telemetry observed ($>70\%$ latency recovery confirmed), and committed to `ScientificMemory`.
- **Step 17**: Complete Markdown and JSON reproducible audit reports exported.
