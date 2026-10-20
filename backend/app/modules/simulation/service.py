"""Digital Twin Orchestration, Branching, Benchmarks, and Scientific Memory (Milestone 03/05)."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.models import (
    CalibrationRunRecord,
    DigitalTwinModelRecord,
    EvidenceRecord,
    InvestigationRecord,
    ScientificMemoryEntryRecord,
    SimulationBranchRecord,
    SimulationSnapshotRecord,
)
from app.modules.laboratory.orchestrator import (
    LAB_SYSTEM_SLUG,
    LabTransactionRequest,
    SyntheticLabOrchestrator,
)
from app.modules.registry.service import RegistryService
from app.modules.safety.service import AuditService
from app.modules.simulation.calibration import TwinCalibrationEngine
from app.modules.simulation.schemas import (
    BranchComparisonResponse,
    CalibrationRunRead,
    DigitalTwinModelRead,
    HypothesisSimulationRequest,
    ScientificMemoryEntryRead,
    SimulationBenchmarkScenarioResult,
    SimulationBenchmarkSuiteResponse,
    SimulationBranchCreateRequest,
    SimulationBranchRead,
    SimulationSnapshotRead,
    SnapshotCreateRequest,
    TwinCalibrationRequest,
    TwinInterventionSpec,
)
from app.modules.simulation.simulator import (
    MAX_BRANCHES_PER_TWIN,
    LivingDigitalTwinSimulator,
    run_simulation_with_uncertainty,
)


class DigitalTwinService:
    """High-level service for Digital Twin calibration, snapshots, branching, and benchmarks."""

    @staticmethod
    async def create_or_calibrate_twin(
        db: AsyncSession,
        request: TwinCalibrationRequest,
        actor: str = "scientific-operator",
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Calibrate a new versioned Digital Twin model from stored telemetry and experiments."""
        twin_rec, cal_rec = await TwinCalibrationEngine.calibrate_from_evidence(
            db, request
        )
        await AuditService.record_event(
            db,
            system_id=twin_rec.system_id,
            actor=actor,
            action="digital_twin.calibrated",
            resource_type="digital_twin_model",
            resource_id=twin_rec.id,
            severity="info" if twin_rec.status == "calibrated" else "warning",
            correlation_id=correlation_id,
            details={
                "version_tag": twin_rec.version_tag,
                "status": twin_rec.status,
                "mae_ms": cal_rec.mae_ms,
                "rmse_ms": cal_rec.rmse_ms,
            },
        )
        await db.commit()
        await event_bus.publish(
            "twin.calibrated",
            {
                "twin_model_id": twin_rec.id,
                "version_tag": twin_rec.version_tag,
                "status": twin_rec.status,
                "mae_ms": cal_rec.mae_ms,
            },
        )
        return {
            "twin_model": DigitalTwinModelRead.model_validate(twin_rec).model_dump(
                mode="json"
            ),
            "calibration_run": CalibrationRunRead.model_validate(cal_rec).model_dump(
                mode="json"
            ),
        }

    @staticmethod
    async def list_twin_models(
        db: AsyncSession,
        system_id: str | None = None,
        limit: int = 50,
    ) -> list[DigitalTwinModelRead]:
        """List calibrated Digital Twin models ordered by newest first."""
        stmt = select(DigitalTwinModelRecord).order_by(
            DigitalTwinModelRecord.created_at.desc()
        )
        if system_id:
            system = await RegistryService.get_system_by_id_or_slug(db, system_id)
            stmt = stmt.where(DigitalTwinModelRecord.system_id == system.id)
        rows = list((await db.execute(stmt.limit(limit))).scalars().all())
        return [DigitalTwinModelRead.model_validate(r) for r in rows]

    @staticmethod
    async def get_twin_model_record(
        db: AsyncSession,
        twin_model_id: str,
    ) -> DigitalTwinModelRecord:
        """Resolve a Digital Twin model record by ID or raise 404."""
        stmt = select(DigitalTwinModelRecord).where(
            DigitalTwinModelRecord.id == twin_model_id
        )
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if rec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Digital Twin model '{twin_model_id}' not found.",
            )
        return rec

    @staticmethod
    async def list_calibration_runs(
        db: AsyncSession,
        twin_model_id: str | None = None,
        limit: int = 50,
    ) -> list[CalibrationRunRead]:
        """List calibration and held-out validation runs."""
        stmt = select(CalibrationRunRecord).order_by(
            CalibrationRunRecord.created_at.desc()
        )
        if twin_model_id:
            stmt = stmt.where(CalibrationRunRecord.twin_model_id == twin_model_id)
        rows = list((await db.execute(stmt.limit(limit))).scalars().all())
        return [CalibrationRunRead.model_validate(r) for r in rows]

    @staticmethod
    async def create_snapshot(
        db: AsyncSession,
        request: SnapshotCreateRequest,
    ) -> SimulationSnapshotRead:
        """Create a serializable simulation state snapshot at t=0 or after `step_index` steps."""
        twin = await DigitalTwinService.get_twin_model_record(
            db, request.twin_model_id
        )
        sim = LivingDigitalTwinSimulator(
            model_parameters=twin.parameters_json,
            random_seed=request.random_seed,
        )
        for _ in range(request.step_index):
            sim.step(1.0)

        snap_dict = sim.capture_snapshot_dict(label=request.label)
        snap_rec = SimulationSnapshotRecord(
            system_id=twin.system_id,
            twin_model_id=twin.id,
            branch_id=request.branch_id,
            label=request.label,
            sim_clock_sec=snap_dict["sim_clock_sec"],
            step_index=snap_dict["step_index"],
            random_seed=snap_dict["random_seed"],
            rng_state_json=snap_dict["rng_state_json"],
            pending_events_json=snap_dict["pending_events_json"],
            service_states_json=snap_dict["service_states_json"],
            active_interventions_json=snap_dict["active_interventions_json"],
        )
        db.add(snap_rec)
        await db.commit()
        return SimulationSnapshotRead.model_validate(snap_rec)

    @staticmethod
    async def list_snapshots(
        db: AsyncSession,
        twin_model_id: str | None = None,
        limit: int = 50,
    ) -> list[SimulationSnapshotRead]:
        """List saved simulation snapshots."""
        stmt = select(SimulationSnapshotRecord).order_by(
            SimulationSnapshotRecord.created_at.desc()
        )
        if twin_model_id:
            stmt = stmt.where(SimulationSnapshotRecord.twin_model_id == twin_model_id)
        rows = list((await db.execute(stmt.limit(limit))).scalars().all())
        return [SimulationSnapshotRead.model_validate(r) for r in rows]

    @staticmethod
    async def get_snapshot_record(
        db: AsyncSession,
        snapshot_id: str,
    ) -> SimulationSnapshotRecord:
        """Retrieve a SimulationSnapshotRecord by ID or raise 404."""
        stmt = select(SimulationSnapshotRecord).where(
            SimulationSnapshotRecord.id == snapshot_id
        )
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if rec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Simulation snapshot '{snapshot_id}' not found.",
            )
        return rec

    @staticmethod
    async def create_and_run_branch(
        db: AsyncSession,
        request: SimulationBranchCreateRequest,
        actor: str = "scientific-operator",
        correlation_id: str | None = None,
    ) -> SimulationBranchRead:
        """Execute a baseline or counterfactual simulation branch from a model or snapshot."""
        twin = await DigitalTwinService.get_twin_model_record(
            db, request.twin_model_id
        )

        # Enforce maximum branch limit per twin
        count_stmt = select(func.count(SimulationBranchRecord.id)).where(
            SimulationBranchRecord.twin_model_id == twin.id
        )
        branch_count = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        if int(branch_count) >= MAX_BRANCHES_PER_TWIN:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Maximum branch count ({MAX_BRANCHES_PER_TWIN}) reached for "
                    f"Digital Twin '{twin.id}'."
                ),
            )

        model_params = deepcopy(twin.parameters_json)
        warnings: list[str] = list(twin.warnings_json)

        if request.incoming_traffic_rps is not None:
            model_params["incoming_traffic_rps"] = request.incoming_traffic_rps
            if request.incoming_traffic_rps > 110.0 or request.incoming_traffic_rps < 10.0:
                warnings.append(
                    f"Extrapolation warning: incoming_traffic_rps={request.incoming_traffic_rps} "
                    "is outside the calibrated operating envelope [10.0, 110.0] req/s."
                )

        # If no initial_snapshot_id was provided, automatically capture an initial snapshot
        initial_snap_dict: dict[str, Any] | None = None
        snapshot_id = request.initial_snapshot_id
        if snapshot_id is not None:
            snap_rec = await DigitalTwinService.get_snapshot_record(db, snapshot_id)
            initial_snap_dict = {
                "label": snap_rec.label,
                "sim_clock_sec": snap_rec.sim_clock_sec,
                "step_index": snap_rec.step_index,
                "random_seed": request.random_seed,
                "rng_state_json": snap_rec.rng_state_json,
                "pending_events_json": snap_rec.pending_events_json,
                "service_states_json": deepcopy(snap_rec.service_states_json),
                "active_interventions_json": deepcopy(
                    snap_rec.active_interventions_json
                ),
            }
            if request.incoming_traffic_rps is not None:
                initial_snap_dict["service_states_json"]["current_parameters"][
                    "incoming_traffic_rps"
                ] = request.incoming_traffic_rps
        else:
            auto_snap = await DigitalTwinService.create_snapshot(
                db,
                SnapshotCreateRequest(
                    twin_model_id=twin.id,
                    step_index=0,
                    label=f"Auto Initial Snapshot ({request.name})",
                    random_seed=request.random_seed,
                ),
            )
            snapshot_id = auto_snap.id
            initial_snap_dict = {
                "label": auto_snap.label,
                "sim_clock_sec": auto_snap.sim_clock_sec,
                "step_index": auto_snap.step_index,
                "random_seed": request.random_seed,
                "rng_state_json": auto_snap.rng_state_json,
                "pending_events_json": auto_snap.pending_events_json,
                "service_states_json": deepcopy(auto_snap.service_states_json),
                "active_interventions_json": deepcopy(
                    auto_snap.active_interventions_json
                ),
            }
            if request.incoming_traffic_rps is not None:
                initial_snap_dict["service_states_json"]["current_parameters"][
                    "incoming_traffic_rps"
                ] = request.incoming_traffic_rps

        interventions_list = [
            i.model_dump(mode="json") for i in request.interventions
        ]
        for iv in request.interventions:
            if iv.intervention_type == "increase_replicas" and iv.value > 8:
                warnings.append(
                    f"Extrapolation warning: replica_count={iv.value} exceeds calibrated "
                    "upper bound of 8 replicas."
                )

        try:
            trajectory, event_log, summary, uncertainty = (
                run_simulation_with_uncertainty(
                    model_parameters=model_params,
                    parameter_uncertainty=twin.parameter_uncertainty_json,
                    interventions=interventions_list,
                    initial_snapshot=initial_snap_dict,
                    random_seed=request.random_seed,
                    horizon_seconds=request.horizon_seconds,
                    dt_seconds=request.dt_seconds,
                    monte_carlo_runs=request.monte_carlo_runs,
                )
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        # Detect shared bottleneck constraints (scaling checkout replicas under DB lock contention)
        db_lock_factor = float(
            model_params["services"]
            .get("order-database-sim", {})
            .get("db_lock_contention_factor", 0.0)
        )
        for iv in request.interventions:
            if (
                iv.intervention_type == "increase_replicas"
                and iv.target_service_key == "checkout-service"
                and db_lock_factor >= 0.35
            ):
                warnings.append(
                    "Shared Bottleneck Warning: Scaling 'checkout-service' replicas while "
                    "'order-database-sim' has high lock contention increases concurrent DB "
                    "row-lock queuing and fails to improve end-to-end checkout throughput."
                )

        branch_rec = SimulationBranchRecord(
            system_id=twin.system_id,
            twin_model_id=twin.id,
            investigation_id=request.investigation_id,
            hypothesis_id=request.hypothesis_id,
            parent_branch_id=request.parent_branch_id,
            initial_snapshot_id=snapshot_id,
            name=request.name,
            branch_type=request.branch_type,
            status="COMPLETED",
            random_seed=request.random_seed,
            horizon_seconds=request.horizon_seconds,
            dt_seconds=request.dt_seconds,
            monte_carlo_runs=request.monte_carlo_runs,
            interventions_json=interventions_list,
            simulation_params_json={
                "incoming_traffic_rps": model_params.get("incoming_traffic_rps", 45.0),
                "horizon_seconds": request.horizon_seconds,
                "dt_seconds": request.dt_seconds,
            },
            trajectory_json=trajectory,
            event_log_json=event_log,
            outcome_summary_json=summary,
            uncertainty_json=uncertainty,
            warnings_json=warnings,
        )
        db.add(branch_rec)
        await db.flush()

        # Persist in Scientific Memory as a counterfactual_prediction
        mem_entry = ScientificMemoryEntryRecord(
            system_id=twin.system_id,
            epistemic_kind="counterfactual_prediction",
            title=f"Simulation Branch: {request.name} ({twin.version_tag})",
            summary=(
                f"Simulated {request.branch_type} branch '{request.name}' over "
                f"{request.horizon_seconds}s (Seed={request.random_seed}): "
                f"Mean Latency={summary.get('mean_latency_ms')}ms "
                f"(95% PI [{uncertainty.get('latency_ci_lower_95_ms')}, "
                f"{uncertainty.get('latency_ci_upper_95_ms')}] ms), "
                f"Error Rate={summary.get('mean_error_rate_pct')}%, "
                f"Bottleneck={summary.get('bottleneck_service_key')}."
            ),
            investigation_id=request.investigation_id,
            hypothesis_id=request.hypothesis_id,
            twin_model_id=twin.id,
            branch_id=branch_rec.id,
            predicted_outcome_json=summary,
            observed_outcome_json={},
            validation_metrics_json=uncertainty,
            provenance_json={
                "epistemic_classification": "simulated_prediction",
                "twin_version_tag": twin.version_tag,
                "initial_snapshot_id": snapshot_id,
                "parent_branch_id": request.parent_branch_id,
                "interventions": interventions_list,
            },
        )
        db.add(mem_entry)
        await AuditService.record_event(
            db,
            system_id=twin.system_id,
            actor=actor,
            action="simulation.branch_executed",
            resource_type="simulation_branch",
            resource_id=branch_rec.id,
            severity="info",
            correlation_id=correlation_id,
            details={
                "name": branch_rec.name,
                "branch_type": branch_rec.branch_type,
                "mean_latency_ms": summary.get("mean_latency_ms"),
            },
        )
        await db.commit()
        return SimulationBranchRead.model_validate(branch_rec)

    @staticmethod
    async def list_branches(
        db: AsyncSession,
        twin_model_id: str | None = None,
        system_id: str | None = None,
        limit: int = 50,
    ) -> list[SimulationBranchRead]:
        """List simulation branches ordered by newest first."""
        stmt = select(SimulationBranchRecord).order_by(
            SimulationBranchRecord.created_at.desc()
        )
        if twin_model_id:
            stmt = stmt.where(SimulationBranchRecord.twin_model_id == twin_model_id)
        if system_id:
            system = await RegistryService.get_system_by_id_or_slug(db, system_id)
            stmt = stmt.where(SimulationBranchRecord.system_id == system.id)
        rows = list((await db.execute(stmt.limit(limit))).scalars().all())
        return [SimulationBranchRead.model_validate(r) for r in rows]

    @staticmethod
    async def get_branch_record(
        db: AsyncSession,
        branch_id: str,
    ) -> SimulationBranchRecord:
        """Retrieve a SimulationBranchRecord by ID or raise 404."""
        stmt = select(SimulationBranchRecord).where(
            SimulationBranchRecord.id == branch_id
        )
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if rec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Simulation branch '{branch_id}' not found.",
            )
        return rec

    @staticmethod
    async def cancel_branch(
        db: AsyncSession,
        branch_id: str,
    ) -> SimulationBranchRead:
        """Mark a simulation branch as CANCELLED."""
        rec = await DigitalTwinService.get_branch_record(db, branch_id)
        rec.status = "CANCELLED"
        await db.commit()
        return SimulationBranchRead.model_validate(rec)

    @staticmethod
    async def compare_branches(
        db: AsyncSession,
        baseline_branch_id: str,
        alternative_branch_id: str,
    ) -> BranchComparisonResponse:
        """Compare a baseline future branch against an alternative counterfactual branch."""
        b_rec = await DigitalTwinService.get_branch_record(db, baseline_branch_id)
        a_rec = await DigitalTwinService.get_branch_record(db, alternative_branch_id)

        b_sum = b_rec.outcome_summary_json
        a_sum = a_rec.outcome_summary_json

        b_lat = float(b_sum.get("mean_latency_ms", 0.0))
        a_lat = float(a_sum.get("mean_latency_ms", 0.0))
        lat_delta_ms = round(a_lat - b_lat, 2)
        lat_delta_pct = round(((a_lat - b_lat) / max(1.0, b_lat)) * 100.0, 2)

        b_err = float(b_sum.get("mean_error_rate_pct", 0.0))
        a_err = float(a_sum.get("mean_error_rate_pct", 0.0))
        err_delta_pct = round(a_err - b_err, 2)

        b_thru = float(b_sum.get("mean_throughput_rps", 0.0))
        a_thru = float(a_sum.get("mean_throughput_rps", 0.0))
        thru_delta_rps = round(a_thru - b_thru, 2)

        b_q = float(b_sum.get("max_queue_depth", 0.0))
        a_q = float(a_sum.get("max_queue_depth", 0.0))
        q_delta = round(a_q - b_q, 2)

        tradeoffs: list[str] = []
        bottleneck_warnings: list[str] = list(a_rec.warnings_json)

        for iv in a_rec.interventions_json:
            itype = iv.get("intervention_type")
            tsvc = iv.get("target_service_key")
            if itype == "enable_circuit_breaker":
                tradeoffs.append(
                    f"Circuit Breaker Tradeoff on '{tsvc}': Reduced mean latency by "
                    f"{abs(lat_delta_ms):.1f}ms ({abs(lat_delta_pct):.1f}%) and prevented "
                    f"upstream queue collapse, at the cost of bounded fast-fail fallback "
                    f"responses ({a_err:.1f}% error rate vs {b_err:.1f}% baseline)."
                )
            elif itype == "reduce_incoming_traffic":
                tradeoffs.append(
                    f"Traffic Shedding Tradeoff: Stabilized latency ({a_lat:.1f}ms vs "
                    f"{b_lat:.1f}ms) and queue depth ({a_q:.1f} vs {b_q:.1f}), but throttled "
                    f"served throughput by {abs(thru_delta_rps):.1f} req/s."
                )
            elif itype == "increase_replicas":
                if lat_delta_pct >= -5.0:
                    msg = (
                        f"Ineffective Horizontal Scaling on '{tsvc}': Increasing replicas did not "
                        f"relieve system latency (Δ={lat_delta_ms:+.1f}ms, {lat_delta_pct:+.1f}%) "
                        f"because shared dependency '{a_sum.get('bottleneck_service_key')}' "
                        "remained the active bottleneck."
                    )
                    tradeoffs.append(msg)
                    if msg not in bottleneck_warnings:
                        bottleneck_warnings.append(msg)
                else:
                    tradeoffs.append(
                        f"Horizontal Scaling on '{tsvc}': Reduced latency by "
                        f"{abs(lat_delta_ms):.1f}ms ({abs(lat_delta_pct):.1f}%) at the cost of "
                        "additional compute replica capacity."
                    )

        if not tradeoffs:
            tradeoffs.append(
                f"Alternative branch modified system mean latency by {lat_delta_ms:+.1f}ms "
                f"({lat_delta_pct:+.1f}%) and throughput by {thru_delta_rps:+.1f} req/s."
            )

        return BranchComparisonResponse(
            baseline_branch=SimulationBranchRead.model_validate(b_rec),
            alternative_branch=SimulationBranchRead.model_validate(a_rec),
            delta_metrics={
                "latency_delta_ms": lat_delta_ms,
                "latency_delta_pct": lat_delta_pct,
                "error_rate_delta_pct": err_delta_pct,
                "throughput_delta_rps": thru_delta_rps,
                "max_queue_depth_delta": q_delta,
                "baseline_bottleneck": b_sum.get("bottleneck_service_key"),
                "alternative_bottleneck": a_sum.get("bottleneck_service_key"),
            },
            tradeoff_analysis=tradeoffs,
            shared_bottleneck_warnings=bottleneck_warnings,
        )

    @staticmethod
    async def simulate_hypothesis_for_investigation(
        db: AsyncSession,
        investigation_id: str,
        request: HypothesisSimulationRequest,
    ) -> dict[str, Any]:
        """Integrate the Digital Twin with the Milestone 2 Causal Investigator.

        Strictly distinguishes:
        - observed_evidence: Real telemetry observed in the laboratory.
        - experimental_evidence: Controlled intervention trials executed in the laboratory.
        - simulated_prediction: Digital Twin counterfactual projection under model assumptions.
        """
        inv_stmt = select(InvestigationRecord).where(
            InvestigationRecord.id == investigation_id
        )
        inv = (await db.execute(inv_stmt)).scalar_one_or_none()
        if inv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation '{investigation_id}' not found.",
            )

        # Calibrate or retrieve Digital Twin linked to this investigation
        twin_bundle = await DigitalTwinService.create_or_calibrate_twin(
            db,
            TwinCalibrationRequest(
                system_slug=LAB_SYSTEM_SLUG,
                investigation_id=investigation_id,
                min_required_observations=6,
            ),
        )
        twin_id = twin_bundle["twin_model"]["id"]

        # Create shared initial snapshot so baseline and intervention branches start identically
        init_snap = await DigitalTwinService.create_snapshot(
            db,
            SnapshotCreateRequest(
                twin_model_id=twin_id,
                step_index=0,
                label=f"Investigation {investigation_id[:8]} Baseline State",
                random_seed=request.random_seed,
            ),
        )

        base_branch = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_id,
                name="Investigation Baseline Projection",
                branch_type="baseline",
                initial_snapshot_id=init_snap.id,
                investigation_id=investigation_id,
                hypothesis_id=request.hypothesis_id,
                random_seed=request.random_seed,
                horizon_seconds=request.horizon_seconds,
                interventions=[],
            ),
        )

        alt_branch = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_id,
                name=(
                    f"Hypothesis Intervention ({request.intervention_type} on "
                    f"{request.suspected_service_key})"
                ),
                branch_type="hypothesis_test",
                parent_branch_id=base_branch.id,
                initial_snapshot_id=init_snap.id,
                investigation_id=investigation_id,
                hypothesis_id=request.hypothesis_id,
                random_seed=request.random_seed,
                horizon_seconds=request.horizon_seconds,
                interventions=[
                    TwinInterventionSpec(
                        intervention_type=request.intervention_type,
                        target_service_key=request.suspected_service_key,
                        value=request.intervention_value,
                        apply_at_sec=0.0,
                        description=f"Counterfactual test for {request.suspected_service_key}",
                    )
                ],
            ),
        )

        comparison = await DigitalTwinService.compare_branches(
            db, base_branch.id, alt_branch.id
        )

        # Gather real observed and experimental evidence from the investigation
        ev_stmt = select(EvidenceRecord).where(
            EvidenceRecord.investigation_id == investigation_id
        )
        ev_rows = list((await db.execute(ev_stmt)).scalars().all())
        obs_ev = [
            {
                "id": e.id,
                "summary": e.summary,
                "correlation_id": e.correlation_id,
            }
            for e in ev_rows
            if e.evidence_type == "observational_correlation"
        ]
        exp_ev = [
            {
                "id": e.id,
                "summary": e.summary,
                "effect_size_ms": e.effect_size,
                "ci_95_ms": [e.ci_lower, e.ci_upper],
                "correlation_id": e.correlation_id,
            }
            for e in ev_rows
            if e.evidence_type == "controlled_experiment"
        ]

        return {
            "investigation_id": investigation_id,
            "epistemic_separation_disclosure": (
                "SIMULATED PREDICTION ONLY: Digital Twin projections estimate expected behavior "
                "under calibrated queueing/contention equations and never substitute for "
                "controlled experimental proof. Held-out validation split was enforced during "
                "calibration."
            ),
            "observed_evidence": {
                "epistemic_status": "historical_observation",
                "baseline_summary": inv.baseline_summary_json,
                "observational_records": obs_ev,
            },
            "experimental_evidence": {
                "epistemic_status": "experimental_evidence",
                "concluded_cause_service_key": inv.concluded_cause_service_key,
                "controlled_experiment_records": exp_ev,
            },
            "simulated_prediction": {
                "epistemic_status": "counterfactual_prediction",
                "twin_model": twin_bundle["twin_model"],
                "calibration_quality": twin_bundle["calibration_run"],
                "comparison": comparison.model_dump(mode="json"),
            },
        }

    @staticmethod
    async def export_simulation_report(
        db: AsyncSession,
        branch_id: str,
        compare_with_branch_id: str | None = None,
        report_format: Literal["markdown", "json"] = "markdown",
    ) -> dict[str, Any]:
        """Export a reproducible Markdown & JSON scientific simulation report."""
        branch = await DigitalTwinService.get_branch_record(db, branch_id)
        twin = await DigitalTwinService.get_twin_model_record(db, branch.twin_model_id)
        bsum = branch.outcome_summary_json
        unc = branch.uncertainty_json

        comparison_data: dict[str, Any] | None = None
        if compare_with_branch_id:
            comp = await DigitalTwinService.compare_branches(
                db, compare_with_branch_id, branch_id
            )
            comparison_data = comp.model_dump(mode="json")
        elif branch.parent_branch_id:
            comp = await DigitalTwinService.compare_branches(
                db, branch.parent_branch_id, branch_id
            )
            comparison_data = comp.model_dump(mode="json")

        cal_sum = twin.calibration_summary_json
        ci_low = unc.get("latency_ci_lower_95_ms")
        ci_high = unc.get("latency_ci_upper_95_ms")
        mc_runs = unc.get("monte_carlo_runs")
        lines: list[str] = [
            f"# ORIGIN Digital Twin Counterfactual Report: {branch.name}",
            "",
            "> **Epistemic Classification:** `counterfactual_prediction` — Generated by the ORIGIN "
            "Living Digital Twin Engine. Predictions are conditioned on calibrated model "
            "parameters and stated physical assumptions, and are strictly distinguished "
            "from empirical observations.",
            "",
            "## 1. Model Provenance & Calibration Quality",
            f"- **Digital Twin Version:** `{twin.version_tag}` (`{twin.id}`)",
            f"- **Calibration Status:** `{twin.status}` (`{twin.calibration_method}`)",
            f"- **Held-Out Validation MAE / RMSE / NRMSE:** `{cal_sum.get('mae_ms')} ms` / "
            f"`{cal_sum.get('rmse_ms')} ms` / `{cal_sum.get('normalized_error_pct')}%`",
            f"- **Branch ID & Type:** `{branch.id}` (`{branch.branch_type}`)",
            f"- **Initial Snapshot ID:** `{branch.initial_snapshot_id}`",
            (
                f"- **Random Seed & Horizon:** Seed `{branch.random_seed}` · "
                f"Horizon `{branch.horizon_seconds}s`"
            ),
            "",
            "## 2. Simulated Outcome & Monte Carlo Uncertainty",
            (
                f"- **System Mean Latency:** `{bsum.get('mean_latency_ms')} ms` "
                f"(95% Prediction Interval: `[{ci_low}, {ci_high}] ms` "
                f"across `{mc_runs}` runs)"
            ),
            f"- **System p95 Latency:** `{bsum.get('p95_latency_ms')} ms`",
            f"- **Mean Error Rate:** `{bsum.get('mean_error_rate_pct')}%`",
            f"- **Mean Throughput:** `{bsum.get('mean_throughput_rps')} req/s`",
            f"- **Max Queue Depth:** `{bsum.get('max_queue_depth')}`",
            f"- **Primary Bottleneck Service:** `{bsum.get('bottleneck_service_key')}`",
            "",
        ]

        if comparison_data:
            dm = comparison_data["delta_metrics"]
            lines.extend(
                [
                    "## 3. Parallel Futures Comparison vs. Baseline",
                    f"- **Latency Effect ($\\Delta$):** `{dm.get('latency_delta_ms')} ms` "
                    f"(`{dm.get('latency_delta_pct')}%`)",
                    f"- **Error Rate Effect ($\\Delta$):** `{dm.get('error_rate_delta_pct')}%`",
                    (
                        f"- **Throughput Effect ($\\Delta$):** "
                        f"`{dm.get('throughput_delta_rps')} req/s`"
                    ),
                    "- **Intervention Tradeoffs:**",
                ]
            )
            for t_note in comparison_data.get("tradeoff_analysis", []):
                lines.append(f"  - {t_note}")
            lines.append("")

        lines.append("## 4. Stated Physical Assumptions & Warnings")
        for a_note in twin.assumptions_json:
            lines.append(f"- **Assumption:** {a_note}")
        for w_note in branch.warnings_json:
            lines.append(f"- **Warning:** {w_note}")

        markdown_text = "\n".join(lines)
        report_payload = {
            "epistemic_label": "counterfactual_prediction",
            "branch": SimulationBranchRead.model_validate(branch).model_dump(
                mode="json"
            ),
            "twin_model": DigitalTwinModelRead.model_validate(twin).model_dump(
                mode="json"
            ),
            "comparison": comparison_data,
        }
        return {
            "branch_id": branch.id,
            "format": report_format,
            "markdown": markdown_text,
            "report": report_payload,
        }

    @staticmethod
    async def run_simulation_benchmarks(
        db: AsyncSession,
        random_seed: int = 2026,
    ) -> SimulationBenchmarkSuiteResponse:
        """Execute all 4 required Milestone 03/05 Digital Twin benchmarks.

        - Benchmark A: Payment degradation calibration & recovery interventions
        - Benchmark B: Database contention (shared bottleneck limits checkout replica scaling)
        - Benchmark C: Traffic surge (horizontal scaling vs rate limiting vs concurrency control)
        - Benchmark D: Cascading failure & circuit-breaker latency/availability tradeoff
        """
        results: list[SimulationBenchmarkScenarioResult] = []

        # -------------------------------------------------------------------
        # Benchmark A — Payment Degradation
        # -------------------------------------------------------------------
        await SyntheticLabOrchestrator.run_workload(
            db,
            LabTransactionRequest(iterations=5, profile="payment_latency_spike"),
            actor="benchmark-suite",
        )
        twin_a_bundle = await DigitalTwinService.create_or_calibrate_twin(
            db,
            TwinCalibrationRequest(
                system_slug=LAB_SYSTEM_SLUG,
                version_tag="benchmark-A-payment-degradation",
                min_required_observations=12,
            ),
        )
        twin_a_id = twin_a_bundle["twin_model"]["id"]
        snap_a = await DigitalTwinService.create_snapshot(
            db,
            SnapshotCreateRequest(
                twin_model_id=twin_a_id,
                label="Benchmark A Initial Snapshot",
                random_seed=random_seed,
            ),
        )
        base_a = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_a_id,
                name="Benchmark A: Baseline Payment Degradation",
                branch_type="benchmark",
                initial_snapshot_id=snap_a.id,
                random_seed=random_seed,
                horizon_seconds=20.0,
            ),
        )
        int_a1 = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_a_id,
                name="Benchmark A: Fast-Path Payment Latency Reduction",
                branch_type="benchmark",
                parent_branch_id=base_a.id,
                initial_snapshot_id=snap_a.id,
                random_seed=random_seed,
                horizon_seconds=20.0,
                interventions=[
                    TwinInterventionSpec(
                        intervention_type="reduce_downstream_latency",
                        target_service_key="payment-simulator",
                        value=0.12,
                        description="Isolate payment fast-path (reduce payment latency to 12%)",
                    )
                ],
            ),
        )
        pass_a = (
            float(int_a1.outcome_summary_json["mean_latency_ms"])
            < float(base_a.outcome_summary_json["mean_latency_ms"]) * 0.55
        )
        results.append(
            SimulationBenchmarkScenarioResult(
                benchmark_key="benchmark_a_payment_degradation",
                title="Benchmark A — Payment Degradation & Recovery",
                description=(
                    "Calibrates Digital Twin against observed payment_latency_spike spans "
                    "and evaluates downstream payment latency isolation."
                ),
                twin_model_id=twin_a_id,
                model_version_tag=twin_a_bundle["twin_model"]["version_tag"],
                calibration_mae_ms=float(twin_a_bundle["calibration_run"]["mae_ms"]),
                calibration_rmse_ms=float(twin_a_bundle["calibration_run"]["rmse_ms"]),
                baseline_branch_id=base_a.id,
                intervention_branch_ids=[int_a1.id],
                baseline_outcome=base_a.outcome_summary_json,
                intervention_outcomes=[int_a1.outcome_summary_json],
                uncertainty_summary=int_a1.uncertainty_json,
                key_scientific_finding=(
                    f"Reducing payment-simulator latency reduced end-to-end system latency from "
                    f"{base_a.outcome_summary_json['mean_latency_ms']}ms to "
                    f"{int_a1.outcome_summary_json['mean_latency_ms']}ms."
                ),
                limitations=[
                    "Assumes upstream api-gateway arrival rate remains stationary during recovery."
                ],
                passed_verification=pass_a,
            )
        )

        # -------------------------------------------------------------------
        # Benchmark B — Database Contention (Shared Bottleneck Proof)
        # -------------------------------------------------------------------
        await SyntheticLabOrchestrator.run_workload(
            db,
            LabTransactionRequest(iterations=5, profile="db_lock_contention"),
            actor="benchmark-suite",
        )
        twin_b_bundle = await DigitalTwinService.create_or_calibrate_twin(
            db,
            TwinCalibrationRequest(
                system_slug=LAB_SYSTEM_SLUG,
                version_tag="benchmark-B-db-contention",
                min_required_observations=12,
            ),
        )
        twin_b_id = twin_b_bundle["twin_model"]["id"]
        snap_b = await DigitalTwinService.create_snapshot(
            db,
            SnapshotCreateRequest(
                twin_model_id=twin_b_id,
                label="Benchmark B Initial Snapshot",
                random_seed=random_seed + 10,
            ),
        )
        base_b = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_b_id,
                name="Benchmark B: Baseline DB Lock Contention",
                branch_type="benchmark",
                initial_snapshot_id=snap_b.id,
                random_seed=random_seed + 10,
                horizon_seconds=20.0,
            ),
        )
        # Naive intervention: scale checkout-service replicas from 2 to 6 (worsens DB locks!)
        naive_b = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_b_id,
                name="Benchmark B: Naive Checkout Replica Scaling (2 -> 6 Replicas)",
                branch_type="benchmark",
                parent_branch_id=base_b.id,
                initial_snapshot_id=snap_b.id,
                random_seed=random_seed + 10,
                horizon_seconds=20.0,
                interventions=[
                    TwinInterventionSpec(
                        intervention_type="increase_replicas",
                        target_service_key="checkout-service",
                        value=6.0,
                        description="Scale checkout-service replicas without fixing DB contention",
                    )
                ],
            ),
        )
        # Effective intervention: expand DB connection/lock capacity
        fix_b = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_b_id,
                name="Benchmark B: Relieve Shared DB Lock Contention",
                branch_type="benchmark",
                parent_branch_id=base_b.id,
                initial_snapshot_id=snap_b.id,
                random_seed=random_seed + 10,
                horizon_seconds=20.0,
                interventions=[
                    TwinInterventionSpec(
                        intervention_type="adjust_db_connection_capacity",
                        target_service_key="order-database-sim",
                        value=180.0,
                        description="Partition row locks and expand DB connection capacity to 180",
                    )
                ],
            ),
        )
        base_b_lat = float(base_b.outcome_summary_json["mean_latency_ms"])
        naive_b_lat = float(naive_b.outcome_summary_json["mean_latency_ms"])
        fix_b_lat = float(fix_b.outcome_summary_json["mean_latency_ms"])
        # Scaling checkout replicas must NOT improve latency when DB lock contention dominates,
        # whereas relieving DB contention MUST significantly reduce latency!
        pass_b = (naive_b_lat >= base_b_lat * 0.96) and (fix_b_lat < base_b_lat * 0.65)
        results.append(
            SimulationBenchmarkScenarioResult(
                benchmark_key="benchmark_b_database_contention",
                title="Benchmark B — Shared Database Contention vs. Replica Scaling",
                description=(
                    "Demonstrates that adding checkout-service replicas fails to improve "
                    "(and amplifies lock contention) when order-database-sim is the bottleneck."
                ),
                twin_model_id=twin_b_id,
                model_version_tag=twin_b_bundle["twin_model"]["version_tag"],
                calibration_mae_ms=float(twin_b_bundle["calibration_run"]["mae_ms"]),
                calibration_rmse_ms=float(twin_b_bundle["calibration_run"]["rmse_ms"]),
                baseline_branch_id=base_b.id,
                intervention_branch_ids=[naive_b.id, fix_b.id],
                baseline_outcome=base_b.outcome_summary_json,
                intervention_outcomes=[
                    naive_b.outcome_summary_json,
                    fix_b.outcome_summary_json,
                ],
                uncertainty_summary=fix_b.uncertainty_json,
                key_scientific_finding=(
                    f"Adding checkout-service replicas (2->6) changed latency from {base_b_lat}ms "
                    f"to {naive_b_lat}ms due to amplified shared DB lock contention, while "
                    f"relieving DB lock capacity reduced latency to {fix_b_lat}ms."
                ),
                limitations=[
                    "Models row-lock contention as a quadratic function of concurrent worker load."
                ],
                passed_verification=pass_b,
            )
        )

        # -------------------------------------------------------------------
        # Benchmark C — Traffic Surge
        # -------------------------------------------------------------------
        await SyntheticLabOrchestrator.run_workload(
            db,
            LabTransactionRequest(iterations=4, profile="normal"),
            actor="benchmark-suite",
        )
        twin_c_bundle = await DigitalTwinService.create_or_calibrate_twin(
            db,
            TwinCalibrationRequest(
                system_slug=LAB_SYSTEM_SLUG,
                version_tag="benchmark-C-traffic-surge",
                min_required_observations=12,
            ),
        )
        twin_c_id = twin_c_bundle["twin_model"]["id"]
        base_c = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_c_id,
                name="Benchmark C: Unmitigated 95 req/s Traffic Surge",
                branch_type="benchmark",
                random_seed=random_seed + 20,
                horizon_seconds=20.0,
                incoming_traffic_rps=95.0,
            ),
        )
        scale_c = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_c_id,
                name="Benchmark C: Horizontal Scaling Across Tier Services",
                branch_type="benchmark",
                parent_branch_id=base_c.id,
                random_seed=random_seed + 20,
                horizon_seconds=20.0,
                incoming_traffic_rps=95.0,
                interventions=[
                    TwinInterventionSpec(
                        intervention_type="increase_replicas",
                        target_service_key="checkout-service",
                        value=5.0,
                    ),
                    TwinInterventionSpec(
                        intervention_type="increase_replicas",
                        target_service_key="inventory-service",
                        value=5.0,
                    ),
                    TwinInterventionSpec(
                        intervention_type="increase_replicas",
                        target_service_key="payment-simulator",
                        value=5.0,
                    ),
                    TwinInterventionSpec(
                        intervention_type="adjust_db_connection_capacity",
                        target_service_key="order-database-sim",
                        value=140.0,
                    ),
                ],
            ),
        )
        ratelimit_c = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_c_id,
                name="Benchmark C: Gateway Rate Limiting (0.55x Surge Shedding)",
                branch_type="benchmark",
                parent_branch_id=base_c.id,
                random_seed=random_seed + 20,
                horizon_seconds=20.0,
                incoming_traffic_rps=95.0,
                interventions=[
                    TwinInterventionSpec(
                        intervention_type="reduce_incoming_traffic",
                        target_service_key="api-gateway",
                        value=0.55,
                    )
                ],
            ),
        )
        pass_c = (
            float(scale_c.outcome_summary_json["mean_latency_ms"])
            < float(base_c.outcome_summary_json["mean_latency_ms"])
            and float(ratelimit_c.outcome_summary_json["mean_throughput_rps"])
            < float(scale_c.outcome_summary_json["mean_throughput_rps"])
        )
        results.append(
            SimulationBenchmarkScenarioResult(
                benchmark_key="benchmark_c_traffic_surge",
                title="Benchmark C — Traffic Surge: Scaling vs. Rate Limiting",
                description=(
                    "Compares multi-service horizontal scaling against gateway rate limiting "
                    "under a 95 req/s traffic surge."
                ),
                twin_model_id=twin_c_id,
                model_version_tag=twin_c_bundle["twin_model"]["version_tag"],
                calibration_mae_ms=float(twin_c_bundle["calibration_run"]["mae_ms"]),
                calibration_rmse_ms=float(twin_c_bundle["calibration_run"]["rmse_ms"]),
                baseline_branch_id=base_c.id,
                intervention_branch_ids=[scale_c.id, ratelimit_c.id],
                baseline_outcome=base_c.outcome_summary_json,
                intervention_outcomes=[
                    scale_c.outcome_summary_json,
                    ratelimit_c.outcome_summary_json,
                ],
                uncertainty_summary=scale_c.uncertainty_json,
                key_scientific_finding=(
                    f"Horizontal scaling preserved high throughput "
                    f"({scale_c.outcome_summary_json['mean_throughput_rps']} req/s) at low latency "
                    f"({scale_c.outcome_summary_json['mean_latency_ms']}ms), while rate limiting "
                    f"stabilized latency ({ratelimit_c.outcome_summary_json['mean_latency_ms']}ms) "
                    f"by shedding throughput to "
                    f"{ratelimit_c.outcome_summary_json['mean_throughput_rps']} req/s."
                ),
                limitations=[
                    (
                        "Instantaneous replica provisioning at t=0s; does not include "
                        "container cold-start delay."
                    )
                ],
                passed_verification=pass_c,
            )
        )

        # -------------------------------------------------------------------
        # Benchmark D — Cascading Failure & Circuit Breaker
        # -------------------------------------------------------------------
        base_d = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_c_id,
                name="Benchmark D: Unprotected Cascading Dependency Failure",
                branch_type="benchmark",
                random_seed=random_seed + 30,
                horizon_seconds=20.0,
                interventions=[
                    TwinInterventionSpec(
                        intervention_type="simulate_dependency_failure",
                        target_service_key="payment-simulator",
                        value=12.0,
                        description="12x downstream latency & error spike on payment-simulator",
                    )
                ],
            ),
        )
        cb_d = await DigitalTwinService.create_and_run_branch(
            db,
            SimulationBranchCreateRequest(
                twin_model_id=twin_c_id,
                name="Benchmark D: Checkout Circuit Breaker Protection Enabled",
                branch_type="benchmark",
                parent_branch_id=base_d.id,
                random_seed=random_seed + 30,
                horizon_seconds=20.0,
                interventions=[
                    TwinInterventionSpec(
                        intervention_type="simulate_dependency_failure",
                        target_service_key="payment-simulator",
                        value=12.0,
                    ),
                    TwinInterventionSpec(
                        intervention_type="enable_circuit_breaker",
                        target_service_key="checkout-service",
                        value=1.0,
                        description="Trip checkout circuit breaker when downstream exceeds 240ms",
                    ),
                ],
            ),
        )
        base_d_lat = float(base_d.outcome_summary_json["mean_latency_ms"])
        cb_d_lat = float(cb_d.outcome_summary_json["mean_latency_ms"])
        base_d_q = float(base_d.outcome_summary_json["max_queue_depth"])
        cb_d_q = float(cb_d.outcome_summary_json["max_queue_depth"])
        cb_d_err = float(cb_d.outcome_summary_json["mean_error_rate_pct"])
        pass_d = (cb_d_lat < base_d_lat * 0.45) and (cb_d_q < base_d_q) and (cb_d_err >= 8.0)
        results.append(
            SimulationBenchmarkScenarioResult(
                benchmark_key="benchmark_d_cascading_failure",
                title="Benchmark D — Cascading Failure & Circuit-Breaker Tradeoff",
                description=(
                    "Models severe downstream slowdown, upstream queue accumulation, and "
                    "circuit-breaker fast-fail protection."
                ),
                twin_model_id=twin_c_id,
                model_version_tag=twin_c_bundle["twin_model"]["version_tag"],
                calibration_mae_ms=float(twin_c_bundle["calibration_run"]["mae_ms"]),
                calibration_rmse_ms=float(twin_c_bundle["calibration_run"]["rmse_ms"]),
                baseline_branch_id=base_d.id,
                intervention_branch_ids=[cb_d.id],
                baseline_outcome=base_d.outcome_summary_json,
                intervention_outcomes=[cb_d.outcome_summary_json],
                uncertainty_summary=cb_d.uncertainty_json,
                key_scientific_finding=(
                    f"Circuit breaker prevented cascading queue collapse (max queue {cb_d_q} vs "
                    f"{base_d_q}, mean latency {cb_d_lat}ms vs {base_d_lat}ms) while introducing "
                    f"an explicit fast-fail fallback error rate of {cb_d_err}%."
                ),
                limitations=[
                    (
                        "Circuit breaker fallback error rate is modeled as a uniform 9.5% "
                        "fast-fail rejection."
                    )
                ],
                passed_verification=pass_d,
            )
        )

        # Restore lab to normal
        await SyntheticLabOrchestrator.run_workload(
            db,
            LabTransactionRequest(iterations=2, profile="normal"),
            actor="benchmark-suite",
        )

        passed_count = sum(1 for r in results if r.passed_verification)
        return SimulationBenchmarkSuiteResponse(
            total_benchmarks=len(results),
            passed_count=passed_count,
            executed_at=datetime.now(UTC).isoformat(),
            benchmarks=results,
        )


