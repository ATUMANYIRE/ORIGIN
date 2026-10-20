"""Autonomous Scientific Investigation Engine and Bounded Reasoning Loop (Milestone 02/05).

Implements the state machine:
CREATED -> OBSERVING -> HYPOTHESIZING -> PLANNING -> EXPERIMENTING -> EVALUATING
-> CONCLUDED / INCONCLUSIVE / FAILED / CANCELLED
"""

import asyncio
import statistics
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.models import (
    EvidenceRecord,
    ExperimentDefinition,
    ExperimentRun,
    HypothesisRecord,
    InvestigationRecord,
)
from app.modules.agents.schemas import (
    InvestigationCreateRequest,
    InvestigationDetailRead,
    InvestigationRead,
)
from app.modules.evidence.hypothesis_engine import HypothesisEngine
from app.modules.evidence.schemas import EvidenceRead, HypothesisRead
from app.modules.experimentation.engine import ExperimentEngine
from app.modules.experimentation.schemas import (
    ExperimentDefinitionRead,
    ExperimentRunRead,
)
from app.modules.laboratory.orchestrator import SyntheticLabOrchestrator
from app.modules.registry.service import RegistryService
from app.modules.safety.service import AuditService
from app.modules.topology.service import TopologyService

VALID_LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"OBSERVING", "CANCELLED", "FAILED"},
    "OBSERVING": {"HYPOTHESIZING", "CANCELLED", "FAILED"},
    "HYPOTHESIZING": {"PLANNING", "INCONCLUSIVE", "CANCELLED", "FAILED"},
    "PLANNING": {
        "EXPERIMENTING",
        "CONCLUDED",
        "INCONCLUSIVE",
        "CANCELLED",
        "FAILED",
    },
    "EXPERIMENTING": {"EVALUATING", "CANCELLED", "FAILED"},
    "EVALUATING": {
        "PLANNING",
        "CONCLUDED",
        "INCONCLUSIVE",
        "CANCELLED",
        "FAILED",
    },
    "CONCLUDED": set(),
    "INCONCLUSIVE": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

# Concurrency semaphore to bound simultaneous autonomous investigations
_INVESTIGATION_SEMAPHORE = asyncio.Semaphore(3)


def validate_state_transition(current_state: str, next_state: str) -> None:
    """Verify that an investigation lifecycle transition is valid."""
    allowed = VALID_LIFECYCLE_TRANSITIONS.get(current_state, set())
    if next_state not in allowed:
        raise ValueError(
            f"Invalid investigation lifecycle transition: {current_state} -> {next_state}. "
            f"Allowed from {current_state}: {sorted(allowed)}"
        )


