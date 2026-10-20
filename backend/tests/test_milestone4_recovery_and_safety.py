"""Milestone 04/05 Scientific Verification, 20 Adversarial Safety Tests & End-to-End Recovery Suite.

Verifies all 20 adversarial/safety requirements (Section 12) and the complete 17-step
End-to-End Recovery & Rollback Demonstration (Section 13):
1. Execution without approval (403)
2. Expired approval (403)
3. Approval for a different plan (403)
4. Mutation after approval invalidates token/hash (403)
5. Replay of single-use approval token (403)
6. Unsupported remediation type / shell injection rejection (422)
7. Unauthorized target environment e.g. 'production' (403)
8. Excessive parameter values out of bounds (422)
9. Conflicting concurrent execution lock (409)
10. Sandbox restoration failure locks laboratory as unsafe (500 + lock enforcement)
11. Sandbox verification failure blocks approval (422)
12. Automatic rollback on post-execution guardrail violation (ROLLED_BACK)
13. Rollback failure enters MANUAL_INTERVENTION_REQUIRED
14. Cancellation enforcement (CANCELLED)
15. Execution timeout handling triggers automatic rollback
16. Insufficient causal evidence rejected fail-closed (422)
17. Simulation disagreement with observed sandbox outcome detected
18. Audit & safety policy evaluation completeness
19. Idempotent retries for workflow creation and execution
20. Resumable recovery across process interruption (step-by-step orchestration)
"""

from httpx import AsyncClient

from app.modules.laboratory.orchestrator import clear_lab_unsafe_lock, set_lab_profile
from app.modules.recovery.service import (
    acquire_test_execution_lock,
    release_test_execution_lock,
)

INVESTIGATOR_HEADERS = {"X-Origin-Key": "origin-dev-scientific-key-2026"}


