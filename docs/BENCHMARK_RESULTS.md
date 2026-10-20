# ORIGIN Hidden-Fault Benchmark Protocol & Results (`docs/BENCHMARK_RESULTS.md`)

**Milestone:** 02/05 — Autonomous Causal Scientist & Experimental Discovery Engine  
**Primary Module:** `backend/app/modules/laboratory/benchmark_controller.py` (`BenchmarkControllerService`)

---

## 1. Epistemic Separation & Blinding Architecture

To prove that ORIGIN discovers hidden faults through scientific experimentation rather than reading configuration flags, Milestone 02/05 enforces strict separation between two roles:

1. **Benchmark Controller (`X-Benchmark-Controller-Key`)**:
   - Stages the hidden fault profile via `set_lab_profile(profile, blinded=True)`.
   - Holds exclusive access to `get_private_ground_truth_for_evaluator()` and `/api/v1/benchmarks/*` endpoints.
   - Scores the investigator's final conclusion against `EXPECTED_BENCHMARK_GROUND_TRUTH` after the investigation terminates.
2. **Autonomous Investigator (`X-Origin-Key`)**:
   - Explicitly blocked from all `/api/v1/benchmarks/*` endpoints (`403 Forbidden` enforced by `verify_benchmark_controller` and verified in `test_epistemic_blinding_and_role_separation`).
   - When `blinded=True`, `/api/v1/lab/status` and `/api/v1/health` return `profile: "blinded_benchmark_mode"` with all fault parameters masked (`null`).
   - All ingested OpenTelemetry spans (`span_observations.attributes_json`) and metrics (`metric_observations.attributes_json`) are scrubbed of any profile names—containing only observable operational signals (`http.status_code`, `duration_ms`, `experiment.arm`, `experiment.intervention`).

---

## 2. Verified 5-Scenario Hidden-Fault Benchmark Matrix (`POST /api/v1/benchmarks/matrix`)

Executed with `random_seed=2026` and `sample_size_per_arm=6` (12 block-randomized trials per experiment):

| Scenario | Hidden Fault Profile | Expected Root Cause | Investigator Concluded Service | Concluded Mechanism | Lifecycle Status | Experiments Used | Trials Executed | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **1. Healthy Baseline System** | `normal` | `none` | `none` | `nominal_healthy_operation` | `CONCLUDED` | 0 / 2 | 0 | **PASS** |
| **2. Hidden Payment Gateway Degradation** | `payment_latency_spike` | `payment-simulator` | `payment-simulator` | `payment_gateway_latency_propagation` | `CONCLUDED` | 1 / 3 | 12 | **PASS** |
| **3. Hidden Database Lock Contention** | `db_lock_contention` | `order-database-sim` | `order-database-sim` | `database_lock_contention` | `CONCLUDED` | 1 / 3 | 12 | **PASS** |
| **4. Hidden Inventory Worker Starvation** | `inventory_cpu_throttling` | `inventory-service` | `inventory-service` | `inventory_worker_starvation` | `CONCLUDED` | 1 / 3 | 12 | **PASS** |
| **5. Ambiguous Multi-Service Noise** | `noisy_ambiguous_jitter` | `None` (`INCONCLUSIVE`) | `None` | `None` | `INCONCLUSIVE` | 3 / 3 | 36 | **PASS** |

### Aggregate Benchmark Metrics
- **Total Scenarios Executed:** `5`
- **Correct Root-Cause / Epistemic Classifications:** `5 / 5` (**100.0% Accuracy**)
- **False Positive Causal Claims on Noisy/Healthy Scenarios:** `0`
- **Blinding Leakage Violations:** `0`
