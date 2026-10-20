# ORIGIN — System & Domain Data Model

## 1. Database Schema Overview

All tables are managed via SQLAlchemy 2.0 Async declarative models (`backend/app/db/models.py`) and versioned through Alembic (`backend/alembic/versions/0001_initial_schema.py`).

| Table Name | Primary Purpose | Milestone 01/05 Usage |
| :--- | :--- | :--- |
| `registered_systems` | Metadata and environment flags (`is_synthetic_lab`) for observed software systems. | **Active** |
| `services` | Service nodes (`service_key`, `service_type`, `tier`, `registration_source`, `health_status`). | **Active** |
| `service_dependencies` | Directed service edges with provenance (`discovery_source`), `observation_count`, `error_count`, `last_latency_ms`. | **Active** |
| `telemetry_sources` | OpenTelemetry SDK/collector metadata (`exporter_protocol`, `sdk_version`, `total_batches_ingested`). | **Active** |
| `metric_observations` | Time-series operational metrics (`request_latency_ms`, `saturation_pct`) with `correlation_id` and `trace_id`. | **Active** |
| `span_observations` | Distributed trace spans establishing `parent_service_key -> service_key` causal call chains. | **Active** |
| `audit_events` | Immutable operational and safety audit trail. | **Active** |
| `hypotheses` | Falsifiable root-cause hypotheses. | **Schema Provisioned (M02/05)** |
| `evidence_records` | Empirical telemetry evidence linked to hypotheses. | **Schema Provisioned (M02/05)** |
| `experiment_definitions` | Bounded perturbation experiment specifications. | **Schema Provisioned (M03/05)** |
| `experiment_runs` | Execution records and safety abort logs for experiments. | **Schema Provisioned (M03/05)** |

## 2. Provenance Model for Services and Dependencies

ORIGIN tracks how every entity entered the system model:

- **`registered`**: Explicitly declared via `/api/v1/systems/{id}/services` or `/api/v1/systems/{id}/dependencies`, but not yet observed in live trace spans.
- **`observed`**: Automatically discovered from incoming OpenTelemetry spans (`service.name` resource attribute or `parent_service_key -> service_key` call transition) without prior manual declaration.
- **`registered_and_observed`**: Declared in the system registry and empirically confirmed by live span observations.

### Strict Non-Inference Rule
ORIGIN never fabricates or infers dependency edges from co-occurring metric spikes or naming heuristics in the topology builder. An edge is marked `verified_by_observation = true` if and only if at least one distributed trace span has been observed traversing `source_service_key -> target_service_key`.

## 3. Service Health Computation

During ingestion and topology synthesis, `TopologyService` evaluates the recent window of spans for each service:
- **`critical`**: Recent window error rate $\ge 15\%$ or $p95$ latency $\ge 600\text{ ms}$.
- **`degraded`**: Recent window error rate $> 0\%$ or $p95$ latency $\ge 220\text{ ms}$.
- **`healthy`**: Zero errors in the recent window and $p95$ latency $< 220\text{ ms}$.
- **`unknown`**: Service is declared (`registered`) but has zero stored observations.
