# ORIGIN — Autonomous Scientific Intelligence Platform for Software Systems

> **Tagline:** *Give software the ability to understand itself.*
>
> **Current Milestone:** `02/05` — Autonomous Causal Scientist & Experimental Discovery Engine

ORIGIN is an autonomous scientific intelligence platform engineered to observe distributed software systems, construct provenance-verified topology graphs from live OpenTelemetry spans and metrics, formulate competing falsifiable causal hypotheses, and discover hidden root causes through seeded, block-randomized controlled experiments.

---

## Core Principles

1. **Zero Decorative Metrics:** Every figure displayed in the ORIGIN UI originates from real database records (`metric_observations`, `span_observations`, `services`, `service_dependencies`, `investigations`, `hypotheses`, `experiment_runs`, `evidence_records`), OpenTelemetry OTLP/HTTP JSON ingestion, or the explicitly labeled **Synthetic Distributed System Laboratory**.
2. **Strict Provenance in Topology Discovery:** ORIGIN never claims to infer dependencies that cannot be established from explicit declarations or observed parent→child span calls (`registered`, `observed`, `registered_and_observed`).
3. **Experimental Causality Over Observational Correlation:** Observational anomalies cap hypothesis prior support at $\le 0.65$. Higher support scores and `CONCLUDED` root-cause verdicts require statistically and practically significant latency reductions under block-randomized controlled interventions (Welch's two-sample $t$-test, 95% CI, and Cohen's $d$).
4. **Blinded Hidden-Fault Discovery:** Strict credential and state separation between the **Benchmark Controller** (`X-Benchmark-Controller-Key`) and **Autonomous Investigator** (`X-Origin-Key`) guarantees that hidden fault profiles are never leaked through status endpoints or span/metric attributes.
5. **Modular 9-Boundary Architecture:** Clear domain separation across `api_and_auth`, `system_registry`, `telemetry_ingestion`, `topology_discovery`, `experimentation`, `simulation` (contract for M03/05), `agents`, `evidence`, and `safety_and_audit`.

---

## Technology Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 Async, Alembic (`0001` & `0002`), `asyncpg` (PostgreSQL 16), `aiosqlite`, Redis 7, OpenTelemetry SDK.
- **Laboratory:** Isolated 5-service Synthetic Distributed System Laboratory (`api-gateway`, `checkout-service`, `inventory-service`, `payment-simulator`, `order-database-sim`), 5 fault profiles (`normal`, `payment_latency_spike`, `db_lock_contention`, `inventory_cpu_throttling`, `noisy_ambiguous_jitter`), and 4 allowlisted experimental interventions (`isolate_payment_fastpath`, `relieve_db_lock_contention`, `scale_inventory_workers`, `hedged_concurrency_limiter`).
- **Frontend:** Next.js 15 App Router, React 19, TypeScript (Strict), Tailwind CSS, React Flow (`@xyflow/react`), Recharts, Lucide Icons.
- **Quality & Verification:** Pytest, Ruff, Mypy (strict), Vitest, Playwright, Docker Compose, GitHub Actions CI.

---

## Quick Start

### 1. Run with Docker Compose (Recommended)

```bash
docker compose up -d --build
```

- **Frontend Scientific Instrument UI:** `http://localhost:3000` (including Causal Investigation Laboratory at `/investigations`)
- **Backend REST + OTLP + SSE + Investigation API:** `http://localhost:8000` (`http://localhost:8000/docs`)
- **PostgreSQL 16:** `localhost:5438` (internal `origin-postgres:5432`)
- **Redis 7:** `localhost:6399` (internal `origin-redis:6379`)
- **Synthetic Laboratory (`origin-lab`):** Strictly isolated on internal Docker network `origin_internal_net:8099` (never exposed publicly).

### 2. Local Development & Testing

**Backend (`backend/`):**
```bash
cd backend
.venv/Scripts/alembic upgrade head
.venv/Scripts/ruff check app tests alembic
.venv/Scripts/mypy app
.venv/Scripts/pytest -v
```

**Frontend (`frontend/`):**
```bash
cd frontend
npm run typecheck
npm run lint
npm run test
npm run build
```

---

## Documentation Index

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 9 modular boundaries, data flow, and system topology.
- [`docs/SYSTEM_MODEL.md`](docs/SYSTEM_MODEL.md) — Entity-relationship schema, provenance states, and health computation rules.
- [`docs/TELEMETRY.md`](docs/TELEMETRY.md) — Supported OTLP/HTTP JSON & native telemetry ingestion formats, correlation IDs, and SSE streaming.
- [`docs/CAUSAL_ENGINE.md`](docs/CAUSAL_ENGINE.md) — Autonomous investigation lifecycle state machine, deterministic hypothesis generation, and epistemic prior cap.
- [`docs/EXPERIMENT_PROTOCOL.md`](docs/EXPERIMENT_PROTOCOL.md) — Allowlisted interventions, experiment selection policy, and seeded block-randomized trial assignment.
- [`docs/SCIENTIFIC_EVIDENCE.md`](docs/SCIENTIFIC_EVIDENCE.md) — Welch's two-sample $t$-test, 95% confidence intervals, Cohen's $d$, and evidence ledger schema.
- [`docs/BENCHMARK_RESULTS.md`](docs/BENCHMARK_RESULTS.md) — Epistemic blinding architecture and verified 5-scenario hidden-fault benchmark matrix results.
- [`docs/INVESTIGATION_API.md`](docs/INVESTIGATION_API.md) — Complete REST API specification for `/api/v1/investigations/*` and `/api/v1/benchmarks/*`.
- [`docs/SECURITY.md`](docs/SECURITY.md) — Network isolation, API authentication, audit trail, and untrusted code prohibition.
- [`docs/TESTING.md`](docs/TESTING.md) — Backend, migration, laboratory, frontend, and Playwright verification guides.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — 5-Milestone execution plan (`01/05` through `05/05`).
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — Architectural Decision Records (ADRs).
- [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) — Truthful status matrix distinguishing implemented, contract-only, and verified capabilities.
