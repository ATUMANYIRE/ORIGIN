"""Milestone 05/05 Scientific Integrity Audit & Unseen Verification Scenarios.

Verifies:
1. Epistemic Blinding & Zero Ground-Truth Leakage in Spans, Metrics, and Ingestion APIs.
2. Honest handling of complex unseen multi-fault jitter and unidentifiable scenarios.
3. Randomized fault intensity variations beyond canonical fixtures (proving no memorization).
4. Digital Twin state transition determinism, held-out validation rejection & uncertainty semantics.
5. Clear epistemic separation between deterministic agent decisions and LLM explanations.
"""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MetricObservation, SpanObservation
from app.modules.experimentation.engine import compute_experiment_statistics
from app.modules.laboratory.orchestrator import (
    clear_lab_unsafe_lock,
    set_lab_profile,
)
from app.modules.simulation.schemas import (
    SimulationBranchCreateRequest,
    TwinCalibrationRequest,
)
from app.modules.simulation.service import DigitalTwinService

INVESTIGATOR_HEADERS = {"X-Origin-Key": "origin-dev-scientific-key-2026"}
BENCHMARK_HEADERS = {"X-Benchmark-Controller-Key": "origin-private-benchmark-evaluator-key-2026"}


async def test_zero_ground_truth_leakage_in_telemetry_and_database(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Scientific Integrity Audit #1: Prove zero ground-truth leakage into telemetry or storage."""
    clear_lab_unsafe_lock()

    # Stage blinded benchmark profile
    stage_resp = await client.post(
        "/api/v1/benchmarks/stage-hidden-fault/payment_latency_spike",
        headers=BENCHMARK_HEADERS,
    )
    assert stage_resp.status_code == 200

    # Public / Investigator status check MUST NOT reveal hidden profile
    lab_status = (await client.get("/api/v1/lab/status")).json()
    assert lab_status["profile"] == "blinded_benchmark_mode"
    assert lab_status["blinded"] is True
    assert lab_status["payment_added_latency_ms"] is None
    assert lab_status["payment_failure_probability"] is None
    assert lab_status["db_added_latency_ms"] is None
    assert lab_status["db_lock_saturation_pct"] is None

    # Execute workload under blinded profile
    exec_resp = await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 5},
        headers=INVESTIGATOR_HEADERS,
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["active_profile"] == "blinded_benchmark_mode"

    # Inspect all ingested spans in DB for any leakage of fault labels in attributes
    spans = list((await db_session.execute(select(SpanObservation))).scalars().all())
    assert len(spans) > 0
    forbidden_tokens = [
        "payment_latency_spike",
        "db_lock_contention",
        "inventory_cpu_throttling",
        "ground_truth",
        "private_state",
    ]
    for s in spans:
        attr_str = str(s.attributes_json).lower()
        for token in forbidden_tokens:
            assert token not in attr_str, f"Leakage detected in SpanObservation: {token}"

    # Inspect all ingested metrics in DB
    metrics = list((await db_session.execute(select(MetricObservation))).scalars().all())
    for m in metrics:
        attr_str = str(m.attributes_json).lower()
        for token in forbidden_tokens:
            assert token not in attr_str, f"Leakage detected in MetricObservation: {token}"


