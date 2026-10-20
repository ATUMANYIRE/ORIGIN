"""Service layer for OpenTelemetry ingestion, provenance-aware dependency updates, and queries."""

import contextlib
import math
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.models import (
    MetricObservation,
    ServiceDependency,
    ServiceRecord,
    SpanObservation,
    TelemetrySource,
)
from app.modules.registry.schemas import SystemCreate
from app.modules.registry.service import RegistryService
from app.modules.telemetry.schemas import (
    MetricObservationIn,
    MetricPointRead,
    MetricSeriesSummary,
    OTLPKeyValue,
    OTLPMetricsPayload,
    OTLPNumberDataPoint,
    OTLPTracesPayload,
    SpanObservationIn,
    SpanRead,
    TelemetryBatchIn,
    TelemetryIngestionReceipt,
)


def _extract_otlp_attributes(kv_list: list[OTLPKeyValue]) -> dict[str, Any]:
    """Flatten OTLP KeyValue list into a standard Python dictionary."""
    out: dict[str, Any] = {}
    for item in kv_list:
        val_dict = item.value
        for v_key in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if v_key in val_dict:
                raw_val = val_dict[v_key]
                if v_key == "intValue" and isinstance(raw_val, str):
                    with contextlib.suppress(ValueError):
                        raw_val = int(raw_val)
                out[item.key] = raw_val
                break
    return out


def _sanitize_slug(raw: str, default: str = "unknown-service") -> str:
    """Ensure service or system slug adheres to strict lowercase alphanumeric-hyphen format."""
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in raw.lower()).strip("-_")
    return cleaned[:120] if len(cleaned) >= 2 else default


