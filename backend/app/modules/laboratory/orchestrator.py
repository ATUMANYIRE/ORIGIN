"""Instrumentable Synthetic Distributed System Laboratory (5 services + load generator).

Contains:
1. api-gateway
2. checkout-service
3. inventory-service
4. payment-simulator
5. order-database-sim
6. load-generator

Supports normal operation and injected performance degradation profiles:
- 'normal': Nominal baseline operation across all 5 services.
- 'payment_latency_spike': Degrades payment-simulator latency & tail errors,
  propagating to checkout-service and api-gateway.
- 'db_lock_contention': Degrades order-database-sim lock wait time,
  propagating to inventory-service, checkout-service, and api-gateway.
"""

import asyncio
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Literal

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.registry.schemas import DependencyCreate, ServiceCreate, SystemCreate
from app.modules.registry.service import RegistryService
from app.modules.safety.service import AuditService
from app.modules.telemetry.schemas import (
    MetricObservationIn,
    OTLPKeyValue,
    OTLPResource,
    OTLPResourceSpans,
    OTLPScopeSpans,
    OTLPSpan,
    OTLPTracesPayload,
    SpanObservationIn,
    TelemetryBatchIn,
)
from app.modules.telemetry.service import TelemetryService

LAB_SYSTEM_SLUG = "origin-synthetic-lab"

LabProfileType = Literal["normal", "payment_latency_spike", "db_lock_contention"]


class LabFaultState(BaseModel):
    """Current operational profile and fault parameters of the Synthetic Laboratory."""

    profile: LabProfileType = "normal"
    payment_added_latency_ms: float = 0.0
    payment_failure_probability: float = 0.0
    db_added_latency_ms: float = 0.0
    db_lock_saturation_pct: float = 18.0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LabTransactionRequest(BaseModel):
    """Request to execute one or more synthetic distributed checkout transactions."""

    iterations: int = Field(default=3, ge=1, le=25)
    profile: LabProfileType | None = None
    sku: str = Field(default="ORIGIN-QUANTUM-SENSOR-X1", max_length=80)
    amount_usd: float = Field(default=249.00, gt=0.0)


class LabTransactionTraceSummary(BaseModel):
    """Summary of a single multi-service request traversing the laboratory."""

    correlation_id: str
    trace_id: str
    profile: LabProfileType
    gateway_status: int
    total_duration_ms: float
    services_traversed: list[str]
    spans_emitted: int
    metrics_emitted: int


class LabExecutionResult(BaseModel):
    """Result of running a single or burst workload against the laboratory."""

    system_slug: str
    execution_mode: str
    active_profile: LabProfileType
    transactions_executed: int
    total_spans_ingested: int
    total_metrics_ingested: int
    traces: list[LabTransactionTraceSummary]


# Process-level state for current lab degradation profile
_CURRENT_LAB_STATE = LabFaultState()


def get_lab_state() -> LabFaultState:
    """Return active laboratory fault profile."""
    return _CURRENT_LAB_STATE


def set_lab_profile(profile: LabProfileType) -> LabFaultState:
    """Configure the laboratory operating profile."""
    global _CURRENT_LAB_STATE
    if profile == "normal":
        _CURRENT_LAB_STATE = LabFaultState(
            profile="normal",
            payment_added_latency_ms=0.0,
            payment_failure_probability=0.0,
            db_added_latency_ms=0.0,
            db_lock_saturation_pct=18.0,
            updated_at=datetime.now(UTC),
        )
    elif profile == "payment_latency_spike":
        _CURRENT_LAB_STATE = LabFaultState(
            profile="payment_latency_spike",
            payment_added_latency_ms=420.0,
            payment_failure_probability=0.18,
            db_added_latency_ms=0.0,
            db_lock_saturation_pct=24.0,
            updated_at=datetime.now(UTC),
        )
    elif profile == "db_lock_contention":
        _CURRENT_LAB_STATE = LabFaultState(
            profile="db_lock_contention",
            payment_added_latency_ms=10.0,
            payment_failure_probability=0.0,
            db_added_latency_ms=340.0,
            db_lock_saturation_pct=91.0,
            updated_at=datetime.now(UTC),
        )
    return _CURRENT_LAB_STATE


