"""Scientific verification suite for Milestone 03/05: Living Digital Twin & Scientific Memory."""

from httpx import AsyncClient

from app.modules.simulation.simulator import (
    LivingDigitalTwinSimulator,
    default_lab_twin_parameters,
)

INVESTIGATOR_HEADERS = {"X-Origin-Key": "origin-dev-scientific-key-2026"}


async def test_deterministic_replay_and_snapshot_rewind() -> None:
    """1 & 2. Prove deterministic replay with identical seeds and exact state rewind."""
    params = default_lab_twin_parameters()
    sim_a = LivingDigitalTwinSimulator(model_parameters=params, random_seed=777)
    sim_b = LivingDigitalTwinSimulator(model_parameters=params, random_seed=777)

    traj_a, events_a, sum_a = sim_a.run_horizon(horizon_seconds=15.0, dt_seconds=1.0)
    traj_b, events_b, sum_b = sim_b.run_horizon(horizon_seconds=15.0, dt_seconds=1.0)

    assert traj_a == traj_b
    assert events_a == events_b
    assert sum_a == sum_b

    # Now verify snapshot capture at step 5 and rewind produces identical continuation
    sim_rewind = LivingDigitalTwinSimulator(model_parameters=params, random_seed=777)
    sim_rewind.schedule_interventions(
        [
            {
                "intervention_type": "increase_replicas",
                "target_service_key": "checkout-service",
                "value": 4.0,
                "apply_at_sec": 8.0,
            }
        ]
    )
    for _ in range(5):
        sim_rewind.step(1.0)

    snap_at_5 = sim_rewind.capture_snapshot_dict(label="t=5s checkpoint")
    first_run_tail = [sim_rewind.step(1.0) for _ in range(10)]

    # Mutate simulator state, then rewind to snap_at_5 and replay
    sim_rewind.step(1.0)
    sim_rewind.restore_from_snapshot_dict(snap_at_5)
    second_run_tail = [sim_rewind.step(1.0) for _ in range(10)]

    assert first_run_tail == second_run_tail


async def test_branch_isolation_and_queue_resource_bounds() -> None:
    """3, 4, 5. Prove branch isolation, intervention dynamics, and physical queue bounds."""
    base_params = default_lab_twin_parameters()
    base_params["incoming_traffic_rps"] = 60.0

    # Branch 1: Baseline load
    sim_base = LivingDigitalTwinSimulator(model_parameters=base_params, random_seed=42)
    snap_0 = sim_base.capture_snapshot_dict("t=0")
    traj_base, _, sum_base = sim_base.run_horizon(horizon_seconds=15.0, dt_seconds=1.0)

    # Branch 2: Restored from snap_0 with dependency failure injected
    sim_fail = LivingDigitalTwinSimulator(model_parameters=base_params, random_seed=42)
    sim_fail.restore_from_snapshot_dict(snap_0)
    sim_fail.schedule_interventions(
        [
            {
                "intervention_type": "simulate_dependency_failure",
                "target_service_key": "payment-simulator",
                "value": 8.0,
                "apply_at_sec": 0.0,
            }
        ]
    )
    traj_fail, _, sum_fail = sim_fail.run_horizon(horizon_seconds=15.0, dt_seconds=1.0)

    # Re-run baseline from snap_0 to prove Branch 2 did not mutate snap_0 or base_params
    sim_base_verify = LivingDigitalTwinSimulator(model_parameters=base_params, random_seed=42)
    sim_base_verify.restore_from_snapshot_dict(snap_0)
    traj_base_2, _, _ = sim_base_verify.run_horizon(horizon_seconds=15.0, dt_seconds=1.0)
    assert traj_base == traj_base_2
    assert sum_fail["mean_latency_ms"] > sum_base["mean_latency_ms"] * 1.5

    # 5. Property check across all frames and services: queue_depth in [0, max_queue_depth]
    for frame in traj_base + traj_fail:
        for sstate in frame["services"].values():
            assert 0.0 <= sstate["queue_depth"] <= sstate["max_queue_depth"]
            assert 0.0 <= sstate["saturation_pct"] <= 100.0
            assert 0.0 <= sstate["error_rate_pct"] <= 100.0
            assert 1 <= sstate["active_concurrency"] <= sstate["concurrency_limit"]


