"""Living Digital Twin Computational Simulation Engine (Milestone 03/05).

Separates:
1. Model definitions & default topology physics
2. Service state transitions & queueing/lock contention dynamics
3. Simulation clock & deterministic priority-queue event scheduler
4. Intervention application with realistic bottleneck constraints
5. Serializable state snapshots & exact RNG/event rewind
6. Monte Carlo ensemble uncertainty estimation & outcome evaluation
"""

import heapq
import random
import statistics
from copy import deepcopy
from typing import Any

MAX_HORIZON_SECONDS = 300.0
MAX_EVENTS_PER_RUN = 5000
MAX_BRANCHES_PER_TWIN = 60

ALLOWLISTED_TWIN_INTERVENTIONS: set[str] = {
    "increase_replicas",
    "reduce_incoming_traffic",
    "adjust_concurrency_limit",
    "enable_circuit_breaker",
    "reduce_downstream_latency",
    "adjust_db_connection_capacity",
    "simulate_dependency_failure",
    "restore_configuration",
}


def default_lab_twin_parameters() -> dict[str, Any]:
    """Return baseline physical parameters for the 5-service Synthetic Laboratory."""
    return {
        "incoming_traffic_rps": 45.0,
        "services": {
            "api-gateway": {
                "service_key": "api-gateway",
                "base_latency_ms": 11.0,
                "latency_std_ms": 2.0,
                "processing_capacity_rps": 65.0,
                "replica_count": 2,
                "concurrency_limit": 120,
                "max_queue_depth": 250,
                "db_lock_contention_factor": 0.0,
                "db_connection_capacity": 100.0,
                "error_base_probability": 0.002,
                "circuit_breaker_enabled": False,
                "circuit_breaker_threshold_ms": 260.0,
                "downstream_targets": ["checkout-service"],
            },
            "checkout-service": {
                "service_key": "checkout-service",
                "base_latency_ms": 19.0,
                "latency_std_ms": 3.5,
                "processing_capacity_rps": 35.0,
                "replica_count": 2,
                "concurrency_limit": 30,
                "max_queue_depth": 200,
                "db_lock_contention_factor": 0.0,
                "db_connection_capacity": 80.0,
                "error_base_probability": 0.004,
                "circuit_breaker_enabled": False,
                "circuit_breaker_threshold_ms": 240.0,
                "downstream_targets": [
                    "inventory-service",
                    "payment-simulator",
                    "order-database-sim",
                ],
            },
            "inventory-service": {
                "service_key": "inventory-service",
                "base_latency_ms": 16.0,
                "latency_std_ms": 2.5,
                "processing_capacity_rps": 32.0,
                "replica_count": 2,
                "concurrency_limit": 50,
                "max_queue_depth": 160,
                "db_lock_contention_factor": 0.0,
                "db_connection_capacity": 60.0,
                "error_base_probability": 0.002,
                "circuit_breaker_enabled": False,
                "circuit_breaker_threshold_ms": 240.0,
                "downstream_targets": ["order-database-sim"],
            },
            "payment-simulator": {
                "service_key": "payment-simulator",
                "base_latency_ms": 29.0,
                "latency_std_ms": 4.5,
                "processing_capacity_rps": 30.0,
                "replica_count": 2,
                "concurrency_limit": 50,
                "max_queue_depth": 160,
                "db_lock_contention_factor": 0.0,
                "db_connection_capacity": 60.0,
                "error_base_probability": 0.005,
                "circuit_breaker_enabled": False,
                "circuit_breaker_threshold_ms": 240.0,
                "downstream_targets": [],
            },
            "order-database-sim": {
                "service_key": "order-database-sim",
                "base_latency_ms": 14.0,
                "latency_std_ms": 2.2,
                "processing_capacity_rps": 75.0,
                "replica_count": 1,
                "concurrency_limit": 65,
                "max_queue_depth": 180,
                "db_lock_contention_factor": 0.15,
                "db_connection_capacity": 65.0,
                "error_base_probability": 0.002,
                "circuit_breaker_enabled": False,
                "circuit_breaker_threshold_ms": 240.0,
                "downstream_targets": [],
            },
        },
        "evaluation_order": [
            "order-database-sim",
            "payment-simulator",
            "inventory-service",
            "checkout-service",
            "api-gateway",
        ],
    }