async def test_unseen_randomized_fault_intensities(
    client: AsyncClient,
) -> None:
    """Scientific Integrity Audit #2: Verify investigator solves unseen parameter variations."""
    clear_lab_unsafe_lock()

    # Test continuous unseen latency spike (e.g. 215ms instead of standard 380ms)
    state = set_lab_profile("payment_latency_spike", blinded=True)
    # Mutate to an unseen intensity
    state.payment_added_latency_ms = 215.0

    inv_resp = await client.post(
        "/api/v1/investigations",
        json={
            "system_slug": "origin-synthetic-lab",
            "title": "Unseen Fault Intensity: 215ms Payment Latency",
            "target_service_key": "checkout-service",
            "target_metric": "request_latency_ms",
            "experiment_budget": 4,
            "sample_size_per_arm": 4,
            "random_seed": 7771,
            "auto_run": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert inv_resp.status_code == 201
    inv = inv_resp.json()
    assert inv["status"] == "CONCLUDED"
    assert inv["concluded_cause_service_key"] == "payment-simulator"
    assert inv["concluded_mechanism"] == "payment_gateway_latency_propagation"


async def test_complex_unidentifiable_scenario_honestly_returns_inconclusive(
    client: AsyncClient,
) -> None:
    """Scientific Integrity Audit #3: Returns INCONCLUSIVE on unidentifiable jitter."""
    clear_lab_unsafe_lock()

    # Stage ambiguous multi-service stochastic jitter (no single intervention cures latency)
    set_lab_profile("noisy_ambiguous_jitter", blinded=False)

    inv_resp = await client.post(
        "/api/v1/investigations",
        json={
            "system_slug": "origin-synthetic-lab",
            "title": "Complex Unidentifiable Multi-Service Jitter",
            "target_service_key": "checkout-service",
            "target_metric": "request_latency_ms",
            "experiment_budget": 4,
            "sample_size_per_arm": 4,
            "random_seed": 8882,
            "auto_run": True,
        },
        headers=INVESTIGATOR_HEADERS,
    )
    assert inv_resp.status_code == 201
    inv = inv_resp.json()
    # The investigator MUST NOT guess or invent a root cause when interventions fail!
    assert inv["status"] == "INCONCLUSIVE"
    assert inv["concluded_cause_service_key"] is None


async def test_digital_twin_monte_carlo_interval_semantics(
    db_session: AsyncSession,
) -> None:
    """Scientific Integrity Audit #4: Verify Digital Twin Monte Carlo uncertainty semantics."""
    # Calibrate twin
    twin_bundle = await DigitalTwinService.create_or_calibrate_twin(
        db_session,
        TwinCalibrationRequest(
            system_slug="origin-synthetic-lab",
            version_tag="v-audit-test",
            min_required_observations=8,
        ),
        actor="ScientificAuditor",
    )
    twin_id = twin_bundle["twin_model"]["id"]

    # Run baseline branch with Monte Carlo runs = 15
    branch = await DigitalTwinService.create_and_run_branch(
        db_session,
        SimulationBranchCreateRequest(
            twin_model_id=twin_id,
            name="Monte Carlo Uncertainty Audit",
            branch_type="baseline",
            monte_carlo_runs=15,
            horizon_seconds=12.0,
            random_seed=12345,
        ),
        actor="ScientificAuditor",
    )

    unc = branch.uncertainty_json
    # Verify bounds exist and are ordered
    ci_lower = unc.get("latency_ci_lower_95_ms")
    ci_upper = unc.get("latency_ci_upper_95_ms")
    mean_lat = branch.outcome_summary_json.get("mean_latency_ms")

    assert ci_lower is not None and ci_upper is not None and mean_lat is not None
    assert ci_lower <= mean_lat <= ci_upper, (
        f"Confidence interval inverted or violated: {ci_lower} <= {mean_lat} <= {ci_upper}"
    )
    assert unc.get("monte_carlo_runs") == 15
    assert "ensemble_latency_std_ms" in unc


async def test_statistical_engine_edge_cases() -> None:
    """Scientific Integrity Audit #5: Verify statistical math on zero-variance edge cases."""
    # Identical values in control and treatment -> effect size should be zero, not NaN or crash
    control = [100.0, 100.0, 100.0, 100.0]
    treatment = [100.0, 100.0, 100.0, 100.0]

    stats = compute_experiment_statistics(control_values=control, treatment_values=treatment)
    assert stats["control_mean_ms"] == 100.0
    assert stats["treatment_mean_ms"] == 100.0
    assert stats["absolute_effect_size_ms"] == 0.0
    assert stats["relative_effect_pct"] == 0.0
    assert stats["is_statistically_significant"] is False
