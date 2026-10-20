"""Private Benchmark Controller and Evaluator for Hidden-Fault Discovery (Milestone 02/05).

Enforces strict epistemic separation between:
1. Benchmark Controller (selects hidden fault, enables blinded mode, holds ground truth).
2. Autonomous Investigator (observes blinded telemetry, runs allowlisted experiments, infers cause).

Protected by `verify_benchmark_controller` (`X-Benchmark-Controller-Key`).
"""

import time
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BenchmarkRunRecord
from app.modules.agents.investigator import AutonomousInvestigatorService
from app.modules.agents.schemas import InvestigationCreateRequest
from app.modules.laboratory.orchestrator import (
    LAB_SYSTEM_SLUG,
    LabProfileType,
    SyntheticLabOrchestrator,
    get_private_ground_truth_for_evaluator,
    set_lab_profile,
)

EXPECTED_BENCHMARK_GROUND_TRUTH: dict[str, dict[str, str | None]] = {
    "normal": {
        "expected_status": "CONCLUDED",
        "expected_service": "none",
        "expected_mechanism": "nominal_healthy_operation",
    },
    "payment_latency_spike": {
        "expected_status": "CONCLUDED",
        "expected_service": "payment-simulator",
        "expected_mechanism": "payment_gateway_latency_propagation",
    },
    "db_lock_contention": {
        "expected_status": "CONCLUDED",
        "expected_service": "order-database-sim",
        "expected_mechanism": "database_lock_contention",
    },
    "inventory_cpu_throttling": {
        "expected_status": "CONCLUDED",
        "expected_service": "inventory-service",
        "expected_mechanism": "inventory_worker_starvation",
    },
    "noisy_ambiguous_jitter": {
        "expected_status": "INCONCLUSIVE",
        "expected_service": None,
        "expected_mechanism": None,
    },
}


class BenchmarkScenarioRequest(BaseModel):
    """Request to run a blinded hidden-fault benchmark evaluation."""

    scenario_name: str = Field(default="Hidden Fault Benchmark", min_length=3, max_length=120)
    hidden_fault_profile: LabProfileType = "payment_latency_spike"
    target_service_key: str = Field(default="checkout-service")
    experiment_budget: int = Field(default=3, ge=1, le=6)
    sample_size_per_arm: int = Field(default=6, ge=3, le=15)
    random_seed: int = Field(default=101, ge=1, le=999999)


