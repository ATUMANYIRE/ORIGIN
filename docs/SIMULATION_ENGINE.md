# ORIGIN — Simulation Engine Physics & Determinism (`Milestone 03/05`)

## 1. Hybrid Discrete-Event + Discrete-Step Execution
Implemented in [`LivingDigitalTwinSimulator`](../backend/app/modules/simulation/simulator.py), the simulator combines:
- **Discrete-Event Scheduling (`EventScheduler`)**: Schedules interventions (`INTERVENTION_APPLIED`), circuit-breaker state transitions (`CIRCUIT_BREAKER_TRIPPED`, `CIRCUIT_BREAKER_RECOVERED`), queue saturation alerts (`QUEUE_SATURATED`), and database lock contention events (`BOTTLENECK_CONTENTION`).
- **Discrete-Time State Evolution (`step(dt_sec)`)**: Evaluates queue depths, worker thread hold times, concurrency limits, and downstream error propagation at each `dt_sec` interval.

---

## 2. Governing Equations & Physical Bounds
For each service $i$ at simulation clock $t$:

1. **Downstream Latency & Circuit Breaker**:
   - If `circuit_breaker_enabled` is `True` and a downstream dependency $j$ exceeds `circuit_breaker_threshold_ms` (or error rate $> 20\%$), the circuit breaker transitions to `OPEN`, replacing the slow dependency call with a fast-fail fallback ($8.5\text{ ms}$) and a bounded fallback error probability ($9.5\%$).
   - Otherwise, downstream latency sums across called dependencies: $L_{\text{down}, i} = \sum_{j \in \text{children}(i)} L_j$.

2. **Shared Database Row-Lock Contention**:
   - For `order-database-sim`, concurrent upstream `checkout-service` replicas and worker threads increase lock contention pressure:
     $$\text{pressure} = \left(\frac{R_{\text{checkout}}}{2}\right)\left(\frac{C_{\text{checkout}}}{30}\right), \quad \rho_{\text{lock}} = \frac{\lambda_{\text{db}} \cdot \text{pressure}}{\text{Cap}_{\text{conn, db}}}$$
   - When $\rho_{\text{lock}} > 0.70$, quadratic lock wait time accumulates:
     $$L_{\text{lock}} = L_{\text{base, db}} \cdot \alpha_{\text{lock}} \cdot 18.0 \cdot (\rho_{\text{lock}} - 0.55)^2$$

3. **Thread-Pool Concurrency & Queue Dynamics**:
   - Worker hold time $W_{\text{hold}} = (L_{\text{base}, i} + L_{\text{down}, i} + L_{\text{lock}, i}) / 1000$.
   - Concurrency-bounded service rate: $\mu_{\text{conc}, i} = \frac{R_i \cdot C_i}{\max(0.015, 3.2 \cdot W_{\text{hold}})}$.
   - Effective service rate: $\mu_{\text{eff}, i} = \max(0.25 \cdot R_i \mu_{0, i}, \min(R_i \mu_{0, i}, \mu_{\text{conc}, i}))$.
   - Queue evolution (bounded within $[0, Q_{\max, i}]$):
     $$Q_i(t + \Delta t) = \text{clip}\left(Q_i(t) + (\lambda_i - \mu_{\text{eff}, i})\Delta t, \, 0, \, Q_{\max, i}\right)$$

---

## 3. Exact Snapshot & Rewind Determinism
`capture_snapshot_dict()` serializes:
- `sim_clock_sec` and `step_index`
- `rng_state_json` (full internal tuple of Python's `random.Random` Mersenne Twister + Gaussian cache)
- `pending_events_json` (sorted priority queue with tie-breaker sequence numbers)
- `service_states_json` and `current_parameters_json`

Restoring a snapshot via `restore_from_snapshot_dict()` and running with the same seed and interventions yields bit-for-bit identical trajectories.
