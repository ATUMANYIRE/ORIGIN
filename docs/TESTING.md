# ORIGIN — Verification & Testing Guide

## 1. Backend Verification Suite (`backend/`)

Run from `E:\Projects\ORIGIN\backend`:

```bash
# 1. Ruff Linter
.venv/Scripts/ruff check app tests alembic

# 2. Mypy Strict Type Check
.venv/Scripts/mypy app

# 3. Pytest Unit, Integration & Migration Suite
.venv/Scripts/pytest -v
```

### What Backend Tests Verify:
- **`test_migrations_and_schema.py`**: Executes `alembic upgrade head`, inspects all 11 schema tables (`registered_systems`, `services`, `service_dependencies`, `telemetry_sources`, `metric_observations`, `span_observations`, `experiment_definitions`, `experiment_runs`, `hypotheses`, `evidence_records`, `audit_events`), verifies `alembic downgrade base`, and re-applies `upgrade head`.
- **`test_registry_and_auth.py`**: Verifies `X-Correlation-ID` propagation, `401 Unauthorized` on invalid `X-Origin-Key`, system/service/dependency registration, `422` rejection on self-referential dependencies, and `audit_events` persistence.
- **`test_telemetry_and_topology.py`**: Verifies OpenTelemetry OTLP/HTTP JSON (`traces` and `metrics`) ingestion, provenance upgrade from `registered` to `registered_and_observed`, discovery of `observed` edges from parent→child spans, and strict non-inference of unestablished dependencies.
- **`test_laboratory_and_contracts.py`**: Executes multi-service transactions across all 5 laboratory services under `normal` and `payment_latency_spike` profiles, verifying latency degradation propagation and truthful reporting across all 9 architectural boundaries.

## 2. Frontend Verification Suite (`frontend/`)

Run from `E:\Projects\ORIGIN\frontend`:

```bash
# 1. TypeScript Strict Typecheck
npm run typecheck

# 2. Vitest Unit Tests
npm run test

# 3. Next.js Production Build
npm run build

# 4. Playwright Browser E2E Smoke Verification (with stack running on :3000 & :8000)
npx playwright test
```
