# ORIGIN — OpenTelemetry Ingestion & Real-Time Streaming

## 1. Supported Telemetry Formats

ORIGIN supports two documented telemetry ingestion formats:

### A. OpenTelemetry OTLP/HTTP JSON (`v1/traces` and `v1/metrics`)

- **Traces Endpoint:** `POST /api/v1/telemetry/otlp/v1/traces`
  - Accepts standard OTLP JSON `resourceSpans -> scopeSpans -> spans`.
  - Extracts `service.name`, `origin.system.slug`, `origin.is_synthetic` from `resource.attributes`.
  - Extracts `origin.correlation_id`, `origin.parent_service`, `http.status_code`, and `origin.duration_ms` (or computes duration from `endTimeUnixNano - startTimeUnixNano`).
- **Metrics Endpoint:** `POST /api/v1/telemetry/otlp/v1/metrics`
  - Accepts standard OTLP JSON `resourceMetrics -> scopeMetrics -> metrics` (`gauge` and `sum` number data points).

### B. Native Structured Telemetry Batch (`/api/v1/telemetry/ingest`)

- **Batch Endpoint:** `POST /api/v1/telemetry/ingest`
- Accepts a validated `TelemetryBatchIn` JSON payload containing `system_slug`, `source_name`, `exporter_protocol`, `sdk_version`, `is_synthetic`, `spans[]`, and `metrics[]`.

## 2. Correlation IDs & Distributed Trace Linkage

- Every HTTP request handled by ORIGIN receives or preserves an `X-Correlation-ID` header.
- Every synthetic laboratory transaction generates a unique `trace_id` and `correlation_id` (`lab-corr-<16-hex>`), which propagates across:
  1. `api-gateway` (`POST /orders/checkout`)
  2. `checkout-service` (`POST /internal/checkout`)
  3. `inventory-service` (`POST /internal/inventory/reserve`)
  4. `payment-simulator` (`POST /internal/payments/authorize`)
  5. `order-database-sim` (`SELECT FOR UPDATE inventory_stock` & `INSERT INTO orders`)
- Operators can filter all spans and metrics by `correlation_id` or `trace_id` via `GET /api/v1/telemetry/spans` and in the `/telemetry` UI workspace.

## 3. Real-Time Updates via Server-Sent Events (SSE)

- **Endpoint:** `GET /api/v1/telemetry/stream`
- Uses `text/event-stream` coordinated via `TelemetryEventBus` (backed by Redis Pub/Sub channel `origin:telemetry:events` with automatic in-memory fallback when Redis is absent in unit tests).
- Whenever a telemetry batch is ingested, ORIGIN emits a `telemetry.ingested` event containing the updated counts and correlation IDs, prompting the Next.js UI to refresh topology and time-series views in real time.
