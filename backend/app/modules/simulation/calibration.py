"""Evidence-Based Digital Twin Calibration Engine (Milestone 03/05).

Implements:
- Dataset provenance tracking (trace_id, correlation_id, experiment_run_id).
- Strict Train vs. Held-Out Validation split by correlation transaction group.
- Intrinsic vs. downstream propagated latency decomposition on the Training split.
- Parameter uncertainty estimation (standard error and 95% confidence bounds).
- Held-out validation evaluation computing MAE, RMSE, Normalized Error %, and per-service residuals.
- Explicit rejection or warning when calibration evidence is insufficient.
"""

import math
import statistics
from collections import defaultdict
from copy import deepcopy
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CalibrationRunRecord,
    DigitalTwinModelRecord,
    ExperimentRun,
    MetricObservation,
    ScientificMemoryEntryRecord,
    SpanObservation,
)
from app.modules.laboratory.orchestrator import (
    LAB_SYSTEM_SLUG,
    SyntheticLabOrchestrator,
)
from app.modules.registry.service import RegistryService
from app.modules.simulation.schemas import TwinCalibrationRequest
from app.modules.simulation.simulator import (
    LivingDigitalTwinSimulator,
    default_lab_twin_parameters,
)


class TwinCalibrationEngine:
    """Calibrates versioned Digital Twin models from real stored telemetry and experiment runs."""

    @staticmethod
    async def calibrate_from_evidence(
        db: AsyncSession,
        request: TwinCalibrationRequest,
    ) -> tuple[DigitalTwinModelRecord, CalibrationRunRecord]:
        """Calibrate a new Digital Twin version and validate against held-out observations."""
        if request.system_slug == LAB_SYSTEM_SLUG:
            await SyntheticLabOrchestrator.ensure_lab_registered(db)
        system = await RegistryService.get_system_by_id_or_slug(db, request.system_slug)

        # Determine next version number for this system
        max_ver_stmt = select(func.max(DigitalTwinModelRecord.version_number)).where(
            DigitalTwinModelRecord.system_id == system.id
        )
        current_max_ver = (await db.execute(max_ver_stmt)).scalar_one_or_none() or 0
        next_ver = int(current_max_ver) + 1
        version_tag = request.version_tag or f"twin-v{next_ver}.0-calibrated"

        # 1. Fetch most recent SpanObservations and MetricObservations
        spans_stmt = (
            select(SpanObservation)
            .where(SpanObservation.system_id == system.id)
            .order_by(SpanObservation.started_at.desc())
            .limit(300)
        )
        spans = list(reversed(list((await db.execute(spans_stmt)).scalars().all())))

        metrics_stmt = (
            select(MetricObservation)
            .where(MetricObservation.system_id == system.id)
            .order_by(MetricObservation.observed_at.desc())
            .limit(300)
        )
        metrics = list(reversed(list((await db.execute(metrics_stmt)).scalars().all())))

        exp_runs_stmt = (
            select(ExperimentRun)
            .where(ExperimentRun.system_id == system.id)
            .order_by(ExperimentRun.created_at.desc())
            .limit(20)
        )
        exp_runs = list((await db.execute(exp_runs_stmt)).scalars().all())

        # Group spans by correlation_id (each correlation_id represents one multi-service trace)
        traces_by_corr: dict[str, list[SpanObservation]] = defaultdict(list)
        for sp in spans:
            traces_by_corr[sp.correlation_id].append(sp)

        corr_ids = list(traces_by_corr.keys())
        total_span_count = len(spans)
        warnings: list[str] = []

        # 2. Check minimum required evidence threshold
        if total_span_count < request.min_required_observations or len(corr_ids) < 2:
            msg = (
                f"Insufficient telemetry for reliable calibration: observed "
                f"{total_span_count} spans across {len(corr_ids)} traces, but minimum "
                f"required is {request.min_required_observations} spans (>= 2 traces)."
            )
            if request.strict_rejection:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=msg,
                )
            warnings.append(msg)
            base_params = default_lab_twin_parameters()
            rejected_model = DigitalTwinModelRecord(
                system_id=system.id,
                investigation_id=request.investigation_id,
                version_number=next_ver,
                version_tag=f"twin-v{next_ver}.0-insufficient-data",
                status="rejected_insufficient_data",
                calibration_method="rejected_due_to_insufficient_observations",
                parameters_json=base_params,
                parameter_uncertainty_json={},
                validity_bounds_json={"calibrated": False},
                calibration_summary_json={
                    "status": "rejected_insufficient_data",
                    "observed_span_count": total_span_count,
                    "min_required_observations": request.min_required_observations,
                },
                assumptions_json=[
                    "Fallback prior parameters only; NOT calibrated from empirical evidence."
                ],
                warnings_json=warnings,
                evidence_sources_json={
                    "span_count": total_span_count,
                    "correlation_ids": corr_ids,
                },
            )
            db.add(rejected_model)
            await db.flush()

            rejected_cal = CalibrationRunRecord(
                system_id=system.id,
                twin_model_id=rejected_model.id,
                investigation_id=request.investigation_id,
                status="rejected_insufficient_data",
                train_sample_count=0,
                validation_sample_count=0,
                train_correlation_ids_json=[],
                validation_correlation_ids_json=[],
                mae_ms=0.0,
                rmse_ms=0.0,
                normalized_error_pct=0.0,
                residuals_json=[],
                parameter_estimates_json={},
                validity_envelope_json={"calibrated": False},
                warnings_json=warnings,
            )
            db.add(rejected_cal)
            await db.commit()
            return rejected_model, rejected_cal

        # 3. Separate Training vs. Held-Out Validation sets (recent 25% of traces held out)
        # Use recent window (up to last 5 traces) so calibration reflects current system regime
        recent_corrs = corr_ids[-5:] if len(corr_ids) > 5 else corr_ids
        val_count = max(1, int(round(len(recent_corrs) * request.validation_split_ratio)))
        train_count = max(1, len(recent_corrs) - val_count)
        train_corrs = recent_corrs[:train_count]
        val_corrs = recent_corrs[train_count:]

        if len(recent_corrs) < 5:
            warnings.append(
                f"Low sample size warning: calibrated on {len(train_corrs)} training traces "
                f"and {len(val_corrs)} validation traces; parameter uncertainty intervals are wide."
            )

        params = deepcopy(default_lab_twin_parameters())
        services_cfg = params["services"]

        # 4. Decompose intrinsic service latency vs. downstream child latency on TRAINING set
        train_intrinsic_by_svc: dict[str, list[float]] = defaultdict(list)
        train_total_by_svc: dict[str, list[float]] = defaultdict(list)
        train_err_by_svc: dict[str, list[int]] = defaultdict(list)

        for cid in train_corrs:
            trace_spans = traces_by_corr[cid]
            dur_by_svc: dict[str, float] = {}
            for sp in trace_spans:
                dur_by_svc[sp.service_key] = max(
                    dur_by_svc.get(sp.service_key, 0.0), float(sp.duration_ms)
                )
                train_total_by_svc[sp.service_key].append(float(sp.duration_ms))
                train_err_by_svc[sp.service_key].append(
                    1 if (sp.status_code == "ERROR" or sp.http_status >= 500) else 0
                )

            for svc_key, total_dur in dur_by_svc.items():
                if svc_key not in services_cfg:
                    continue
                down_targets = services_cfg[svc_key].get("downstream_targets", [])
                down_sum = sum(dur_by_svc.get(dt, 0.0) for dt in down_targets)
                intrinsic = max(3.0, total_dur - down_sum)
                train_intrinsic_by_svc[svc_key].append(intrinsic)

        # Check saturation metrics for order-database-sim lock contention calibration
        db_sat_vals = [
            float(m.value)
            for m in metrics
            if m.service_key == "order-database-sim"
            and m.metric_name in ("db_lock_saturation_pct", "service_saturation_pct")
            and (m.correlation_id in train_corrs or not m.correlation_id)
        ]

        param_uncertainty: dict[str, Any] = {}
        param_estimates: dict[str, Any] = {}

        for svc_key, scfg in services_cfg.items():
            intr_samples = train_intrinsic_by_svc.get(svc_key, [])
            tot_samples = train_total_by_svc.get(svc_key, [])
            err_samples = train_err_by_svc.get(svc_key, [])

            if intr_samples:
                est_base = statistics.fmean(intr_samples)
                est_std = (
                    statistics.stdev(intr_samples)
                    if len(intr_samples) > 1
                    else max(1.5, est_base * 0.12)
                )
                se_base = est_std / math.sqrt(len(intr_samples))
                scfg["base_latency_ms"] = round(est_base, 2)
                scfg["latency_std_ms"] = round(max(1.0, est_std), 2)
            else:
                est_base = float(scfg["base_latency_ms"])
                est_std = float(scfg["latency_std_ms"])
                se_base = est_base * 0.20
                warnings.append(
                    f"Parameter identification warning: no training spans observed "
                    f"for '{svc_key}'; retaining prior nominal parameter."
                )

            if err_samples:
                scfg["error_base_probability"] = round(
                    max(0.001, statistics.fmean(err_samples)), 4
                )

            # Calibrate DB lock contention factor when order-database-sim is slow or saturated
            if svc_key == "order-database-sim":
                mean_db_sat = statistics.fmean(db_sat_vals) if db_sat_vals else 18.0
                if est_base > 80.0 or mean_db_sat > 65.0:
                    # Allocate part of observed DB delay to lock contention physics
                    scfg["db_lock_contention_factor"] = round(
                        min(2.2, max(0.85, (est_base / 120.0))), 3
                    )
                    scfg["base_latency_ms"] = round(max(14.0, est_base * 0.25), 2)
                    scfg["db_connection_capacity"] = 34.0
                else:
                    scfg["db_lock_contention_factor"] = 0.12
                    scfg["db_connection_capacity"] = 85.0

            base_lat_val = float(scfg["base_latency_ms"])
            param_uncertainty[svc_key] = {
                "sample_count": len(intr_samples),
                "base_latency_mean_ms": base_lat_val,
                "base_latency_se_ms": round(se_base, 2),
                "ci_95_lower_ms": round(max(1.0, base_lat_val - 1.96 * se_base), 2),
                "ci_95_upper_ms": round(base_lat_val + 1.96 * se_base, 2),
                "observed_total_mean_ms": (
                    round(statistics.fmean(tot_samples), 2) if tot_samples else None
                ),
            }
            param_estimates[svc_key] = {
                "base_latency_ms": scfg["base_latency_ms"],
                "latency_std_ms": scfg["latency_std_ms"],
                "processing_capacity_rps": scfg["processing_capacity_rps"],
                "replica_count": scfg["replica_count"],
                "db_lock_contention_factor": scfg["db_lock_contention_factor"],
            }

        # 5. Evaluate calibrated model on HELD-OUT VALIDATION set (never used in fitting)
        sim_val = LivingDigitalTwinSimulator(model_parameters=params, random_seed=101)
        val_traj, _, _ = sim_val.run_horizon(horizon_seconds=12.0, dt_seconds=1.0)
        predicted_mean_by_svc: dict[str, float] = {}
        for skey in services_cfg:
            predicted_mean_by_svc[skey] = statistics.fmean(
                float(f["services"][skey]["mean_latency_ms"]) for f in val_traj
            )

        residuals: list[dict[str, Any]] = []
        abs_errors: list[float] = []
        sq_errors: list[float] = []
        obs_values: list[float] = []

        for cid in val_corrs:
            for sp in traces_by_corr[cid]:
                if sp.service_key not in predicted_mean_by_svc:
                    continue
                obs_val = float(sp.duration_ms)
                pred_val = float(predicted_mean_by_svc[sp.service_key])
                err = pred_val - obs_val
                abs_errors.append(abs(err))
                sq_errors.append(err * err)
                obs_values.append(obs_val)
                residuals.append(
                    {
                        "correlation_id": cid,
                        "service_key": sp.service_key,
                        "observed_latency_ms": round(obs_val, 2),
                        "predicted_latency_ms": round(pred_val, 2),
                        "residual_ms": round(err, 2),
                    }
                )

        mae_ms = round(statistics.fmean(abs_errors), 2) if abs_errors else 0.0
        rmse_ms = round(math.sqrt(statistics.fmean(sq_errors)), 2) if sq_errors else 0.0
        mean_obs = statistics.fmean(obs_values) if obs_values else 1.0
        norm_err_pct = round((mae_ms / max(1.0, mean_obs)) * 100.0, 2)

        if norm_err_pct > 25.0:
            warnings.append(
                f"Calibration residual warning: held-out normalized error is {norm_err_pct}% "
                "(model exhibits elevated variance across multi-service jitter)."
            )

        validity_bounds = {
            "calibrated": True,
            "arrival_rate_rps_range": [10.0, 110.0],
            "replica_count_range": [1, 8],
            "concurrency_limit_range": [10, 240],
            "extrapolation_warning": (
                "Simulations with incoming traffic > 110 req/s or replica count > 8 extrapolate "
                "beyond empirical laboratory observations."
            ),
        }

        assumptions = [
            (
                "Service latencies decompose into intrinsic processing, queueing wait, "
                "DB lock contention, and downstream RPC propagation."
            ),
            (
                "Shared database row-lock contention scales quadratically with concurrent "
                "upstream checkout workers once DB connection saturation exceeds 70%."
            ),
            (
                "Circuit breakers shed slow downstream RPCs above threshold at the cost "
                "of bounded fast-fail fallback responses."
            ),
            (
                "Held-out validation metrics (MAE, RMSE, NRMSE) are computed strictly on "
                "traces excluded from parameter estimation."
            ),
        ]

        evidence_sources = {
            "total_spans_considered": sum(len(traces_by_corr[c]) for c in recent_corrs),
            "train_trace_count": len(train_corrs),
            "validation_trace_count": len(val_corrs),
            "train_correlation_ids": train_corrs,
            "validation_correlation_ids": val_corrs,
            "experiment_run_ids": [r.id for r in exp_runs[:5]],
        }

        cal_summary = {
            "mae_ms": mae_ms,
            "rmse_ms": rmse_ms,
            "normalized_error_pct": norm_err_pct,
            "train_sample_count": sum(len(traces_by_corr[c]) for c in train_corrs),
            "validation_sample_count": len(residuals),
            "validation_split_ratio": request.validation_split_ratio,
        }

        twin_record = DigitalTwinModelRecord(
            system_id=system.id,
            investigation_id=request.investigation_id,
            version_number=next_ver,
            version_tag=version_tag,
            status="calibrated" if norm_err_pct <= 30.0 else "degraded_validity",
            calibration_method="intrinsic_decomposition_and_heldout_validation",
            parameters_json=params,
            parameter_uncertainty_json=param_uncertainty,
            validity_bounds_json=validity_bounds,
            calibration_summary_json=cal_summary,
            assumptions_json=assumptions,
            warnings_json=warnings,
            evidence_sources_json=evidence_sources,
        )
        db.add(twin_record)
        await db.flush()

        cal_record = CalibrationRunRecord(
            system_id=system.id,
            twin_model_id=twin_record.id,
            investigation_id=request.investigation_id,
            status="completed" if not warnings else "warning_low_data",
            train_sample_count=sum(len(traces_by_corr[c]) for c in train_corrs),
            validation_sample_count=len(residuals),
            train_correlation_ids_json=train_corrs,
            validation_correlation_ids_json=val_corrs,
            mae_ms=mae_ms,
            rmse_ms=rmse_ms,
            normalized_error_pct=norm_err_pct,
            residuals_json=residuals[:40],
            parameter_estimates_json=param_estimates,
            validity_envelope_json=validity_bounds,
            warnings_json=warnings,
        )
        db.add(cal_record)

        # Record in Scientific Memory
        mem_entry = ScientificMemoryEntryRecord(
            system_id=system.id,
            epistemic_kind="calibrated_model",
            title=f"Calibrated Digital Twin {version_tag}",
            summary=(
                f"Calibrated Digital Twin {version_tag} on {len(train_corrs)} training traces "
                f"and validated on {len(val_corrs)} held-out traces "
                f"(MAE={mae_ms}ms, RMSE={rmse_ms}ms, NRMSE={norm_err_pct}%)."
            ),
            investigation_id=request.investigation_id,
            twin_model_id=twin_record.id,
            predicted_outcome_json={
                "predicted_service_latencies_ms": {
                    k: round(v, 2) for k, v in predicted_mean_by_svc.items()
                }
            },
            observed_outcome_json={
                "heldout_sample_count": len(residuals),
                "validation_correlation_ids": val_corrs,
            },
            validation_metrics_json=cal_summary,
            provenance_json=evidence_sources,
        )
        db.add(mem_entry)
        await db.commit()
        return twin_record, cal_record
