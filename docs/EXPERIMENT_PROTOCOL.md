# ORIGIN Controlled Experimentation Protocol (`docs/EXPERIMENT_PROTOCOL.md`)

**Milestone:** 02/05 — Autonomous Causal Scientist & Experimental Discovery Engine  
**Primary Module:** `backend/app/modules/experimentation/engine.py` (`ExperimentEngine`, `compute_experiment_statistics`, `generate_block_randomized_assignment`)

---

## 1. Safety & Allowlisted Interventions

The ORIGIN Experimentation Engine **never** executes arbitrary shell commands, dynamic SQL, or untrusted user code. Only explicitly allowlisted, reversible laboratory interventions defined in `ALLOWLISTED_INTERVENTIONS` (`backend/app/modules/laboratory/orchestrator.py`) may be planned or executed:

| Intervention Key | Target Service | Mechanism Tested | Physical Effect in Synthetic Laboratory |
| :--- | :--- | :--- | :--- |
| `isolate_payment_fastpath` | `payment-simulator` | `payment_gateway_latency_propagation` | Routes payment authorization through an isolated fast-path pool, neutralizing payment gateway latency spikes (~88% added latency reduction) without altering database or inventory faults. |
| `relieve_db_lock_contention` | `order-database-sim` | `database_lock_contention` | Enables optimistic concurrency & lock partitioning on order persistence, relieving row-lock contention (~88% added lock latency reduction) without altering payment or inventory faults. |
| `scale_inventory_workers` | `inventory-service` | `inventory_worker_starvation` | Allocates dedicated high-priority CPU worker threads for inventory reservation (~88% added CPU throttling reduction) without altering payment or database faults. |
| `hedged_concurrency_limiter` | `checkout-service` | `concurrency_queue_accumulation` | Applies adaptive concurrency limiting and request hedging at checkout orchestration (~15% jitter damping across general noise). |

Attempting to schedule any intervention key outside this allowlist raises a `ValueError` prior to execution.

---

## 2. Experiment Selection Policy (`ExperimentEngine.select_and_plan_experiment`)

During the `PLANNING` state, `ExperimentEngine.select_and_plan_experiment`:
1. Filters candidate hypotheses to those in `"proposed"` state that have not yet been tested in the current investigation.
2. Verifies that the investigation has remaining `experiment_budget` (`experiments_used + budget_cost <= experiment_budget`).
3. Scores each candidate by combining its observational prior score with topological specificity (preferring leaf/downstream dependency interventions over broad upstream mitigations to isolate root causes).
4. Persists an `ExperimentDefinition` record containing explicit `control_condition_json`, `treatment_condition_json`, `sample_size_per_arm`, `random_seed`, `selection_score`, and `safety_envelope_json`.

---

## 3. Seeded Block-Randomized Trial Assignment

To prevent temporal drift or warmup effects from biasing treatment vs. control comparisons, `generate_block_randomized_assignment(sample_size_per_arm, random_seed)` divides the $2N$ trials into $N$ consecutive blocks of size 2:
- Each block contains exactly one `"control"` trial (`intervention="none"`) and one `"treatment"` trial (`intervention=perturbation_type`), shuffled deterministically using `random.Random(random_seed)`.
- Identical `(sample_size_per_arm, random_seed)` pairs always produce the exact same trial assignment sequence (`assignment_order_json`).
- Every individual trial executes a real multi-service OpenTelemetry-instrumented transaction across all 5 services (`api-gateway`, `checkout-service`, `inventory-service`, `payment-simulator`, `order-database-sim`) and records its `correlation_id`, `trace_id`, `target_metric_value_ms`, and `focal_service_latency_ms` in `trial_observations_json`.
