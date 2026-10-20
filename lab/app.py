"""Isolated Synthetic Distributed System Laboratory for ORIGIN.

Hosts 5 instrumented service endpoints and a load generator controller:
1. API Gateway (`/services/api-gateway/orders/checkout`)
2. Checkout Service (`/services/checkout/process`)
3. Inventory Service (`/services/inventory/reserve`)
4. Payment Simulator (`/services/payment/authorize`)
5. Order Database Simulator (`/services/database/query`)
6. Load Generator & Fault Controller (`/internal/lab/execute`, `/internal/lab/health`)

Never exposed publicly outside the internal Docker network.
"""

import asyncio
from datetime import UTC, datetime
import os
import random
import time
from typing import Any, Literal
import uuid

from fastapi import FastAPI, Header
import httpx
from pydantic import BaseModel, Field

ORIGIN_BACKEND_URL = os.getenv("ORIGIN_BACKEND_URL", "http://localhost:8000")
LAB_SELF_URL = os.getenv("LAB_SELF_URL", "http://127.0.0.1:8099")
LAB_SYSTEM_SLUG = "origin-synthetic-lab"

LabProfile = Literal[
    "normal",
    "payment_latency_spike",
    "db_lock_contention",
    "inventory_cpu_throttling",
    "noisy_ambiguous_jitter",
]


class LabRuntimeConfig(BaseModel):
    """Mutable fault profile configuration for the laboratory."""

    profile: LabProfile = "normal"
    payment_added_latency_ms: float = 0.0
    payment_failure_probability: float = 0.0
    db_added_latency_ms: float = 0.0
    db_lock_saturation_pct: float = 18.0


_RUNTIME = LabRuntimeConfig()


def apply_profile(profile: LabProfile) -> LabRuntimeConfig:
    """Update laboratory fault parameters for the requested profile."""
    global _RUNTIME
    if profile == "normal":
        _RUNTIME = LabRuntimeConfig(
            profile="normal",
            payment_added_latency_ms=0.0,
            payment_failure_probability=0.0,
            db_added_latency_ms=0.0,
            db_lock_saturation_pct=18.0,
        )
    elif profile == "payment_latency_spike":
        _RUNTIME = LabRuntimeConfig(
            profile="payment_latency_spike",
            payment_added_latency_ms=420.0,
            payment_failure_probability=0.18,
            db_added_latency_ms=0.0,
            db_lock_saturation_pct=24.0,
        )
    elif profile == "db_lock_contention":
        _RUNTIME = LabRuntimeConfig(
            profile="db_lock_contention",
            payment_added_latency_ms=10.0,
            payment_failure_probability=0.0,
            db_added_latency_ms=340.0,
            db_lock_saturation_pct=91.0,
        )
    return _RUNTIME


class OrderPayload(BaseModel):
    """Order payload sent through the laboratory services."""

    sku: str = "ORIGIN-QUANTUM-SENSOR-X1"
    amount_usd: float = 249.0


class LoadExecuteRequest(BaseModel):
    """Request to run N real HTTP requests across the laboratory services."""

    iterations: int = Field(default=3, ge=1, le=25)
    profile: LabProfile = "normal"
    sku: str = "ORIGIN-QUANTUM-SENSOR-X1"
    amount_usd: float = 249.0


app = FastAPI(
    title="ORIGIN Synthetic Distributed System Laboratory",
    version="0.1.0",
)


@app.get("/internal/lab/health")
async def lab_health() -> dict[str, Any]:
    """Internal health endpoint for Docker Compose & ORIGIN backend."""
    return {
        "status": "healthy",
        "service": "origin-synthetic-lab",
        "active_profile": _RUNTIME.profile,
        "services": [
            "api-gateway",
            "checkout-service",
            "inventory-service",
            "payment-simulator",
            "order-database-sim",
            "load-generator",
        ],
    }