class ScientificMemoryService:
    """Persistent, queryable Scientific Memory distinguishing facts and predictions."""

    @staticmethod
    async def list_memory_entries(
        db: AsyncSession,
        system_id: str | None = None,
        epistemic_kind: str | None = None,
        limit: int = 80,
    ) -> list[ScientificMemoryEntryRead]:
        """Query persistent scientific memory entries with optional epistemic filtering."""
        # Synchronize any recent investigations/evidence not yet indexed in memory
        await ScientificMemoryService.sync_investigation_evidence_to_memory(db)

        stmt = select(ScientificMemoryEntryRecord).order_by(
            ScientificMemoryEntryRecord.created_at.desc()
        )
        if system_id:
            system = await RegistryService.get_system_by_id_or_slug(db, system_id)
            stmt = stmt.where(ScientificMemoryEntryRecord.system_id == system.id)
        if epistemic_kind:
            stmt = stmt.where(
                ScientificMemoryEntryRecord.epistemic_kind == epistemic_kind
            )
        rows = list((await db.execute(stmt.limit(limit))).scalars().all())
        return [ScientificMemoryEntryRead.model_validate(r) for r in rows]

    @staticmethod
    async def sync_investigation_evidence_to_memory(db: AsyncSession) -> None:
        """Index historical investigations and experimental evidence in Scientific Memory."""
        existing_inv_ids = set(
            (
                await db.execute(
                    select(ScientificMemoryEntryRecord.investigation_id).where(
                        ScientificMemoryEntryRecord.epistemic_kind.in_(
                            ["historical_observation", "experimental_evidence"]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

        invs = list(
            (
                await db.execute(
                    select(InvestigationRecord)
                    .order_by(InvestigationRecord.created_at.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )

        added = False
        for inv in invs:
            if inv.id in existing_inv_ids:
                continue
            # 1. Record historical observation baseline
            obs_mem = ScientificMemoryEntryRecord(
                system_id=inv.system_id,
                epistemic_kind="historical_observation",
                title=f"Observed Baseline: {inv.title}",
                summary=(
                    f"Historical observation on '{inv.target_service_key}' "
                    f"({inv.target_metric}): baseline mean="
                    f"{inv.baseline_summary_json.get('baseline_mean_ms', 'N/A')}ms."
                ),
                investigation_id=inv.id,
                predicted_outcome_json={},
                observed_outcome_json=inv.baseline_summary_json,
                validation_metrics_json={},
                provenance_json={
                    "epistemic_classification": "historical_observation",
                    "correlation_ids": inv.baseline_summary_json.get(
                        "correlation_ids", []
                    ),
                },
            )
            db.add(obs_mem)

            # 2. If concluded or experimental evidence exists, record experimental finding
            if inv.status in ("CONCLUDED", "INCONCLUSIVE") and inv.experiments_used > 0:
                exp_mem = ScientificMemoryEntryRecord(
                    system_id=inv.system_id,
                    epistemic_kind="experimental_evidence",
                    title=f"Experimental Finding: {inv.title} [{inv.status}]",
                    summary=inv.conclusion_summary
                    or f"Investigation finished with status {inv.status}.",
                    investigation_id=inv.id,
                    predicted_outcome_json={},
                    observed_outcome_json={
                        "status": inv.status,
                        "concluded_cause_service_key": inv.concluded_cause_service_key,
                        "concluded_mechanism": inv.concluded_mechanism,
                        "experiments_used": inv.experiments_used,
                    },
                    validation_metrics_json={},
                    provenance_json={
                        "epistemic_classification": "experimental_evidence",
                        "uncertainty_summary": inv.uncertainty_summary,
                    },
                )
                db.add(exp_mem)
            added = True

        if added:
            await db.commit()