def _rng_state_to_json(rng: random.Random) -> dict[str, Any]:
    """Serialize Python random.Random state into JSON-safe primitives."""
    version, internal_state, gauss_next = rng.getstate()
    return {
        "version": version,
        "internal_state": list(internal_state),
        "gauss_next": gauss_next,
    }


def _restore_rng_from_json(rng: random.Random, data: dict[str, Any]) -> None:
    """Restore Python random.Random state from JSON-safe primitives."""
    state_tuple = (
        int(data["version"]),
        tuple(int(x) for x in data["internal_state"]),
        data["gauss_next"],
    )
    rng.setstate(state_tuple)


class EventScheduler:
    """Deterministic priority-queue scheduler for discrete simulation events."""

    def __init__(self) -> None:
        self._queue: list[tuple[float, int, dict[str, Any]]] = []
        self._seq: int = 0

    def schedule(
        self,
        timestamp_sec: float,
        event_type: str,
        service_key: str,
        payload: dict[str, Any],
    ) -> None:
        """Schedule a discrete event at `timestamp_sec`."""
        self._seq += 1
        event = {
            "timestamp_sec": round(timestamp_sec, 3),
            "seq": self._seq,
            "event_type": event_type,
            "service_key": service_key,
            "payload": deepcopy(payload),
        }
        heapq.heappush(self._queue, (timestamp_sec, self._seq, event))

    def pop_due_events(self, up_to_sec: float) -> list[dict[str, Any]]:
        """Pop all events scheduled at or before `up_to_sec` in deterministic order."""
        due: list[dict[str, Any]] = []
        while self._queue and self._queue[0][0] <= up_to_sec + 1e-9:
            _, _, ev = heapq.heappop(self._queue)
            due.append(ev)
        return due

    def dump_state(self) -> list[dict[str, Any]]:
        """Serialize pending events for snapshot persistence."""
        return [
            {
                "timestamp_sec": ts,
                "seq": seq,
                "event": deepcopy(ev),
            }
            for ts, seq, ev in sorted(self._queue)
        ]

    def restore_state(self, dumped: list[dict[str, Any]]) -> None:
        """Restore pending events from a serialized snapshot."""
        self._queue = []
        max_seq = 0
        for item in dumped:
            ts = float(item["timestamp_sec"])
            seq = int(item["seq"])
            ev = deepcopy(item["event"])
            max_seq = max(max_seq, seq)
            heapq.heappush(self._queue, (ts, seq, ev))
        self._seq = max_seq


