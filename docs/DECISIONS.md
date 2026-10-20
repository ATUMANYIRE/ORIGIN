# ORIGIN — Architectural Decision Records (ADRs)

## ADR-001: Strict Provenance Separation in Topology Discovery
- **Context:** Many APM tools conflate declared service catalogs with observed runtime call graphs or use heuristic correlation to guess edges.
- **Decision:** Every `ServiceRecord` and `ServiceDependency` tracks its explicit provenance (`registered`, `observed`, `registered_and_observed`). `TopologyService` never infers edges that are not explicitly declared or directly observed via `parent_service_key -> service_key` span transitions.
- **Consequence:** Operators and downstream causal discovery algorithms (Milestone 02/05) can distinguish verified runtime call paths from unverified architectural declarations.

## ADR-002: Dual OTLP/HTTP JSON + Structured Batch Telemetry Ingestion
- **Context:** Standard OpenTelemetry SDKs export `OTLP/HTTP JSON` (`resourceSpans`, `resourceMetrics`), while internal laboratory orchestrators benefit from atomic batch ingestion of spans and metrics.
- **Decision:** Implement standard OTLP JSON endpoints (`/api/v1/telemetry/otlp/v1/traces` and `/api/v1/telemetry/otlp/v1/metrics`) that normalize into ORIGIN's `TelemetryBatchIn` pipeline (`/api/v1/telemetry/ingest`).
- **Consequence:** Both standard OpenTelemetry collectors/SDKs and the Synthetic Distributed System Laboratory use the same persistence, provenance, and SSE broadcast pipeline.

## ADR-003: Dual-Mode Synthetic Distributed System Laboratory (Isolated Container + Embedded Pipeline)
- **Context:** In Docker Compose, the 5-service laboratory runs as an isolated container (`origin-lab`) on `origin_internal_net` without public host ports. In standalone `pytest` runs or local single-process development, the container may not be running separately.
- **Decision:** Provide the isolated FastAPI multi-service HTTP application (`lab/app.py`) for containerized deployment AND an identical instrumented pipeline in `SyntheticLabOrchestrator` as an automatic fallback when `LAB_CONTROLLER_URL` is unreachable.
- **Consequence:** Reproducible multi-service telemetry is guaranteed in both full Docker Compose deployments and fast local/CI test suites.

## ADR-004: Honest Contract Boundaries for Milestones 02–04
- **Context:** Milestone 01/05 establishes all 9 architectural boundaries, but Experimentation, Simulation, Agent Orchestration, and Causal Evidence are scheduled for Milestones 02–04.
- **Decision:** Provision the database tables (`experiment_definitions`, `experiment_runs`, `hypotheses`, `evidence_records`) in Migration `0001` and define typed Python `Protocol` and Pydantic contracts for Modules 5–8, while explicitly reporting `status: "architecture_contract_only"` and `execution_enabled: false`.