class AutonomousInvestigatorService:
    """Coordinates the autonomous causal investigation lifecycle."""

    @staticmethod
    async def transition_state(
        db: AsyncSession,
        investigation: InvestigationRecord,
        next_state: str,
        note: str,
    ) -> None:
        """Validate and persist a lifecycle state transition."""
        validate_state_transition(investigation.status, next_state)
        prev_state = investigation.status
        now_iso = datetime.now(UTC).isoformat()
        investigation.status = next_state
        history = list(investigation.lifecycle_history_json or [])
        history.append(
            {
                "from_state": prev_state,
                "to_state": next_state,
                "timestamp": now_iso,
                "note": note,
            }
        )
        investigation.lifecycle_history_json = history
        await db.flush()

        await event_bus.publish(
            "investigation.transition",
            {
                "investigation_id": investigation.id,
                "from_state": prev_state,
                "to_state": next_state,
                "note": note,
                "timestamp": now_iso,
            },
        )

    @staticmethod
    async def record_decision(
        db: AsyncSession,
        investigation: InvestigationRecord,
        step_type: str,
        rationale: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append an inspectable reasoning step to the investigation decision history."""
        decisions = list(investigation.decision_history_json or [])
        decisions.append(
            {
                "step_index": len(decisions) + 1,
                "phase": investigation.status,
                "step_type": step_type,
                "rationale": rationale,
                "details": details or {},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        investigation.decision_history_json = decisions
        await db.flush()

    @staticmethod
    async def create_investigation(
        db: AsyncSession,
        request: InvestigationCreateRequest,
        actor: str = "operator",
        correlation_id: str | None = None,
    ) -> InvestigationRecord:
        """Create a new investigation in CREATED state."""
        await SyntheticLabOrchestrator.ensure_lab_registered(
            db, actor=actor, correlation_id=correlation_id
        )
        system = await RegistryService.get_system_by_id_or_slug(db, request.system_slug)
        now = datetime.now(UTC)

        inv = InvestigationRecord(
            system_id=system.id,
            title=request.title,
            target_service_key=request.target_service_key,
            target_metric=request.target_metric,
            status="CREATED",
            experiment_budget=request.experiment_budget,
            experiments_used=0,
            sample_size_per_arm=request.sample_size_per_arm,
            random_seed=request.random_seed,
            timeout_seconds=request.timeout_seconds,
            cancel_requested=False,
            baseline_summary_json={},
            lifecycle_history_json=[
                {
                    "from_state": None,
                    "to_state": "CREATED",
                    "timestamp": now.isoformat(),
                    "note": (
                        f"Investigation created for target "
                        f"'{request.target_service_key}.{request.target_metric}' "
                        f"with budget={request.experiment_budget}, seed={request.random_seed}."
                    ),
                }
            ],
            decision_history_json=[],
        )
        db.add(inv)
        await db.flush()

        await AuditService.record_event(
            db,
            system_id=system.id,
            actor=actor,
            action="investigation.created",
            resource_type="investigation",
            resource_id=inv.id,
            correlation_id=correlation_id,
            details={
                "target_service_key": inv.target_service_key,
                "experiment_budget": inv.experiment_budget,
                "random_seed": inv.random_seed,
            },
        )
        await db.commit()
        return inv

    @staticmethod
    async def cancel_investigation(
        db: AsyncSession,
        investigation_id: str,
        actor: str = "operator",
        reason: str = "Cancelled by operator request.",
    ) -> InvestigationRecord:
        """Request or finalize cancellation of an investigation."""
        inv = await AutonomousInvestigatorService.get_investigation_model(db, investigation_id)
        inv.cancel_requested = True
        if inv.status not in ("CONCLUDED", "INCONCLUSIVE", "FAILED", "CANCELLED"):
            await AutonomousInvestigatorService.transition_state(db, inv, "CANCELLED", reason)
            inv.completed_at = datetime.now(UTC)
            inv.conclusion_summary = f"Investigation cancelled: {reason}"
            await AuditService.record_event(
                db,
                system_id=inv.system_id,
                actor=actor,
                action="investigation.cancelled",
                resource_type="investigation",
                resource_id=inv.id,
                severity="warning",
                details={"reason": reason},
            )
        await db.commit()
        return inv

    @staticmethod
    async def run_investigation(
        db: AsyncSession,
        investigation_id: str,
        actor: str = "autonomous-investigator",
    ) -> InvestigationDetailRead:
        """Execute the bounded autonomous scientific reasoning loop from start to conclusion."""
        async with _INVESTIGATION_SEMAPHORE:
            inv = await AutonomousInvestigatorService.get_investigation_model(db, investigation_id)
            if inv.status in ("CONCLUDED", "INCONCLUSIVE", "FAILED", "CANCELLED"):
                return await AutonomousInvestigatorService.get_investigation_detail(db, inv.id)

            t_start = time.perf_counter()
            inv.started_at = datetime.now(UTC)

            async def _is_cancelled_or_timed_out() -> bool:
                await db.refresh(inv, attribute_names=["cancel_requested", "status"])
                if inv.cancel_requested or inv.status == "CANCELLED":
                    return True
                elapsed_s = time.perf_counter() - t_start
                return elapsed_s > float(inv.timeout_seconds)

            try:
                # ---------------------------------------------------------------
                # Phase 1: OBSERVING
                # ---------------------------------------------------------------
                await AutonomousInvestigatorService.transition_state(
                    db,
                    inv,
                    "OBSERVING",
                    "Collecting fresh baseline telemetry and provenance-verified topology.",
                )

                baseline_traces = []
                for obs_idx in range(4):
                    obs_seed = inv.random_seed * 100 + obs_idx
                    tr = await SyntheticLabOrchestrator.execute_instrumented_transaction(
                        db,
                        profile=None,
                        intervention="none",
                        experiment_arm="baseline_observation",
                        rng_seed=obs_seed,
                    )
                    baseline_traces.append(tr)

                target_vals = [
                    float(t.service_latencies_ms.get(inv.target_service_key, t.total_duration_ms))
                    for t in baseline_traces
                ]
                baseline_mean = round(statistics.fmean(target_vals), 2)
                baseline_max = round(max(target_vals), 2)
                baseline_corrs = [t.correlation_id for t in baseline_traces]

                topology = await TopologyService.build_topology_graph(db, inv.system_id)
                inv.baseline_summary_json = {
                    "target_service_key": inv.target_service_key,
                    "target_metric": inv.target_metric,
                    "sample_count": len(target_vals),
                    "baseline_mean_ms": baseline_mean,
                    "baseline_max_ms": baseline_max,
                    "is_degraded_at_baseline": baseline_mean >= 145.0,
                    "correlation_ids": baseline_corrs,
                    "observed_topology_nodes": topology.total_nodes,
                    "verified_topology_edges": topology.verified_edges,
                }
                await AutonomousInvestigatorService.record_decision(
                    db,
                    inv,
                    "observe_baseline",
                    (
                        f"Observed {len(target_vals)} baseline requests on "
                        f"'{inv.target_service_key}': mean={baseline_mean}ms, "
                        f"max={baseline_max}ms across {topology.verified_edges} verified edges."
                    ),
                    inv.baseline_summary_json,
                )

                if await _is_cancelled_or_timed_out():
                    if inv.status != "CANCELLED":
                        await AutonomousInvestigatorService.transition_state(
                            db,
                            inv,
                            "CANCELLED",
                            "Investigation cancelled or timed out during OBSERVING phase.",
                        )
                    inv.completed_at = datetime.now(UTC)
                    await db.commit()
                    return await AutonomousInvestigatorService.get_investigation_detail(db, inv.id)

                # ---------------------------------------------------------------
                # Phase 2: HYPOTHESIZING
                # ---------------------------------------------------------------
                await AutonomousInvestigatorService.transition_state(
                    db,
                    inv,
                    "HYPOTHESIZING",
                    "Synthesizing competing causal hypotheses from topology and telemetry.",
                )
                hypotheses, _obs_ev = await HypothesisEngine.generate_competing_hypotheses(
                    db,
                    system_id=inv.system_id,
                    investigation_id=inv.id,
                    target_service_key=inv.target_service_key,
                    target_metric=inv.target_metric,
                    topology=topology,
                )
                await AutonomousInvestigatorService.record_decision(
                    db,
                    inv,
                    "generate_hypotheses",
                    (
                        f"Generated {len(hypotheses)} competing falsifiable hypotheses "
                        f"constrained by verified topology."
                    ),
                    {
                        "hypothesis_count": len(hypotheses),
                        "candidates": [
                            {
                                "id": h.id,
                                "root_cause_service_key": h.root_cause_service_key,
                                "mechanism": h.suspected_mechanism,
                                "prior_score": h.confidence_score,
                                "intervention": h.recommended_intervention,
                            }
                            for h in hypotheses
                        ],
                    },
                )

                if not hypotheses:
                    await AutonomousInvestigatorService.transition_state(
                        db,
                        inv,
                        "INCONCLUSIVE",
                        "No testable hypotheses could be constructed for target service.",
                    )
                    inv.conclusion_summary = (
                        "Inconclusive: No testable downstream causal hypotheses found."
                    )
                    inv.completed_at = datetime.now(UTC)
                    await db.commit()
                    return await AutonomousInvestigatorService.get_investigation_detail(db, inv.id)

                # ---------------------------------------------------------------
                # Phases 3-5 Iterative Loop: PLANNING -> EXPERIMENTING -> EVALUATING
                # ---------------------------------------------------------------
                executed_interventions: set[str] = set()
                supported_hypothesis: HypothesisRecord | None = None

                while inv.experiments_used < inv.experiment_budget:
                    if await _is_cancelled_or_timed_out():
                        if inv.status != "CANCELLED":
                            await AutonomousInvestigatorService.transition_state(
                                db,
                                inv,
                                "CANCELLED",
                                "Investigation cancelled or timed out before next experiment.",
                            )
                        inv.completed_at = datetime.now(UTC)
                        await db.commit()
                        return await AutonomousInvestigatorService.get_investigation_detail(
                            db, inv.id
                        )

                    await AutonomousInvestigatorService.transition_state(
                        db,
                        inv,
                        "PLANNING",
                        (
                            f"Selecting next informative experiment "
                            f"(budget used: {inv.experiments_used}/{inv.experiment_budget})."
                        ),
                    )

                    remaining_budget = inv.experiment_budget - inv.experiments_used
                    selected_hyp, sel_score, sel_reason = (
                        ExperimentEngine.select_next_hypothesis_for_experiment(
                            hypotheses=hypotheses,
                            executed_interventions=executed_interventions,
                            remaining_budget=remaining_budget,
                        )
                    )
                    await AutonomousInvestigatorService.record_decision(
                        db,
                        inv,
                        "select_experiment",
                        sel_reason,
                        {
                            "selected_hypothesis_id": (selected_hyp.id if selected_hyp else None),
                            "selection_score": sel_score,
                            "remaining_budget": remaining_budget,
                        },
                    )

                    if selected_hyp is None:
                        break

                    # Transition to EXPERIMENTING
                    await AutonomousInvestigatorService.transition_state(
                        db,
                        inv,
                        "EXPERIMENTING",
                        (
                            f"Executing paired block-randomized experiment: "
                            f"'{selected_hyp.recommended_intervention}' on "
                            f"'{selected_hyp.root_cause_service_key}'."
                        ),
                    )
                    exp_seed = inv.random_seed + (inv.experiments_used + 1) * 31
                    (
                        exp_def,
                        exp_run,
                        stats_summary,
                    ) = await ExperimentEngine.plan_and_execute_experiment(
                        db,
                        system_id=inv.system_id,
                        investigation_id=inv.id,
                        hypothesis=selected_hyp,
                        sample_size_per_arm=inv.sample_size_per_arm,
                        random_seed=exp_seed,
                        selection_score=sel_score,
                        selection_reason=sel_reason,
                        actor=actor,
                        check_cancel_fn=_is_cancelled_or_timed_out,
                    )

                    if exp_run.status == "cancelled" or await _is_cancelled_or_timed_out():
                        if inv.status != "CANCELLED":
                            await AutonomousInvestigatorService.transition_state(
                                db,
                                inv,
                                "CANCELLED",
                                "Investigation cancelled during experiment execution.",
                            )
                        inv.completed_at = datetime.now(UTC)
                        await db.commit()
                        return await AutonomousInvestigatorService.get_investigation_detail(
                            db, inv.id
                        )

                    inv.experiments_used += exp_def.budget_cost
                    executed_interventions.add(selected_hyp.recommended_intervention)

                    # Transition to EVALUATING
                    await AutonomousInvestigatorService.transition_state(
                        db,
                        inv,
                        "EVALUATING",
                        (
                            f"Evaluating statistical outcome of '{exp_def.name}' "
                            f"and updating hypothesis ledger."
                        ),
                    )
                    updated_hyp, ev_rec = await HypothesisEngine.revise_hypothesis_from_experiment(
                        db,
                        hypothesis=selected_hyp,
                        experiment_run_id=exp_run.id,
                        stats_summary=stats_summary,
                    )
                    await AutonomousInvestigatorService.record_decision(
                        db,
                        inv,
                        "evaluate_experiment",
                        ev_rec.summary,
                        {
                            "hypothesis_id": updated_hyp.id,
                            "updated_status": updated_hyp.status,
                            "updated_support_score": updated_hyp.confidence_score,
                            "effect_size_ms": stats_summary.get("absolute_effect_size_ms"),
                            "relative_effect_pct": stats_summary.get("relative_effect_pct"),
                            "ci_95_ms": [
                                stats_summary.get("ci_lower_95_ms"),
                                stats_summary.get("ci_upper_95_ms"),
                            ],
                        },
                    )

                    if updated_hyp.status == "supported":
                        supported_hypothesis = updated_hyp
                        # Mark remaining untested hypotheses as superseded/refuted contextually
                        break

                # ---------------------------------------------------------------
                # Phase 6: Final Conclusion vs Inconclusive Determination
                # ---------------------------------------------------------------
                if supported_hypothesis is not None:
                    inv.concluded_cause_service_key = supported_hypothesis.root_cause_service_key
                    inv.concluded_mechanism = supported_hypothesis.suspected_mechanism
                    inv.conclusion_summary = (
                        f"Concluded Root Cause: '{supported_hypothesis.root_cause_service_key}' "
                        f"via mechanism '{supported_hypothesis.suspected_mechanism}' "
                        f"(empirical support score={supported_hypothesis.confidence_score:.2f}). "
                        f"Controlled intervention "
                        f"'{supported_hypothesis.recommended_intervention}' "
                        f"produced a statistically significant latency reduction."
                    )
                    inv.uncertainty_summary = (
                        "Conclusion is grounded in block-randomized experimental evidence "
                        "(95% Welch t-interval excluding zero). Residual uncertainty applies "
                        "to untested external network hops outside the laboratory boundary."
                    )
                    await AutonomousInvestigatorService.transition_state(
                        db,
                        inv,
                        "CONCLUDED",
                        inv.conclusion_summary,
                    )
                elif not inv.baseline_summary_json.get("is_degraded_at_baseline", True):
                    # System was healthy at baseline and experiments confirmed no active fault
                    inv.concluded_cause_service_key = "none"
                    inv.concluded_mechanism = "nominal_healthy_operation"
                    inv.conclusion_summary = (
                        f"Concluded Healthy Baseline: '{inv.target_service_key}' baseline "
                        f"latency ({baseline_mean}ms) is within nominal operational bounds "
                        f"and controlled trials confirmed no hidden service degradation."
                    )
                    inv.uncertainty_summary = (
                        "No statistically significant degradation was observed or elicited "
                        "across baseline and experimental control arms."
                    )
                    await AutonomousInvestigatorService.transition_state(
                        db,
                        inv,
                        "CONCLUDED",
                        inv.conclusion_summary,
                    )
                else:
                    # Degradation was present, but no tested intervention produced a
                    # statistically significant resolution -> INCONCLUSIVE (never fabricate!)
                    inv.concluded_cause_service_key = None
                    inv.concluded_mechanism = None
                    inv.conclusion_summary = (
                        f"Inconclusive Investigation: '{inv.target_service_key}' exhibited "
                        f"elevated baseline latency ({baseline_mean}ms), but after "
                        f"{inv.experiments_used} controlled experiment(s) none of the "
                        f"allowlisted interventions produced a statistically significant "
                        f"latency reduction (95% CIs overlapped zero or fell below practical "
                        f"effect threshold)."
                    )
                    inv.uncertainty_summary = (
                        "Observed latency variance is consistent with uncorrelated multi-service "
                        "stochastic jitter or an unmodeled external factor. ORIGIN refuses to "
                        "assert a false-positive causal root when experimental evidence is "
                        "inconclusive."
                    )
                    await AutonomousInvestigatorService.transition_state(
                        db,
                        inv,
                        "INCONCLUSIVE",
                        inv.conclusion_summary,
                    )

                inv.completed_at = datetime.now(UTC)
                await AuditService.record_event(
                    db,
                    system_id=inv.system_id,
                    actor=actor,
                    action=f"investigation.{inv.status.lower()}",
                    resource_type="investigation",
                    resource_id=inv.id,
                    details={
                        "status": inv.status,
                        "concluded_cause_service_key": inv.concluded_cause_service_key,
                        "concluded_mechanism": inv.concluded_mechanism,
                        "experiments_used": inv.experiments_used,
                    },
                )
                await db.commit()

                await event_bus.publish(
                    "investigation.finished",
                    {
                        "investigation_id": inv.id,
                        "status": inv.status,
                        "concluded_cause_service_key": inv.concluded_cause_service_key,
                        "concluded_mechanism": inv.concluded_mechanism,
                    },
                )
                return await AutonomousInvestigatorService.get_investigation_detail(db, inv.id)

            except Exception as exc:
                inv.status = "FAILED"
                inv.failure_reason = str(exc)
                inv.completed_at = datetime.now(UTC)
                await db.commit()
                raise

    @staticmethod
    async def get_investigation_model(
        db: AsyncSession, investigation_id: str
    ) -> InvestigationRecord:
        """Fetch an InvestigationRecord by ID or raise 404."""
        stmt = select(InvestigationRecord).where(InvestigationRecord.id == investigation_id)
        inv = (await db.execute(stmt)).scalar_one_or_none()
        if inv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation '{investigation_id}' not found.",
            )
        return inv

    @staticmethod
    async def list_investigations(
        db: AsyncSession,
        system_id: str | None = None,
        limit: int = 50,
    ) -> list[InvestigationRead]:
        """List recent investigations ordered newest first."""
        stmt = (
            select(InvestigationRecord).order_by(InvestigationRecord.created_at.desc()).limit(limit)
        )
        if system_id:
            stmt = stmt.where(InvestigationRecord.system_id == system_id)
        rows = list((await db.execute(stmt)).scalars().all())
        return [InvestigationRead.model_validate(r) for r in rows]

    @staticmethod
    async def get_investigation_detail(
        db: AsyncSession, investigation_id: str
    ) -> InvestigationDetailRead:
        """Fetch an investigation with all hypotheses, experiment plans, runs, and evidence."""
        inv = await AutonomousInvestigatorService.get_investigation_model(db, investigation_id)
        hyps = list(
            (
                await db.execute(
                    select(HypothesisRecord)
                    .where(HypothesisRecord.investigation_id == inv.id)
                    .order_by(HypothesisRecord.confidence_score.desc())
                )
            )
            .scalars()
            .all()
        )
        plans = list(
            (
                await db.execute(
                    select(ExperimentDefinition)
                    .where(ExperimentDefinition.investigation_id == inv.id)
                    .order_by(ExperimentDefinition.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        runs = list(
            (
                await db.execute(
                    select(ExperimentRun)
                    .where(ExperimentRun.investigation_id == inv.id)
                    .order_by(ExperimentRun.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        evidences = list(
            (
                await db.execute(
                    select(EvidenceRecord)
                    .where(EvidenceRecord.investigation_id == inv.id)
                    .order_by(EvidenceRecord.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

        base_read = InvestigationRead.model_validate(inv)
        return InvestigationDetailRead(
            **base_read.model_dump(),
            hypotheses=[HypothesisRead.model_validate(h) for h in hyps],
            experiment_plans=[ExperimentDefinitionRead.model_validate(p) for p in plans],
            experiment_runs=[ExperimentRunRead.model_validate(r) for r in runs],
            evidence_records=[EvidenceRead.model_validate(e) for e in evidences],
        )

    @staticmethod
    async def export_investigation_report(
        db: AsyncSession,
        investigation_id: str,
        report_format: str = "markdown",
    ) -> dict[str, Any]:
        """Generate a reproducible scientific investigation report in Markdown and JSON."""
        detail = await AutonomousInvestigatorService.get_investigation_detail(db, investigation_id)

        base_mean = detail.baseline_summary_json.get("baseline_mean_ms", "N/A")
        base_max = detail.baseline_summary_json.get("baseline_max_ms", "N/A")
        base_corrs = ", ".join(detail.baseline_summary_json.get("correlation_ids", []))
        cause_svc = detail.concluded_cause_service_key or "Inconclusive / None"
        cause_mech = detail.concluded_mechanism or "Inconclusive / None"

        lines: list[str] = [
            f"# ORIGIN Scientific Investigation Report: {detail.title}",
            "",
            f"- **Investigation ID:** `{detail.id}`",
            (
                f"- **Target Service & Metric:** `{detail.target_service_key}` · "
                f"`{detail.target_metric}`"
            ),
            f"- **Lifecycle Status:** **{detail.status}**",
            (
                f"- **Experiments Executed:** "
                f"`{detail.experiments_used} / {detail.experiment_budget}`"
            ),
            (
                f"- **Sample Size per Arm:** `{detail.sample_size_per_arm}` "
                f"(Seed `{detail.random_seed}`)"
            ),
            f"- **Concluded Root Cause Service:** `{cause_svc}`",
            f"- **Concluded Mechanism:** `{cause_mech}`",
            "",
            "## 1. Executive Conclusion & Epistemic Uncertainty",
            "",
            f"**Conclusion:** {detail.conclusion_summary or 'Pending completion.'}",
            "",
            f"**Uncertainty & Limitations:** {detail.uncertainty_summary or 'N/A'}",
            "",
            "## 2. Baseline System Observations",
            "",
            f"- **Baseline Mean Latency:** `{base_mean} ms`",
            f"- **Baseline Max Latency:** `{base_max} ms`",
            f"- **Baseline Correlation IDs:** `{base_corrs}`",
            "",
            "## 3. Competing Causal Hypotheses",
            "",
        ]

        for idx, h in enumerate(detail.hypotheses, start=1):
            lines.extend(
                [
                    f"### 3.{idx}. [{h.status.upper()}] {h.statement}",
                    f"- **Hypothesis ID:** `{h.id}`",
                    f"- **Suspected Root Cause:** `{h.root_cause_service_key}` "
                    f"(`{h.suspected_mechanism}`)",
                    f"- **Recommended Intervention:** `{h.recommended_intervention}`",
                    f"- **Empirical Support Score:** `{h.confidence_score}`",
                    f"- **Score Interpretation:** {h.score_interpretation}",
                    f"- **Alternative Explanations:** {'; '.join(h.alternative_explanations_json)}",
                    "",
                ]
            )

        lines.append("## 4. Controlled Experiments & Statistical Outcomes")
        lines.append("")
        for idx, run in enumerate(detail.experiment_runs, start=1):
            ms = run.metrics_summary_json
            c_summary = (
                f"`{ms.get('control_mean_ms')} ms` / "
                f"`{ms.get('control_median_ms')} ms` / "
                f"`{ms.get('control_std_ms')} ms` ($n={ms.get('control_n')}$)"
            )
            t_summary = (
                f"`{ms.get('treatment_mean_ms')} ms` / "
                f"`{ms.get('treatment_median_ms')} ms` / "
                f"`{ms.get('treatment_std_ms')} ms` ($n={ms.get('treatment_n')}$)"
            )
            eff_summary = (
                f"`{ms.get('absolute_effect_size_ms')} ms` (`{ms.get('relative_effect_pct')}%`)"
            )
            ci_summary = (
                f"`[{ms.get('ci_lower_95_ms')}, {ms.get('ci_upper_95_ms')}] ms` "
                f"($t = {ms.get('welch_t_stat')}$, $d = {ms.get('cohens_d')}$)"
            )
            trial_corrs = ", ".join(ms.get("trial_correlation_ids", [])[:8])
            lines.extend(
                [
                    f"### 4.{idx}. Experiment Run `{run.id}` (`{run.status}`)",
                    f"- **Control Mean / Median / SD:** {c_summary}",
                    f"- **Treatment Mean / Median / SD:** {t_summary}",
                    f"- **Absolute Effect Size ($\\Delta$):** {eff_summary}",
                    f"- **95% Welch Confidence Interval:** {ci_summary}",
                    f"- **Statistically Significant:** `{ms.get('is_statistically_significant')}`",
                    f"- **Trial Correlation IDs:** `{trial_corrs}`",
                    "",
                ]
            )

        lines.append("## 5. Scientific Evidence Ledger")
        lines.append("")
        for ev in detail.evidence_records:
            lines.append(
                f"- **`{ev.id[:8]}` [{ev.evidence_type} · {ev.direction.upper()}]:** {ev.summary} "
                f"(Corr: `{ev.correlation_id or 'n/a'}`)"
            )

        markdown_text = "\n".join(lines)
        return {
            "investigation_id": detail.id,
            "format": report_format,
            "generated_at": datetime.now(UTC).isoformat(),
            "markdown": markdown_text,
            "investigation": detail.model_dump(mode="json"),
        }