class LivingDigitalTwinSimulator:
    """Executable discrete-event + discrete-step simulator for distributed service topology."""

    def __init__(
        self,
        model_parameters: dict[str, Any],
        random_seed: int = 42,
    ) -> None:
        if "services" not in model_parameters:
            model_parameters = default_lab_twin_parameters()
        self.initial_parameters: dict[str, Any] = deepcopy(model_parameters)
        self.current_parameters: dict[str, Any] = deepcopy(model_parameters)
        self.random_seed: int = random_seed
        self.rng = random.Random(random_seed)
        self.sim_clock_sec: float = 0.0
        self.step_index: int = 0
        self.scheduler = EventScheduler()
        self.active_interventions: list[dict[str, Any]] = []
        self.event_log: list[dict[str, Any]] = []
        self.service_states: dict[str, dict[str, Any]] = {}
        self._initialize_service_states()

    def _initialize_service_states(self) -> None:
        """Initialize dynamic queue, concurrency, and circuit-breaker states."""
        services_cfg = self.current_parameters.get("services", {})
        base_rps = float(self.current_parameters.get("incoming_traffic_rps", 45.0))
        self.service_states = {}
        for svc_key, cfg in services_cfg.items():
            replicas = max(1, int(cfg.get("replica_count", 1)))
            cap_per_rep = float(cfg.get("processing_capacity_rps", 35.0))
            eff_cap = replicas * cap_per_rep
            base_lat = float(cfg.get("base_latency_ms", 20.0))
            self.service_states[svc_key] = {
                "service_key": svc_key,
                "replica_count": replicas,
                "available_replicas": replicas,
                "concurrency_limit": int(cfg.get("concurrency_limit", 50)),
                "active_concurrency": min(
                    int(cfg.get("concurrency_limit", 50)),
                    max(1, int(round(base_rps * (base_lat / 1000.0) * 4.0))),
                ),
                "queue_depth": 0.0,
                "max_queue_depth": float(cfg.get("max_queue_depth", 200.0)),
                "arrival_rate_rps": base_rps,
                "effective_capacity_rps": eff_cap,
                "saturation_pct": round(min(100.0, (base_rps / max(1.0, eff_cap)) * 100.0), 2),
                "mean_latency_ms": base_lat,
                "p95_latency_ms": round(base_lat * 1.25, 2),
                "error_rate_pct": round(float(cfg.get("error_base_probability", 0.002)) * 100.0, 2),
                "throughput_rps": base_rps,
                "circuit_breaker_state": "CLOSED",
                "circuit_breaker_open_until_sec": 0.0,
                "db_lock_wait_ms": 0.0,
            }

    def schedule_interventions(self, interventions: list[dict[str, Any]]) -> None:
        """Schedule counterfactual interventions onto the discrete event queue."""
        for item in interventions:
            itype = str(item.get("intervention_type", ""))
            if itype not in ALLOWLISTED_TWIN_INTERVENTIONS:
                raise ValueError(
                    f"Unsupported Digital Twin intervention '{itype}'. "
                    f"Permitted: {sorted(ALLOWLISTED_TWIN_INTERVENTIONS)}"
                )
            apply_at = float(item.get("apply_at_sec", 0.0))
            target_svc = str(item.get("target_service_key", "checkout-service"))
            self.scheduler.schedule(
                timestamp_sec=apply_at,
                event_type="INTERVENTION_APPLIED",
                service_key=target_svc,
                payload=deepcopy(item),
            )

    def _apply_intervention_now(self, item: dict[str, Any]) -> dict[str, Any]:
        """Mutate simulator parameters and runtime state for a scheduled intervention."""
        itype = str(item.get("intervention_type"))
        target_svc = str(item.get("target_service_key", "checkout-service"))
        val = float(item.get("value", 1.0))
        services_cfg = self.current_parameters["services"]

        if itype == "restore_configuration":
            self.current_parameters = deepcopy(self.initial_parameters)
            for skey, scfg in self.current_parameters["services"].items():
                if skey in self.service_states:
                    self.service_states[skey]["replica_count"] = int(scfg["replica_count"])
                    self.service_states[skey]["available_replicas"] = int(scfg["replica_count"])
                    self.service_states[skey]["concurrency_limit"] = int(scfg["concurrency_limit"])
                    self.service_states[skey]["circuit_breaker_state"] = "CLOSED"
            self.active_interventions.append(deepcopy(item))
            return {"applied": itype, "target": "all_services"}

        if itype == "reduce_incoming_traffic":
            # val is multiplier in (0.1, 2.5) or explicit RPS if > 5.0
            cur_rps = float(self.current_parameters.get("incoming_traffic_rps", 45.0))
            new_rps = max(2.0, min(500.0, cur_rps * val if val <= 3.0 else val))
            self.current_parameters["incoming_traffic_rps"] = round(new_rps, 2)
            self.active_interventions.append(deepcopy(item))
            return {"applied": itype, "incoming_traffic_rps": new_rps}

        if target_svc not in services_cfg:
            raise ValueError(f"Service '{target_svc}' not found in Digital Twin topology.")

        scfg = services_cfg[target_svc]
        sstate = self.service_states[target_svc]

        if itype == "increase_replicas":
            new_reps = max(1, min(16, int(round(val))))
            scfg["replica_count"] = new_reps
            sstate["replica_count"] = new_reps
            sstate["available_replicas"] = new_reps
        elif itype == "adjust_concurrency_limit":
            new_limit = max(5, min(500, int(round(val))))
            scfg["concurrency_limit"] = new_limit
            sstate["concurrency_limit"] = new_limit
        elif itype == "enable_circuit_breaker":
            scfg["circuit_breaker_enabled"] = bool(val >= 0.5)
            if val > 20.0:
                scfg["circuit_breaker_threshold_ms"] = val
        elif itype == "reduce_downstream_latency":
            # val in (0.05, 1.0) scales base_latency_ms; val > 1.0 sets explicit ms
            if val <= 1.0:
                scfg["base_latency_ms"] = max(4.0, float(scfg["base_latency_ms"]) * val)
            else:
                scfg["base_latency_ms"] = max(4.0, val)
        elif itype == "adjust_db_connection_capacity":
            db_cfg = services_cfg.get("order-database-sim", scfg)
            new_db_cap = max(10.0, min(400.0, val))
            db_cfg["db_connection_capacity"] = new_db_cap
            # Increasing DB connection capacity & lock partitioning reduces lock contention factor
            db_cfg["db_lock_contention_factor"] = max(
                0.02, float(db_cfg.get("db_lock_contention_factor", 0.15)) * (48.0 / new_db_cap)
            )
        elif itype == "simulate_dependency_failure":
            # Inject latency multiplier or replica drop on target dependency
            mult = max(1.5, min(15.0, val))
            scfg["base_latency_ms"] = min(1500.0, float(scfg["base_latency_ms"]) * mult)
            scfg["error_base_probability"] = min(
                0.65, float(scfg.get("error_base_probability", 0.005)) + 0.08 * (mult - 1.0)
            )

        self.active_interventions.append(deepcopy(item))
        return {"applied": itype, "target_service_key": target_svc, "value": val}

    def capture_snapshot_dict(self, label: str = "Snapshot") -> dict[str, Any]:
        """Capture complete simulator state including RNG state and pending event queue."""
        return {
            "label": label,
            "sim_clock_sec": round(self.sim_clock_sec, 4),
            "step_index": self.step_index,
            "random_seed": self.random_seed,
            "rng_state_json": _rng_state_to_json(self.rng),
            "pending_events_json": self.scheduler.dump_state(),
            "service_states_json": {
                "current_parameters": deepcopy(self.current_parameters),
                "services": deepcopy(self.service_states),
                "event_log": deepcopy(self.event_log),
            },
            "active_interventions_json": deepcopy(self.active_interventions),
        }

    def restore_from_snapshot_dict(self, snap: dict[str, Any]) -> None:
        """Restore complete simulator state for deterministic rewind and branching."""
        self.sim_clock_sec = float(snap["sim_clock_sec"])
        self.step_index = int(snap["step_index"])
        self.random_seed = int(snap["random_seed"])
        _restore_rng_from_json(self.rng, snap["rng_state_json"])
        self.scheduler.restore_state(snap["pending_events_json"])
        state_bundle = snap["service_states_json"]
        self.current_parameters = deepcopy(state_bundle["current_parameters"])
        self.service_states = deepcopy(state_bundle["services"])
        self.event_log = deepcopy(state_bundle.get("event_log", []))
        self.active_interventions = deepcopy(snap["active_interventions_json"])

    def step(self, dt_sec: float = 1.0) -> dict[str, Any]:
        """Advance the simulation clock by `dt_sec` and compute physical state transitions."""
        if len(self.event_log) >= MAX_EVENTS_PER_RUN:
            raise RuntimeError(f"Simulation event count limit ({MAX_EVENTS_PER_RUN}) exceeded.")

        next_clock = round(self.sim_clock_sec + dt_sec, 4)
        due_events = self.scheduler.pop_due_events(next_clock)
        step_events: list[dict[str, Any]] = []

        for ev in due_events:
            if ev["event_type"] == "INTERVENTION_APPLIED":
                effect = self._apply_intervention_now(ev["payload"])
                ev["effect"] = effect
            self.event_log.append(ev)
            step_events.append(ev)

        services_cfg = self.current_parameters["services"]
        eval_order: list[str] = self.current_parameters.get(
            "evaluation_order",
            [
                "order-database-sim",
                "payment-simulator",
                "inventory-service",
                "checkout-service",
                "api-gateway",
            ],
        )

        # Stochastic arrival jitter around configured incoming_traffic_rps
        nominal_rps = float(self.current_parameters.get("incoming_traffic_rps", 45.0))
        arrival_jitter = self.rng.gauss(0.0, nominal_rps * 0.035)
        gateway_arrivals_rps = max(1.0, nominal_rps + arrival_jitter)

        # Determine upstream checkout replica pressure for shared DB lock contention physics
        checkout_cfg = services_cfg.get("checkout-service", {})
        checkout_replicas = max(1, int(checkout_cfg.get("replica_count", 2)))
        checkout_conc_limit = max(5, int(checkout_cfg.get("concurrency_limit", 60)))

        # Propagate arrival demand from root to leaves
        demand_by_service: dict[str, float] = {
            "api-gateway": gateway_arrivals_rps,
            "checkout-service": gateway_arrivals_rps,
            "inventory-service": gateway_arrivals_rps,
            "payment-simulator": gateway_arrivals_rps,
            "order-database-sim": gateway_arrivals_rps * 1.35,  # Both checkout & inventory hit DB
        }

        # Evaluate bottom-up so upstream latencies reflect downstream queueing & circuit breakers
        for svc_key in eval_order:
            if svc_key not in services_cfg:
                continue
            cfg = services_cfg[svc_key]
            st = self.service_states[svc_key]

            replicas = max(1, int(cfg.get("replica_count", 1)))
            cap_per_rep = float(cfg.get("processing_capacity_rps", 35.0))
            eff_cap = replicas * cap_per_rep
            max_q = max(10.0, float(cfg.get("max_queue_depth", 200.0)))
            conc_limit = max(5, int(cfg.get("concurrency_limit", 50)))

            arr_rps = demand_by_service.get(svc_key, gateway_arrivals_rps)
            base_lat = float(cfg.get("base_latency_ms", 20.0))
            lat_std = float(cfg.get("latency_std_ms", 3.0))

            # 1. Compute downstream latency & error contribution
            downstream_lat_ms = 0.0
            downstream_err_prob = 0.0
            cb_enabled = bool(cfg.get("circuit_breaker_enabled", False))
            cb_thresh_ms = float(cfg.get("circuit_breaker_threshold_ms", 240.0))
            cb_state = str(st.get("circuit_breaker_state", "CLOSED"))

            for target_key in cfg.get("downstream_targets", []):
                if target_key not in self.service_states:
                    continue
                t_state = self.service_states[target_key]
                t_lat = float(t_state["mean_latency_ms"])
                t_err = float(t_state["error_rate_pct"]) / 100.0

                if cb_enabled and (t_lat > cb_thresh_ms or t_err > 0.20):
                    if cb_state != "OPEN":
                        cb_state = "OPEN"
                        st["circuit_breaker_open_until_sec"] = next_clock + 6.0
                        cb_ev = {
                            "timestamp_sec": next_clock,
                            "seq": len(self.event_log) + 1,
                            "event_type": "CIRCUIT_BREAKER_TRIPPED",
                            "service_key": svc_key,
                            "payload": {
                                "downstream_target": target_key,
                                "downstream_latency_ms": round(t_lat, 2),
                                "threshold_ms": cb_thresh_ms,
                            },
                        }
                        self.event_log.append(cb_ev)
                        step_events.append(cb_ev)
                    # Circuit breaker OPEN fast-fails slow dependency calls (protects latency,
                    # but introduces bounded fallback error tradeoff of ~9.5%)
                    downstream_lat_ms += 8.5
                    downstream_err_prob = max(downstream_err_prob, 0.095)
                else:
                    if cb_state == "OPEN" and next_clock >= float(
                        st.get("circuit_breaker_open_until_sec", 0.0)
                    ):
                        cb_state = "CLOSED"
                        rec_ev = {
                            "timestamp_sec": next_clock,
                            "seq": len(self.event_log) + 1,
                            "event_type": "CIRCUIT_BREAKER_RECOVERED",
                            "service_key": svc_key,
                            "payload": {"downstream_target": target_key},
                        }
                        self.event_log.append(rec_ev)
                        step_events.append(rec_ev)
                    downstream_lat_ms += t_lat
                    downstream_err_prob = max(downstream_err_prob, t_err * 0.85)

            st["circuit_breaker_state"] = cb_state

            # 2. Shared Database Lock Contention Physics
            db_lock_wait_ms = 0.0
            lock_factor = float(cfg.get("db_lock_contention_factor", 0.0))
            if svc_key == "order-database-sim" and lock_factor > 0.0:
                db_conn_cap = max(10.0, float(cfg.get("db_connection_capacity", 48.0)))
                # More upstream checkout replicas / concurrency increase concurrent lock contention!
                upstream_concurrency_pressure = (checkout_replicas / 2.0) * (
                    checkout_conc_limit / 30.0
                )
                lock_load_ratio = (arr_rps * upstream_concurrency_pressure) / db_conn_cap
                if lock_load_ratio > 0.70:
                    db_lock_wait_ms = (
                        base_lat * lock_factor * 18.0 * ((lock_load_ratio - 0.55) ** 2)
                    )
                    if db_lock_wait_ms > 120.0 and self.step_index % 5 == 0:
                        lock_ev = {
                            "timestamp_sec": next_clock,
                            "seq": len(self.event_log) + 1,
                            "event_type": "BOTTLENECK_CONTENTION",
                            "service_key": svc_key,
                            "payload": {
                                "db_lock_wait_ms": round(db_lock_wait_ms, 2),
                                "upstream_checkout_replicas": checkout_replicas,
                                "db_connection_capacity": db_conn_cap,
                            },
                        }
                        self.event_log.append(lock_ev)
                        step_events.append(lock_ev)

            st["db_lock_wait_ms"] = round(db_lock_wait_ms, 2)

            # 3. Queue Dynamics & Concurrency Backpressure
            # Effective capacity degrades when downstream latency holds worker threads/connections
            thread_hold_sec = (base_lat + downstream_lat_ms + db_lock_wait_ms) / 1000.0
            concurrency_bound_rps = (replicas * conc_limit) / max(0.015, thread_hold_sec * 3.2)
            effective_service_rate_rps = max(eff_cap * 0.25, min(eff_cap, concurrency_bound_rps))

            prev_q = float(st["queue_depth"])
            net_queue_rate = arr_rps - effective_service_rate_rps
            # When service has spare capacity, queue drains faster
            if net_queue_rate < 0:
                new_q = max(0.0, prev_q + net_queue_rate * dt_sec * 1.8)
            else:
                new_q = min(max_q, prev_q + net_queue_rate * dt_sec)

            queue_wait_ms = min(850.0, (new_q / max(15.0, eff_cap)) * 180.0)

            # Stochastic noise sample from seeded RNG
            noise_ms = self.rng.gauss(0.0, max(0.5, lat_std * 0.45))
            mean_lat_ms = max(
                2.0,
                base_lat + db_lock_wait_ms + queue_wait_ms + downstream_lat_ms + noise_ms,
            )
            p95_lat_ms = mean_lat_ms * 1.24 + abs(noise_ms) * 1.4

            # Active concurrency (Little's Law L = lambda * W bounded by concurrency_limit)
            littles_concurrency = int(round(arr_rps * (mean_lat_ms / 1000.0)))
            active_conc = max(1, min(conc_limit, littles_concurrency))

            util_ratio = arr_rps / max(1.0, effective_service_rate_rps)
            saturation_pct = min(
                100.0,
                max(
                    (active_conc / max(1, conc_limit)) * 100.0,
                    util_ratio * 85.0,
                    (new_q / max_q) * 100.0,
                ),
            )

            # Error rate from queue overflow, timeout (>450ms), or downstream errors
            base_err = float(cfg.get("error_base_probability", 0.002))
            overflow_err = max(0.0, (new_q - max_q * 0.75) / max_q) * 0.35
            timeout_err = (
                min(0.45, ((mean_lat_ms - 420.0) / 600.0) * 0.30)
                if mean_lat_ms > 420.0 and cb_state != "OPEN"
                else 0.0
            )
            total_err_prob = min(0.85, base_err + overflow_err + timeout_err + downstream_err_prob)

            throughput_rps = min(arr_rps, effective_service_rate_rps) * (1.0 - total_err_prob * 0.5)

            if saturation_pct >= 92.0 and self.step_index % 6 == 0:
                sat_ev = {
                    "timestamp_sec": next_clock,
                    "seq": len(self.event_log) + 1,
                    "event_type": "QUEUE_SATURATED",
                    "service_key": svc_key,
                    "payload": {
                        "queue_depth": round(new_q, 2),
                        "saturation_pct": round(saturation_pct, 2),
                    },
                }
                self.event_log.append(sat_ev)
                step_events.append(sat_ev)

            st.update(
                {
                    "replica_count": replicas,
                    "available_replicas": replicas,
                    "concurrency_limit": conc_limit,
                    "active_concurrency": active_conc,
                    "queue_depth": round(new_q, 2),
                    "max_queue_depth": max_q,
                    "arrival_rate_rps": round(arr_rps, 2),
                    "effective_capacity_rps": round(effective_service_rate_rps, 2),
                    "saturation_pct": round(saturation_pct, 2),
                    "mean_latency_ms": round(mean_lat_ms, 2),
                    "p95_latency_ms": round(p95_lat_ms, 2),
                    "error_rate_pct": round(total_err_prob * 100.0, 2),
                    "throughput_rps": round(throughput_rps, 2),
                }
            )

        self.sim_clock_sec = next_clock
        self.step_index += 1

        gw_state = self.service_states.get("api-gateway", next(iter(self.service_states.values())))
        co_state = self.service_states.get("checkout-service", gw_state)
        total_q = sum(float(s["queue_depth"]) for s in self.service_states.values())
        max_sat = max(float(s["saturation_pct"]) for s in self.service_states.values())

        return {
            "step_index": self.step_index,
            "sim_clock_sec": self.sim_clock_sec,
            "incoming_traffic_rps": round(gateway_arrivals_rps, 2),
            "system_mean_latency_ms": float(gw_state["mean_latency_ms"]),
            "system_p95_latency_ms": float(gw_state["p95_latency_ms"]),
            "checkout_mean_latency_ms": float(co_state["mean_latency_ms"]),
            "checkout_p95_latency_ms": float(co_state["p95_latency_ms"]),
            "system_error_rate_pct": float(gw_state["error_rate_pct"]),
            "system_throughput_rps": float(gw_state["throughput_rps"]),
            "total_queue_depth": round(total_q, 2),
            "max_saturation_pct": round(max_sat, 2),
            "services": deepcopy(self.service_states),
            "events_in_step": step_events,
        }

    def run_horizon(
        self,
        horizon_seconds: float = 30.0,
        dt_seconds: float = 1.0,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        """Execute simulation across `horizon_seconds` and return trajectory and summary."""
        if horizon_seconds > MAX_HORIZON_SECONDS:
            raise ValueError(
                f"Requested horizon ({horizon_seconds}s) exceeds maximum "
                f"allowed ({MAX_HORIZON_SECONDS}s)."
            )
        steps = max(1, int(round(horizon_seconds / dt_seconds)))
        trajectory: list[dict[str, Any]] = []
        for _ in range(steps):
            frame = self.step(dt_seconds)
            trajectory.append(frame)

        summary = summarize_trajectory(trajectory, self.active_interventions)
        return trajectory, deepcopy(self.event_log), summary


def summarize_trajectory(
    trajectory: list[dict[str, Any]],
    active_interventions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute aggregate outcome metrics, bottleneck identification, and recovery time."""
    if not trajectory:
        return {}

    sys_lats = [float(f["system_mean_latency_ms"]) for f in trajectory]
    sys_p95s = [float(f["system_p95_latency_ms"]) for f in trajectory]
    co_lats = [float(f["checkout_mean_latency_ms"]) for f in trajectory]
    errs = [float(f["system_error_rate_pct"]) for f in trajectory]
    thrus = [float(f["system_throughput_rps"]) for f in trajectory]
    queues = [float(f["total_queue_depth"]) for f in trajectory]

    # Identify primary bottleneck service (highest mean saturation across trajectory)
    svc_keys = list(trajectory[0]["services"].keys())
    mean_sat_by_svc: dict[str, float] = {}
    mean_lat_by_svc: dict[str, float] = {}
    for skey in svc_keys:
        mean_sat_by_svc[skey] = round(
            statistics.fmean(float(f["services"][skey]["saturation_pct"]) for f in trajectory),
            2,
        )
        mean_lat_by_svc[skey] = round(
            statistics.fmean(float(f["services"][skey]["mean_latency_ms"]) for f in trajectory),
            2,
        )

    bottleneck_svc = max(mean_sat_by_svc, key=lambda k: mean_sat_by_svc[k])

    # Compute recovery time: seconds after peak latency until system_mean_latency_ms < 165ms
    peak_idx = max(range(len(sys_lats)), key=lambda i: sys_lats[i])
    peak_clock = float(trajectory[peak_idx]["sim_clock_sec"])
    recovery_sec: float | None = None
    if sys_lats[peak_idx] > 165.0:
        for idx in range(peak_idx + 1, len(trajectory)):
            if sys_lats[idx] <= 165.0:
                recovery_sec = round(float(trajectory[idx]["sim_clock_sec"]) - peak_clock, 2)
                break
    else:
        recovery_sec = 0.0

    return {
        "mean_latency_ms": round(statistics.fmean(sys_lats), 2),
        "p95_latency_ms": round(statistics.fmean(sys_p95s), 2),
        "max_latency_ms": round(max(sys_lats), 2),
        "checkout_mean_latency_ms": round(statistics.fmean(co_lats), 2),
        "mean_error_rate_pct": round(statistics.fmean(errs), 2),
        "max_error_rate_pct": round(max(errs), 2),
        "mean_throughput_rps": round(statistics.fmean(thrus), 2),
        "max_queue_depth": round(max(queues), 2),
        "final_queue_depth": round(queues[-1], 2),
        "recovery_time_sec": recovery_sec,
        "bottleneck_service_key": bottleneck_svc,
        "service_mean_saturation_pct": mean_sat_by_svc,
        "service_mean_latency_ms": mean_lat_by_svc,
        "interventions_applied_count": len(active_interventions),
    }


def run_simulation_with_uncertainty(
    *,
    model_parameters: dict[str, Any],
    parameter_uncertainty: dict[str, Any],
    interventions: list[dict[str, Any]],
    initial_snapshot: dict[str, Any] | None,
    random_seed: int,
    horizon_seconds: float,
    dt_seconds: float,
    monte_carlo_runs: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Run primary deterministic trajectory plus Monte Carlo ensemble for 95% intervals."""
    primary_sim = LivingDigitalTwinSimulator(
        model_parameters=model_parameters,
        random_seed=random_seed,
    )
    if initial_snapshot is not None:
        primary_sim.restore_from_snapshot_dict(initial_snapshot)
    if interventions:
        primary_sim.schedule_interventions(interventions)

    trajectory, event_log, summary = primary_sim.run_horizon(
        horizon_seconds=horizon_seconds,
        dt_seconds=dt_seconds,
    )

    ensemble_means: list[float] = [float(summary["mean_latency_ms"])]
    ensemble_errs: list[float] = [float(summary["mean_error_rate_pct"])]
    step_lat_samples: list[list[float]] = [[float(f["system_mean_latency_ms"])] for f in trajectory]

    mc_count = max(1, min(20, monte_carlo_runs))
    for k in range(1, mc_count):
        seed_k = random_seed + k * 997
        rng_k = random.Random(seed_k)
        perturbed_params = deepcopy(model_parameters)
        for skey, scfg in perturbed_params.get("services", {}).items():
            unc = parameter_uncertainty.get(skey, {})
            se_lat = float(unc.get("base_latency_se_ms", float(scfg["base_latency_ms"]) * 0.08))
            scfg["base_latency_ms"] = max(
                2.0, float(scfg["base_latency_ms"]) + rng_k.gauss(0.0, se_lat)
            )

        sim_k = LivingDigitalTwinSimulator(
            model_parameters=perturbed_params,
            random_seed=seed_k,
        )
        if initial_snapshot is not None:
            snap_copy = deepcopy(initial_snapshot)
            snap_copy["service_states_json"]["current_parameters"] = perturbed_params
            sim_k.restore_from_snapshot_dict(snap_copy)
            # Advance RNG seed for ensemble member k
            sim_k.rng = random.Random(seed_k)
        if interventions:
            sim_k.schedule_interventions(interventions)

        traj_k, _, sum_k = sim_k.run_horizon(
            horizon_seconds=horizon_seconds,
            dt_seconds=dt_seconds,
        )
        ensemble_means.append(float(sum_k["mean_latency_ms"]))
        ensemble_errs.append(float(sum_k["mean_error_rate_pct"]))
        for idx, frame_k in enumerate(traj_k):
            if idx < len(step_lat_samples):
                step_lat_samples[idx].append(float(frame_k["system_mean_latency_ms"]))

    # Annotate each trajectory step with 95% prediction interval bands
    for idx, frame in enumerate(trajectory):
        samples = step_lat_samples[idx]
        m_val = statistics.fmean(samples)
        sd_val = statistics.stdev(samples) if len(samples) > 1 else m_val * 0.05
        frame["latency_ci_lower_95_ms"] = round(max(1.0, m_val - 1.96 * sd_val), 2)
        frame["latency_ci_upper_95_ms"] = round(m_val + 1.96 * sd_val, 2)

    ens_mean = statistics.fmean(ensemble_means)
    ens_sd = statistics.stdev(ensemble_means) if len(ensemble_means) > 1 else ens_mean * 0.05
    err_mean = statistics.fmean(ensemble_errs)
    err_sd = statistics.stdev(ensemble_errs) if len(ensemble_errs) > 1 else 0.2

    uncertainty = {
        "monte_carlo_runs": mc_count,
        "ensemble_latency_mean_ms": round(ens_mean, 2),
        "ensemble_latency_std_ms": round(ens_sd, 2),
        "latency_ci_lower_95_ms": round(max(1.0, ens_mean - 1.96 * ens_sd), 2),
        "latency_ci_upper_95_ms": round(ens_mean + 1.96 * ens_sd, 2),
        "error_rate_ci_lower_95_pct": round(max(0.0, err_mean - 1.96 * err_sd), 2),
        "error_rate_ci_upper_95_pct": round(min(100.0, err_mean + 1.96 * err_sd), 2),
        "methodology": (
            f"Seeded Monte Carlo ensemble ({mc_count} runs) sampling parameter uncertainty "
            "and arrival/service stochasticity."
        ),
    }

    return trajectory, event_log, summary, uncertainty
