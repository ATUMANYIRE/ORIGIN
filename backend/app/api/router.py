"""Unified REST + OTLP + SSE + Causal Investigation API Router for ORIGIN (Milestone 02/05)."""

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.models import (
    EvidenceRecord,
    ExperimentDefinition,
    ExperimentRun,
    HypothesisRecord,
)
from app.db.session import get_db
from app.modules.agents.contract import get_module_contract_status as get_agents_status
from app.modules.agents.investigator import AutonomousInvestigatorService
from app.modules.agents.schemas import (
    InvestigationCreateRequest,
    InvestigationDetailRead,
    InvestigationRead,
)
from app.modules.auth.dependencies import (
    AuthenticatedPrincipal,
    get_correlation_id,
    verify_api_key,
    verify_benchmark_controller,
)
from app.modules.evidence.contract import (
    get_module_contract_status as get_evidence_status,
)
from app.modules.evidence.schemas import EvidenceRead, HypothesisRead
from app.modules.experimentation.contract import (
    get_module_contract_status as get_experimentation_status,
)
from app.modules.experimentation.schemas import (
    ExperimentDefinitionRead,
    ExperimentRunRead,
)
from app.modules.laboratory.benchmark_controller import (
    BenchmarkControllerService,
    BenchmarkMatrixResponse,
    BenchmarkRunRead,
    BenchmarkScenarioRequest,
)
from app.modules.laboratory.orchestrator import (
    ALLOWLISTED_INTERVENTIONS,
    ALLOWLISTED_REMEDIATION_ACTIONS,
    LabExecutionResult,
    LabFaultState,
    LabProfileType,
    LabTransactionRequest,
    PrivateLabGroundTruthState,
    SyntheticLabOrchestrator,
    clear_lab_unsafe_lock,
    get_lab_state,
    get_private_ground_truth_for_evaluator,
    is_lab_unsafe_locked,
    set_lab_profile,
)
from app.modules.recovery.policy import SafetyPolicyEngine
from app.modules.recovery.schemas import (
    ApprovalRecordRead,
    CandidateGenerationRequest,
    ManualRollbackRequest,
    PlanMutationRequest,
    RecoveryApprovalRequest,
    RecoveryExecutionRequest,
    RecoveryPlanDetailRead,
    RecoveryPlanRead,
    RecoveryWorkflowCreateRequest,
    SandboxVerifyRequest,
)
from app.modules.recovery.service import AutonomousRecoveryService
from app.modules.registry.schemas import (
    DependencyCreate,
    DependencyRead,
    ServiceCreate,
    ServiceRead,
    SystemCreate,
    SystemDetailRead,
    SystemRead,
)
from app.modules.registry.service import RegistryService
from app.modules.safety.service import (
    AuditEventRead,
    AuditService,
    SafetyEnvelopeContract,
)
from app.modules.simulation.contract import (
    get_module_contract_status as get_simulation_status,
)
from app.modules.simulation.schemas import (
    BranchComparisonResponse,
    CalibrationRunRead,
    DigitalTwinModelRead,
    HypothesisSimulationRequest,
    ScientificMemoryEntryRead,
    SimulationBenchmarkSuiteResponse,
    SimulationBranchCreateRequest,
    SimulationBranchRead,
    SimulationSnapshotRead,
    SnapshotCreateRequest,
    TwinCalibrationRequest,
)
from app.modules.simulation.service import DigitalTwinService, ScientificMemoryService
from app.modules.simulation.simulator import ALLOWLISTED_TWIN_INTERVENTIONS
from app.modules.telemetry.schemas import (
    MetricSeriesSummary,
    OTLPMetricsPayload,
    OTLPTracesPayload,
    SpanRead,
    TelemetryBatchIn,
    TelemetryIngestionReceipt,
)
from app.modules.telemetry.service import TelemetryService
from app.modules.topology.schemas import TopologyGraphResponse
from app.modules.topology.service import TopologyService

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health", tags=["platform"])
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Deep health check verifying database connectivity, Redis, and public lab view."""
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_info = await event_bus.redis_status()
    lab_state = get_lab_state()
    return {
        "status": "healthy" if db_ok else "degraded",
        "platform": "ORIGIN",
        "tagline": "Give software the ability to understand itself.",
        "milestone": "02/05 — Autonomous Causal Scientist & Experimental Discovery Engine",
        "timestamp": datetime.now(UTC).isoformat(),
        "database_connected": db_ok,
        "redis": redis_info,
        "laboratory_profile": lab_state.profile,
        "laboratory_blinded": lab_state.blinded,
    }


# ---------------------------------------------------------------------------
# Boundary 2: System, Service, and Dependency Registry
# ---------------------------------------------------------------------------


@api_router.get("/systems", response_model=list[SystemRead], tags=["registry"])
async def list_systems(
    db: AsyncSession = Depends(get_db),
) -> list[SystemRead]:
    """List all registered systems with live telemetry and topology counts."""
    return await RegistryService.list_systems(db)


@api_router.post(
    "/systems",
    response_model=SystemRead,
    status_code=status.HTTP_201_CREATED,
    tags=["registry"],
)
async def create_system(
    payload: SystemCreate,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
    correlation_id: str = Depends(get_correlation_id),
) -> SystemRead:
    """Register a new system or update metadata for an existing system slug."""
    system = await RegistryService.create_or_get_system(
        db, payload, actor=principal.actor, correlation_id=correlation_id
    )
    await db.commit()
    stats = await RegistryService.compute_system_stats(db, system.id)
    read_obj = SystemRead.model_validate(system)
    read_obj.stats = stats
    return read_obj


@api_router.get(
    "/systems/{system_id}",
    response_model=SystemDetailRead,
    tags=["registry"],
)
async def get_system_detail(
    system_id: str,
    db: AsyncSession = Depends(get_db),
) -> SystemDetailRead:
    """Get comprehensive system details including services, dependencies, and sources."""
    return await RegistryService.get_system_detail(db, system_id)


@api_router.post(
    "/systems/{system_id}/services",
    response_model=ServiceRead,
    status_code=status.HTTP_201_CREATED,
    tags=["registry"],
)
async def register_service(
    system_id: str,
    payload: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
    correlation_id: str = Depends(get_correlation_id),
) -> ServiceRead:
    """Register or update a service within a system."""
    svc = await RegistryService.register_service(
        db,
        system_id,
        payload,
        actor=principal.actor,
        correlation_id=correlation_id,
    )
    await db.commit()
    return ServiceRead.model_validate(svc)


@api_router.post(
    "/systems/{system_id}/dependencies",
    response_model=DependencyRead,
    status_code=status.HTTP_201_CREATED,
    tags=["registry"],
)
async def register_dependency(
    system_id: str,
    payload: DependencyCreate,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
    correlation_id: str = Depends(get_correlation_id),
) -> DependencyRead:
    """Declare an explicit directed dependency between two services."""
    dep = await RegistryService.register_dependency(
        db,
        system_id,
        payload,
        actor=principal.actor,
        correlation_id=correlation_id,
    )
    await db.commit()
    return DependencyRead.model_validate(dep)


# ---------------------------------------------------------------------------
# Boundary 3: OpenTelemetry Ingestion, Time-Series Queries & SSE Stream
# ---------------------------------------------------------------------------


@api_router.post(
    "/telemetry/ingest",
    response_model=TelemetryIngestionReceipt,
    status_code=status.HTTP_201_CREATED,
    tags=["telemetry"],
)
async def ingest_telemetry_batch(
    payload: TelemetryBatchIn,
    db: AsyncSession = Depends(get_db),
) -> TelemetryIngestionReceipt:
    """Ingest a structured batch of OpenTelemetry spans and metric observations."""
    return await TelemetryService.ingest_batch(db, payload)


@api_router.post(
    "/telemetry/otlp/v1/traces",
    response_model=list[TelemetryIngestionReceipt],
    status_code=status.HTTP_201_CREATED,
    tags=["telemetry"],
)
async def ingest_otlp_traces(
    payload: OTLPTracesPayload,
    db: AsyncSession = Depends(get_db),
) -> list[TelemetryIngestionReceipt]:
    """Standard OpenTelemetry OTLP/HTTP JSON Traces ingestion endpoint."""
    return await TelemetryService.ingest_otlp_traces(db, payload)


@api_router.post(
    "/telemetry/otlp/v1/metrics",
    response_model=list[TelemetryIngestionReceipt],
    status_code=status.HTTP_201_CREATED,
    tags=["telemetry"],
)
async def ingest_otlp_metrics(
    payload: OTLPMetricsPayload,
    db: AsyncSession = Depends(get_db),
) -> list[TelemetryIngestionReceipt]:
    """Standard OpenTelemetry OTLP/HTTP JSON Metrics ingestion endpoint."""
    return await TelemetryService.ingest_otlp_metrics(db, payload)


@api_router.get(
    "/telemetry/metrics",
    response_model=MetricSeriesSummary,
    tags=["telemetry"],
)
async def query_metrics(
    system_id: str = Query(default="origin-synthetic-lab"),
    metric_name: str = Query(default="request_latency_ms"),
    service_key: str | None = Query(default=None),
    limit: int = Query(default=120, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> MetricSeriesSummary:
    """Query time-series metric observations and statistical aggregations."""
    return await TelemetryService.query_metric_series(
        db,
        system_identifier=system_id,
        metric_name=metric_name,
        service_key=service_key,
        limit=limit,
    )


@api_router.get(
    "/telemetry/spans",
    response_model=list[SpanRead],
    tags=["telemetry"],
)
async def query_spans(
    system_id: str = Query(default="origin-synthetic-lab"),
    correlation_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    service_key: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[SpanRead]:
    """Query distributed trace spans filtered by system, correlation_id, or trace_id."""
    return await TelemetryService.list_recent_spans(
        db,
        system_identifier=system_id,
        correlation_id=correlation_id,
        trace_id=trace_id,
        service_key=service_key,
        limit=limit,
    )


@api_router.get("/telemetry/stream", tags=["telemetry"])
async def stream_telemetry_events() -> StreamingResponse:
    """Server-Sent Events (SSE) stream pushing live telemetry, topology, & investigation events."""

    async def event_generator() -> AsyncGenerator[str, None]:
        queue = event_bus.subscribe()
        try:
            init_payload = {
                "event_type": "stream.connected",
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {"status": "subscribed"},
            }
            yield f"data: {json.dumps(init_payload)}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except TimeoutError:
                    heartbeat = {
                        "event_type": "stream.heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "payload": {},
                    }
                    yield f"data: {json.dumps(heartbeat)}\n\n"
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Boundary 4: Topology Discovery & Graph Generation
# ---------------------------------------------------------------------------


@api_router.get(
    "/systems/{system_id}/topology",
    response_model=TopologyGraphResponse,
    tags=["topology"],
)
async def get_system_topology(
    system_id: str,
    db: AsyncSession = Depends(get_db),
) -> TopologyGraphResponse:
    """Synthesize the provenance-verified topology graph for a registered system."""
    return await TopologyService.build_topology_graph(db, system_id)


# ---------------------------------------------------------------------------
# Synthetic Distributed System Laboratory Controller
# ---------------------------------------------------------------------------


@api_router.get(
    "/lab/status",
    response_model=LabFaultState,
    tags=["laboratory"],
)
async def get_laboratory_status() -> LabFaultState:
    """Inspect the public view of the Synthetic Laboratory (masks hidden faults when blinded)."""
    return get_lab_state()


@api_router.post(
    "/lab/profile/{profile}",
    response_model=LabFaultState,
    tags=["laboratory"],
)
async def update_laboratory_profile(
    profile: LabProfileType,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
    correlation_id: str = Depends(get_correlation_id),
) -> LabFaultState:
    """Switch the Synthetic Laboratory operating profile (unblinded operator mode)."""
    state = set_lab_profile(profile, blinded=False)
    sys_id = await SyntheticLabOrchestrator.ensure_lab_registered(
        db, actor=principal.actor, correlation_id=correlation_id
    )
    await AuditService.record_event(
        db,
        system_id=sys_id,
        actor=principal.actor,
        action="laboratory.profile_changed",
        resource_type="synthetic_laboratory",
        resource_id=profile,
        severity="warning" if profile != "normal" else "info",
        correlation_id=correlation_id,
        details=state.model_dump(mode="json"),
    )
    await db.commit()
    return state


@api_router.post(
    "/lab/execute",
    response_model=LabExecutionResult,
    tags=["laboratory"],
)
async def execute_laboratory_workload(
    request: LabTransactionRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
    correlation_id: str = Depends(get_correlation_id),
) -> LabExecutionResult:
    """Trigger real instrumented multi-service requests through the Synthetic Laboratory."""
    return await SyntheticLabOrchestrator.run_workload(
        db,
        request=request,
        actor=principal.actor,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Boundaries 5, 7, 8: Autonomous Causal Investigations, Experiments & Evidence
# ---------------------------------------------------------------------------


@api_router.get("/experiments/interventions", tags=["experimentation"])
async def list_allowlisted_interventions() -> dict[str, Any]:
    """List allowlisted experimental interventions permitted in the Synthetic Laboratory."""
    return {
        "allowlisted_interventions": ALLOWLISTED_INTERVENTIONS,
        "safety_policy": (
            "Arbitrary shell commands and untrusted code execution are strictly prohibited. "
            "Only allowlisted laboratory interventions may be scheduled."
        ),
    }


@api_router.post(
    "/investigations",
    response_model=InvestigationDetailRead,
    status_code=status.HTTP_201_CREATED,
    tags=["investigations"],
)
async def create_investigation(
    payload: InvestigationCreateRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
    correlation_id: str = Depends(get_correlation_id),
) -> InvestigationDetailRead:
    """Create a new autonomous scientific investigation and optionally run it immediately."""
    inv = await AutonomousInvestigatorService.create_investigation(
        db,
        request=payload,
        actor=principal.actor,
        correlation_id=correlation_id,
    )
    if payload.auto_run:
        return await AutonomousInvestigatorService.run_investigation(
            db, inv.id, actor=principal.actor
        )
    return await AutonomousInvestigatorService.get_investigation_detail(db, inv.id)


@api_router.get(
    "/investigations",
    response_model=list[InvestigationRead],
    tags=["investigations"],
)
async def list_investigations(
    system_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[InvestigationRead]:
    """List recent autonomous scientific investigations."""
    return await AutonomousInvestigatorService.list_investigations(
        db, system_id=system_id, limit=limit
    )


@api_router.get(
    "/investigations/{investigation_id}",
    response_model=InvestigationDetailRead,
    tags=["investigations"],
)
async def get_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
) -> InvestigationDetailRead:
    """Inspect an investigation including its hypotheses, experiments, runs, and evidence."""
    return await AutonomousInvestigatorService.get_investigation_detail(db, investigation_id)


@api_router.post(
    "/investigations/{investigation_id}/start",
    response_model=InvestigationDetailRead,
    tags=["investigations"],
)
async def start_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> InvestigationDetailRead:
    """Start or resume an investigation that is in CREATED state."""
    return await AutonomousInvestigatorService.run_investigation(
        db, investigation_id, actor=principal.actor
    )


@api_router.post(
    "/investigations/{investigation_id}/cancel",
    response_model=InvestigationRead,
    tags=["investigations"],
)
async def cancel_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> InvestigationRead:
    """Cancel an active or pending investigation."""
    inv = await AutonomousInvestigatorService.cancel_investigation(
        db, investigation_id, actor=principal.actor
    )
    return InvestigationRead.model_validate(inv)


@api_router.get(
    "/investigations/{investigation_id}/hypotheses",
    response_model=list[HypothesisRead],
    tags=["investigations"],
)
async def get_investigation_hypotheses(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[HypothesisRead]:
    """Retrieve competing causal hypotheses for an investigation."""
    await AutonomousInvestigatorService.get_investigation_model(db, investigation_id)
    rows = list(
        (
            await db.execute(
                select(HypothesisRecord)
                .where(HypothesisRecord.investigation_id == investigation_id)
                .order_by(HypothesisRecord.confidence_score.desc())
            )
        )
        .scalars()
        .all()
    )
    return [HypothesisRead.model_validate(r) for r in rows]


@api_router.get(
    "/investigations/{investigation_id}/experiments",
    tags=["investigations"],
)
async def get_investigation_experiments(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve experiment plans and trial execution results for an investigation."""
    await AutonomousInvestigatorService.get_investigation_model(db, investigation_id)
    plans = list(
        (
            await db.execute(
                select(ExperimentDefinition)
                .where(ExperimentDefinition.investigation_id == investigation_id)
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
                .where(ExperimentRun.investigation_id == investigation_id)
                .order_by(ExperimentRun.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "investigation_id": investigation_id,
        "experiment_plans": [
            ExperimentDefinitionRead.model_validate(p).model_dump(mode="json") for p in plans
        ],
        "experiment_runs": [
            ExperimentRunRead.model_validate(r).model_dump(mode="json") for r in runs
        ],
    }


@api_router.get(
    "/investigations/{investigation_id}/evidence",
    response_model=list[EvidenceRead],
    tags=["investigations"],
)
async def get_investigation_evidence(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceRead]:
    """Inspect immutable scientific evidence records for an investigation."""
    await AutonomousInvestigatorService.get_investigation_model(db, investigation_id)
    rows = list(
        (
            await db.execute(
                select(EvidenceRecord)
                .where(EvidenceRecord.investigation_id == investigation_id)
                .order_by(EvidenceRecord.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [EvidenceRead.model_validate(r) for r in rows]


@api_router.get(
    "/investigations/{investigation_id}/export",
    tags=["investigations"],
)
async def export_investigation_report(
    investigation_id: str,
    format: Literal["markdown", "json"] = Query(default="markdown"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export a reproducible scientific investigation report in Markdown and JSON."""
    return await AutonomousInvestigatorService.export_investigation_report(
        db, investigation_id, report_format=format
    )


@api_router.post(
    "/investigations/{investigation_id}/simulate",
    tags=["investigations", "digital-twin"],
)
async def simulate_investigation_hypothesis(
    investigation_id: str,
    payload: HypothesisSimulationRequest,
    db: AsyncSession = Depends(get_db),
    _principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> dict[str, Any]:
    """Simulate a causal hypothesis inside the calibrated Digital Twin with epistemic disclosure."""
    return await DigitalTwinService.simulate_hypothesis_for_investigation(
        db, investigation_id, payload
    )


# ---------------------------------------------------------------------------
# Boundary 6: Living Digital Twin, Counterfactual Branches & Scientific Memory
# ---------------------------------------------------------------------------


@api_router.get("/twins/interventions", tags=["digital-twin"])
async def list_twin_interventions() -> dict[str, Any]:
    """List allowlisted counterfactual interventions supported by the Digital Twin Engine."""
    return {
        "allowlisted_twin_interventions": sorted(ALLOWLISTED_TWIN_INTERVENTIONS),
        "epistemic_notice": (
            "Digital Twin interventions operate strictly on in-memory/persisted simulation "
            "models and never mutate live production or laboratory infrastructure."
        ),
    }


@api_router.post(
    "/twins/calibrate",
    status_code=status.HTTP_201_CREATED,
    tags=["digital-twin"],
)
async def calibrate_digital_twin(
    payload: TwinCalibrationRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
    correlation_id: str = Depends(get_correlation_id),
) -> dict[str, Any]:
    """Calibrate a new versioned Digital Twin model from stored telemetry and experiments."""
    return await DigitalTwinService.create_or_calibrate_twin(
        db,
        request=payload,
        actor=principal.actor,
        correlation_id=correlation_id,
    )


@api_router.get(
    "/twins",
    response_model=list[DigitalTwinModelRead],
    tags=["digital-twin"],
)
async def list_digital_twins(
    system_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[DigitalTwinModelRead]:
    """List calibrated Digital Twin model versions."""
    return await DigitalTwinService.list_twin_models(db, system_id=system_id, limit=limit)


@api_router.get(
    "/twins/{twin_model_id}",
    response_model=DigitalTwinModelRead,
    tags=["digital-twin"],
)
async def get_digital_twin(
    twin_model_id: str,
    db: AsyncSession = Depends(get_db),
) -> DigitalTwinModelRead:
    """Retrieve metadata, parameters, validity bounds, and warnings for a Digital Twin model."""
    rec = await DigitalTwinService.get_twin_model_record(db, twin_model_id)
    return DigitalTwinModelRead.model_validate(rec)


@api_router.get(
    "/twins/{twin_model_id}/calibrations",
    response_model=list[CalibrationRunRead],
    tags=["digital-twin"],
)
async def get_twin_calibrations(
    twin_model_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[CalibrationRunRead]:
    """Inspect calibration runs, held-out residuals, and quality metrics for a Digital Twin."""
    return await DigitalTwinService.list_calibration_runs(db, twin_model_id=twin_model_id)


@api_router.post(
    "/simulations/snapshots",
    response_model=SimulationSnapshotRead,
    status_code=status.HTTP_201_CREATED,
    tags=["digital-twin"],
)
async def create_simulation_snapshot(
    payload: SnapshotCreateRequest,
    db: AsyncSession = Depends(get_db),
    _principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> SimulationSnapshotRead:
    """Create a serializable simulation snapshot for deterministic rewind and branching."""
    return await DigitalTwinService.create_snapshot(db, payload)


@api_router.get(
    "/simulations/snapshots",
    response_model=list[SimulationSnapshotRead],
    tags=["digital-twin"],
)
async def list_simulation_snapshots(
    twin_model_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[SimulationSnapshotRead]:
    """List saved simulation state snapshots."""
    return await DigitalTwinService.list_snapshots(db, twin_model_id=twin_model_id, limit=limit)


@api_router.get(
    "/simulations/snapshots/{snapshot_id}",
    response_model=SimulationSnapshotRead,
    tags=["digital-twin"],
)
async def get_simulation_snapshot(
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> SimulationSnapshotRead:
    """Inspect a saved simulation snapshot including RNG and pending event state."""
    rec = await DigitalTwinService.get_snapshot_record(db, snapshot_id)
    return SimulationSnapshotRead.model_validate(rec)


@api_router.post(
    "/simulations/branches",
    response_model=SimulationBranchRead,
    status_code=status.HTTP_201_CREATED,
    tags=["digital-twin"],
)
async def create_simulation_branch(
    payload: SimulationBranchCreateRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
    correlation_id: str = Depends(get_correlation_id),
) -> SimulationBranchRead:
    """Run a baseline or counterfactual simulation branch from a Digital Twin or snapshot."""
    return await DigitalTwinService.create_and_run_branch(
        db,
        request=payload,
        actor=principal.actor,
        correlation_id=correlation_id,
    )


@api_router.get(
    "/simulations/branches",
    response_model=list[SimulationBranchRead],
    tags=["digital-twin"],
)
async def list_simulation_branches(
    twin_model_id: str | None = Query(default=None),
    system_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[SimulationBranchRead]:
    """List baseline and counterfactual simulation branches."""
    return await DigitalTwinService.list_branches(
        db, twin_model_id=twin_model_id, system_id=system_id, limit=limit
    )


@api_router.get(
    "/simulations/branches/{branch_id}",
    response_model=SimulationBranchRead,
    tags=["digital-twin"],
)
async def get_simulation_branch(
    branch_id: str,
    db: AsyncSession = Depends(get_db),
) -> SimulationBranchRead:
    """Retrieve full trajectory, event log, outcome summary, and uncertainty for a branch."""
    rec = await DigitalTwinService.get_branch_record(db, branch_id)
    return SimulationBranchRead.model_validate(rec)


@api_router.post(
    "/simulations/branches/{branch_id}/cancel",
    response_model=SimulationBranchRead,
    tags=["digital-twin"],
)
async def cancel_simulation_branch(
    branch_id: str,
    db: AsyncSession = Depends(get_db),
    _principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> SimulationBranchRead:
    """Cancel a simulation branch."""
    return await DigitalTwinService.cancel_branch(db, branch_id)


@api_router.get(
    "/simulations/compare",
    response_model=BranchComparisonResponse,
    tags=["digital-twin"],
)
async def compare_simulation_branches(
    baseline_branch_id: str = Query(...),
    alternative_branch_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> BranchComparisonResponse:
    """Compare a baseline simulation branch against an alternative counterfactual branch."""
    return await DigitalTwinService.compare_branches(
        db,
        baseline_branch_id=baseline_branch_id,
        alternative_branch_id=alternative_branch_id,
    )


@api_router.get(
    "/simulations/branches/{branch_id}/export",
    tags=["digital-twin"],
)
async def export_simulation_branch_report(
    branch_id: str,
    compare_with_branch_id: str | None = Query(default=None),
    format: Literal["markdown", "json"] = Query(default="markdown"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export a reproducible Markdown & JSON report for a simulation branch."""
    return await DigitalTwinService.export_simulation_report(
        db,
        branch_id=branch_id,
        compare_with_branch_id=compare_with_branch_id,
        report_format=format,
    )


@api_router.post(
    "/simulations/benchmarks/run",
    response_model=SimulationBenchmarkSuiteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["digital-twin"],
)
async def run_digital_twin_benchmarks(
    random_seed: int = Query(default=2026, ge=1, le=999999),
    db: AsyncSession = Depends(get_db),
    _principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> SimulationBenchmarkSuiteResponse:
    """Execute all 4 canonical Milestone 03/05 Digital Twin benchmarks (A, B, C, D)."""
    return await DigitalTwinService.run_simulation_benchmarks(db, random_seed=random_seed)


@api_router.get(
    "/memory/entries",
    response_model=list[ScientificMemoryEntryRead],
    tags=["scientific-memory"],
)
async def list_scientific_memory(
    system_id: str | None = Query(default=None),
    epistemic_kind: str | None = Query(default=None),
    limit: int = Query(default=80, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[ScientificMemoryEntryRead]:
    """Query persistent Scientific Memory (observations, experiments, models, predictions)."""
    return await ScientificMemoryService.list_memory_entries(
        db,
        system_id=system_id,
        epistemic_kind=epistemic_kind,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Protected Benchmark Controller & Hidden-Fault Evaluator Endpoints
# (Requires X-Benchmark-Controller-Key; rejects Investigator credentials with 403)
# ---------------------------------------------------------------------------


@api_router.get(
    "/benchmarks/ground-truth",
    response_model=PrivateLabGroundTruthState,
    tags=["benchmarks"],
)
async def inspect_private_ground_truth(
    _controller: AuthenticatedPrincipal = Depends(verify_benchmark_controller),
) -> PrivateLabGroundTruthState:
    """Inspect private laboratory ground truth (Strictly restricted to Benchmark Controller)."""
    return get_private_ground_truth_for_evaluator()


@api_router.post(
    "/benchmarks/stage-hidden-fault/{profile}",
    tags=["benchmarks"],
)
async def stage_hidden_fault(
    profile: LabProfileType,
    _controller: AuthenticatedPrincipal = Depends(verify_benchmark_controller),
) -> dict[str, Any]:
    """Stage a hidden fault in blinded mode (Benchmark Controller only)."""
    return BenchmarkControllerService.stage_blinded_hidden_fault(profile)


@api_router.post(
    "/benchmarks/run",
    response_model=BenchmarkRunRead,
    status_code=status.HTTP_201_CREATED,
    tags=["benchmarks"],
)
async def run_single_benchmark(
    payload: BenchmarkScenarioRequest,
    db: AsyncSession = Depends(get_db),
    _controller: AuthenticatedPrincipal = Depends(verify_benchmark_controller),
) -> BenchmarkRunRead:
    """Execute a blinded hidden-fault benchmark and evaluate Investigator conclusion."""
    return await BenchmarkControllerService.run_single_benchmark(db, payload)


@api_router.post(
    "/benchmarks/matrix",
    response_model=BenchmarkMatrixResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["benchmarks"],
)
async def run_benchmark_matrix(
    random_seed: int = Query(default=2026, ge=1, le=999999),
    db: AsyncSession = Depends(get_db),
    _controller: AuthenticatedPrincipal = Depends(verify_benchmark_controller),
) -> BenchmarkMatrixResponse:
    """Execute the full 5-scenario hidden-fault benchmark matrix and return scores."""
    return await BenchmarkControllerService.run_benchmark_matrix(db, random_seed=random_seed)


@api_router.get(
    "/benchmarks/runs",
    response_model=list[BenchmarkRunRead],
    tags=["benchmarks"],
)
async def list_benchmark_runs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _controller: AuthenticatedPrincipal = Depends(verify_benchmark_controller),
) -> list[BenchmarkRunRead]:
    """List private benchmark evaluation runs (Benchmark Controller only)."""
    return await BenchmarkControllerService.list_benchmark_runs(db, limit=limit)


# ---------------------------------------------------------------------------
# Safety Audit & Architectural Boundaries
# ---------------------------------------------------------------------------


@api_router.get(
    "/safety/audit-events",
    response_model=list[AuditEventRead],
    tags=["safety"],
)
async def list_audit_events(
    system_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEventRead]:
    """List immutable safety and operational audit events."""
    rows = await AuditService.list_events(db, system_id=system_id, limit=limit)
    return [AuditEventRead.model_validate(r) for r in rows]


@api_router.get("/safety/policies", tags=["safety"])
async def get_safety_policy_rules() -> dict[str, Any]:
    """Return the fail-closed Operational Safety Policy specification and laboratory lock state."""
    locked, reason = is_lab_unsafe_locked()
    return {
        "policy_engine": "SafetyPolicyEngine (Fail-Closed)",
        "lab_unsafe_locked": locked,
        "lab_unsafe_reason": reason,
        "rules": SafetyPolicyEngine.get_policy_specification(),
        "allowlisted_remediation_actions": sorted(ALLOWLISTED_REMEDIATION_ACTIONS),
    }


@api_router.post("/safety/clear-lab-lock", tags=["safety"])
async def reset_lab_unsafe_lock(
    _principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> dict[str, Any]:
    """Clear the laboratory unsafe lock and restore safe baseline configuration."""
    clear_lab_unsafe_lock()
    return {"status": "restored", "lab_unsafe_locked": False}


# ---------------------------------------------------------------------------
# Milestone 04/05: Verified Autonomous Recovery, Sandbox & Approval Endpoints
# ---------------------------------------------------------------------------


@api_router.post(
    "/recovery/plans",
    response_model=RecoveryPlanDetailRead,
    status_code=status.HTTP_201_CREATED,
    tags=["recovery"],
)
async def create_recovery_plan(
    payload: RecoveryWorkflowCreateRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
    correlation_id: str = Depends(get_correlation_id),
) -> RecoveryPlanDetailRead:
    """Create a recovery workflow from causal evidence and optionally verify in sandbox."""
    return await AutonomousRecoveryService.create_recovery_workflow(
        db,
        payload,
        actor=principal.actor,
        correlation_id=correlation_id,
    )


@api_router.get(
    "/recovery/plans",
    response_model=list[RecoveryPlanRead],
    tags=["recovery"],
)
async def list_recovery_plans(
    system_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[RecoveryPlanRead]:
    """List autonomous recovery workflows."""
    return await AutonomousRecoveryService.list_plans(db, system_id=system_id, limit=limit)


@api_router.get(
    "/recovery/plans/{plan_id}",
    response_model=RecoveryPlanDetailRead,
    tags=["recovery"],
)
async def get_recovery_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
) -> RecoveryPlanDetailRead:
    """Inspect a recovery workflow including candidates, sandbox runs, approvals, and rollbacks."""
    return await AutonomousRecoveryService.get_plan_detail(db, plan_id)


@api_router.post(
    "/recovery/plans/{plan_id}/candidates",
    response_model=RecoveryPlanDetailRead,
    tags=["recovery"],
)
async def generate_recovery_candidates(
    plan_id: str,
    payload: CandidateGenerationRequest | None = None,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> RecoveryPlanDetailRead:
    """Generate bounded remediation candidates and simulate each in the calibrated Digital Twin."""
    return await AutonomousRecoveryService.generate_and_simulate_candidates(
        db, plan_id, payload, actor=principal.actor
    )


@api_router.post(
    "/recovery/plans/{plan_id}/sandbox-verify",
    response_model=RecoveryPlanDetailRead,
    tags=["recovery"],
)
async def verify_recovery_candidate_in_sandbox(
    plan_id: str,
    payload: SandboxVerifyRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> RecoveryPlanDetailRead:
    """Run real isolated laboratory sandbox verification with restoration verification."""
    return await AutonomousRecoveryService.run_sandbox_verification(
        db, plan_id, payload, actor=principal.actor
    )


@api_router.patch(
    "/recovery/plans/{plan_id}",
    response_model=RecoveryPlanDetailRead,
    tags=["recovery"],
)
async def mutate_recovery_plan_endpoint(
    plan_id: str,
    payload: PlanMutationRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> RecoveryPlanDetailRead:
    """Update a recovery plan's candidate or parameters (invalidates prior approvals)."""
    return await AutonomousRecoveryService.mutate_recovery_plan(
        db, plan_id, payload, actor=principal.actor
    )


@api_router.post(
    "/recovery/plans/{plan_id}/approve",
    response_model=ApprovalRecordRead,
    status_code=status.HTTP_201_CREATED,
    tags=["recovery"],
)
async def approve_or_reject_recovery_plan(
    plan_id: str,
    payload: RecoveryApprovalRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> ApprovalRecordRead:
    """Record a human approval or rejection and issue a single-use authorization token."""
    return await AutonomousRecoveryService.submit_human_approval(
        db, plan_id, payload, actor=principal.actor
    )


@api_router.post(
    "/recovery/plans/{plan_id}/execute",
    response_model=RecoveryPlanDetailRead,
    tags=["recovery"],
)
async def execute_approved_recovery_plan(
    plan_id: str,
    payload: RecoveryExecutionRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> RecoveryPlanDetailRead:
    """Execute an approved recovery action, observe telemetry, and auto-rollback on regression."""
    return await AutonomousRecoveryService.execute_approved_recovery(
        db, plan_id, payload, actor=principal.actor
    )


@api_router.post(
    "/recovery/plans/{plan_id}/rollback",
    response_model=RecoveryPlanDetailRead,
    tags=["recovery"],
)
async def rollback_recovery_plan_endpoint(
    plan_id: str,
    payload: ManualRollbackRequest,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> RecoveryPlanDetailRead:
    """Trigger an explicit rollback of an executed recovery action."""
    return await AutonomousRecoveryService.trigger_manual_rollback(
        db, plan_id, payload, actor=principal.actor
    )


@api_router.post(
    "/recovery/plans/{plan_id}/cancel",
    response_model=RecoveryPlanDetailRead,
    tags=["recovery"],
)
async def cancel_recovery_plan_endpoint(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(verify_api_key),
) -> RecoveryPlanDetailRead:
    """Cancel a recovery workflow (and roll back if currently executing)."""
    return await AutonomousRecoveryService.cancel_recovery_plan(db, plan_id, actor=principal.actor)


@api_router.get(
    "/recovery/plans/{plan_id}/export",
    tags=["recovery"],
)
async def export_recovery_plan_report(
    plan_id: str,
    format: Literal["markdown", "json"] = Query(default="markdown"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export a reproducible Markdown & JSON scientific recovery & safety audit report."""
    return await AutonomousRecoveryService.export_recovery_report(db, plan_id, report_format=format)


@api_router.get("/architecture/modules", tags=["architecture"])
async def list_module_boundaries() -> dict[str, Any]:
    """Return explicit implementation status across all 9 ORIGIN architectural boundaries."""
    return {
        "milestone": (
            "04/05 — Verified Autonomous Recovery, Agent Orchestration & Operational Safety"
        ),
        "boundaries": [
            {
                "boundary_number": 1,
                "module": "api_and_auth",
                "status": "implemented",
                "capabilities": [
                    "FastAPI REST + OTLP + SSE router",
                    "X-Origin-Key / Bearer authentication",
                    "X-Benchmark-Controller-Key epistemic access separation",
                    "X-Correlation-ID request correlation",
                ],
            },
            {
                "boundary_number": 2,
                "module": "system_registry",
                "status": "implemented",
                "capabilities": [
                    "System registration & metadata",
                    "Service & tier registration",
                    "Explicit dependency registration",
                ],
            },
            {
                "boundary_number": 3,
                "module": "telemetry_ingestion",
                "status": "implemented",
                "capabilities": [
                    "OTLP/HTTP JSON Traces & Metrics ingestion",
                    "Structured batch ingestion",
                    "Time-series statistical queries (mean, p95, min, max)",
                    "Distributed trace span correlation queries",
                    "Real-time SSE event streaming",
                ],
            },
            {
                "boundary_number": 4,
                "module": "topology_discovery",
                "status": "implemented",
                "capabilities": [
                    "Provenance-strict graph generation (registered vs observed vs verified)",
                    "Live node health & latency/error computation",
                    "Zero unestablished dependency inference",
                ],
            },
            get_experimentation_status(),
            get_simulation_status(),
            get_agents_status(),
            get_evidence_status(),
            {
                "boundary_number": 9,
                "module": "safety_and_audit",
                "status": "implemented",
                "capabilities": [
                    "Immutable audit_events persistence for all mutations and experiments",
                    "Allowlisted intervention validation & zero untrusted code execution",
                    "SafetyEnvelopeContract enforcement",
                ],
                "default_safety_envelope": SafetyEnvelopeContract().model_dump(),
            },
        ],
    }