@app.post("/services/database/query")
async def database_simulator_endpoint(
    payload: dict[str, Any],
    x_trace_id: str = Header(..., alias="X-Trace-ID"),
    x_correlation_id: str = Header(..., alias="X-Correlation-ID"),
    x_parent_span_id: str = Header(..., alias="X-Parent-Span-ID"),
    x_parent_service: str = Header(..., alias="X-Parent-Service"),
) -> dict[str, Any]:
    """Database Simulator: executes simulated SQL query with optional lock contention."""
    span_id = uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    op_name = str(payload.get("operation", "SELECT_FOR_UPDATE"))

    base_delay_ms = random.uniform(9.0, 17.0) + _RUNTIME.db_added_latency_ms * random.uniform(
        0.88, 1.15
    )
    await asyncio.sleep(min(base_delay_ms / 1000.0, 0.08))
    measured_ms = round(max((time.perf_counter() - t0) * 1000.0, base_delay_ms), 2)

    failed = _RUNTIME.db_lock_saturation_pct >= 90.0 and random.random() < 0.15
    http_status = 504 if failed else 200
    status_code = "ERROR" if failed else "OK"

    span_record = {
        "trace_id": x_trace_id,
        "span_id": span_id,
        "parent_span_id": x_parent_span_id,
        "correlation_id": x_correlation_id,
        "service_key": "order-database-sim",
        "parent_service_key": x_parent_service,
        "operation_name": op_name,
        "span_kind": "SERVER",
        "status_code": status_code,
        "http_status": http_status,
        "duration_ms": measured_ms,
        "attributes_json": {
            "telemetry.environment": "synthetic-lab",
            "db.operation": op_name,
            "rpc.system": "sql",
        },
        "started_at": datetime.now(UTC).isoformat(),
    }
    return {"ok": not failed, "http_status": http_status, "spans": [span_record]}


@app.post("/services/inventory/reserve")
async def inventory_service_endpoint(
    payload: OrderPayload,
    x_trace_id: str = Header(..., alias="X-Trace-ID"),
    x_correlation_id: str = Header(..., alias="X-Correlation-ID"),
    x_parent_span_id: str = Header(..., alias="X-Parent-Span-ID"),
    x_parent_service: str = Header(..., alias="X-Parent-Service"),
) -> dict[str, Any]:
    """Inventory Service: verifies stock by querying the Database Simulator."""
    span_id = uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    await asyncio.sleep(0.005)

    async with httpx.AsyncClient(base_url=LAB_SELF_URL, timeout=5.0) as client:
        db_resp = await client.post(
            "/services/database/query",
            json={"operation": "SELECT FOR UPDATE inventory_stock", "sku": payload.sku},
            headers={
                "X-Trace-ID": x_trace_id,
                "X-Correlation-ID": x_correlation_id,
                "X-Parent-Span-ID": span_id,
                "X-Parent-Service": "inventory-service",
            },
        )
        db_data = db_resp.json()

    downstream_spans: list[dict[str, Any]] = db_data.get("spans", [])
    db_dur = sum(float(s["duration_ms"]) for s in downstream_spans)
    local_dur = random.uniform(11.0, 20.0)
    total_dur = round(max((time.perf_counter() - t0) * 1000.0, db_dur + local_dur), 2)

    span_record = {
        "trace_id": x_trace_id,
        "span_id": span_id,
        "parent_span_id": x_parent_span_id,
        "correlation_id": x_correlation_id,
        "service_key": "inventory-service",
        "parent_service_key": x_parent_service,
        "operation_name": "POST /internal/inventory/reserve",
        "span_kind": "SERVER",
        "status_code": "OK",
        "http_status": 200,
        "duration_ms": total_dur,
        "attributes_json": {
            "telemetry.environment": "synthetic-lab",
            "inventory.sku": payload.sku,
            "rpc.system": "http",
        },
        "started_at": datetime.now(UTC).isoformat(),
    }
    return {
        "ok": db_data.get("ok", True),
        "http_status": 200,
        "spans": [span_record, *downstream_spans],
    }


@app.post("/services/payment/authorize")
async def payment_simulator_endpoint(
    payload: OrderPayload,
    x_trace_id: str = Header(..., alias="X-Trace-ID"),
    x_correlation_id: str = Header(..., alias="X-Correlation-ID"),
    x_parent_span_id: str = Header(..., alias="X-Parent-Span-ID"),
    x_parent_service: str = Header(..., alias="X-Parent-Service"),
) -> dict[str, Any]:
    """Payment Simulator: authorizes payment with configurable latency spike & failure rate."""
    span_id = uuid.uuid4().hex[:16]
    t0 = time.perf_counter()

    sim_ms = random.uniform(24.0, 42.0) + _RUNTIME.payment_added_latency_ms * random.uniform(
        0.9, 1.25
    )
    await asyncio.sleep(min(sim_ms / 1000.0, 0.08))
    total_dur = round(max((time.perf_counter() - t0) * 1000.0, sim_ms), 2)

    failed = random.random() < _RUNTIME.payment_failure_probability
    http_status = 503 if failed else 200
    status_code = "ERROR" if failed else "OK"

    span_record = {
        "trace_id": x_trace_id,
        "span_id": span_id,
        "parent_span_id": x_parent_span_id,
        "correlation_id": x_correlation_id,
        "service_key": "payment-simulator",
        "parent_service_key": x_parent_service,
        "operation_name": "POST /internal/payments/authorize",
        "span_kind": "SERVER",
        "status_code": status_code,
        "http_status": http_status,
        "duration_ms": total_dur,
        "attributes_json": {
            "telemetry.environment": "synthetic-lab",
            "payment.amount_usd": payload.amount_usd,
            "rpc.system": "http",
        },
        "started_at": datetime.now(UTC).isoformat(),
    }
    return {"ok": not failed, "http_status": http_status, "spans": [span_record]}