async def test_shared_db_bottleneck_and_circuit_breaker_tradeoffs() -> None:
    """6 & 7. Prove shared DB lock bottleneck limits scaling and circuit breaker tradeoffs."""
    db_params = default_lab_twin_parameters()
    db_params["services"]["order-database-sim"]["db_lock_contention_factor"] = 1.4
    db_params["services"]["order-database-sim"]["db_connection_capacity"] = 34.0

    sim_base = LivingDigitalTwinSimulator(model_parameters=db_params, random_seed=99)
    _, _, sum_base = sim_base.run_horizon(horizon_seconds=15.0)

    # Scaling checkout-service replicas 2->6 must NOT improve latency under DB lock bottleneck
    sim_naive = LivingDigitalTwinSimulator(model_parameters=db_params, random_seed=99)
    sim_naive.schedule_interventions(
        [
            {
                "intervention_type": "increase_replicas",
                "target_service_key": "checkout-service",
                "value": 6.0,
                "apply_at_sec": 0.0,
            }
        ]
    )
    _, _, sum_naive = sim_naive.run_horizon(horizon_seconds=15.0)
    assert sum_naive["mean_latency_ms"] >= sum_base["mean_latency_ms"]

    # Relieving DB connection/lock capacity DOES reduce latency
    sim_db_fix = LivingDigitalTwinSimulator(model_parameters=db_params, random_seed=99)
    sim_db_fix.schedule_interventions(
        [
            {
                "intervention_type": "adjust_db_connection_capacity",
                "target_service_key": "order-database-sim",
                "value": 180.0,
                "apply_at_sec": 0.0,
            }
        ]
    )
    _, _, sum_db_fix = sim_db_fix.run_horizon(horizon_seconds=15.0)
    assert sum_db_fix["mean_latency_ms"] < sum_base["mean_latency_ms"] * 0.65

    # 7. Circuit breaker tradeoff under severe downstream slowdown
    cb_params = default_lab_twin_parameters()
    cb_params["services"]["payment-simulator"]["base_latency_ms"] = 480.0
    sim_no_cb = LivingDigitalTwinSimulator(model_parameters=cb_params, random_seed=55)
    _, _, sum_no_cb = sim_no_cb.run_horizon(horizon_seconds=15.0)

    sim_with_cb = LivingDigitalTwinSimulator(model_parameters=cb_params, random_seed=55)
    sim_with_cb.schedule_interventions(
        [
            {
                "intervention_type": "enable_circuit_breaker",
                "target_service_key": "checkout-service",
                "value": 1.0,
                "apply_at_sec": 0.0,
            }
        ]
    )
    _, _, sum_with_cb = sim_with_cb.run_horizon(horizon_seconds=15.0)

    # Circuit breaker reduces latency and queue depth, with bounded fast-fail error rate
    assert sum_with_cb["mean_latency_ms"] < sum_no_cb["mean_latency_ms"] * 0.45
    assert sum_with_cb["max_queue_depth"] < sum_no_cb["max_queue_depth"]
    assert sum_with_cb["mean_error_rate_pct"] >= 8.0