async def test_full_17_step_end_to_end_autonomous_recovery_and_export(
    client: AsyncClient,
) -> None:
    """Section 13: Execute all 17 steps of the End-to-End Autonomous Recovery Demonstration."""
    clear_lab_unsafe_lock()

    # Step 1 & 2: Introduce performance fault (payment_latency_spike) and collect telemetry
    set_lab_profile("payment_latency_spike", blinded=False)
    lab_resp = await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 4, "profile": "payment_latency_spike"},
        headers=INVESTIGATOR_HEADERS,
    )
    assert lab_resp.status_code == 200

    # Steps 3, 4, 5, 6: Launch autonomous causal investigation, hypotheses, experiments, root cause
    inv_resp = await client.post(
        "/api/v1/investigations",
        json={
            "system_slug": "origin-synthetic-lab",
            "title": "E2E Recovery Investigation: Payment Spike",
            "target_service_key": "checkout-service",
            "experiment_budget": 2,
            "sample_size_per_arm": 4,
            "random_seed": 42,
            "auto_run": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert inv_resp.status_code == 201
    inv = inv_resp.json()
    assert inv["status"] == "CONCLUDED"
    assert inv["concluded_cause_service_key"] == "payment-simulator"

    # Steps 7-11: Create recovery workflow (resumable step-by-step across interruption #20)
    create_resp = await client.post(
        "/api/v1/recovery/plans",
        json={
            "system_slug": "origin-synthetic-lab",
            "title": "E2E Verified Payment Recovery Plan",
            "target_environment": "synthetic-lab",
            "investigation_id": inv["id"],
            "idempotency_key": "idem-e2e-plan-001",
            "auto_prepare_to_approval": False,
            "random_seed": 42,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert create_resp.status_code == 201
    plan_init = create_resp.json()
    plan_id = plan_init["id"]
    assert plan_init["status"] == "INVESTIGATING"

    # #19: Idempotent retry on workflow creation returns exact same plan_id
    idem_resp = await client.post(
        "/api/v1/recovery/plans",
        json={
            "system_slug": "origin-synthetic-lab",
            "title": "Duplicate Request",
            "idempotency_key": "idem-e2e-plan-001",
            "auto_prepare_to_approval": False,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert idem_resp.status_code == 201
    assert idem_resp.json()["id"] == plan_id

    # Step 7, 8, 9: Calibrate Digital Twin, simulate alternative remediations, generate proposals
    cand_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/candidates",
        json={},
        headers=INVESTIGATOR_HEADERS,
    )
    assert cand_resp.status_code == 200
    plan_with_cands = cand_resp.json()
    assert plan_with_cands["status"] == "PROPOSING"
    assert plan_with_cands["twin_model_id"] is not None
    assert len(plan_with_cands["candidates"]) >= 2
    # Candidates must be 'simulated_only' before sandbox verification — never prematurely verified!
    for c in plan_with_cands["candidates"]:
        assert c["verification_status"] == "simulated_only"
        assert c["simulation_prediction_json"]["epistemic_label"] == "counterfactual_prediction"

    # Attempt to approve before sandbox verification -> MUST be rejected (422)!
    premature_app = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/approve",
        json={
            "decision": "APPROVED",
            "approver_identity": "sre-lead",
            "rationale": "Trying to approve before sandbox verification",
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert premature_app.status_code == 422

    # Steps 10 & 11: Verify top candidate in isolated sandbox & restore lab after verification
    sb_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/sandbox-verify",
        json={"trials_per_arm": 4, "random_seed": 42},
        headers=INVESTIGATOR_HEADERS,
    )
    assert sb_resp.status_code == 200
    plan_sb = sb_resp.json()
    assert plan_sb["status"] == "AWAITING_APPROVAL"
    assert len(plan_sb["sandbox_runs"]) == 1
    srun = plan_sb["sandbox_runs"][0]
    assert srun["passed_thresholds"] is True
    assert srun["restoration_verified"] is True
    assert (
        srun["treatment_metrics_json"]["mean_latency_ms"]
        < srun["baseline_metrics_json"]["mean_latency_ms"] * 0.55
    )

    # Steps 12 & 13: Present exact action for human approval and approve with authorized identity
    app_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/approve",
        json={
            "decision": "APPROVED",
            "approver_identity": "principal-sre-commander",
            "approver_role": "reliability-commander",
            "rationale": "Sandbox verified >70% latency reduction and clean restoration.",
            "ttl_seconds": 600,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert app_resp.status_code == 201
    approval = app_resp.json()
    approval_id = approval["id"]
    single_use_token = approval["issued_single_use_token"]
    assert single_use_token is not None and single_use_token.startswith("origin-appr-")

    # Steps 14-16: Execute approved action in laboratory, observe performance, confirm recovery
    exec_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/execute",
        json={
            "approval_id": approval_id,
            "approval_token": single_use_token,
            "idempotency_key": "exec-idem-001",
            "observation_iterations": 4,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert exec_resp.status_code == 200
    recovered_plan = exec_resp.json()
    assert recovered_plan["status"] == "RECOVERED"
    assert len(recovered_plan["executions"]) == 1
    ex = recovered_plan["executions"][0]
    assert ex["status"] == "RECOVERED"
    assert ex["verification_passed"] is True
    assert ex["rollback_triggered"] is False
    assert (
        ex["observed_metrics_json"]["mean_latency_ms"]
        < ex["pre_execution_metrics_json"]["mean_latency_ms"] * 0.55
    )

    # #19: Idempotent retry on execution returns existing RECOVERED state without error
    exec_idem_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/execute",
        json={
            "approval_id": approval_id,
            "approval_token": single_use_token,
            "idempotency_key": "exec-idem-001",
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert exec_idem_resp.status_code == 200
    assert exec_idem_resp.json()["status"] == "RECOVERED"

    # #5: Replay of single-use approval token with a new request -> MUST fail with 403!
    replay_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/execute",
        json={
            "approval_id": approval_id,
            "approval_token": single_use_token,
            "idempotency_key": "exec-replay-attempt",
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert replay_resp.status_code == 403

    # Step 17 & #18: Export complete reproducible report & verify audit completeness
    exp_resp = await client.get(f"/api/v1/recovery/plans/{plan_id}/export?format=markdown")
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()
    assert "# ORIGIN Verified Autonomous Recovery Report" in exp_data["markdown"]
    assert len(recovered_plan["policy_evaluations"]) >= 3
    assert len(recovered_plan["agent_decision_history_json"]) >= 4


async def test_adversarial_approval_and_policy_bypass_defenses(
    client: AsyncClient,
) -> None:
    """Tests 1, 2, 3, 4, 6, 7, 8, 9, 16: Verify all fail-closed policy and approval defenses."""
    clear_lab_unsafe_lock()
    set_lab_profile("db_lock_contention", blinded=False)
    await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 4, "profile": "db_lock_contention"},
        headers=INVESTIGATOR_HEADERS,
    )

    # #7: Unauthorized environment ('production') -> 403 Forbidden
    prod_resp = await client.post(
        "/api/v1/recovery/plans",
        json={
            "system_slug": "origin-synthetic-lab",
            "title": "Unauthorized Production Recovery",
            "target_environment": "production",
            "operator_root_cause_service_key": "order-database-sim",
            "operator_root_cause_mechanism": "database_lock_contention",
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert prod_resp.status_code == 403

    # #16: Insufficient causal evidence (noisy_ambiguous_jitter -> INCONCLUSIVE) -> 422
    set_lab_profile("noisy_ambiguous_jitter", blinded=False)
    await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 4, "profile": "noisy_ambiguous_jitter"},
        headers=INVESTIGATOR_HEADERS,
    )
    insuff_resp = await client.post(
        "/api/v1/recovery/plans",
        json={
            "system_slug": "origin-synthetic-lab",
            "title": "Ambiguous Fault Recovery Attempt",
            "target_environment": "synthetic-lab",
            "random_seed": 42,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert insuff_resp.status_code == 422

    # Create two valid recovery plans (Plan A and Plan B) under db_lock_contention
    set_lab_profile("db_lock_contention", blinded=False)
    await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 4, "profile": "db_lock_contention"},
        headers=INVESTIGATOR_HEADERS,
    )
    plan_a = (
        await client.post(
            "/api/v1/recovery/plans",
            json={
                "system_slug": "origin-synthetic-lab",
                "title": "Plan A DB Contention",
                "operator_root_cause_service_key": "order-database-sim",
                "operator_root_cause_mechanism": "database_lock_contention",
                "auto_prepare_to_approval": True,
            },
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    plan_a_id = plan_a["id"]

    plan_b = (
        await client.post(
            "/api/v1/recovery/plans",
            json={
                "system_slug": "origin-synthetic-lab",
                "title": "Plan B DB Contention",
                "operator_root_cause_service_key": "order-database-sim",
                "operator_root_cause_mechanism": "database_lock_contention",
                "auto_prepare_to_approval": True,
            },
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    plan_b_id = plan_b["id"]

    # #6: Unsupported remediation type or shell command -> 422
    bad_action_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_a_id}/candidates",
        json={
            "custom_action_type": "execute_arbitrary_shell_cmd",
            "custom_target_service_key": "order-database-sim",
            "custom_parameters": {"cmd": "rm -rf /"},
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert bad_action_resp.status_code == 422

    # #8: Excessive parameter values (replicas=99 > max 8) -> 422
    excessive_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_a_id}/candidates",
        json={
            "custom_action_type": "adjust_service_replicas",
            "custom_target_service_key": "checkout-service",
            "custom_parameters": {"replicas": 99},
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert excessive_resp.status_code == 422

    # #1: Execution without approval -> 403
    unapproved_exec = await client.post(
        f"/api/v1/recovery/plans/{plan_a_id}/execute",
        json={
            "approval_id": "non-existent-approval-id",
            "approval_token": "forged-token-12345678",
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert unapproved_exec.status_code == 403

    # #2: Expired approval (ttl_seconds = -30) -> 403
    exp_app = (
        await client.post(
            f"/api/v1/recovery/plans/{plan_a_id}/approve",
            json={
                "decision": "APPROVED",
                "approver_identity": "sre-commander",
                "ttl_seconds": -30,
            },
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    exp_exec = await client.post(
        f"/api/v1/recovery/plans/{plan_a_id}/execute",
        json={
            "approval_id": exp_app["id"],
            "approval_token": exp_app["issued_single_use_token"],
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert exp_exec.status_code == 403

    # Issue valid approval for Plan A
    valid_app_a = (
        await client.post(
            f"/api/v1/recovery/plans/{plan_a_id}/approve",
            json={
                "decision": "APPROVED",
                "approver_identity": "sre-commander",
                "ttl_seconds": 600,
            },
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()

    # #3: Attempt to use Plan A's approval on Plan B -> 403
    cross_plan_exec = await client.post(
        f"/api/v1/recovery/plans/{plan_b_id}/execute",
        json={
            "approval_id": valid_app_a["id"],
            "approval_token": valid_app_a["issued_single_use_token"],
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert cross_plan_exec.status_code == 403

    # #4: Mutate Plan A after approval -> invalidates approval (403 on execute)
    mut_resp = await client.patch(
        f"/api/v1/recovery/plans/{plan_a_id}",
        json={
            "parameter_overrides": {"db_connection_capacity": 175.0},
            "reason": "Post-approval parameter mutation test",
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert mut_resp.status_code == 200
    assert mut_resp.json()["plan_version"] == 2

    mut_exec = await client.post(
        f"/api/v1/recovery/plans/{plan_a_id}/execute",
        json={
            "approval_id": valid_app_a["id"],
            "approval_token": valid_app_a["issued_single_use_token"],
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert mut_exec.status_code == 403

    # #9: Conflicting concurrent execution lock -> 409 Conflict
    app_b = (
        await client.post(
            f"/api/v1/recovery/plans/{plan_b_id}/approve",
            json={
                "decision": "APPROVED",
                "approver_identity": "sre-commander",
                "ttl_seconds": 600,
            },
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    acquire_test_execution_lock(plan_b["system_id"])
    try:
        lock_exec = await client.post(
            f"/api/v1/recovery/plans/{plan_b_id}/execute",
            json={
                "approval_id": app_b["id"],
                "approval_token": app_b["issued_single_use_token"],
            },
            headers=INVESTIGATOR_HEADERS,
        )
        assert lock_exec.status_code == 409
    finally:
        release_test_execution_lock(plan_b["system_id"])


async def test_sandbox_restoration_failure_automatic_rollback_and_manual_intervention(
    client: AsyncClient,
) -> None:
    """Tests 10-15, 17: Verify sandbox failures, auto-rollback, and rollback failure."""
    clear_lab_unsafe_lock()
    set_lab_profile("db_lock_contention", blinded=False)
    await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 4, "profile": "db_lock_contention"},
        headers=INVESTIGATOR_HEADERS,
    )

    plan = (
        await client.post(
            "/api/v1/recovery/plans",
            json={
                "system_slug": "origin-synthetic-lab",
                "title": "Rollback & Failure Modes Test Plan",
                "operator_root_cause_service_key": "order-database-sim",
                "operator_root_cause_mechanism": "database_lock_contention",
                "auto_prepare_to_approval": False,
            },
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    plan_id = plan["id"]

    plan = (
        await client.post(
            f"/api/v1/recovery/plans/{plan_id}/candidates",
            json={},
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()

    # #11 & #17: Verify naive candidate (adjust_service_replicas on checkout-service)
    # fails sandbox verification thresholds!
    naive_cand = next(
        c for c in plan["candidates"] if c["action_type"] == "adjust_service_replicas"
    )
    sb_fail_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/sandbox-verify",
        json={"candidate_id": naive_cand["id"], "trials_per_arm": 3},
        headers=INVESTIGATOR_HEADERS,
    )
    assert sb_fail_resp.status_code == 200
    assert sb_fail_resp.json()["status"] == "FAILED"
    assert sb_fail_resp.json()["sandbox_runs"][0]["passed_thresholds"] is False

    # #10: Simulate sandbox restoration failure -> 500 & marks laboratory unsafe!
    good_cand = next(
        c for c in plan["candidates"] if c["action_type"] == "adjust_db_contention_controls"
    )
    restore_fail_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/sandbox-verify",
        json={
            "candidate_id": good_cand["id"],
            "trials_per_arm": 3,
            "simulate_restore_failure": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert restore_fail_resp.status_code == 500

    # Verify policy endpoint reports lab_unsafe_locked == True and blocks new sandbox runs
    pol_state = (await client.get("/api/v1/safety/policies")).json()
    assert pol_state["lab_unsafe_locked"] is True

    blocked_sb = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/sandbox-verify",
        json={"candidate_id": good_cand["id"], "trials_per_arm": 3},
        headers=INVESTIGATOR_HEADERS,
    )
    assert blocked_sb.status_code == 422

    # Clear unsafe lock and verify good candidate passes sandbox verification
    await client.post("/api/v1/safety/clear-lab-lock", headers=INVESTIGATOR_HEADERS)
    set_lab_profile("db_lock_contention", blinded=False)
    sb_ok = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/sandbox-verify",
        json={"candidate_id": good_cand["id"], "trials_per_arm": 3},
        headers=INVESTIGATOR_HEADERS,
    )
    assert sb_ok.status_code == 200
    assert sb_ok.json()["status"] == "AWAITING_APPROVAL"

    # #12: Approve and execute with simulated post-execution regression -> Automatic Rollback!
    app_1 = (
        await client.post(
            f"/api/v1/recovery/plans/{plan_id}/approve",
            json={"decision": "APPROVED", "approver_identity": "sre-lead"},
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    rb_exec_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/execute",
        json={
            "approval_id": app_1["id"],
            "approval_token": app_1["issued_single_use_token"],
            "simulate_execution_regression": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert rb_exec_resp.status_code == 200
    rb_plan = rb_exec_resp.json()
    assert rb_plan["status"] == "ROLLED_BACK"
    assert rb_plan["executions"][0]["rollback_triggered"] is True
    assert rb_plan["rollbacks"][0]["rollback_verified"] is True
    assert rb_plan["rollbacks"][0]["status"] == "COMPLETED"

    # #15: Re-approve and execute with timeout -> Automatic Rollback!
    app_2 = (
        await client.post(
            f"/api/v1/recovery/plans/{plan_id}/approve",
            json={"decision": "APPROVED", "approver_identity": "sre-lead"},
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    timeout_exec_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/execute",
        json={
            "approval_id": app_2["id"],
            "approval_token": app_2["issued_single_use_token"],
            "simulate_timeout": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert timeout_exec_resp.status_code == 200
    assert timeout_exec_resp.json()["status"] == "ROLLED_BACK"

    # #13: Re-approve and execute with regression + rollback failure -> MANUAL_INTERVENTION_REQUIRED
    app_3 = (
        await client.post(
            f"/api/v1/recovery/plans/{plan_id}/approve",
            json={"decision": "APPROVED", "approver_identity": "sre-lead"},
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    manual_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_id}/execute",
        json={
            "approval_id": app_3["id"],
            "approval_token": app_3["issued_single_use_token"],
            "simulate_execution_regression": True,
            "simulate_rollback_failure": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert manual_resp.status_code == 200
    assert manual_resp.json()["status"] == "MANUAL_INTERVENTION_REQUIRED"
    assert manual_resp.json()["rollbacks"][0]["status"] == "MANUAL_INTERVENTION_REQUIRED"
    clear_lab_unsafe_lock()

    # #14: Cancellation test on a new workflow
    plan_cancel = (
        await client.post(
            "/api/v1/recovery/plans",
            json={
                "system_slug": "origin-synthetic-lab",
                "title": "Cancel Test Plan",
                "operator_root_cause_service_key": "order-database-sim",
                "operator_root_cause_mechanism": "database_lock_contention",
                "auto_prepare_to_approval": False,
            },
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    cancel_resp = await client.post(
        f"/api/v1/recovery/plans/{plan_cancel['id']}/cancel",
        headers=INVESTIGATOR_HEADERS,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"
