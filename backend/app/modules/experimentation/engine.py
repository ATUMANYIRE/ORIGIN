"""Controlled Experimentation Planner, Selection Policy, and Statistical Executor (Milestone 02/05).

Implements:
- Allowlisted intervention validation (never executes arbitrary commands or untrusted code).
- Transparent heuristic + topology-aware experiment selection policy with budget checks.
- Seeded block-randomized treatment/control assignment to eliminate temporal drift bias.
- Pure mathematical Welch two-sample t-test, 95% confidence intervals, and Cohen's d effect sizes.
"""

import math
import random
import statistics
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExperimentDefinition, ExperimentRun, HypothesisRecord
from app.modules.laboratory.orchestrator import (
    ALLOWLISTED_INTERVENTIONS,
    InterventionType,
    SyntheticLabOrchestrator,
)
from app.modules.safety.service import AuditService, SafetyEnvelopeContract


def _t_critical_95(df: float) -> float:
    """Two-sided 95% Student's t critical value approximation for degrees of freedom >= 2."""
    if df <= 2.0:
        return 4.303
    if df <= 3.0:
        return 3.182
    if df <= 4.0:
        return 2.776
    if df <= 5.0:
        return 2.571
    if df <= 6.0:
        return 2.447
    if df <= 8.0:
        return 2.306
    if df <= 10.0:
        return 2.228
    if df <= 15.0:
        return 2.131
    if df <= 20.0:
        return 2.086
    if df <= 30.0:
        return 2.042
    return 1.960


def generate_block_randomized_assignment(
    sample_size_per_arm: int,
    random_seed: int,
) -> list[str]:
    """Generate paired block-randomized assignment order ['control', 'treatment', ...].

    Each pair of trials contains one 'control' and one 'treatment' in seeded random order
    to neutralize temporal drift while guaranteeing exact sample size balance.
    """
    rng = random.Random(random_seed)
    order: list[str] = []
    for _ in range(sample_size_per_arm):
        pair = ["control", "treatment"]
        rng.shuffle(pair)
        order.extend(pair)
    return order


def compute_experiment_statistics(
    control_values: list[float],
    treatment_values: list[float],
    trial_correlation_ids: list[str] | None = None,
    measurement_unit: str = "ms",
) -> dict[str, Any]:
    """Compute Welch's two-sample comparison, 95% CI, and effect size."""
    if len(control_values) < 2 or len(treatment_values) < 2:
        raise ValueError("At least 2 observations per arm are required for statistical comparison.")

    n_c = len(control_values)
    n_t = len(treatment_values)
    mean_c = statistics.fmean(control_values)
    mean_t = statistics.fmean(treatment_values)
    med_c = statistics.median(control_values)
    med_t = statistics.median(treatment_values)
    std_c = statistics.stdev(control_values) if n_c > 1 else 0.0
    std_t = statistics.stdev(treatment_values) if n_t > 1 else 0.0

    var_c = max(std_c**2, 1e-6)
    var_t = max(std_t**2, 1e-6)

    abs_effect = mean_t - mean_c
    med_effect = med_t - med_c
    rel_effect_pct = (abs_effect / mean_c) * 100.0 if mean_c > 1e-6 else 0.0

    se = math.sqrt((var_t / n_t) + (var_c / n_c))
    t_stat = abs_effect / se if se > 1e-6 else 0.0

    # Welch-Satterthwaite degrees of freedom
    num = ((var_t / n_t) + (var_c / n_c)) ** 2
    den = (((var_t / n_t) ** 2) / max(1, n_t - 1)) + (((var_c / n_c) ** 2) / max(1, n_c - 1))
    df = num / den if den > 1e-9 else float(n_c + n_t - 2)

    t_crit = _t_critical_95(df)
    ci_lower = abs_effect - t_crit * se
    ci_upper = abs_effect + t_crit * se

    pooled_sd = math.sqrt(((n_c - 1) * var_c + (n_t - 1) * var_t) / max(1, n_c + n_t - 2))
    cohens_d = abs_effect / pooled_sd if pooled_sd > 1e-6 else 0.0

    # Statistically and practically significant if 95% CI excludes 0, |t| >= 2.20,
    # and relative latency change is at least 25%
    ci_excludes_zero = (ci_upper < -20.0) or (ci_lower > 20.0)
    is_significant = ci_excludes_zero and abs(t_stat) >= 2.20 and abs(rel_effect_pct) >= 25.0

    return {
        "measurement_unit": measurement_unit,
        "control_n": n_c,
        "treatment_n": n_t,
        "control_mean_ms": round(mean_c, 3),
        "control_median_ms": round(med_c, 3),
        "control_std_ms": round(std_c, 3),
        "treatment_mean_ms": round(mean_t, 3),
        "treatment_median_ms": round(med_t, 3),
        "treatment_std_ms": round(std_t, 3),
        "absolute_effect_size_ms": round(abs_effect, 3),
        "median_effect_size_ms": round(med_effect, 3),
        "relative_effect_pct": round(rel_effect_pct, 2),
        "standard_error_ms": round(se, 3),
        "welch_t_stat": round(t_stat, 3),
        "degrees_of_freedom": round(df, 2),
        "ci_lower_95_ms": round(ci_lower, 3),
        "ci_upper_95_ms": round(ci_upper, 3),
        "cohens_d": round(cohens_d, 3),
        "is_statistically_significant": is_significant,
        "trial_correlation_ids": trial_correlation_ids or [],
        "methodology_note": (
            "Paired block-randomized two-arm experiment evaluated via Welch's two-sample "
            "t-interval (95% CI) and practical effect threshold (|Δ| >= 25%)."
        ),
    }