async def test_calibration_insufficient_data_and_heldout_validation(
    client: AsyncClient,
) -> None:
    """8, 9, 10. Verify insufficient data rejection, calibration, and held-out split."""
    # 10. Requesting strict calibration with min_required_observations=450 -> 422
    strict_resp = await client.post(
        "/api/v1/twins/calibrate",
        json={
            "system_slug": "origin-synthetic-lab",
            "min_required_observations": 450,
            "strict_rejection": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert strict_resp.status_code == 422

    # Non-strict with high threshold returns status="rejected_insufficient_data"
    warn_resp = await client.post(
        "/api/v1/twins/calibrate",
        json={
            "system_slug": "origin-synthetic-lab",
            "min_required_observations": 450,
            "strict_rejection": False,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert warn_resp.status_code == 201
    warn_data = warn_resp.json()
    assert warn_data["twin_model"]["status"] == "rejected_insufficient_data"
    assert len(warn_data["twin_model"]["warnings_json"]) >= 1

    # 8 & 9. Generate real laboratory telemetry and calibrate with held-out validation split
    await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 6, "profile": "payment_latency_spike"},
        headers=INVESTIGATOR_HEADERS,
    )
    cal_resp = await client.post(
        "/api/v1/twins/calibrate",
        json={
            "system_slug": "origin-synthetic-lab",
            "min_required_observations": 12,
            "validation_split_ratio": 0.25,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert cal_resp.status_code == 201
    cal_bundle = cal_resp.json()
    twin = cal_bundle["twin_model"]
    cal_run = cal_bundle["calibration_run"]

    assert twin["status"] in ("calibrated", "degraded_validity")
    train_ids = set(cal_run["train_correlation_ids_json"])
    val_ids = set(cal_run["validation_correlation_ids_json"])
    assert len(train_ids) >= 3
    assert len(val_ids) >= 1
    # Train and held-out validation correlation sets must be strictly disjoint!
    assert train_ids.isdisjoint(val_ids)
    assert cal_run["mae_ms"] >= 0.0
    assert cal_run["rmse_ms"] >= 0.0
    assert len(cal_run["residuals_json"]) >= 1


async def test_persisted_snapshots_branches_cancellation_and_memory(
    client: AsyncClient,
) -> None:
    """11, 12, 13, 14. Verify persisted snapshots, branch comparison, and memory."""
    await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 4, "profile": "payment_latency_spike"},
        headers=INVESTIGATOR_HEADERS,
    )
    cal_resp = await client.post(
        "/api/v1/twins/calibrate",
        json={"system_slug": "origin-synthetic-lab", "min_required_observations": 12},
        headers=INVESTIGATOR_HEADERS,
    )
    twin_id = cal_resp.json()["twin_model"]["id"]

    # 12. Create persisted snapshot at step 3
    snap_resp = await client.post(
        "/api/v1/simulations/snapshots",
        json={
            "twin_model_id": twin_id,
            "step_index": 3,
            "label": "Checkpoint t=3s",
            "random_seed": 42,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert snap_resp.status_code == 201
    snap_id = snap_resp.json()["id"]
    assert snap_resp.json()["sim_clock_sec"] == 3.0

    # Run baseline branch from persisted snapshot
    b1_resp = await client.post(
        "/api/v1/simulations/branches",
        json={
            "twin_model_id": twin_id,
            "name": "Baseline from t=3s",
            "branch_type": "baseline",
            "initial_snapshot_id": snap_id,
            "random_seed": 42,
            "horizon_seconds": 15.0,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert b1_resp.status_code == 201
    b1 = b1_resp.json()

    # Re-run identical branch from same persisted snapshot -> identical trajectory
    b1_replay = (
        await client.post(
            "/api/v1/simulations/branches",
            json={
                "twin_model_id": twin_id,
                "name": "Replay from t=3s",
                "branch_type": "baseline",
                "initial_snapshot_id": snap_id,
                "random_seed": 42,
                "horizon_seconds": 15.0,
            },
            headers=INVESTIGATOR_HEADERS,
        )
    ).json()
    assert b1["trajectory_json"] == b1_replay["trajectory_json"]

    # Run counterfactual branch with payment latency reduction
    b2_resp = await client.post(
        "/api/v1/simulations/branches",
        json={
            "twin_model_id": twin_id,
            "name": "Counterfactual Payment Recovery",
            "branch_type": "counterfactual",
            "parent_branch_id": b1["id"],
            "initial_snapshot_id": snap_id,
            "random_seed": 42,
            "horizon_seconds": 15.0,
            "interventions": [
                {
                    "intervention_type": "reduce_downstream_latency",
                    "target_service_key": "payment-simulator",
                    "value": 0.15,
                    "apply_at_sec": 3.0,
                }
            ],
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert b2_resp.status_code == 201
    b2 = b2_resp.json()

    # Compare branches
    comp_resp = await client.get(
        f"/api/v1/simulations/compare?baseline_branch_id={b1['id']}&alternative_branch_id={b2['id']}"
    )
    assert comp_resp.status_code == 200
    comp = comp_resp.json()
    assert comp["epistemic_label"] == "counterfactual_prediction"
    assert comp["delta_metrics"]["latency_delta_ms"] < 0.0

    # Export simulation report
    exp_resp = await client.get(
        f"/api/v1/simulations/branches/{b2['id']}/export?compare_with_branch_id={b1['id']}"
    )
    assert exp_resp.status_code == 200
    assert "counterfactual_prediction" in exp_resp.json()["markdown"]

    # 14. Cancellation endpoint
    cancel_resp = await client.post(
        f"/api/v1/simulations/branches/{b2['id']}/cancel",
        headers=INVESTIGATOR_HEADERS,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # 11 & 13. Causal integration & Scientific Memory epistemic separation + evidence immutability
    inv_resp = await client.post(
        "/api/v1/investigations",
        json={
            "system_slug": "origin-synthetic-lab",
            "title": "Causal + Twin Integration Test",
            "target_service_key": "checkout-service",
            "experiment_budget": 2,
            "sample_size_per_arm": 4,
            "random_seed": 42,
            "auto_run": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    inv_data = inv_resp.json()
    inv_id = inv_data["id"]
    evidence_before = (await client.get(f"/api/v1/investigations/{inv_id}/evidence")).json()

    sim_hyp_resp = await client.post(
        f"/api/v1/investigations/{inv_id}/simulate",
        json={
            "suspected_service_key": "payment-simulator",
            "intervention_type": "reduce_downstream_latency",
            "intervention_value": 0.15,
            "random_seed": 42,
            "horizon_seconds": 15.0,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert sim_hyp_resp.status_code == 200
    sim_hyp = sim_hyp_resp.json()
    assert sim_hyp["observed_evidence"]["epistemic_status"] == "historical_observation"
    assert sim_hyp["experimental_evidence"]["epistemic_status"] == "experimental_evidence"
    assert sim_hyp["simulated_prediction"]["epistemic_status"] == "counterfactual_prediction"

    # 13. Verify historical evidence records of the investigation were not mutated by simulation!
    evidence_after = (await client.get(f"/api/v1/investigations/{inv_id}/evidence")).json()
    assert evidence_before == evidence_after

    # Verify Scientific Memory queries
    mem_resp = await client.get("/api/v1/memory/entries")
    assert mem_resp.status_code == 200
    mem_entries = mem_resp.json()
    kinds = {m["epistemic_kind"] for m in mem_entries}
    assert "calibrated_model" in kinds
    assert "counterfactual_prediction" in kinds
    assert "historical_observation" in kinds


async def test_four_simulation_benchmarks_suite(client: AsyncClient) -> None:
    """12 (Section 12). Execute all 4 canonical Digital Twin benchmarks (A, B, C, D)."""
    bench_resp = await client.post(
        "/api/v1/simulations/benchmarks/run?random_seed=2026",
        headers=INVESTIGATOR_HEADERS,
    )
    assert bench_resp.status_code == 201
    suite = bench_resp.json()
    assert suite["total_benchmarks"] == 4
    assert suite["passed_count"] == 4
    for b in suite["benchmarks"]:
        assert b["passed_verification"] is True