class SyntheticLabOrchestrator:
    """Registers the Synthetic Distributed System Laboratory and executes instrumented workloads."""

    @staticmethod
    async def ensure_lab_registered(
        db: AsyncSession,
        actor: str = "system-bootstrap",
        correlation_id: str | None = None,
    ) -> str:
        """Register the canonical 5-service Synthetic Distributed System Laboratory."""
        system = await RegistryService.create_or_get_system(
            db,
            SystemCreate(
                slug=LAB_SYSTEM_SLUG,
                name="ORIGIN Synthetic Distributed Commerce Lab",
                environment="synthetic-lab",
                description=(
                    "Isolated 5-service distributed laboratory (API Gateway, Checkout Service, "
                    "Inventory Service, Payment Simulator, Order Database Simulator) with "
                    "OpenTelemetry trace and metric instrumentation."
                ),
                is_synthetic_lab=True,
                metadata_json={
                    "purpose": "Causal Discovery & Living System Intelligence Benchmark",
                    "components": [
                        "api-gateway",
                        "checkout-service",
                        "inventory-service",
                        "payment-simulator",
                        "order-database-sim",
                        "load-generator",
                    ],
                },
            ),
            actor=actor,
            correlation_id=correlation_id,
        )

        services_spec: list[ServiceCreate] = [
            ServiceCreate(
                service_key="api-gateway",
                display_name="Edge API Gateway",
                service_type="gateway",
                tier="tier-0",
                owner_team="edge-platform",
                metadata_json={"port": 8091, "entrypoint": "POST /orders/checkout"},
            ),
            ServiceCreate(
                service_key="checkout-service",
                display_name="Checkout Orchestrator",
                service_type="microservice",
                tier="tier-1",
                owner_team="commerce-core",
                metadata_json={"port": 8092, "role": "Distributed transaction coordinator"},
            ),
            ServiceCreate(
                service_key="inventory-service",
                display_name="Inventory Reservation Service",
                service_type="microservice",
                tier="tier-2",
                owner_team="supply-chain",
                metadata_json={"port": 8093, "role": "Stock verification and reservation"},
            ),
            ServiceCreate(
                service_key="payment-simulator",
                display_name="Payment Gateway Simulator",
                service_type="external_simulator",
                tier="tier-2",
                owner_team="payments-eng",
                metadata_json={"port": 8094, "role": "Payment authorization & clearing simulator"},
            ),
            ServiceCreate(
                service_key="order-database-sim",
                display_name="Order & Inventory Database Simulator",
                service_type="database",
                tier="tier-3",
                owner_team="data-infrastructure",
                metadata_json={"port": 8095, "engine": "transactional-kv-simulator"},
            ),
        ]
        for svc_spec in services_spec:
            await RegistryService.register_service(
                db, system.id, svc_spec, actor=actor, correlation_id=correlation_id
            )

        # Register 4 of the 5 edges explicitly, leaving inventory-service -> order-database-sim
        # to be discovered purely from live OpenTelemetry span observations ('observed'),
        # while the other 4 become 'registered_and_observed' upon traffic execution.
        declared_edges: list[DependencyCreate] = [
            DependencyCreate(
                source_service_key="api-gateway",
                target_service_key="checkout-service",
                protocol="http",
                metadata_json={"route": "POST /internal/checkout"},
            ),
            DependencyCreate(
                source_service_key="checkout-service",
                target_service_key="inventory-service",
                protocol="http",
                metadata_json={"route": "POST /internal/inventory/reserve"},
            ),
            DependencyCreate(
                source_service_key="checkout-service",
                target_service_key="payment-simulator",
                protocol="http",
                metadata_json={"route": "POST /internal/payments/authorize"},
            ),
            DependencyCreate(
                source_service_key="checkout-service",
                target_service_key="order-database-sim",
                protocol="sql",
                metadata_json={"query": "INSERT INTO orders"},
            ),
        ]
        for edge_spec in declared_edges:
            await RegistryService.register_dependency(
                db, system.id, edge_spec, actor=actor, correlation_id=correlation_id
            )

        await db.commit()
        return system.id

    @staticmethod
    async def execute_instrumented_transaction(
        db: AsyncSession,
        profile: LabProfileType,
        sku: str = "ORIGIN-QUANTUM-SENSOR-X1",
        amount_usd: float = 249.0,
        rng_seed: int | None = None,
    ) -> LabTransactionTraceSummary:
        """Execute a real instrumented request traversing all 5 laboratory services."""
        rng = random.Random(rng_seed) if rng_seed is not None else random.Random()
        state = set_lab_profile(profile)

        trace_id = uuid.uuid4().hex
        correlation_id = f"lab-corr-{trace_id[:16]}"
        t0 = time.perf_counter()
        base_ts = datetime.now(UTC)

        # Span IDs for the 5-service call hierarchy
        gw_span_id = uuid.uuid4().hex[:16]
        chk_span_id = uuid.uuid4().hex[:16]
        inv_span_id = uuid.uuid4().hex[:16]
        db_inv_span_id = uuid.uuid4().hex[:16]
        pay_span_id = uuid.uuid4().hex[:16]
        db_ord_span_id = uuid.uuid4().hex[:16]

        # 1. Inventory -> Database Simulator query
        await asyncio.sleep(0.002)
        db_inv_dur = round(
            rng.uniform(8.5, 16.0) + state.db_added_latency_ms * rng.uniform(0.85, 1.15),
            2,
        )

        # 2. Inventory Service reservation (includes DB call + local stock logic)
        inv_local_dur = round(rng.uniform(11.0, 21.0), 2)
        inv_total_dur = round(db_inv_dur + inv_local_dur, 2)

        # 3. Payment Simulator authorization
        await asyncio.sleep(0.002)
        pay_dur = round(
            rng.uniform(24.0, 42.0)
            + state.payment_added_latency_ms * rng.uniform(0.9, 1.25),
            2,
        )
        pay_failed = rng.random() < state.payment_failure_probability
        pay_http_status = 503 if pay_failed else 200
        pay_status_code: Literal["OK", "ERROR"] = "ERROR" if pay_failed else "OK"

        # 4. Checkout -> Database Simulator order commit
        db_ord_dur = round(
            rng.uniform(10.0, 19.5) + state.db_added_latency_ms * rng.uniform(0.9, 1.2),
            2,
        )
        db_failed = state.db_lock_saturation_pct >= 90.0 and rng.random() < 0.15
        db_http_status = 504 if db_failed else 200
        db_status_code: Literal["OK", "ERROR"] = "ERROR" if db_failed else "OK"

        # 5. Checkout Orchestrator total duration & status
        chk_overhead = round(rng.uniform(9.5, 17.5), 2)
        chk_total_dur = round(inv_total_dur + pay_dur + db_ord_dur + chk_overhead, 2)
        chk_failed = pay_failed or db_failed
        chk_http_status = 502 if chk_failed else 200
        chk_status_code: Literal["OK", "ERROR"] = "ERROR" if chk_failed else "OK"

        # 6. API Gateway total duration & status
        gw_overhead = round(rng.uniform(6.0, 12.0), 2)
        gw_total_dur = round(chk_total_dur + gw_overhead, 2)
        gw_http_status = 502 if chk_failed else 200

        _ = time.perf_counter() - t0

        # Emit OTLP Traces for the gateway hop to exercise OTLP/HTTP JSON trace ingestion
        otlp_payload = OTLPTracesPayload(
            resourceSpans=[
                OTLPResourceSpans(
                    resource=OTLPResource(
                        attributes=[
                            OTLPKeyValue(
                                key="service.name",
                                value={"stringValue": "api-gateway"},
                            ),
                            OTLPKeyValue(
                                key="origin.system.slug",
                                value={"stringValue": LAB_SYSTEM_SLUG},
                            ),
                            OTLPKeyValue(
                                key="origin.is_synthetic",
                                value={"boolValue": True},
                            ),
                        ]
                    ),
                    scopeSpans=[
                        OTLPScopeSpans(
                            scope={"name": "origin.lab.tracer", "version": "0.1.0"},
                            spans=[
                                OTLPSpan(
                                    traceId=trace_id,
                                    spanId=gw_span_id,
                                    parentSpanId=None,
                                    name="POST /orders/checkout",
                                    attributes=[
                                        OTLPKeyValue(
                                            key="origin.correlation_id",
                                            value={"stringValue": correlation_id},
                                        ),
                                        OTLPKeyValue(
                                            key="origin.duration_ms",
                                            value={"doubleValue": gw_total_dur},
                                        ),
                                        OTLPKeyValue(
                                            key="http.status_code",
                                            value={"intValue": gw_http_status},
                                        ),
                                        OTLPKeyValue(
                                            key="lab.profile",
                                            value={"stringValue": profile},
                                        ),
                                        OTLPKeyValue(
                                            key="order.sku",
                                            value={"stringValue": sku},
                                        ),
                                    ],
                                    status={"code": 2 if chk_failed else 1},
                                )
                            ],
                        )
                    ],
                )
            ]
        )
        await TelemetryService.ingest_otlp_traces(
            db, otlp_payload, default_system_slug=LAB_SYSTEM_SLUG
        )

        # Emit downstream spans and rich operational metrics for all 5 services
        batch = TelemetryBatchIn(
            system_slug=LAB_SYSTEM_SLUG,
            source_name="origin-lab-otel-sdk",
            exporter_protocol="otlp-http-json",
            sdk_version="opentelemetry-python-1.27",
            is_synthetic=True,
            spans=[
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=chk_span_id,
                    parent_span_id=gw_span_id,
                    correlation_id=correlation_id,
                    service_key="checkout-service",
                    parent_service_key="api-gateway",
                    operation_name="POST /internal/checkout",
                    span_kind="SERVER",
                    status_code=chk_status_code,
                    http_status=chk_http_status,
                    duration_ms=chk_total_dur,
                    attributes_json={
                        "lab.profile": profile,
                        "order.amount_usd": amount_usd,
                        "rpc.system": "http",
                    },
                    started_at=base_ts,
                ),
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=inv_span_id,
                    parent_span_id=chk_span_id,
                    correlation_id=correlation_id,
                    service_key="inventory-service",
                    parent_service_key="checkout-service",
                    operation_name="POST /internal/inventory/reserve",
                    span_kind="SERVER",
                    status_code="OK",
                    http_status=200,
                    duration_ms=inv_total_dur,
                    attributes_json={
                        "lab.profile": profile,
                        "inventory.sku": sku,
                        "rpc.system": "http",
                    },
                    started_at=base_ts,
                ),
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=db_inv_span_id,
                    parent_span_id=inv_span_id,
                    correlation_id=correlation_id,
                    service_key="order-database-sim",
                    parent_service_key="inventory-service",
                    operation_name="SELECT FOR UPDATE inventory_stock",
                    span_kind="SERVER",
                    status_code=db_status_code,
                    http_status=db_http_status,
                    duration_ms=db_inv_dur,
                    attributes_json={
                        "lab.profile": profile,
                        "db.operation": "SELECT_FOR_UPDATE",
                        "rpc.system": "sql",
                    },
                    started_at=base_ts,
                ),
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=pay_span_id,
                    parent_span_id=chk_span_id,
                    correlation_id=correlation_id,
                    service_key="payment-simulator",
                    parent_service_key="checkout-service",
                    operation_name="POST /internal/payments/authorize",
                    span_kind="SERVER",
                    status_code=pay_status_code,
                    http_status=pay_http_status,
                    duration_ms=pay_dur,
                    attributes_json={
                        "lab.profile": profile,
                        "payment.amount_usd": amount_usd,
                        "rpc.system": "http",
                    },
                    started_at=base_ts,
                ),
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=db_ord_span_id,
                    parent_span_id=chk_span_id,
                    correlation_id=correlation_id,
                    service_key="order-database-sim",
                    parent_service_key="checkout-service",
                    operation_name="INSERT INTO orders",
                    span_kind="SERVER",
                    status_code=db_status_code,
                    http_status=db_http_status,
                    duration_ms=db_ord_dur,
                    attributes_json={
                        "lab.profile": profile,
                        "db.operation": "INSERT",
                        "rpc.system": "sql",
                    },
                    started_at=base_ts,
                ),
            ],
            metrics=[
                MetricObservationIn(
                    service_key="checkout-service",
                    metric_name="request_latency_ms",
                    metric_unit="ms",
                    value=chk_total_dur,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json={"profile": profile},
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="inventory-service",
                    metric_name="request_latency_ms",
                    metric_unit="ms",
                    value=inv_total_dur,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json={"profile": profile},
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="payment-simulator",
                    metric_name="request_latency_ms",
                    metric_unit="ms",
                    value=pay_dur,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json={"profile": profile},
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="order-database-sim",
                    metric_name="request_latency_ms",
                    metric_unit="ms",
                    value=round((db_inv_dur + db_ord_dur) / 2.0, 2),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json={"profile": profile},
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="api-gateway",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        rng.uniform(22.0, 35.0)
                        + (28.0 if profile != "normal" else 0.0),
                        2,
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="checkout-service",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        rng.uniform(28.0, 42.0)
                        + (36.0 if profile != "normal" else 0.0),
                        2,
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="inventory-service",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        rng.uniform(19.0, 31.0)
                        + (35.0 if profile == "db_lock_contention" else 0.0),
                        2,
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="payment-simulator",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        rng.uniform(20.0, 34.0)
                        + (58.0 if profile == "payment_latency_spike" else 0.0),
                        2,
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="order-database-sim",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        state.db_lock_saturation_pct + rng.uniform(-3.0, 4.0), 2
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    observed_at=base_ts,
                ),
            ],
        )

        receipt = await TelemetryService.ingest_batch(db, batch)
        return LabTransactionTraceSummary(
            correlation_id=correlation_id,
            trace_id=trace_id,
            profile=profile,
            gateway_status=gw_http_status,
            total_duration_ms=gw_total_dur,
            services_traversed=[
                "api-gateway",
                "checkout-service",
                "inventory-service",
                "payment-simulator",
                "order-database-sim",
            ],
            spans_emitted=receipt.spans_ingested + 1,
            metrics_emitted=receipt.metrics_ingested + 1,
        )

    @staticmethod
    async def run_workload(
        db: AsyncSession,
        request: LabTransactionRequest,
        actor: str = "operator",
        correlation_id: str | None = None,
    ) -> LabExecutionResult:
        """Execute a laboratory workload via the isolated lab container or embedded runner."""
        system_id = await SyntheticLabOrchestrator.ensure_lab_registered(
            db, actor=actor, correlation_id=correlation_id
        )
        active_profile = request.profile or get_lab_state().profile
        set_lab_profile(active_profile)

        settings = get_settings()
        execution_mode = "embedded_instrumented_pipeline"
        traces: list[LabTransactionTraceSummary] = []

        # Try calling the isolated lab container over internal network first if configured
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.post(
                    f"{settings.lab_controller_url}/internal/lab/execute",
                    json={
                        "iterations": request.iterations,
                        "profile": active_profile,
                        "sku": request.sku,
                        "amount_usd": request.amount_usd,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    execution_mode = "isolated_lab_container_http"
                    traces = [
                        LabTransactionTraceSummary(**t)
                        for t in data.get("traces", [])
                    ]
        except Exception:
            # Fallback to local in-process execution of the 5 instrumented lab services
            pass

        if not traces:
            for _ in range(request.iterations):
                summary = await SyntheticLabOrchestrator.execute_instrumented_transaction(
                    db,
                    profile=active_profile,
                    sku=request.sku,
                    amount_usd=request.amount_usd,
                )
                traces.append(summary)

        await AuditService.record_event(
            db,
            system_id=system_id,
            actor=actor,
            action="laboratory.workload_executed",
            resource_type="synthetic_laboratory",
            resource_id=LAB_SYSTEM_SLUG,
            severity="warning" if active_profile != "normal" else "info",
            correlation_id=correlation_id or (traces[0].correlation_id if traces else None),
            details={
                "profile": active_profile,
                "iterations": request.iterations,
                "execution_mode": execution_mode,
                "trace_ids": [t.trace_id for t in traces],
            },
        )
        await db.commit()

        return LabExecutionResult(
            system_slug=LAB_SYSTEM_SLUG,
            execution_mode=execution_mode,
            active_profile=active_profile,
            transactions_executed=len(traces),
            total_spans_ingested=sum(t.spans_emitted for t in traces),
            total_metrics_ingested=sum(t.metrics_emitted for t in traces),
            traces=traces,
        )
