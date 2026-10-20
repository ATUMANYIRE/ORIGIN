"""Unified REST + OTLP + SSE API Router for ORIGIN (Milestone 01/05)."""

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.session import get_db
from app.modules.agents.contract import get_module_contract_status as get_agents_status
from app.modules.auth.dependencies import (
    AuthenticatedPrincipal,
    get_correlation_id,
    verify_api_key,
)
from app.modules.evidence.contract import get_module_contract_status as get_evidence_status
from app.modules.experimentation.contract import (
    get_module_contract_status as get_experimentation_status,
)
from app.modules.laboratory.orchestrator import (
    LabExecutionResult,
    LabFaultState,
    LabProfileType,
    LabTransactionRequest,
    SyntheticLabOrchestrator,
    get_lab_state,
    set_lab_profile,
)
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
from app.modules.safety.service import AuditEventRead, AuditService, SafetyEnvelopeContract
from app.modules.simulation.contract import (
    get_module_contract_status as get_simulation_status,
)
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
    """Deep health check verifying database connectivity, Redis coordination, and lab state."""
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
        "milestone": "01/05 — Foundation, Product Experience & Living System Intelligence",
        "timestamp": datetime.now(UTC).isoformat(),
        "database_connected": db_ok,
        "redis": redis_info,
        "laboratory_profile": lab_state.profile,
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
    """Server-Sent Events (SSE) stream pushing live telemetry & topology updates."""

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
    """Inspect the active fault/degradation profile of the Synthetic Laboratory."""
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
    """Switch the Synthetic Laboratory between normal operation and performance degradation."""
    state = set_lab_profile(profile)
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
# Boundaries 5, 6, 7, 8 & 9: Safety Audit & Future Research Module Contracts
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


@api_router.get("/architecture/modules", tags=["architecture"])
async def list_module_boundaries() -> dict[str, Any]:
    """Return explicit implementation status across all 9 ORIGIN architectural boundaries."""
    return {
        "milestone": "01/05 — Foundation, Product Experience & Living System Intelligence",
        "boundaries": [
            {
                "boundary_number": 1,
                "module": "api_and_auth",
                "status": "implemented",
                "capabilities": [
                    "FastAPI REST + OTLP + SSE router",
                    "X-Origin-Key / Bearer authentication",
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
                "status": "implemented_with_future_guard_contract",
                "capabilities": [
                    "Immutable audit_events persistence for all mutations",
                    "SafetyEnvelopeContract specification for Milestone 03/05",
                ],
                "default_safety_envelope": SafetyEnvelopeContract().model_dump(),
            },
        ],
    }