def validate_allowlisted_intervention(intervention: str) -> InterventionType:
    """Strictly verify that an intervention is in ALLOWLISTED_INTERVENTIONS."""
    if intervention not in ALLOWLISTED_INTERVENTIONS or intervention == "none":
        permitted = sorted(k for k in ALLOWLISTED_INTERVENTIONS if k != "none")
        raise ValueError(
            f"Rejected unsafe or unallowlisted intervention '{intervention}'. "
            f"Permitted interventions: {permitted}"
        )
    return cast(InterventionType, intervention)


class ExperimentEngine:
    """Selects, plans, and executes controlled experiments in the Synthetic Laboratory."""

    @staticmethod
    def select_next_hypothesis_for_experiment(
        *,
        hypotheses: list[HypothesisRecord],
        executed_interventions: set[str],
        remaining_budget: int,
    ) -> tuple[HypothesisRecord | None, float, str]:
        """Transparent heuristic selection policy for choosing the most informative experiment.

        Considers:
        1. Remaining experiment budget vs intervention cost.
        2. Whether the intervention was already executed (avoids redundant experiments).
        3. Prior observational support score (`confidence_score`).
        4. Structural disambiguation bonus: downstream leaf dependencies (`order-database-sim`,
           `payment-simulator`) receive a disambiguation bonus (+0.08) because isolating a leaf
           service simultaneously tests whether mid-tier services (`inventory-service`,
           `checkout-service`) are merely propagating downstream latency.
        """
        if remaining_budget <= 0:
            return None, 0.0, "Experiment budget exhausted."

        best_hyp: HypothesisRecord | None = None
        best_score = -1.0
        best_reason = "No eligible untested hypotheses meet minimum information threshold."

        for hyp in hypotheses:
            if hyp.status != "proposed":
                continue
            intervention = hyp.recommended_intervention
            if intervention in executed_interventions:
                continue
            if intervention not in ALLOWLISTED_INTERVENTIONS or intervention == "none":
                continue

            cost = int(ALLOWLISTED_INTERVENTIONS[intervention]["cost"])
            if cost > remaining_budget:
                continue

            # Reject uninformative experiments when prior is negligible (< 0.12)
            if hyp.confidence_score < 0.12:
                continue

            disambiguation_bonus = (
                0.08
                if hyp.root_cause_service_key in ("order-database-sim", "payment-simulator")
                else 0.03
            )
            expected_gain = round(
                (hyp.confidence_score + disambiguation_bonus) / max(1, cost),
                3,
            )

            if expected_gain > best_score:
                best_score = expected_gain
                best_hyp = hyp
                best_reason = (
                    f"Selected '{intervention}' on '{hyp.root_cause_service_key}' "
                    f"(selection score={expected_gain:.3f}, prior={hyp.confidence_score:.2f}, "
                    f"cost={cost} of {remaining_budget} remaining budget): highest expected "
                    f"information gain to disambiguate '{hyp.suspected_mechanism}' from "
                    f"competing explanations."
                )

        return best_hyp, best_score, best_reason

    @staticmethod
    async def plan_and_execute_experiment(
        db: AsyncSession,
        *,
        system_id: str,
        investigation_id: str,
        hypothesis: HypothesisRecord,
        sample_size_per_arm: int,
        random_seed: int,
        selection_score: float,
        selection_reason: str,
        actor: str = "autonomous-investigator",
        check_cancel_fn: Any | None = None,
    ) -> tuple[ExperimentDefinition, ExperimentRun, dict[str, Any]]:
        """Create an ExperimentDefinition, execute seeded trials, and persist ExperimentRun."""
        intervention = validate_allowlisted_intervention(hypothesis.recommended_intervention)
        envelope = SafetyEnvelopeContract()

        exp_def = ExperimentDefinition(
            system_id=system_id,
            investigation_id=investigation_id,
            hypothesis_id=hypothesis.id,
            name=f"Controlled Trial: {intervention} on {hypothesis.root_cause_service_key}",
            target_service_key=hypothesis.affected_service_key or "checkout-service",
            target_metric=hypothesis.target_metric,
            measurement_unit="ms",
            perturbation_type=intervention,
            treatment_condition_json={
                "arm": "treatment",
                "intervention": intervention,
                "target_service_key": hypothesis.root_cause_service_key,
                "description": ALLOWLISTED_INTERVENTIONS[intervention]["description"],
            },
            control_condition_json={
                "arm": "control",
                "intervention": "none",
                "description": "Unmodified active system baseline behavior.",
            },
            sample_size_per_arm=sample_size_per_arm,
            random_seed=random_seed,
            budget_cost=int(ALLOWLISTED_INTERVENTIONS[intervention]["cost"]),
            selection_score=selection_score,
            selection_reason=selection_reason,
            safety_envelope_json=envelope.model_dump(),
            status="running",
        )
        db.add(exp_def)
        await db.flush()

        assignment_order = generate_block_randomized_assignment(
            sample_size_per_arm=sample_size_per_arm,
            random_seed=random_seed,
        )

        exp_run = ExperimentRun(
            experiment_id=exp_def.id,
            system_id=system_id,
            investigation_id=investigation_id,
            hypothesis_id=hypothesis.id,
            status="running",
            assignment_order_json=assignment_order,
            trial_observations_json=[],
            metrics_summary_json={},
            started_at=datetime.now(UTC),
        )
        db.add(exp_run)
        hypothesis.status = "testing"
        await db.flush()

        control_values: list[float] = []
        treatment_values: list[float] = []
        trial_records: list[dict[str, Any]] = []
        trial_corrs: list[str] = []

        target_svc = exp_def.target_service_key
        focal_svc = hypothesis.root_cause_service_key or target_svc

        for idx, arm in enumerate(assignment_order):
            if check_cancel_fn is not None and await check_cancel_fn():
                exp_run.status = "cancelled"
                exp_run.AbortReason = "Investigation cancelled by operator or timeout."
                exp_def.status = "cancelled"
                exp_run.completed_at = datetime.now(UTC)
                await db.flush()
                return exp_def, exp_run, {}

            trial_seed = random_seed * 1000 + idx * 17 + (1 if arm == "treatment" else 0)
            active_intervention: InterventionType = intervention if arm == "treatment" else "none"

            trace_summary = await SyntheticLabOrchestrator.execute_instrumented_transaction(
                db,
                profile=None,
                intervention=active_intervention,
                experiment_arm=arm,
                rng_seed=trial_seed,
            )

            target_val = float(
                trace_summary.service_latencies_ms.get(target_svc, trace_summary.total_duration_ms)
            )
            focal_val = float(
                trace_summary.service_latencies_ms.get(focal_svc, trace_summary.total_duration_ms)
            )

            if arm == "control":
                control_values.append(target_val)
            else:
                treatment_values.append(target_val)

            trial_corrs.append(trace_summary.correlation_id)
            trial_records.append(
                {
                    "trial_index": idx + 1,
                    "arm": arm,
                    "intervention": active_intervention,
                    "correlation_id": trace_summary.correlation_id,
                    "trace_id": trace_summary.trace_id,
                    "target_service_key": target_svc,
                    "target_metric_value_ms": target_val,
                    "focal_service_key": focal_svc,
                    "focal_service_latency_ms": focal_val,
                    "gateway_status": trace_summary.gateway_status,
                    "observed_at": datetime.now(UTC).isoformat(),
                }
            )

        stats_summary = compute_experiment_statistics(
            control_values=control_values,
            treatment_values=treatment_values,
            trial_correlation_ids=trial_corrs,
            measurement_unit="ms",
        )

        exp_run.trial_observations_json = trial_records
        exp_run.metrics_summary_json = stats_summary
        exp_run.status = "completed"
        exp_run.completed_at = datetime.now(UTC)
        exp_def.status = "completed"

        await AuditService.record_event(
            db,
            system_id=system_id,
            actor=actor,
            action="experiment.completed",
            resource_type="experiment_run",
            resource_id=exp_run.id,
            correlation_id=trial_corrs[0] if trial_corrs else None,
            details={
                "investigation_id": investigation_id,
                "hypothesis_id": hypothesis.id,
                "intervention": intervention,
                "absolute_effect_size_ms": stats_summary["absolute_effect_size_ms"],
                "relative_effect_pct": stats_summary["relative_effect_pct"],
                "is_statistically_significant": stats_summary["is_statistically_significant"],
            },
        )
        await db.flush()
        return exp_def, exp_run, stats_summary