class TelemetryService:
    """Handles persistent telemetry ingestion, observed topology updates, and metric queries."""

    @staticmethod
    async def ingest_batch(
        db: AsyncSession,
        batch: TelemetryBatchIn,
    ) -> TelemetryIngestionReceipt:
        """Persist a batch of metrics and spans, updating observed services and dependencies."""
        now = datetime.now(UTC)
        system = await RegistryService.create_or_get_system(
            db,
            SystemCreate(
                slug=batch.system_slug,
                name=batch.system_slug.replace("-", " ").title(),
                environment="synthetic-lab" if batch.is_synthetic else "production",
                description=(
                    "Synthetic Distributed System Laboratory"
                    if batch.is_synthetic
                    else f"Observed system {batch.system_slug}"
                ),
                is_synthetic_lab=batch.is_synthetic,
            ),
        )

        # Upsert TelemetrySource metadata
        src_stmt = select(TelemetrySource).where(
            TelemetrySource.system_id == system.id,
            TelemetrySource.source_name == batch.source_name,
        )
        source = (await db.execute(src_stmt)).scalar_one_or_none()
        if source is None:
            source = TelemetrySource(
                system_id=system.id,
                source_name=batch.source_name,
                exporter_protocol=batch.exporter_protocol,
                sdk_version=batch.sdk_version,
                is_synthetic=batch.is_synthetic,
                total_batches_ingested=1,
                last_ingested_at=now,
            )
            db.add(source)
            await db.flush()
        else:
            source.total_batches_ingested += 1
            source.last_ingested_at = now
            source.is_synthetic = batch.is_synthetic

        # Cache existing services for this system
        svc_rows = (
            (await db.execute(select(ServiceRecord).where(ServiceRecord.system_id == system.id)))
            .scalars()
            .all()
        )
        service_map: dict[str, ServiceRecord] = {s.service_key: s for s in svc_rows}

        async def ensure_service_observed(
            service_key: str,
            latency_ms: float | None = None,
            is_error: bool = False,
        ) -> ServiceRecord:
            svc = service_map.get(service_key)
            if svc is None:
                svc = ServiceRecord(
                    system_id=system.id,
                    service_key=service_key,
                    display_name=service_key.replace("-", " ").title(),
                    service_type="microservice",
                    tier="tier-1",
                    owner_team="observed-telemetry",
                    registration_source="observed",
                    health_status="healthy",
                    last_seen_at=now,
                )
                db.add(svc)
                await db.flush()
                service_map[service_key] = svc
            else:
                svc.last_seen_at = now
                if svc.registration_source == "registered":
                    svc.registration_source = "registered_and_observed"

            if is_error:
                svc.health_status = "critical"
            elif latency_ms is not None:
                if latency_ms >= 600.0:
                    svc.health_status = "critical"
                elif latency_ms >= 220.0:
                    svc.health_status = "degraded"
                else:
                    svc.health_status = "healthy"
            elif svc.health_status == "unknown":
                svc.health_status = "healthy"
            return svc

        correlation_ids: set[str] = set()

        # 1. Map span_id -> service_key within the batch for parent service resolution
        batch_span_service: dict[str, str] = {sp.span_id: sp.service_key for sp in batch.spans}

        observed_edges_updated = 0

        # 2. Persist SpanObservations and update observed ServiceDependencies
        for sp in batch.spans:
            correlation_ids.add(sp.correlation_id)
            is_err = sp.status_code == "ERROR" or sp.http_status >= 500
            await ensure_service_observed(
                sp.service_key, latency_ms=sp.duration_ms, is_error=is_err
            )

            resolved_parent_service = sp.parent_service_key
            if not resolved_parent_service and sp.parent_span_id:
                resolved_parent_service = batch_span_service.get(sp.parent_span_id)
                if not resolved_parent_service:
                    parent_row = (
                        await db.execute(
                            select(SpanObservation.service_key).where(
                                SpanObservation.system_id == system.id,
                                SpanObservation.span_id == sp.parent_span_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if parent_row:
                        resolved_parent_service = parent_row

            span_model = SpanObservation(
                system_id=system.id,
                trace_id=sp.trace_id,
                span_id=sp.span_id,
                parent_span_id=sp.parent_span_id,
                correlation_id=sp.correlation_id,
                service_key=sp.service_key,
                parent_service_key=resolved_parent_service,
                operation_name=sp.operation_name,
                span_kind=sp.span_kind,
                status_code=sp.status_code,
                http_status=sp.http_status,
                duration_ms=sp.duration_ms,
                is_synthetic=batch.is_synthetic,
                attributes_json=sp.attributes_json,
                started_at=sp.started_at,
            )
            db.add(span_model)

            # Update directed dependency ONLY when an actual parent->child call is observed
            if resolved_parent_service and resolved_parent_service != sp.service_key:
                await ensure_service_observed(resolved_parent_service)
                dep_stmt = select(ServiceDependency).where(
                    ServiceDependency.system_id == system.id,
                    ServiceDependency.source_service_key == resolved_parent_service,
                    ServiceDependency.target_service_key == sp.service_key,
                )
                dep = (await db.execute(dep_stmt)).scalar_one_or_none()
                if dep is None:
                    dep = ServiceDependency(
                        system_id=system.id,
                        source_service_key=resolved_parent_service,
                        target_service_key=sp.service_key,
                        protocol=str(sp.attributes_json.get("rpc.system", "http")),
                        discovery_source="observed",
                        observation_count=1,
                        error_count=1 if is_err else 0,
                        last_latency_ms=sp.duration_ms,
                        last_observed_at=sp.started_at,
                    )
                    db.add(dep)
                    await db.flush()
                else:
                    if dep.discovery_source == "registered":
                        dep.discovery_source = "registered_and_observed"
                    dep.observation_count += 1
                    if is_err:
                        dep.error_count += 1
                    dep.last_latency_ms = sp.duration_ms
                    dep.last_observed_at = sp.started_at
                observed_edges_updated += 1

        # 3. Persist MetricObservations
        for m in batch.metrics:
            if m.correlation_id:
                correlation_ids.add(m.correlation_id)
            is_lat = "latency" in m.metric_name or "duration" in m.metric_name
            latency_hint = m.value if is_lat else None
            await ensure_service_observed(m.service_key, latency_ms=latency_hint)
            metric_model = MetricObservation(
                system_id=system.id,
                service_key=m.service_key,
                metric_name=m.metric_name,
                metric_unit=m.metric_unit,
                value=m.value,
                correlation_id=m.correlation_id,
                trace_id=m.trace_id,
                is_synthetic=batch.is_synthetic,
                attributes_json=m.attributes_json,
                observed_at=m.observed_at,
            )
            db.add(metric_model)

        await db.commit()

        receipt = TelemetryIngestionReceipt(
            system_id=system.id,
            system_slug=system.slug,
            source_id=source.id,
            metrics_ingested=len(batch.metrics),
            spans_ingested=len(batch.spans),
            observed_edges_updated=observed_edges_updated,
            correlation_ids=sorted(correlation_ids),
            ingested_at=now,
        )

        await event_bus.publish(
            "telemetry.ingested",
            {
                "system_id": system.id,
                "system_slug": system.slug,
                "metrics_ingested": receipt.metrics_ingested,
                "spans_ingested": receipt.spans_ingested,
                "observed_edges_updated": receipt.observed_edges_updated,
                "correlation_ids": receipt.correlation_ids[:5],
            },
        )
        return receipt

    @staticmethod
    async def ingest_otlp_traces(
        db: AsyncSession,
        payload: OTLPTracesPayload,
        default_system_slug: str = "origin-synthetic-lab",
    ) -> list[TelemetryIngestionReceipt]:
        """Translate standard OpenTelemetry OTLP JSON Traces into ORIGIN telemetry batches."""
        batches_by_system: dict[str, TelemetryBatchIn] = {}

        for res_spans in payload.resourceSpans:
            res_attrs = _extract_otlp_attributes(res_spans.resource.attributes)
            sys_slug = _sanitize_slug(
                str(res_attrs.get("origin.system.slug", default_system_slug)),
                default=default_system_slug,
            )
            service_key = _sanitize_slug(str(res_attrs.get("service.name", "unknown-service")))
            is_synthetic = bool(res_attrs.get("origin.is_synthetic", True))

            batch = batches_by_system.get(sys_slug)
            if batch is None:
                batch = TelemetryBatchIn(
                    system_slug=sys_slug,
                    source_name="otlp-http-json-traces",
                    exporter_protocol="otlp-http-json",
                    sdk_version=str(res_attrs.get("telemetry.sdk.version", "otel-1.27")),
                    is_synthetic=is_synthetic,
                )
                batches_by_system[sys_slug] = batch

            for scope_span in res_spans.scopeSpans:
                for sp in scope_span.spans:
                    sp_attrs = _extract_otlp_attributes(sp.attributes)
                    start_ns = int(sp.startTimeUnixNano or 0)
                    end_ns = int(sp.endTimeUnixNano or 0)
                    duration_ms = (
                        max(0.05, (end_ns - start_ns) / 1_000_000.0)
                        if end_ns > start_ns
                        else float(sp_attrs.get("origin.duration_ms", 1.0))
                    )
                    started_at = (
                        datetime.fromtimestamp(start_ns / 1_000_000_000.0, tz=UTC)
                        if start_ns > 0
                        else datetime.now(UTC)
                    )
                    corr_id = str(sp_attrs.get("origin.correlation_id", f"otlp-{sp.traceId[:16]}"))
                    parent_svc_raw = sp_attrs.get("origin.parent_service")
                    parent_svc = _sanitize_slug(str(parent_svc_raw)) if parent_svc_raw else None
                    http_status = int(sp_attrs.get("http.status_code", 200))
                    status_code: Any = "ERROR" if http_status >= 500 else "OK"
                    if sp.status.get("code") in (2, "STATUS_CODE_ERROR", "ERROR"):
                        status_code = "ERROR"

                    batch.spans.append(
                        SpanObservationIn(
                            trace_id=sp.traceId,
                            span_id=sp.spanId,
                            parent_span_id=sp.parentSpanId or None,
                            correlation_id=corr_id,
                            service_key=service_key,
                            parent_service_key=parent_svc,
                            operation_name=sp.name,
                            span_kind="SERVER",
                            status_code=status_code,
                            http_status=http_status,
                            duration_ms=round(duration_ms, 3),
                            attributes_json=sp_attrs,
                            started_at=started_at,
                        )
                    )
                    # Also record span duration as a latency metric observation
                    batch.metrics.append(
                        MetricObservationIn(
                            service_key=service_key,
                            metric_name="request_latency_ms",
                            metric_unit="ms",
                            value=round(duration_ms, 3),
                            correlation_id=corr_id,
                            trace_id=sp.traceId,
                            attributes_json={"operation": sp.name, "http_status": http_status},
                            observed_at=started_at,
                        )
                    )

        receipts: list[TelemetryIngestionReceipt] = []
        for b in batches_by_system.values():
            receipts.append(await TelemetryService.ingest_batch(db, b))
        return receipts

    @staticmethod
    async def ingest_otlp_metrics(
        db: AsyncSession,
        payload: OTLPMetricsPayload,
        default_system_slug: str = "origin-synthetic-lab",
    ) -> list[TelemetryIngestionReceipt]:
        """Translate standard OpenTelemetry OTLP JSON Metrics into ORIGIN telemetry batches."""
        batches_by_system: dict[str, TelemetryBatchIn] = {}

        for res_metrics in payload.resourceMetrics:
            res_attrs = _extract_otlp_attributes(res_metrics.resource.attributes)
            sys_slug = _sanitize_slug(
                str(res_attrs.get("origin.system.slug", default_system_slug)),
                default=default_system_slug,
            )
            service_key = _sanitize_slug(str(res_attrs.get("service.name", "unknown-service")))
            is_synthetic = bool(res_attrs.get("origin.is_synthetic", True))

            batch = batches_by_system.get(sys_slug)
            if batch is None:
                batch = TelemetryBatchIn(
                    system_slug=sys_slug,
                    source_name="otlp-http-json-metrics",
                    exporter_protocol="otlp-http-json",
                    sdk_version=str(res_attrs.get("telemetry.sdk.version", "otel-1.27")),
                    is_synthetic=is_synthetic,
                )
                batches_by_system[sys_slug] = batch

            for scope_metric in res_metrics.scopeMetrics:
                for m_item in scope_metric.metrics:
                    points: list[OTLPNumberDataPoint | dict[str, Any]] = []
                    if m_item.gauge and "dataPoints" in m_item.gauge:
                        points.extend(m_item.gauge["dataPoints"])
                    if m_item.sum and "dataPoints" in m_item.sum:
                        points.extend(m_item.sum["dataPoints"])

                    for pt in points:
                        if isinstance(pt, OTLPNumberDataPoint):
                            pt_attrs = _extract_otlp_attributes(pt.attributes)
                            val = (
                                float(pt.asDouble)
                                if pt.asDouble is not None
                                else float(pt.asInt or 0.0)
                            )
                            ts_ns = int(pt.timeUnixNano or 0)
                        else:
                            pt_attrs = _extract_otlp_attributes(
                                [OTLPKeyValue(**kv) for kv in pt.get("attributes", [])]
                            )
                            raw_num = pt.get("asDouble")
                            if raw_num is None:
                                raw_num = pt.get("asInt", 0.0)
                            val = float(raw_num or 0.0)
                            ts_ns = int(pt.get("timeUnixNano") or 0)

                        observed_at = (
                            datetime.fromtimestamp(ts_ns / 1_000_000_000.0, tz=UTC)
                            if ts_ns > 0
                            else datetime.now(UTC)
                        )
                        corr_id = (
                            str(pt_attrs["origin.correlation_id"])
                            if "origin.correlation_id" in pt_attrs
                            else None
                        )
                        batch.metrics.append(
                            MetricObservationIn(
                                service_key=service_key,
                                metric_name=m_item.name,
                                metric_unit=m_item.unit or "ms",
                                value=val,
                                correlation_id=corr_id,
                                attributes_json=pt_attrs,
                                observed_at=observed_at,
                            )
                        )

        receipts: list[TelemetryIngestionReceipt] = []
        for b in batches_by_system.values():
            receipts.append(await TelemetryService.ingest_batch(db, b))
        return receipts

    @staticmethod
    async def query_metric_series(
        db: AsyncSession,
        system_identifier: str,
        metric_name: str = "request_latency_ms",
        service_key: str | None = None,
        limit: int = 120,
    ) -> MetricSeriesSummary:
        """Query time-series metric points and compute statistical aggregations."""
        system = await RegistryService.get_system_by_id_or_slug(db, system_identifier)
        stmt = (
            select(MetricObservation)
            .where(
                MetricObservation.system_id == system.id,
                MetricObservation.metric_name == metric_name,
            )
            .order_by(MetricObservation.observed_at.desc())
            .limit(limit)
        )
        if service_key:
            stmt = stmt.where(MetricObservation.service_key == service_key)

        rows = list((await db.execute(stmt)).scalars().all())
        # Reverse to chronological order for plotting
        rows.reverse()

        values = [r.value for r in rows]
        unit = rows[-1].metric_unit if rows else "ms"
        if not values:
            return MetricSeriesSummary(
                system_id=system.id,
                service_key=service_key,
                metric_name=metric_name,
                metric_unit=unit,
                sample_count=0,
                min_value=None,
                max_value=None,
                mean_value=None,
                p95_value=None,
                latest_value=None,
                points=[],
            )

        sorted_vals = sorted(values)
        p95_idx = min(len(sorted_vals) - 1, max(0, math.ceil(0.95 * len(sorted_vals)) - 1))
        return MetricSeriesSummary(
            system_id=system.id,
            service_key=service_key,
            metric_name=metric_name,
            metric_unit=unit,
            sample_count=len(values),
            min_value=round(min(values), 3),
            max_value=round(max(values), 3),
            mean_value=round(sum(values) / len(values), 3),
            p95_value=round(sorted_vals[p95_idx], 3),
            latest_value=round(values[-1], 3),
            points=[MetricPointRead.model_validate(r) for r in rows],
        )

    @staticmethod
    async def list_recent_spans(
        db: AsyncSession,
        system_identifier: str,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        service_key: str | None = None,
        limit: int = 100,
    ) -> list[SpanRead]:
        """Query distributed trace spans with optional correlation_id or trace_id filtering."""
        system = await RegistryService.get_system_by_id_or_slug(db, system_identifier)
        stmt = (
            select(SpanObservation)
            .where(SpanObservation.system_id == system.id)
            .order_by(SpanObservation.started_at.desc())
            .limit(limit)
        )
        if correlation_id:
            stmt = stmt.where(SpanObservation.correlation_id == correlation_id)
        if trace_id:
            stmt = stmt.where(SpanObservation.trace_id == trace_id)
        if service_key:
            stmt = stmt.where(SpanObservation.service_key == service_key)

        rows = list((await db.execute(stmt)).scalars().all())
        return [SpanRead.model_validate(r) for r in rows]
