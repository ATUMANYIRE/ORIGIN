# ORIGIN — Counterfactual Reasoning & Parallel Futures (`Milestone 03/05`)

## 1. Counterfactual Branching
A **Counterfactual Branch** (`SimulationBranchRecord`) represents a simulated future trajectory conditioned on:
1. A calibrated Digital Twin model (`twin_model_id`)
2. An optional saved state snapshot (`initial_snapshot_id`)
3. A deterministic random seed (`random_seed`)
4. A sequence of allowlisted interventions (`interventions_json`)

---

## 2. Allowlisted Counterfactual Interventions
Arbitrary shell execution and untrusted code are strictly prohibited. Only the following 8 typed interventions are permitted (`ALLOWLISTED_TWIN_INTERVENTIONS`):

| Intervention Type | Target | Physical Effect in Simulator |
|---|---|---|
| `increase_replicas` | Any service | Scales `replica_count` (expands service capacity, but increases downstream DB lock concurrency pressure if `checkout-service` is scaled). |
| `reduce_incoming_traffic` | `api-gateway` | Applies rate-limiting factor to `incoming_traffic_rps` (stabilizes latency and queues at the cost of reduced throughput). |
| `adjust_concurrency_limit` | Any service | Modifies worker thread-pool concurrency limit per replica. |
| `enable_circuit_breaker` | Upstream service | Enables fast-fail circuit breaking when downstream latency exceeds `circuit_breaker_threshold_ms` (protects latency and queue depth with bounded fallback error rate). |
| `reduce_downstream_latency` | Downstream service | Isolates or optimizes downstream dependency latency by factor `value`. |
| `adjust_db_connection_capacity` | `order-database-sim` | Expands database connection pool and row-lock concurrency capacity, relieving shared lock contention. |
| `simulate_dependency_failure` | Any service | Injects latency multiplier and elevated error probability to test cascading failure resilience. |
| `restore_configuration` | System-wide | Restores all service parameters and replicas to their initial calibrated baseline. |

---

## 3. Shared Bottleneck & Tradeoff Analysis
`DigitalTwinService.compare_branches()` computes:
- `latency_delta_ms` and `latency_reduction_pct`
- `error_rate_delta_pct`, `throughput_delta_rps`, `max_queue_delta`, `saturation_delta_pct`
- `shared_bottleneck_warnings`: Automatic detection when scaling an upstream service (`checkout-service`) fails to improve latency because a downstream shared dependency (`order-database-sim`) is lock-saturated.
- `tradeoff_analysis`: Explicit reporting of throughput shedding (under rate limiting) or fast-fail error rate increases (under circuit breaking).