@app.post("/services/checkout/process")
async def checkout_service_endpoint(
    payload: OrderPayload,
    x_trace_id: str = Header(..., alias="X-Trace-ID"),
    x_correlation_id: str = Header(..., alias="X-Correlation-ID"),
    x_parent_span_id: str = Header(..., alias="X-Parent-Span-ID"),
    x_parent_service: str = Header(..., alias="X-Parent-Service"),
) -> dict[str, Any]:
    """Checkout Service: orchestrates Inventory, Payment Simulator, and Order Database commit."""
    span_id = uuid.uuid4().hex[:16]
    t0 = time.perf_counter()

    async with httpx.AsyncClient(base_url=LAB_SELF_URL, timeout=8.0) as client:
        inv_resp = await client.post(
            "/services/inventory/reserve",
            json=payload.model_dump(),
            headers={
                "X-Trace-ID": x_trace_id,
                "X-Correlation-ID": x_correlation_id,
                "X-Parent-Span-ID": span_id,
                "X-Parent-Service": "checkout-service",
            },
        )
        pay_resp = await client.post(
            "/services/payment/authorize",
            json=payload.model_dump(),
            headers={
                "X-Trace-ID": x_trace_id,
                "X-Correlation-ID": x_correlation_id,
                "X-Parent-Span-ID": span_id,
                "X-Parent-Service": "checkout-service",
            },
        )
        db_resp = await client.post(
            "/services/database/query",
            json={"operation": "INSERT INTO orders", "sku": payload.sku},
            headers={
                "X-Trace-ID": x_trace_id,
                "X-Correlation-ID": x_correlation_id,
                "X-Parent-Span-ID": span_id,
                "X-Parent-Service": "checkout-service",
            },
        )

    inv_data = inv_resp.json()
    pay_data = pay_resp.json()
    db_data = db_resp.json()

    child_spans: list[dict[str, Any]] = [
        *inv_data.get("spans", []),
        *pay_data.get("spans", []),
        *db_data.get("spans", []),
    ]
    direct_child_dur = sum(
        float(s["duration_ms"])
        for s in child_spans
        if s.get("parent_span_id") == span_id
    )
    total_dur = round(
        max((time.perf_counter() - t0) * 1000.0, direct_child_dur + random.uniform(9.5, 17.5)),
        2,
    )
    all_ok = inv_data.get("ok", True) and pay_data.get("ok", True) and db_data.get("ok", True)
    http_status = 200 if all_ok else 502
    status_code = "OK" if all_ok else "ERROR"

    span_record = {
        "trace_id": x_trace_id,
        "span_id": span_id,
        "parent_span_id": x_parent_span_id,
        "correlation_id": x_correlation_id,
        "service_key": "checkout-service",
        "parent_service_key": x_parent_service,
        "operation_name": "POST /internal/checkout",
        "span_kind": "SERVER",
        "status_code": status_code,
        "http_status": http_status,
        "duration_ms": total_dur,
        "attributes_json": {
            "telemetry.environment": "synthetic-lab",
            "order.amount_usd": payload.amount_usd,
            "rpc.system": "http",
        },
        "started_at": datetime.now(UTC).isoformat(),
    }
    return {
        "ok": all_ok,
        "http_status": http_status,
        "spans": [span_record, *child_spans],
    }


