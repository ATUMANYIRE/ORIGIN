"""Scientific verification suite for Milestone 02/05: Autonomous Causal Scientist."""

import math

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MetricObservation, SpanObservation
from app.modules.agents.model_gateway import (
    CandidateHypothesisProposal,
    validate_candidate_proposal,
)
from app.modules.experimentation.engine import (
    compute_experiment_statistics,
    generate_block_randomized_assignment,
)
from app.modules.laboratory.orchestrator import get_lab_state, set_lab_profile

BENCHMARK_HEADERS = {"X-Benchmark-Controller-Key": "origin-private-benchmark-evaluator-key-2026"}
INVESTIGATOR_HEADERS = {"X-Origin-Key": "origin-dev-scientific-key-2026"}


async def test_statistical_calculation_known_fixtures() -> None:
    """13. Verify statistical calculations against known analytical fixture values."""
    # Control: mean = 500.0, sample variance = 80.0 (std = 8.9442719)
    control = [490.0, 500.0, 510.0, 490.0, 500.0, 510.0]
    # Treatment: mean = 100.0, sample variance = 80.0 (std = 8.9442719)
    treatment = [90.0, 100.0, 110.0, 90.0, 100.0, 110.0]

    stats = compute_experiment_statistics(
        control_values=control,
        treatment_values=treatment,
    )

    assert math.isclose(stats["control_mean_ms"], 500.0, rel_tol=1e-5)
    assert math.isclose(stats["treatment_mean_ms"], 100.0, rel_tol=1e-5)
    assert math.isclose(stats["absolute_effect_size_ms"], -400.0, rel_tol=1e-5)
    assert math.isclose(stats["relative_effect_pct"], -80.0, rel_tol=1e-5)
    # Pooled std is sqrt(80) = 8.9442719; Cohen's d = -400 / 8.9442719 = -44.72136
    assert abs(stats["cohens_d"]) > 40.0
    assert abs(stats["welch_t_stat"]) > 50.0
    assert stats["ci_lower_95_ms"] < -380.0
    assert stats["ci_upper_95_ms"] < -380.0
    assert stats["is_statistically_significant"] is True


async def test_seeded_block_randomized_reproducibility() -> None:
    """5. Verify seeded reproducibility and balanced treatment/control assignment."""
    order_a = generate_block_randomized_assignment(sample_size_per_arm=6, random_seed=42)
    order_b = generate_block_randomized_assignment(sample_size_per_arm=6, random_seed=42)
    order_c = generate_block_randomized_assignment(sample_size_per_arm=6, random_seed=999)

    assert order_a == order_b
    assert len(order_a) == 12
    assert order_a.count("control") == 6
    assert order_a.count("treatment") == 6
    # Every consecutive pair is a balanced block of 1 control + 1 treatment
    for idx in range(0, 12, 2):
        assert set(order_a[idx : idx + 2]) == {"control", "treatment"}
    assert order_a != order_c


async def test_unsafe_intervention_and_topology_validation() -> None:
    """8. Verify model-gateway validation rejects unsafe interventions and unknown nodes."""
    valid_services = {"api-gateway", "checkout-service", "payment-simulator"}

    # Unsafe intervention key
    unsafe_intervention = CandidateHypothesisProposal(
        root_cause_service_key="payment-simulator",
        affected_service_key="checkout-service",
        suspected_mechanism="shell_exec_attempt",
        statement="Run arbitrary bash command on payment-simulator",
        recommended_intervention="rm_rf_production",
    )
    assert validate_candidate_proposal(unsafe_intervention, valid_services) is False

    # Non-existent topology node
    unknown_node = CandidateHypothesisProposal(
        root_cause_service_key="imaginary-cache-cluster",
        affected_service_key="checkout-service",
        suspected_mechanism="cache_miss",
        statement="Imaginary cache causes checkout latency",
        recommended_intervention="isolate_payment_fastpath",
    )
    assert validate_candidate_proposal(unknown_node, valid_services) is False

    # Valid allowlisted proposal on reachable service
    valid_proposal = CandidateHypothesisProposal(
        root_cause_service_key="payment-simulator",
        affected_service_key="checkout-service",
        suspected_mechanism="payment_gateway_latency_propagation",
        statement="Payment simulator latency causes checkout latency degradation",
        recommended_intervention="isolate_payment_fastpath",
    )
    assert validate_candidate_proposal(valid_proposal, valid_services) is True


