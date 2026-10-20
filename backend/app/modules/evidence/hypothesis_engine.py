"""Deterministic, evidence-driven Hypothesis Generation and Revision Engine (Milestone 02/05).

Uses real stored telemetry (SpanObservation, MetricObservation) and provenance-verified
topology (TopologyGraphResponse) to construct competing causal hypotheses.
Never treats observational correlation or model priors as statistical proof.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvidenceRecord, HypothesisRecord, SpanObservation
from app.modules.laboratory.orchestrator import ALLOWLISTED_INTERVENTIONS
from app.modules.topology.schemas import TopologyGraphResponse, TopologyNode

NOMINAL_SERVICE_LATENCY_MS: dict[str, float] = {
    "api-gateway": 115.0,
    "checkout-service": 100.0,
    "inventory-service": 35.0,
    "payment-simulator": 42.0,
    "order-database-sim": 20.0,
}


def find_downstream_reachable(
    target_service_key: str,
    graph: TopologyGraphResponse,
) -> set[str]:
    """Traverse verified/declared topology edges to find all downstream dependencies."""
    visited: set[str] = {target_service_key}
    queue: list[str] = [target_service_key]
    adj: dict[str, list[str]] = {}
    for edge in graph.edges:
        adj.setdefault(edge.source, []).append(edge.target)

    while queue:
        curr = queue.pop(0)
        for nxt in adj.get(curr, []):
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return visited


class HypothesisEngine:
    """Generates and updates falsifiable causal hypotheses from telemetry and experiments."""

    @staticmethod
    async def generate_competing_hypotheses(
        db: AsyncSession,
        *,
        system_id: str,
        investigation_id: str,
        target_service_key: str,
        target_metric: str,
        topology: TopologyGraphResponse,
    ) -> tuple[list[HypothesisRecord], list[EvidenceRecord]]:
        """Generate competing causal hypotheses grounded in real topology and telemetry."""
        now_iso = datetime.now(UTC).isoformat()
        reachable = find_downstream_reachable(target_service_key, topology)
        nodes_by_key: dict[str, TopologyNode] = {
            n.service_key: n for n in topology.nodes if n.service_key in reachable
        }

        # Fetch recent spans to link real correlation IDs to observational evidence
        recent_spans = list(
            (
                await db.execute(
                    select(SpanObservation)
                    .where(SpanObservation.system_id == system_id)
                    .order_by(SpanObservation.started_at.desc())
                    .limit(120)
                )
            )
            .scalars()
            .all()
        )
        corr_by_service: dict[str, list[str]] = {}
        local_compute_by_service: dict[str, list[float]] = {}
        for sp in recent_spans:
            c_list = corr_by_service.setdefault(sp.service_key, [])
            if sp.correlation_id not in c_list and len(c_list) < 6:
                c_list.append(sp.correlation_id)
            if "inventory.local_compute_ms" in sp.attributes_json:
                local_compute_by_service.setdefault(sp.service_key, []).append(
                    float(sp.attributes_json["inventory.local_compute_ms"])
                )

        hypotheses_created: list[HypothesisRecord] = []
        observational_evidence: list[EvidenceRecord] = []

        # Helper to build a hypothesis record and observational evidence
        async def _register_candidate(
            *,
            root_service: str,
            mechanism: str,
            statement: str,
            intervention: str,
            supporting: list[dict[str, Any]],
            contradicting: list[dict[str, Any]],
            alternatives: list[str],
            prior_score: float,
        ) -> None:
            if root_service not in nodes_by_key:
                return
            if intervention not in ALLOWLISTED_INTERVENTIONS:
                return

            bounded_prior = round(min(0.65, max(0.10, prior_score)), 3)
            interp = (
                f"Observational prior ({bounded_prior:.2f}, capped at 0.65 before experiment): "
                "derived from passive latency/saturation anomalies along the topology path. "
                "Requires a controlled intervention to establish or refute causality."
            )

            hyp = HypothesisRecord(
                system_id=system_id,
                investigation_id=investigation_id,
                statement=statement,
                suspected_mechanism=mechanism,
                root_cause_service_key=root_service,
                affected_service_key=target_service_key,
                target_metric=target_metric,
                recommended_intervention=intervention,
                supporting_observations_json=supporting,
                contradicting_observations_json=contradicting,
                expected_intervention_effect_json={
                    "intervention_type": intervention,
                    "target_service_key": root_service,
                    "target_metric": target_metric,
                    "expected_direction": "decrease",
                    "min_expected_reduction_pct": 25.0,
                    "rationale": ALLOWLISTED_INTERVENTIONS[intervention]["description"],
                },
                alternative_explanations_json=alternatives,
                confidence_score=bounded_prior,
                score_interpretation=interp,
                status="proposed",
                revision_history_json=[
                    {
                        "timestamp": now_iso,
                        "phase": "HYPOTHESIZING",
                        "status": "proposed",
                        "score": bounded_prior,
                        "reason": "Initial generation from baseline topology and span telemetry.",
                    }
                ],
            )
            db.add(hyp)
            await db.flush()
            hypotheses_created.append(hyp)

            corr_ids = corr_by_service.get(root_service, [])
            ev = EvidenceRecord(
                system_id=system_id,
                investigation_id=investigation_id,
                experiment_run_id=None,
                hypothesis_id=hyp.id,
                evidence_type="observational_correlation",
                direction="supporting" if supporting else "inconclusive",
                summary=(
                    f"Observational telemetry on {root_service} ({mechanism}): "
                    f"{len(supporting)} supporting / {len(contradicting)} contradicting signals."
                ),
                correlation_id=corr_ids[0] if corr_ids else None,
                effect_size=None,
                ci_lower=None,
                ci_upper=None,
                sample_size=len(corr_ids),
                artifact_payload_json={
                    "root_cause_service_key": root_service,
                    "supporting_observations": supporting,
                    "contradicting_observations": contradicting,
                    "correlation_ids": corr_ids,
                    "epistemic_warning": (
                        "Observational correlation only; confounded by shared upstream traffic "
                        "and cascading calls."
                    ),
                },
            )
            db.add(ev)
            await db.flush()
            observational_evidence.append(ev)

        # 1. Evaluate Payment Simulator hypothesis
        if "payment-simulator" in nodes_by_key:
            pay_node = nodes_by_key["payment-simulator"]
            pay_p95 = pay_node.metrics.p95_latency_ms or 0.0
            pay_err = pay_node.metrics.error_rate_pct
            pay_nom = NOMINAL_SERVICE_LATENCY_MS["payment-simulator"]
            supporting_pay: list[dict[str, Any]] = []
            contradicting_pay: list[dict[str, Any]] = []

            if pay_p95 > pay_nom * 2.2:
                supporting_pay.append(
                    {
                        "service_key": "payment-simulator",
                        "metric_name": "p95_latency_ms",
                        "observed_value": pay_p95,
                        "baseline_reference": pay_nom,
                        "correlation_ids": corr_by_service.get("payment-simulator", []),
                        "note": (
                            f"payment-simulator p95 latency ({pay_p95}ms) exceeds nominal "
                            f"baseline ({pay_nom}ms)."
                        ),
                    }
                )
            else:
                contradicting_pay.append(
                    {
                        "service_key": "payment-simulator",
                        "metric_name": "p95_latency_ms",
                        "observed_value": pay_p95,
                        "baseline_reference": pay_nom,
                        "correlation_ids": corr_by_service.get("payment-simulator", []),
                        "note": f"payment-simulator p95 latency ({pay_p95}ms) is near nominal.",
                    }
                )

            if pay_err > 0.0:
                supporting_pay.append(
                    {
                        "service_key": "payment-simulator",
                        "metric_name": "error_rate_pct",
                        "observed_value": pay_err,
                        "baseline_reference": 0.0,
                        "correlation_ids": corr_by_service.get("payment-simulator", []),
                        "note": f"payment-simulator exhibits {pay_err}% HTTP 5xx errors.",
                    }
                )

            prior_pay = (
                0.62
                if pay_p95 > 250.0
                else (0.42 if pay_p95 > pay_nom * 1.8 else 0.18)
            )
            await _register_candidate(
                root_service="payment-simulator",
                mechanism="payment_gateway_latency_propagation",
                statement=(
                    f"Payment service latency in 'payment-simulator' causes "
                    f"'{target_service_key}' degradation via synchronous authorization blocking."
                ),
                intervention="isolate_payment_fastpath",
                supporting=supporting_pay,
                contradicting=contradicting_pay,
                alternatives=[
                    "Database lock contention in order-database-sim delaying order commit",
                    "Transient network jitter across all downstream dependencies",
                ],
                prior_score=prior_pay,
            )

        # 2. Evaluate Database Lock Contention hypothesis
        if "order-database-sim" in nodes_by_key:
            db_node = nodes_by_key["order-database-sim"]
            db_p95 = db_node.metrics.p95_latency_ms or 0.0
            db_sat = db_node.metrics.saturation_pct or 0.0
            db_nom = NOMINAL_SERVICE_LATENCY_MS["order-database-sim"]
            supporting_db: list[dict[str, Any]] = []
            contradicting_db: list[dict[str, Any]] = []

            if db_p95 > db_nom * 2.5:
                supporting_db.append(
                    {
                        "service_key": "order-database-sim",
                        "metric_name": "p95_latency_ms",
                        "observed_value": db_p95,
                        "baseline_reference": db_nom,
                        "correlation_ids": corr_by_service.get("order-database-sim", []),
                        "note": (
                            f"order-database-sim p95 query latency ({db_p95}ms) is elevated "
                            f"above nominal ({db_nom}ms), affecting both inventory and checkout."
                        ),
                    }
                )
            else:
                contradicting_db.append(
                    {
                        "service_key": "order-database-sim",
                        "metric_name": "p95_latency_ms",
                        "observed_value": db_p95,
                        "baseline_reference": db_nom,
                        "correlation_ids": corr_by_service.get("order-database-sim", []),
                        "note": f"order-database-sim p95 latency ({db_p95}ms) is within baseline.",
                    }
                )

            if db_sat >= 70.0:
                supporting_db.append(
                    {
                        "service_key": "order-database-sim",
                        "metric_name": "saturation_pct",
                        "observed_value": db_sat,
                        "baseline_reference": 20.0,
                        "correlation_ids": corr_by_service.get("order-database-sim", []),
                        "note": f"Database lock saturation is elevated at {db_sat}%.",
                    }
                )

            prior_db = (
                0.64
                if (db_p95 > 180.0 and db_sat >= 75.0)
                else (0.45 if db_p95 > db_nom * 2.5 else 0.19)
            )
            await _register_candidate(
                root_service="order-database-sim",
                mechanism="database_lock_contention",
                statement=(
                    f"Database lock contention in 'order-database-sim' causes "
                    f"'{target_service_key}' degradation across stock reservation and order commit."
                ),
                intervention="relieve_db_lock_contention",
                supporting=supporting_db,
                contradicting=contradicting_db,
                alternatives=[
                    "Internal compute throttling inside inventory-service",
                    "Checkout orchestrator concurrency saturation",
                ],
                prior_score=prior_db,
            )

        # 3. Evaluate Inventory Processing Delay hypothesis
        if "inventory-service" in nodes_by_key:
            inv_node = nodes_by_key["inventory-service"]
            inv_p95 = inv_node.metrics.p95_latency_ms or 0.0
            inv_nom = NOMINAL_SERVICE_LATENCY_MS["inventory-service"]
            db_p95_val = (
                nodes_by_key["order-database-sim"].metrics.p95_latency_ms or 0.0
                if "order-database-sim" in nodes_by_key
                else 0.0
            )
            supporting_inv: list[dict[str, Any]] = []
            contradicting_inv: list[dict[str, Any]] = []

            if inv_p95 > inv_nom * 2.2:
                supporting_inv.append(
                    {
                        "service_key": "inventory-service",
                        "metric_name": "p95_latency_ms",
                        "observed_value": inv_p95,
                        "baseline_reference": inv_nom,
                        "correlation_ids": corr_by_service.get("inventory-service", []),
                        "note": (
                            f"inventory-service p95 latency ({inv_p95}ms) is elevated above "
                            f"nominal ({inv_nom}ms)."
                        ),
                    }
                )
            else:
                contradicting_inv.append(
                    {
                        "service_key": "inventory-service",
                        "metric_name": "p95_latency_ms",
                        "observed_value": inv_p95,
                        "baseline_reference": inv_nom,
                        "correlation_ids": corr_by_service.get("inventory-service", []),
                        "note": f"inventory-service p95 latency ({inv_p95}ms) is nominal.",
                    }
                )

            if db_p95_val > 180.0:
                contradicting_inv.append(
                    {
                        "service_key": "order-database-sim",
                        "metric_name": "p95_latency_ms",
                        "observed_value": db_p95_val,
                        "baseline_reference": 20.0,
                        "correlation_ids": corr_by_service.get("order-database-sim", []),
                        "note": (
                            "Downstream order-database-sim is also slow, suggesting inventory "
                            "latency may be inherited from database lock contention."
                        ),
                    }
                )

            prior_inv = (
                0.60
                if (inv_p95 > 220.0 and db_p95_val < 80.0)
                else (0.41 if inv_p95 > 180.0 else 0.17)
            )
            await _register_candidate(
                root_service="inventory-service",
                mechanism="inventory_worker_starvation",
                statement=(
                    f"Inventory processing delays in 'inventory-service' cause "
                    f"'{target_service_key}' degradation during synchronous stock reservation."
                ),
                intervention="scale_inventory_workers",
                supporting=supporting_inv,
                contradicting=contradicting_inv,
                alternatives=[
                    "Downstream database lock contention in order-database-sim",
                    "Payment gateway latency dominating total checkout duration",
                ],
                prior_score=prior_inv,
            )

        # 4. Evaluate Excessive Request Concurrency / Queue Accumulation hypothesis
        if "checkout-service" in nodes_by_key:
            chk_node = nodes_by_key["checkout-service"]
            chk_p95 = chk_node.metrics.p95_latency_ms or 0.0
            chk_sat = chk_node.metrics.saturation_pct or 0.0
            supporting_chk: list[dict[str, Any]] = []
            contradicting_chk: list[dict[str, Any]] = []

            if chk_sat > 45.0:
                supporting_chk.append(
                    {
                        "service_key": "checkout-service",
                        "metric_name": "saturation_pct",
                        "observed_value": chk_sat,
                        "baseline_reference": 30.0,
                        "correlation_ids": corr_by_service.get("checkout-service", []),
                        "note": f"checkout-service queue saturation is {chk_sat}%.",
                    }
                )
            else:
                contradicting_chk.append(
                    {
                        "service_key": "checkout-service",
                        "metric_name": "saturation_pct",
                        "observed_value": chk_sat,
                        "baseline_reference": 30.0,
                        "correlation_ids": corr_by_service.get("checkout-service", []),
                        "note": f"checkout-service saturation ({chk_sat}%) is moderate.",
                    }
                )

            prior_chk = 0.34 if chk_p95 > 220.0 else 0.15
            await _register_candidate(
                root_service="checkout-service",
                mechanism="request_concurrency_queue_saturation",
                statement=(
                    f"Excessive request concurrency at 'checkout-service' causes internal "
                    f"queue accumulation and '{target_service_key}' latency degradation."
                ),
                intervention="hedged_concurrency_limiter",
                supporting=supporting_chk,
                contradicting=contradicting_chk,
                alternatives=[
                    "Blocking calls to degraded downstream dependencies (payment, DB, inventory)",
                ],
                prior_score=prior_chk,
            )

        return hypotheses_created, observational_evidence

    @staticmethod
    async def revise_hypothesis_from_experiment(
        db: AsyncSession,
        *,
        hypothesis: HypothesisRecord,
        experiment_run_id: str,
        stats_summary: dict[str, Any],
    ) -> tuple[HypothesisRecord, EvidenceRecord]:
        """Update hypothesis support score, status, and evidence ledger after an experiment."""
        now_iso = datetime.now(UTC).isoformat()
        rel_effect_pct = float(stats_summary.get("relative_effect_pct", 0.0))
        abs_effect_ms = float(stats_summary.get("absolute_effect_size_ms", 0.0))
        ci_lower = float(stats_summary.get("ci_lower_95_ms", 0.0))
        ci_upper = float(stats_summary.get("ci_upper_95_ms", 0.0))
        is_sig = bool(stats_summary.get("is_statistically_significant", False))
        control_mean = float(stats_summary.get("control_mean_ms", 0.0))
        treatment_mean = float(stats_summary.get("treatment_mean_ms", 0.0))
        total_n = int(stats_summary.get("control_n", 0)) + int(
            stats_summary.get("treatment_n", 0)
        )
        trial_corrs: list[str] = list(stats_summary.get("trial_correlation_ids", []))

        # Note: For latency, a negative abs_effect_ms / rel_effect_pct means the treatment
        # REDUCED latency compared to control (e.g., -72% latency reduction).
        latency_reduction_pct = -rel_effect_pct

        # Determine whether the system was actually healthy in the control arm
        control_was_healthy = control_mean < 145.0

        if control_was_healthy:
            new_status = "refuted"
            direction = "contradicting"
            new_score = 0.08
            interp = (
                f"Refuted by controlled experiment: Control arm baseline was healthy "
                f"({control_mean:.1f}ms), demonstrating no active degradation from "
                f"{hypothesis.root_cause_service_key}."
            )
            summary_text = (
                f"Controlled intervention '{hypothesis.recommended_intervention}' on "
                f"'{hypothesis.root_cause_service_key}' showed healthy control baseline "
                f"({control_mean:.1f}ms vs {treatment_mean:.1f}ms, Δ={abs_effect_ms:.1f}ms)."
            )
        elif is_sig and latency_reduction_pct >= 30.0 and ci_upper < -40.0:
            new_status = "supported"
            direction = "supporting"
            # Calculate empirical support score bounded in [0.82, 0.98]
            new_score = round(min(0.98, 0.78 + min(0.20, latency_reduction_pct / 350.0)), 3)
            interp = (
                f"Empirically supported by controlled intervention "
                f"('{hypothesis.recommended_intervention}'): latency decreased by "
                f"{latency_reduction_pct:.1f}% ({abs_effect_ms:.1f}ms, 95% CI "
                f"[{ci_lower:.1f}, {ci_upper:.1f}] ms). Note: Support score reflects "
                f"experimental effect magnitude under laboratory assumptions."
            )
            summary_text = (
                f"Experimental confirmation: applying '{hypothesis.recommended_intervention}' "
                f"reduced '{hypothesis.affected_service_key}' latency from "
                f"{control_mean:.1f}ms (control) to {treatment_mean:.1f}ms (treatment), "
                f"effect Δ={abs_effect_ms:.1f}ms ({rel_effect_pct:.1f}%, 95% CI "
                f"[{ci_lower:.1f}, {ci_upper:.1f}] ms)."
            )
        elif latency_reduction_pct < 15.0 or ci_upper >= 0.0:
            new_status = "refuted"
            direction = "contradicting"
            new_score = round(max(0.05, hypothesis.confidence_score * 0.22), 3)
            interp = (
                f"Refuted by controlled intervention ('{hypothesis.recommended_intervention}'): "
                f"degradation persisted in treatment arm ({treatment_mean:.1f}ms vs control "
                f"{control_mean:.1f}ms; 95% CI [{ci_lower:.1f}, {ci_upper:.1f}] ms includes 0 "
                f"or negligible reduction)."
            )
            summary_text = (
                f"Experimental refutation: '{hypothesis.recommended_intervention}' failed to "
                f"resolve degradation (control {control_mean:.1f}ms vs treatment "
                f"{treatment_mean:.1f}ms, Δ={abs_effect_ms:.1f}ms, 95% CI "
                f"[{ci_lower:.1f}, {ci_upper:.1f}] ms)."
            )
        else:
            new_status = "inconclusive"
            direction = "inconclusive"
            new_score = round(min(0.49, max(0.25, hypothesis.confidence_score)), 3)
            interp = (
                f"Inconclusive experimental outcome: partial effect observed "
                f"({latency_reduction_pct:.1f}% reduction, 95% CI "
                f"[{ci_lower:.1f}, {ci_upper:.1f}] ms), "
                f"insufficient to establish a definitive single causal root."
            )
            summary_text = (
                f"Inconclusive intervention '{hypothesis.recommended_intervention}': "
                f"control {control_mean:.1f}ms vs treatment {treatment_mean:.1f}ms "
                f"(Δ={abs_effect_ms:.1f}ms, 95% CI [{ci_lower:.1f}, {ci_upper:.1f}] ms)."
            )

        hypothesis.status = new_status
        hypothesis.confidence_score = new_score
        hypothesis.score_interpretation = interp

        revisions = list(hypothesis.revision_history_json or [])
        revisions.append(
            {
                "timestamp": now_iso,
                "phase": "EVALUATING",
                "experiment_run_id": experiment_run_id,
                "status": new_status,
                "score": new_score,
                "effect_size_ms": abs_effect_ms,
                "ci_95_ms": [ci_lower, ci_upper],
                "reason": summary_text,
            }
        )
        hypothesis.revision_history_json = revisions

        if direction == "supporting":
            sup = list(hypothesis.supporting_observations_json or [])
            sup.append(
                {
                    "service_key": hypothesis.root_cause_service_key,
                    "metric_name": "experimental_treatment_vs_control_ms",
                    "observed_value": treatment_mean,
                    "baseline_reference": control_mean,
                    "correlation_ids": trial_corrs[:6],
                    "note": summary_text,
                }
            )
            hypothesis.supporting_observations_json = sup
        else:
            con = list(hypothesis.contradicting_observations_json or [])
            con.append(
                {
                    "service_key": hypothesis.root_cause_service_key,
                    "metric_name": "experimental_treatment_vs_control_ms",
                    "observed_value": treatment_mean,
                    "baseline_reference": control_mean,
                    "correlation_ids": trial_corrs[:6],
                    "note": summary_text,
                }
            )
            hypothesis.contradicting_observations_json = con

        evidence = EvidenceRecord(
            system_id=hypothesis.system_id,
            investigation_id=hypothesis.investigation_id,
            experiment_run_id=experiment_run_id,
            hypothesis_id=hypothesis.id,
            evidence_type="controlled_experiment",
            direction=direction,
            summary=summary_text,
            correlation_id=trial_corrs[0] if trial_corrs else None,
            effect_size=abs_effect_ms,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            sample_size=total_n,
            artifact_payload_json=stats_summary,
        )
        db.add(evidence)
        await db.flush()
        return hypothesis, evidence
