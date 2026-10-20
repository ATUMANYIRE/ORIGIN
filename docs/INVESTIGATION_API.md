# ORIGIN Investigation & Benchmark API Reference (`docs/INVESTIGATION_API.md`)

**Milestone:** 02/05 — Autonomous Causal Scientist & Experimental Discovery Engine  
**Base Router:** `backend/app/api/router.py` (`/api/v1`)

---

## 1. Investigator Endpoints (`X-Origin-Key`)

### `POST /api/v1/investigations`
Create a new autonomous scientific investigation and optionally execute the full reasoning and experimentation loop immediately (`auto_run: true`).

**Request Body (`InvestigationCreateRequest`):**
```json
{
  "system_slug": "origin-synthetic-lab",
  "title": "Autonomous Checkout Latency Investigation",
  "target_service_key": "checkout-service",
  "target_metric": "request_latency_ms",
  "experiment_budget": 3,
  "sample_size_per_arm": 6,
  "random_seed": 42,
  "timeout_seconds": 60,
  "auto_run": true
}
```
**Response (`201 Created`):** `InvestigationDetailRead` (includes `lifecycle_history_json`, `decision_history_json`, `hypotheses`, `experiment_plans`, `experiment_runs`, and `evidence_records`).

### `GET /api/v1/investigations`
List recent investigations ordered by creation timestamp (`list[InvestigationRead]`).

### `GET /api/v1/investigations/{investigation_id}`
Retrieve full investigation detail (`InvestigationDetailRead`).

### `POST /api/v1/investigations/{investigation_id}/start`
Start or resume an investigation created with `auto_run: false`.

### `POST /api/v1/investigations/{investigation_id}/cancel`
Request immediate cancellation of a pending or running investigation, transitioning its state to `CANCELLED`.

### `GET /api/v1/investigations/{investigation_id}/hypotheses`
Retrieve all competing causal hypotheses generated for the investigation, ordered by posterior `confidence_score` (`list[HypothesisRead]`).

### `GET /api/v1/investigations/{investigation_id}/experiments`
Retrieve all planned `ExperimentDefinitionRead` specifications and executed `ExperimentRunRead` trial records.

### `GET /api/v1/investigations/{investigation_id}/evidence`
Retrieve all immutable `EvidenceRecord` artifacts (`observational_correlation` and `controlled_experiment`) linked to the investigation.

### `GET /api/v1/investigations/{investigation_id}/export?format=markdown|json`
Export a reproducible scientific investigation report containing executive conclusions, remaining uncertainty, baseline observations, competing hypotheses, Welch two-sample statistical tables, and trace correlation IDs.

### `GET /api/v1/experiments/interventions`
List allowlisted laboratory interventions (`isolate_payment_fastpath`, `relieve_db_lock_contention`, `scale_inventory_workers`, `hedged_concurrency_limiter`) and the active safety policy.

---

## 2. Protected Benchmark Controller Endpoints (`X-Benchmark-Controller-Key` Only)

> **Security & Epistemic Separation Note:** Requests bearing `X-Origin-Key` (Investigator credentials) or missing `X-Benchmark-Controller-Key` receive `403 Forbidden`.

### `GET /api/v1/benchmarks/ground-truth`
Inspect the unmasked private laboratory fault state (`PrivateLabGroundTruthState`).

### `POST /api/v1/benchmarks/stage-hidden-fault/{profile}`
Stage a fault profile (`normal`, `payment_latency_spike`, `db_lock_contention`, `inventory_cpu_throttling`, `noisy_ambiguous_jitter`) with `blinded=True`.

### `POST /api/v1/benchmarks/run`
Execute a single blinded hidden-fault benchmark run (`BenchmarkScenarioRequest`) and evaluate the investigator's conclusion (`BenchmarkRunRead`).

### `POST /api/v1/benchmarks/matrix?random_seed=2026`
Execute the complete 5-scenario hidden-fault benchmark matrix and return aggregate accuracy and per-scenario evaluation records (`BenchmarkMatrixResponse`).

### `GET /api/v1/benchmarks/runs`
List historical benchmark evaluation records (`list[BenchmarkRunRead]`).
