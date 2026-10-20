# ORIGIN — Digital Twin Simulation Benchmarks (`Milestone 03/05`)

## Four Canonical Simulation Benchmarks (`POST /api/v1/simulations/benchmarks/run`)

Implemented in [`DigitalTwinService.run_simulation_benchmarks`](../backend/app/modules/simulation/service.py) and verified in [`test_milestone3_digital_twin.py`](../backend/tests/test_milestone3_digital_twin.py):

### Benchmark A — Payment Degradation (`benchmark_a_payment_degradation`)
- **Scenario**: Synthetic Laboratory emits traces under `payment_latency_spike`. Digital Twin calibrates from observed spans with 75%/25% held-out validation.
- **Counterfactual Intervention**: `reduce_downstream_latency` on `payment-simulator` (`0.12x`).
- **Scientific Verification**: End-to-end latency drops by $> 45\%$ compared to the unmitigated baseline branch.

### Benchmark B — Shared Database Lock Contention (`benchmark_b_database_contention`)
- **Scenario**: Synthetic Laboratory emits traces under `db_lock_contention`. Digital Twin calibrates elevated `db_lock_contention_factor` on `order-database-sim`.
- **Competing Interventions**:
  1. *Naive Intervention*: `increase_replicas` on `checkout-service` (`2 → 6` replicas).
  2. *Targeted Intervention*: `adjust_db_connection_capacity` on `order-database-sim` (`180` connections).
- **Scientific Verification**: Scaling `checkout-service` replicas fails to reduce latency (and amplifies shared DB lock wait), whereas relieving `order-database-sim` lock capacity reduces end-to-end latency by $> 35\%$.

### Benchmark C — Traffic Surge (`benchmark_c_traffic_surge`)
- **Scenario**: Incoming arrival rate surges to `95 req/s` (`> 2x` nominal baseline).
- **Competing Interventions**:
  1. *Horizontal Scaling*: `increase_replicas` across `checkout-service`, `inventory-service`, `payment-simulator` + DB capacity expansion.
  2. *Gateway Rate Limiting*: `reduce_incoming_traffic` on `api-gateway` (`0.55x`).
- **Scientific Verification**: Both interventions reduce queue buildup and latency compared to the unmitigated surge, while explicitly demonstrating the throughput tradeoff (rate limiting sheds throughput compared to horizontal scaling).

### Benchmark D — Cascading Failure & Circuit Breaker (`benchmark_d_cascading_circuit_breaker`)
- **Scenario**: Severe downstream failure (`simulate_dependency_failure`, `12x` latency spike on `payment-simulator`).
- **Counterfactual Intervention**: `enable_circuit_breaker` on `checkout-service` (`threshold = 240ms`).
- **Scientific Verification**: Circuit breaker trips to `OPEN`, preventing upstream queue saturation and reducing end-to-end mean latency by $> 55\%$ while introducing a bounded fast-fail error rate tradeoff.