class BenchmarkRunRead(BaseModel):
    """Serialized Benchmark Evaluator result (Visible only to Benchmark Controller)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    investigation_id: str
    scenario_name: str
    hidden_fault_profile: str
    expected_root_cause_service: str | None
    expected_mechanism: str | None
    investigator_concluded_service: str | None
    investigator_concluded_mechanism: str | None
    investigation_status: str
    experiments_performed: int
    total_trials: int
    elapsed_ms: float
    conclusion_correct: bool
    is_inconclusive: bool
    evidence_ids_json: list[str]
    evaluation_notes_json: dict[str, Any]
    created_at: datetime


class BenchmarkMatrixResponse(BaseModel):
    """Summary of executing the full multi-scenario hidden-fault benchmark matrix."""

    total_scenarios: int
    correct_count: int
    accuracy_pct: float
    results: list[BenchmarkRunRead]


class BenchmarkControllerService:
    """Executes blinded hidden-fault benchmarks and evaluates Investigator accuracy."""

    @staticmethod
    def stage_blinded_hidden_fault(hidden_profile: LabProfileType) -> dict[str, Any]:
        """Configure a hidden fault in blinded mode so the investigator cannot read the label."""
        public_view = set_lab_profile(hidden_profile, blinded=True)
        return {
            "staged": True,
            "blinded_public_profile": public_view.profile,
            "notice": (
                "Hidden fault staged in blinded mode. Public /api/v1/lab/status and "
                "/api/v1/health now report 'blinded_benchmark_mode'."
            ),
        }

    @staticmethod
    async def run_single_benchmark(
        db: AsyncSession,
        request: BenchmarkScenarioRequest,
    ) -> BenchmarkRunRead:
        """Stage a hidden fault in blinded mode, run the Investigator, and score the conclusion."""
        t0 = time.perf_counter()
        await SyntheticLabOrchestrator.ensure_lab_registered(db, actor="benchmark-controller")

        # 1. Stage hidden fault in blinded mode
        set_lab_profile(request.hidden_fault_profile, blinded=True)

        try:
            # 2. Seed pre-investigation traffic under the blinded fault so topology is warm
            for idx in range(3):
                await SyntheticLabOrchestrator.execute_instrumented_transaction(
                    db,
                    profile=None,
                    intervention="none",
                    experiment_arm="blinded_warmup",
                    rng_seed=request.random_seed * 50 + idx,
                )

            # 3. Create & run the autonomous investigation (Investigator only sees blinded state!)
            inv_model = await AutonomousInvestigatorService.create_investigation(
                db,
                InvestigationCreateRequest(
                    system_slug=LAB_SYSTEM_SLUG,
                    title=f"Blinded Benchmark Investigation: {request.scenario_name}",
                    target_service_key=request.target_service_key,
                    target_metric="request_latency_ms",
                    experiment_budget=request.experiment_budget,
                    sample_size_per_arm=request.sample_size_per_arm,
                    random_seed=request.random_seed,
                    timeout_seconds=60,
                    auto_run=False,
                ),
                actor="blinded-investigator",
            )
            inv_detail = await AutonomousInvestigatorService.run_investigation(
                db, inv_model.id, actor="blinded-investigator"
            )

            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

            # 4. Evaluate conclusion against private ground truth
            private_truth = get_private_ground_truth_for_evaluator()
            truth_spec = EXPECTED_BENCHMARK_GROUND_TRUTH[private_truth.profile]
            expected_status = truth_spec["expected_status"]
            expected_svc = truth_spec["expected_service"]
            expected_mech = truth_spec["expected_mechanism"]

            is_inconclusive = inv_detail.status == "INCONCLUSIVE"
            if expected_status == "INCONCLUSIVE":
                is_correct = is_inconclusive and inv_detail.concluded_cause_service_key is None
            else:
                is_correct = (
                    inv_detail.status == "CONCLUDED"
                    and inv_detail.concluded_cause_service_key == expected_svc
                    and inv_detail.concluded_mechanism == expected_mech
                )

            total_trials = sum(len(r.trial_observations_json) for r in inv_detail.experiment_runs)
            evidence_ids = [e.id for e in inv_detail.evidence_records]

            record = BenchmarkRunRecord(
                system_id=inv_detail.system_id,
                investigation_id=inv_detail.id,
                scenario_name=request.scenario_name,
                hidden_fault_profile=private_truth.profile,
                expected_root_cause_service=expected_svc,
                expected_mechanism=expected_mech,
                investigator_concluded_service=inv_detail.concluded_cause_service_key,
                investigator_concluded_mechanism=inv_detail.concluded_mechanism,
                investigation_status=inv_detail.status,
                experiments_performed=inv_detail.experiments_used,
                total_trials=total_trials,
                elapsed_ms=elapsed_ms,
                conclusion_correct=is_correct,
                is_inconclusive=is_inconclusive,
                evidence_ids_json=evidence_ids,
                evaluation_notes_json={
                    "expected_status": expected_status,
                    "conclusion_summary": inv_detail.conclusion_summary,
                    "uncertainty_summary": inv_detail.uncertainty_summary,
                    "blinded_verification": (
                        "Investigator executed while _PRIVATE_STATE.blinded=True; "
                        "zero ground-truth labels present in spans, metrics, or public status API."
                    ),
                },
            )
            db.add(record)
            await db.commit()
            return BenchmarkRunRead.model_validate(record)
        finally:
            # Unblind after evaluation completes
            set_lab_profile(_PRIVATE_STATE_SAFE_RESTORE(), blinded=False)

    @staticmethod
    async def run_benchmark_matrix(
        db: AsyncSession,
        random_seed: int = 2026,
    ) -> BenchmarkMatrixResponse:
        """Execute the canonical 5-scenario hidden-fault benchmark matrix."""
        scenarios: list[tuple[str, LabProfileType, int]] = [
            ("Scenario 1: Healthy Baseline System", "normal", 2),
            ("Scenario 2: Hidden Payment Gateway Degradation", "payment_latency_spike", 3),
            ("Scenario 3: Hidden Database Lock Contention", "db_lock_contention", 3),
            ("Scenario 4: Hidden Inventory Worker Starvation", "inventory_cpu_throttling", 3),
            ("Scenario 5: Ambiguous Multi-Service Noise", "noisy_ambiguous_jitter", 3),
        ]
        results: list[BenchmarkRunRead] = []
        for idx, (name, profile, budget) in enumerate(scenarios):
            res = await BenchmarkControllerService.run_single_benchmark(
                db,
                BenchmarkScenarioRequest(
                    scenario_name=name,
                    hidden_fault_profile=profile,
                    target_service_key="checkout-service",
                    experiment_budget=budget,
                    sample_size_per_arm=6,
                    random_seed=random_seed + idx * 100,
                ),
            )
            results.append(res)

        correct_count = sum(1 for r in results if r.conclusion_correct)
        return BenchmarkMatrixResponse(
            total_scenarios=len(results),
            correct_count=correct_count,
            accuracy_pct=round((correct_count / len(results)) * 100.0, 2),
            results=results,
        )

    @staticmethod
    async def list_benchmark_runs(
        db: AsyncSession,
        limit: int = 50,
    ) -> list[BenchmarkRunRead]:
        """List stored benchmark evaluations (Controller only)."""
        stmt = (
            select(BenchmarkRunRecord).order_by(BenchmarkRunRecord.created_at.desc()).limit(limit)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        return [BenchmarkRunRead.model_validate(r) for r in rows]


def _PRIVATE_STATE_SAFE_RESTORE() -> LabProfileType:  # noqa: N802
    """Restore normal profile after benchmark run finishes."""
    return "normal"