@app.post("/services/api-gateway/orders/checkout")
async def api_gateway_endpoint(
    payload: OrderPayload,
    x_trace_id: str = Header(..., alias="X-Trace-ID"),
    x_correlation_id: str = Header(..., alias="X-Correlation-ID"),
) -> dict[str, Any]:
    """API Gateway: root entrypoint forwarding requests to Checkout Service."""
    gw_span_id = uuid.uuid4().hex[:16]
    t0 = time.perf_counter()

    async with httpx.AsyncClient(base_url=LAB_SELF_URL, timeout=10.0) as client:
        chk_resp = await client.post(
            "/services/checkout/process",
            json=payload.model_dump(),
            headers={
                "X-Trace-ID": x_trace_id,
                "X-Correlation-ID": x_correlation_id,
                "X-Parent-Span-ID": gw_span_id,
                "X-Parent-Service": "api-gateway",
            },
        )
    chk_data = chk_resp.json()
    downstream_spans: list[dict[str, Any]] = chk_data.get("spans", [])
    chk_dur = next(
        (float(s["duration_ms"]) for s in downstream_spans if s["service_key"] == "checkout-service"),
        45.0,
    )
    gw_total_dur = round(
        max((time.perf_counter() - t0) * 1000.0, chk_dur + random.uniform(6.0, 12.0)),
        2,
    )
    all_ok = chk_data.get("ok", True)
    gw_http_status = 200 if all_ok else 502

    gw_span = {
        "trace_id": x_trace_id,
        "span_id": gw_span_id,
        "parent_span_id": None,
        "correlation_id": x_correlation_id,
        "service_key": "api-gateway",
        "parent_service_key": None,
        "operation_name": "POST /orders/checkout",
        "span_kind": "SERVER",
        "status_code": "OK" if all_ok else "ERROR",
        "http_status": gw_http_status,
        "duration_ms": gw_total_dur,
        "attributes_json": {
            "telemetry.environment": "synthetic-lab",
            "order.sku": payload.sku,
            "rpc.system": "http",
        },
        "started_at": datetime.now(UTC).isoformat(),
    }

    all_spans = [gw_span, *downstream_spans]
    now_iso = datetime.now(UTC).isoformat()

    # Build metrics for all 5 services from actual span durations
    metrics: list[dict[str, Any]] = []
    for sp in all_spans:
        metrics.append(
            {
                "service_key": sp["service_key"],
                "metric_name": "request_latency_ms",
                "metric_unit": "ms",
                "value": sp["duration_ms"],
                "correlation_id": x_correlation_id,
                "trace_id": x_trace_id,
                "attributes_json": {"operation": sp["operation_name"]},
                "observed_at": now_iso,
            }
        )

    for svc_key in [
        "api-gateway",
        "checkout-service",
        "inventory-service",
        "payment-simulator",
        "order-database-sim",
    ]:
        sat = random.uniform(20.0, 35.0)
        if _RUNTIME.profile == "payment_latency_spike" and svc_key in (
            "payment-simulator",
            "checkout-service",
            "api-gateway",
        ):
            sat += 52.0 if svc_key == "payment-simulator" else 30.0
        elif _RUNTIME.profile == "db_lock_contention" and svc_key in (
            "order-database-sim",
            "inventory-service",
            "checkout-service",
        ):
            sat = (
                _RUNTIME.db_lock_saturation_pct
                if svc_key == "order-database-sim"
                else sat + 35.0
            )
        metrics.append(
            {
                "service_key": svc_key,
                "metric_name": "saturation_pct",
                "metric_unit": "%",
                "value": round(sat, 2),
                "correlation_id": x_correlation_id,
                "trace_id": x_trace_id,
                "attributes_json": {"telemetry.environment": "synthetic-lab"},
                "observed_at": now_iso,
            }
        )

    # Export telemetry batch to ORIGIN Backend
    async with httpx.AsyncClient(timeout=8.0) as client:
        await client.post(
            f"{ORIGIN_BACKEND_URL}/api/v1/telemetry/ingest",
            json={
                "system_slug": LAB_SYSTEM_SLUG,
                "source_name": "origin-lab-isolated-container",
                "exporter_protocol": "otlp-http-json",
                "sdk_version": "opentelemetry-python-1.27",
                "is_synthetic": True,
                "spans": all_spans,
                "metrics": metrics,
            },
        )

    return {
        "correlation_id": x_correlation_id,
        "trace_id": x_trace_id,
        "profile": _RUNTIME.profile,
        "gateway_status": gw_http_status,
        "total_duration_ms": gw_total_dur,
        "services_traversed": [
            "api-gateway",
            "checkout-service",
            "inventory-service",
            "payment-simulator",
            "order-database-sim",
        ],
        "spans_emitted": len(all_spans),
        "metrics_emitted": len(metrics),
    }


@app.post("/internal/lab/execute")
async def execute_lab_load(request: LoadExecuteRequest) -> dict[str, Any]:
    """Load Generator controller: drives real multi-service HTTP calls through API Gateway."""
    apply_profile(request.profile)
    traces: list[dict[str, Any]] = []
    async with httpx.AsyncClient(base_url=LAB_SELF_URL, timeout=15.0) as client:
        for _ in range(request.iterations):
            trace_id = uuid.uuid4().hex
            corr_id = f"lab-corr-{trace_id[:16]}"
            resp = await client.post(
                "/services/api-gateway/orders/checkout",
                json={"sku": request.sku, "amount_usd": request.amount_usd},
                headers={
                    "X-Trace-ID": trace_id,
                    "X-Correlation-ID": corr_id,
                },
            )
            traces.append(resp.json())
    return {
        "profile": _RUNTIME.profile,
        "iterations": request.iterations,
        "traces": traces,
    }