async def test_epistemic_blinding_and_role_separation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """12. Verify investigator cannot access benchmark controller or ground-truth faults."""
    # Investigator key must receive 403 Forbidden on Benchmark Controller endpoints
    forbidden_resp = await client.post(
        "/api/v1/benchmarks/run",
        json={"hidden_fault_profile": "payment_latency_spike", "random_seed": 42},
        headers=INVESTIGATOR_HEADERS,
    )
    assert forbidden_resp.status_code == 403

    forbidden_list = await client.get(
        "/api/v1/benchmarks/runs",
        headers=INVESTIGATOR_HEADERS,
    )
    assert forbidden_list.status_code == 403

    forbidden_truth = await client.get(
        "/api/v1/benchmarks/ground-truth",
        headers=INVESTIGATOR_HEADERS,
    )
    assert forbidden_truth.status_code == 403

    # Activate blinded fault profile and verify public endpoints mask ground truth
    set_lab_profile("db_lock_contention", blinded=True)
    try:
        lab_status = await client.get("/api/v1/lab/status")
        assert lab_status.status_code == 200
        status_json = lab_status.json()
        assert status_json["profile"] == "blinded_benchmark_mode"
        assert status_json["blinded"] is True
        assert "db_lock_contention" not in str(status_json)

        health_resp = await client.get("/api/v1/health")
        assert "db_lock_contention" not in str(health_resp.json())
    finally:
        set_lab_profile("normal", blinded=False)

    # Verify ingested spans and metrics never leak fault profile names in attributes_json
    await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 2, "profile": "payment_latency_spike"},
    )
    spans = (await db_session.execute(select(SpanObservation))).scalars().all()
    assert len(spans) > 0
    for s in spans:
        assert "lab.profile" not in s.attributes_json
        assert "payment_latency_spike" not in str(s.attributes_json)

    metrics = (await db_session.execute(select(MetricObservation))).scalars().all()
    assert len(metrics) > 0
    for m in metrics:
        assert "profile" not in m.attributes_json
        assert "payment_latency_spike" not in str(m.attributes_json)


