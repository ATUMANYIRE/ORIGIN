"""Pydantic v2 schemas for OpenTelemetry OTLP JSON and native telemetry ingestion."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MetricObservationIn(BaseModel):
    """Single operational metric observation point."""

    service_key: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9\-_]*$")
    metric_name: str = Field(..., min_length=2, max_length=120)
    metric_unit: str = Field(default="ms", max_length=32)
    value: float = Field(...)
    correlation_id: str | None = Field(default=None, max_length=120)
    trace_id: str | None = Field(default=None, max_length=64)
    attributes_json: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SpanObservationIn(BaseModel):
    """Single distributed trace span observation."""

    trace_id: str = Field(..., min_length=8, max_length=64)
    span_id: str = Field(..., min_length=4, max_length=64)
    parent_span_id: str | None = Field(default=None, max_length=64)
    correlation_id: str = Field(..., min_length=4, max_length=120)
    service_key: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9\-_]*$")
    parent_service_key: str | None = Field(
        default=None, min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9\-_]*$"
    )
    operation_name: str = Field(..., min_length=1, max_length=200)
    span_kind: Literal["SERVER", "CLIENT", "INTERNAL", "PRODUCER", "CONSUMER"] = "SERVER"
    status_code: Literal["OK", "ERROR", "UNSET"] = "OK"
    http_status: int = Field(default=200, ge=100, le=599)
    duration_ms: float = Field(..., ge=0.0)
    attributes_json: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TelemetryBatchIn(BaseModel):
    """Structured batch ingestion payload for ORIGIN."""

    system_slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9\-_]*$")
    source_name: str = Field(default="otel-collector", min_length=2, max_length=160)
    exporter_protocol: str = Field(default="otlp-http-json", max_length=64)
    sdk_version: str = Field(default="opentelemetry-python-1.27", max_length=64)
    is_synthetic: bool = Field(default=False)
    metrics: list[MetricObservationIn] = Field(default_factory=list)
    spans: list[SpanObservationIn] = Field(default_factory=list)


class OTLPKeyValue(BaseModel):
    """OTLP JSON attribute key-value pair."""

    key: str
    value: dict[str, Any]


class OTLPResource(BaseModel):
    """OTLP JSON resource descriptor."""

    attributes: list[OTLPKeyValue] = Field(default_factory=list)


class OTLPSpan(BaseModel):
    """OTLP JSON span representation."""

    traceId: str  # noqa: N815
    spanId: str  # noqa: N815
    parentSpanId: str | None = None  # noqa: N815
    name: str
    kind: int | str = 2
    startTimeUnixNano: int | str | None = None  # noqa: N815
    endTimeUnixNano: int | str | None = None  # noqa: N815
    attributes: list[OTLPKeyValue] = Field(default_factory=list)
    status: dict[str, Any] = Field(default_factory=dict)


class OTLPScopeSpans(BaseModel):
    """OTLP JSON scopeSpans container."""

    scope: dict[str, Any] = Field(default_factory=dict)
    spans: list[OTLPSpan] = Field(default_factory=list)


class OTLPResourceSpans(BaseModel):
    """OTLP JSON resourceSpans item."""

    resource: OTLPResource = Field(default_factory=OTLPResource)
    scopeSpans: list[OTLPScopeSpans] = Field(default_factory=list)  # noqa: N815


class OTLPTracesPayload(BaseModel):
    """Standard OpenTelemetry OTLP/HTTP JSON Traces export payload."""

    resourceSpans: list[OTLPResourceSpans] = Field(default_factory=list)  # noqa: N815


class OTLPNumberDataPoint(BaseModel):
    """OTLP JSON metric number data point."""

    attributes: list[OTLPKeyValue] = Field(default_factory=list)
    timeUnixNano: int | str | None = None  # noqa: N815
    asDouble: float | None = None  # noqa: N815
    asInt: int | str | None = None  # noqa: N815


class OTLPMetricItem(BaseModel):
    """OTLP JSON metric definition."""

    name: str
    unit: str = "ms"
    gauge: dict[str, list[OTLPNumberDataPoint]] | None = None
    sum: dict[str, Any] | None = None


class OTLPScopeMetrics(BaseModel):
    """OTLP JSON scopeMetrics container."""

    scope: dict[str, Any] = Field(default_factory=dict)
    metrics: list[OTLPMetricItem] = Field(default_factory=list)


class OTLPResourceMetrics(BaseModel):
    """OTLP JSON resourceMetrics item."""

    resource: OTLPResource = Field(default_factory=OTLPResource)
    scopeMetrics: list[OTLPScopeMetrics] = Field(default_factory=list)  # noqa: N815


class OTLPMetricsPayload(BaseModel):
    """Standard OpenTelemetry OTLP/HTTP JSON Metrics export payload."""

    resourceMetrics: list[OTLPResourceMetrics] = Field(default_factory=list)  # noqa: N815


class TelemetryIngestionReceipt(BaseModel):
    """Receipt returned after persisting a telemetry batch."""

    system_id: str
    system_slug: str
    source_id: str
    metrics_ingested: int
    spans_ingested: int
    observed_edges_updated: int
    correlation_ids: list[str]
    ingested_at: datetime


class MetricPointRead(BaseModel):
    """Serialized time-series metric point."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    service_key: str
    metric_name: str
    metric_unit: str
    value: float
    correlation_id: str | None
    trace_id: str | None
    is_synthetic: bool
    attributes_json: dict[str, Any]
    observed_at: datetime


class MetricSeriesSummary(BaseModel):
    """Statistical summary of a queried metric time-series."""

    system_id: str
    service_key: str | None
    metric_name: str
    metric_unit: str
    sample_count: int
    min_value: float | None
    max_value: float | None
    mean_value: float | None
    p95_value: float | None
    latest_value: float | None
    points: list[MetricPointRead]


class SpanRead(BaseModel):
    """Serialized distributed trace span observation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    correlation_id: str
    service_key: str
    parent_service_key: str | None
    operation_name: str
    span_kind: str
    status_code: str
    http_status: int
    duration_ms: float
    is_synthetic: bool
    attributes_json: dict[str, Any]
    started_at: datetime