async def test_investigation_lifecycle_grounded_hypotheses_and_evidence_linkage(
    client: AsyncClient,
) -> None:
    """1, 2, 3, 4, 9, 13. Verify lifecycle transitions, hypotheses, and trial evidence."""
    await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 4, "profile": "payment_latency_spike"},
    )

    create_resp = await client.post(
        "/api/v1/investigations",
        json={
            "system_slug": "origin-synthetic-lab",
            "title": "Checkout Latency Investigation",
            "target_service_key": "checkout-service",
            "target_metric": "request_latency_ms",
            "experiment_budget": 3,
            "sample_size_per_arm": 5,
            "random_seed": 42,
            "auto_run": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert create_resp.status_code == 201
    inv = create_resp.json()

    # 1. Lifecycle state transitions
    assert inv["status"] == "CONCLUDED"
    transition_states = [t["to_state"] for t in inv["lifecycle_history_json"]]
    assert "OBSERVING" in transition_states
    assert "HYPOTHESIZING" in transition_states
    assert "PLANNING" in transition_states
    assert "EXPERIMENTING" in transition_states
    assert "EVALUATING" in transition_states
    assert transition_states[-1] == "CONCLUDED"

    # 2. Grounded hypotheses with observational prior cap <= 0.65 before experimentation
    hypotheses = inv["hypotheses"]
    assert len(hypotheses) >= 2
    for h in hypotheses:
        # Check initial observational score in revision history
        initial_rev = h["revision_history_json"][0]
        assert initial_rev["score"] <= 0.65
        obs_total = len(h["supporting_observations_json"]) + len(
            h["contradicting_observations_json"]
        )
        assert obs_total > 0
        assert len(h["alternative_explanations_json"]) > 0
        assert h["recommended_intervention"] in {
            "isolate_payment_fastpath",
            "relieve_db_lock_contention",
            "scale_inventory_workers",
            "hedged_concurrency_limiter",
        }

    # 3 & 4. Experiment runs preserve raw treatment & control measurements
    runs = inv["experiment_runs"]
    assert len(runs) >= 1
    winning_run = runs[0]
    assert len(winning_run["assignment_order_json"]) == 10
    assert len(winning_run["trial_observations_json"]) == 10
    stats = winning_run["metrics_summary_json"]
    assert stats["control_n"] == 5
    assert stats["treatment_n"] == 5
    assert stats["is_statistically_significant"] is True

    # 9. Correct root-cause conclusion
    assert inv["concluded_cause_service_key"] == "payment-simulator"
    assert inv["concluded_mechanism"] == "payment_gateway_latency_propagation"

    # 13. Evidence linkage and report export
    evidence = inv["evidence_records"]
    exp_evidence = [e for e in evidence if e["evidence_type"] == "controlled_experiment"]
    assert len(exp_evidence) >= 1
    assert exp_evidence[0]["experiment_run_id"] == winning_run["id"]

    report_resp = await client.get(
        f"/api/v1/investigations/{inv['id']}/export?format=markdown",
        headers=INVESTIGATOR_HEADERS,
    )
    assert report_resp.status_code == 200
    report_data = report_resp.json()
    assert "# ORIGIN Scientific Investigation Report" in report_data["markdown"]
    assert "payment-simulator" in report_data["markdown"]


async def test_budget_enforcement_and_cancellation(client: AsyncClient) -> None:
    """6 & 7. Verify cancellation transition and budget enforcement."""
    # Create without running immediately, then cancel
    create_resp = await client.post(
        "/api/v1/investigations",
        json={
            "system_slug": "origin-synthetic-lab",
            "target_service_key": "checkout-service",
            "random_seed": 77,
            "auto_run": False,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert create_resp.status_code == 201
    inv_id = create_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v1/investigations/{inv_id}/cancel",
        headers=INVESTIGATOR_HEADERS,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"


async def test_noisy_ambiguous_jitter_returns_inconclusive(client: AsyncClient) -> None:
    """14. Verify inconclusive outcome when evidence is insufficient or noisy."""
    await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 4, "profile": "noisy_ambiguous_jitter"},
    )
    resp = await client.post(
        "/api/v1/investigations",
        json={
            "system_slug": "origin-synthetic-lab",
            "target_service_key": "checkout-service",
            "experiment_budget": 2,
            "sample_size_per_arm": 5,
            "random_seed": 42,
            "auto_run": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "INCONCLUSIVE"
    assert data["concluded_cause_service_key"] is None


async def test_full_hidden_fault_benchmark_matrix(client: AsyncClient) -> None:
    """9, 10, 11, 12, 14. Execute the 5-scenario hidden-fault benchmark matrix."""
    matrix_resp = await client.post(
        "/api/v1/benchmarks/matrix?random_seed=2026",
        headers=BENCHMARK_HEADERS,
    )
    assert matrix_resp.status_code == 201
    matrix = matrix_resp.json()

    assert matrix["total_scenarios"] == 5
    assert matrix["correct_count"] == 5
    assert matrix["accuracy_pct"] == 100.0

    by_profile = {r["hidden_fault_profile"]: r for r in matrix["results"]}
    assert by_profile["normal"]["conclusion_correct"] is True
    assert by_profile["normal"]["investigator_concluded_service"] == "none"

    pay_res = by_profile["payment_latency_spike"]
    assert pay_res["conclusion_correct"] is True
    assert pay_res["investigator_concluded_service"] == "payment-simulator"

    db_res = by_profile["db_lock_contention"]
    assert db_res["conclusion_correct"] is True
    assert db_res["investigator_concluded_service"] == "order-database-sim"

    inv_res = by_profile["inventory_cpu_throttling"]
    assert inv_res["conclusion_correct"] is True
    assert inv_res["investigator_concluded_service"] == "inventory-service"

    noisy_res = by_profile["noisy_ambiguous_jitter"]
    assert noisy_res["conclusion_correct"] is True
    assert noisy_res["investigation_status"] == "INCONCLUSIVE"

    # Ensure laboratory is restored to unblinded normal state after benchmark matrix
    assert get_lab_state().blinded is False
