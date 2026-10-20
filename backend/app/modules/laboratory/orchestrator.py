"""Instrumentable Synthetic Distributed System Laboratory (5 services + load & intervention engine).

Contains:
1. api-gateway
2. checkout-service
3. inventory-service
4. payment-simulator
5. order-database-sim
6. load-generator & allowlisted experimental intervention controller

Supports normal operation, injected performance degradation, and hidden-fault benchmark blinding:
- 'normal': Nominal baseline operation across all 5 services.
- 'payment_latency_spike': Degrades payment-simulator latency & tail errors,
  propagating to checkout-service and api-gateway.
- 'db_lock_contention': Degrades order-database-sim lock wait time,
  propagating to inventory-service, checkout-service, and api-gateway.
- 'inventory_cpu_throttling': Degrades inventory-service local worker processing time,
  propagating to checkout-service and api-gateway while order-database-sim remains healthy.
- 'noisy_ambiguous_jitter': Stochastic uncorrelated latency spikes across services with no
  consistent single-service root cause (used to verify INCONCLUSIVE scientific outcomes).
"""

import asyncio
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.registry.schemas import DependencyCreate, ServiceCreate, SystemCreate
from app.modules.registry.service import RegistryService
from app.modules.safety.service import AuditService
from app.modules.telemetry.schemas import (
    MetricObservationIn,
    OTLPKeyValue,
    OTLPResource,
    OTLPResourceSpans,
    OTLPScopeSpans,
    OTLPSpan,
    OTLPTracesPayload,
    SpanObservationIn,
    TelemetryBatchIn,
)
from app.modules.telemetry.service import TelemetryService

LAB_SYSTEM_SLUG = "origin-synthetic-lab"

LabProfileType = Literal[
    "normal",
    "payment_latency_spike",
    "db_lock_contention",
    "inventory_cpu_throttling",
    "noisy_ambiguous_jitter",
]

PublicLabProfileView = Literal[
    "normal",
    "payment_latency_spike",
    "db_lock_contention",
    "inventory_cpu_throttling",
    "noisy_ambiguous_jitter",
    "blinded_benchmark_mode",
]

InterventionType = Literal[
    "none",
    "isolate_payment_fastpath",
    "relieve_db_lock_contention",
    "scale_inventory_workers",
    "hedged_concurrency_limiter",
]

ALLOWLISTED_INTERVENTIONS: dict[str, dict[str, Any]] = {
    "none": {
        "target_service_key": "none",
        "description": "Control condition: no experimental intervention applied.",
        "cost": 0,
    },
    "isolate_payment_fastpath": {
        "target_service_key": "payment-simulator",
        "description": (
            "Route payment authorization through an isolated pre-authorized clearing pool "
            "to test whether upstream payment gateway latency causes checkout degradation."
        ),
        "cost": 1,
    },
    "relieve_db_lock_contention": {
        "target_service_key": "order-database-sim",
        "description": (
            "Enable snapshot isolation and dedicated lock-free connection pool on "
            "order-database-sim to test whether row lock contention causes checkout degradation."
        ),
        "cost": 1,
    },
    "scale_inventory_workers": {
        "target_service_key": "inventory-service",
        "description": (
            "Double local compute worker pool in inventory-service to test whether "
            "internal inventory CPU throttling causes checkout degradation."
        ),
        "cost": 1,
    },
    "hedged_concurrency_limiter": {
        "target_service_key": "checkout-service",
        "description": (
            "Apply adaptive concurrency pacing at checkout-service to test whether "
            "excessive request concurrency causes queue accumulation."
        ),
        "cost": 1,
    },
}


class PrivateLabGroundTruthState(BaseModel):
    """Internal laboratory fault state (Private to Benchmark Controller when blinded)."""

    profile: LabProfileType = "normal"
    blinded: bool = False
    payment_added_latency_ms: float = 0.0
    payment_failure_probability: float = 0.0
    db_added_latency_ms: float = 0.0
    db_lock_saturation_pct: float = 18.0
    inventory_added_latency_ms: float = 0.0
    ambiguous_jitter_ms: float = 0.0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LabFaultState(BaseModel):
    """Public/Investigator-safe view of the Synthetic Laboratory state.

    When `blinded` is True (during a hidden-fault benchmark), `profile` is masked as
    `"blinded_benchmark_mode"` and internal fault parameters are zeroed/hidden so the
    investigator cannot read the answer from `/api/v1/lab/status` or `/api/v1/health`.
    """

    profile: PublicLabProfileView = "normal"
    blinded: bool = False
    payment_added_latency_ms: float | None = 0.0
    payment_failure_probability: float | None = 0.0
    db_added_latency_ms: float | None = 0.0
    db_lock_saturation_pct: float | None = 18.0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LabTransactionRequest(BaseModel):
    """Request to execute one or more synthetic distributed checkout transactions."""

    iterations: int = Field(default=3, ge=1, le=25)
    profile: LabProfileType | None = None
    intervention: InterventionType = "none"
    sku: str = Field(default="ORIGIN-QUANTUM-SENSOR-X1", max_length=80)
    amount_usd: float = Field(default=249.00, gt=0.0)


class LabTransactionTraceSummary(BaseModel):
    """Summary of a single multi-service request traversing the laboratory.

    Never exposes the hidden ground-truth fault label.
    """

    correlation_id: str
    trace_id: str
    profile: PublicLabProfileView
    intervention: InterventionType = "none"
    gateway_status: int
    total_duration_ms: float
    service_latencies_ms: dict[str, float] = Field(default_factory=dict)
    services_traversed: list[str]
    spans_emitted: int
    metrics_emitted: int


class LabExecutionResult(BaseModel):
    """Result of running a single or burst workload against the laboratory."""

    system_slug: str
    execution_mode: str
    active_profile: PublicLabProfileView
    transactions_executed: int
    total_spans_ingested: int
    total_metrics_ingested: int
    traces: list[LabTransactionTraceSummary]


# Private process-level state managed by Benchmark Controller / Lab Orchestrator
_PRIVATE_STATE = PrivateLabGroundTruthState()

ALLOWLISTED_REMEDIATION_ACTIONS: set[str] = {
    "adjust_service_replicas",
    "modify_concurrency_limit",
    "toggle_circuit_breaker",
    "apply_rate_limiting",
    "adjust_db_contention_controls",
    "restore_safe_lab_configuration",
    "restart_synthetic_service",
}


class LabRuntimeConfiguration(BaseModel):
    """Mutable, inspectable, and restorable runtime configuration of the Synthetic Laboratory."""

    environment: str = "synthetic-lab"
    service_replicas: dict[str, int] = Field(
        default_factory=lambda: {
            "api-gateway": 2,
            "checkout-service": 2,
            "inventory-service": 2,
            "payment-simulator": 2,
            "order-database-sim": 1,
        }
    )
    concurrency_limits: dict[str, int] = Field(
        default_factory=lambda: {
            "api-gateway": 120,
            "checkout-service": 30,
            "inventory-service": 50,
            "payment-simulator": 50,
            "order-database-sim": 65,
        }
    )
    circuit_breakers: dict[str, bool] = Field(
        default_factory=lambda: {
            "api-gateway": False,
            "checkout-service": False,
            "inventory-service": False,
            "payment-simulator": False,
            "order-database-sim": False,
        }
    )
    rate_limit_factor: float = 1.0
    db_connection_capacity: float = 65.0
    db_lock_relief_enabled: bool = False
    payment_fastpath_enabled: bool = False
    restarted_services: list[str] = Field(default_factory=list)
    regression_penalty_ms: float = 0.0
    lab_unsafe_locked: bool = False
    unsafe_reason: str | None = None


_LAB_RUNTIME_CONFIG = LabRuntimeConfiguration()


def capture_lab_configuration() -> dict[str, Any]:
    """Capture a deep copy of the current laboratory runtime & fault configuration."""
    return {
        "runtime_config": _LAB_RUNTIME_CONFIG.model_copy(deep=True).model_dump(mode="json"),
        "fault_state": _PRIVATE_STATE.model_copy(deep=True).model_dump(mode="json"),
    }


def is_lab_unsafe_locked() -> tuple[bool, str | None]:
    """Return whether the laboratory is locked due to a failed sandbox restoration."""
    return _LAB_RUNTIME_CONFIG.lab_unsafe_locked, _LAB_RUNTIME_CONFIG.unsafe_reason


def mark_lab_unsafe(reason: str) -> None:
    """Mark the laboratory unsafe and block further experiments until restored."""
    _LAB_RUNTIME_CONFIG.lab_unsafe_locked = True
    _LAB_RUNTIME_CONFIG.unsafe_reason = reason


def clear_lab_unsafe_lock() -> None:
    """Clear the unsafe laboratory lock and reset runtime configuration to safe defaults."""
    global _LAB_RUNTIME_CONFIG
    _LAB_RUNTIME_CONFIG = LabRuntimeConfiguration()


def restore_lab_configuration(
    snapshot: dict[str, Any],
    *,
    simulate_restore_failure: bool = False,
) -> tuple[bool, dict[str, Any]]:
    """Restore the laboratory to a previously captured configuration snapshot and verify it."""
    global _LAB_RUNTIME_CONFIG, _PRIVATE_STATE
    if simulate_restore_failure:
        mark_lab_unsafe(
            "Sandbox configuration restoration failed verification: "
            "residual mutation remained active."
        )
        return False, capture_lab_configuration()

    if "runtime_config" in snapshot:
        _LAB_RUNTIME_CONFIG = LabRuntimeConfiguration(**snapshot["runtime_config"])
    if "fault_state" in snapshot:
        fs = snapshot["fault_state"]
        _PRIVATE_STATE = PrivateLabGroundTruthState(
            profile=fs.get("profile", "normal"),
            blinded=bool(fs.get("blinded", False)),
            payment_added_latency_ms=float(fs.get("payment_added_latency_ms", 0.0)),
            payment_failure_probability=float(fs.get("payment_failure_probability", 0.0)),
            db_added_latency_ms=float(fs.get("db_added_latency_ms", 0.0)),
            db_lock_saturation_pct=float(fs.get("db_lock_saturation_pct", 18.0)),
            inventory_added_latency_ms=float(fs.get("inventory_added_latency_ms", 0.0)),
            ambiguous_jitter_ms=float(fs.get("ambiguous_jitter_ms", 0.0)),
        )
    current = capture_lab_configuration()
    verified = current["runtime_config"] == snapshot.get("runtime_config") and current[
        "fault_state"
    ]["profile"] == snapshot.get("fault_state", {}).get("profile")
    if not verified:
        mark_lab_unsafe("Configuration hash mismatch after restoration.")
    return verified, current


def apply_lab_remediation_action(
    action_type: str,
    target_service_key: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Apply an allowlisted remediation action to the isolated Synthetic Laboratory."""
    global _LAB_RUNTIME_CONFIG
    if action_type not in ALLOWLISTED_REMEDIATION_ACTIONS:
        raise ValueError(f"Unsupported or disallowed remediation action: {action_type}")

    if action_type == "restore_safe_lab_configuration":
        _LAB_RUNTIME_CONFIG = LabRuntimeConfiguration()
        set_lab_profile("normal", blinded=False)
        return capture_lab_configuration()

    if action_type == "adjust_service_replicas":
        replicas = int(parameters.get("replicas", parameters.get("value", 3)))
        _LAB_RUNTIME_CONFIG.service_replicas[target_service_key] = replicas
        # If scaling checkout-service under unresolved DB lock contention, amplify lock penalty
        if (
            target_service_key == "checkout-service"
            and replicas >= 5
            and _PRIVATE_STATE.profile == "db_lock_contention"
            and not _LAB_RUNTIME_CONFIG.db_lock_relief_enabled
        ):
            _LAB_RUNTIME_CONFIG.regression_penalty_ms = 240.0

    elif action_type == "modify_concurrency_limit":
        limit = int(parameters.get("concurrency_limit", parameters.get("value", 40)))
        _LAB_RUNTIME_CONFIG.concurrency_limits[target_service_key] = limit
        if limit < 12:
            # Excessively low concurrency limit causes thread queuing regression
            _LAB_RUNTIME_CONFIG.regression_penalty_ms = 290.0

    elif action_type == "toggle_circuit_breaker":
        enabled = bool(parameters.get("enabled", True))
        _LAB_RUNTIME_CONFIG.circuit_breakers[target_service_key] = enabled

    elif action_type == "apply_rate_limiting":
        factor = float(parameters.get("rate_limit_factor", parameters.get("value", 0.65)))
        _LAB_RUNTIME_CONFIG.rate_limit_factor = factor

    elif action_type == "adjust_db_contention_controls":
        conn_cap = float(parameters.get("db_connection_capacity", parameters.get("value", 160.0)))
        _LAB_RUNTIME_CONFIG.db_connection_capacity = conn_cap
        _LAB_RUNTIME_CONFIG.db_lock_relief_enabled = conn_cap >= 100.0
        _LAB_RUNTIME_CONFIG.regression_penalty_ms = 0.0

    elif action_type == "restart_synthetic_service":
        if target_service_key not in _LAB_RUNTIME_CONFIG.restarted_services:
            _LAB_RUNTIME_CONFIG.restarted_services.append(target_service_key)
        if target_service_key == "payment-simulator":
            _LAB_RUNTIME_CONFIG.payment_fastpath_enabled = True
            _LAB_RUNTIME_CONFIG.regression_penalty_ms = 0.0

    if parameters.get("induce_regression"):
        _LAB_RUNTIME_CONFIG.regression_penalty_ms = float(
            parameters.get("regression_penalty_ms", 360.0)
        )

    return capture_lab_configuration()


def get_lab_state() -> LabFaultState:
    """Return Investigator-safe laboratory state (masks ground truth when blinded)."""
    if _PRIVATE_STATE.blinded:
        return LabFaultState(
            profile="blinded_benchmark_mode",
            blinded=True,
            payment_added_latency_ms=None,
            payment_failure_probability=None,
            db_added_latency_ms=None,
            db_lock_saturation_pct=None,
            updated_at=_PRIVATE_STATE.updated_at,
        )
    return LabFaultState(
        profile=_PRIVATE_STATE.profile,
        blinded=False,
        payment_added_latency_ms=_PRIVATE_STATE.payment_added_latency_ms,
        payment_failure_probability=_PRIVATE_STATE.payment_failure_probability,
        db_added_latency_ms=_PRIVATE_STATE.db_added_latency_ms,
        db_lock_saturation_pct=_PRIVATE_STATE.db_lock_saturation_pct,
        updated_at=_PRIVATE_STATE.updated_at,
    )


def get_private_ground_truth_for_evaluator() -> PrivateLabGroundTruthState:
    """Return unmasked private ground-truth state for the Benchmark Evaluator ONLY."""
    return _PRIVATE_STATE.model_copy(deep=True)


def set_lab_profile(
    profile: LabProfileType,
    *,
    blinded: bool = False,
    preserve_runtime_config: bool = False,
) -> LabFaultState:
    """Configure the laboratory operating profile (optionally blinded for hidden benchmarks)."""
    global _PRIVATE_STATE, _LAB_RUNTIME_CONFIG
    if not preserve_runtime_config:
        _LAB_RUNTIME_CONFIG = LabRuntimeConfiguration()
    now = datetime.now(UTC)
    if profile == "normal":
        _PRIVATE_STATE = PrivateLabGroundTruthState(
            profile="normal",
            blinded=blinded,
            payment_added_latency_ms=0.0,
            payment_failure_probability=0.0,
            db_added_latency_ms=0.0,
            db_lock_saturation_pct=18.0,
            inventory_added_latency_ms=0.0,
            ambiguous_jitter_ms=0.0,
            updated_at=now,
        )
    elif profile == "payment_latency_spike":
        _PRIVATE_STATE = PrivateLabGroundTruthState(
            profile="payment_latency_spike",
            blinded=blinded,
            payment_added_latency_ms=420.0,
            payment_failure_probability=0.18,
            db_added_latency_ms=0.0,
            db_lock_saturation_pct=24.0,
            inventory_added_latency_ms=0.0,
            ambiguous_jitter_ms=0.0,
            updated_at=now,
        )
    elif profile == "db_lock_contention":
        _PRIVATE_STATE = PrivateLabGroundTruthState(
            profile="db_lock_contention",
            blinded=blinded,
            payment_added_latency_ms=10.0,
            payment_failure_probability=0.0,
            db_added_latency_ms=340.0,
            db_lock_saturation_pct=91.0,
            inventory_added_latency_ms=0.0,
            ambiguous_jitter_ms=0.0,
            updated_at=now,
        )
    elif profile == "inventory_cpu_throttling":
        _PRIVATE_STATE = PrivateLabGroundTruthState(
            profile="inventory_cpu_throttling",
            blinded=blinded,
            payment_added_latency_ms=5.0,
            payment_failure_probability=0.0,
            db_added_latency_ms=0.0,
            db_lock_saturation_pct=21.0,
            inventory_added_latency_ms=380.0,
            ambiguous_jitter_ms=0.0,
            updated_at=now,
        )
    elif profile == "noisy_ambiguous_jitter":
        _PRIVATE_STATE = PrivateLabGroundTruthState(
            profile="noisy_ambiguous_jitter",
            blinded=blinded,
            payment_added_latency_ms=0.0,
            payment_failure_probability=0.0,
            db_added_latency_ms=0.0,
            db_lock_saturation_pct=48.0,
            inventory_added_latency_ms=0.0,
            ambiguous_jitter_ms=260.0,
            updated_at=now,
        )
    return get_lab_state()


class SyntheticLabOrchestrator:
    """Registers the Synthetic Distributed System Laboratory and executes instrumented workloads."""

    @staticmethod
    async def ensure_lab_registered(
        db: AsyncSession,
        actor: str = "system-bootstrap",
        correlation_id: str | None = None,
    ) -> str:
        """Register the canonical 5-service Synthetic Distributed System Laboratory."""
        system = await RegistryService.create_or_get_system(
            db,
            SystemCreate(
                slug=LAB_SYSTEM_SLUG,
                name="ORIGIN Synthetic Distributed Commerce Lab",
                environment="synthetic-lab",
                description=(
                    "Isolated 5-service distributed laboratory (API Gateway, Checkout Service, "
                    "Inventory Service, Payment Simulator, Order Database Simulator) with "
                    "OpenTelemetry trace and metric instrumentation."
                ),
                is_synthetic_lab=True,
                metadata_json={
                    "purpose": "Causal Discovery & Living System Intelligence Benchmark",
                    "components": [
                        "api-gateway",
                        "checkout-service",
                        "inventory-service",
                        "payment-simulator",
                        "order-database-sim",
                        "load-generator",
                    ],
                },
            ),
            actor=actor,
            correlation_id=correlation_id,
        )

        services_spec: list[ServiceCreate] = [
            ServiceCreate(
                service_key="api-gateway",
                display_name="Edge API Gateway",
                service_type="gateway",
                tier="tier-0",
                owner_team="edge-platform",
                metadata_json={"port": 8091, "entrypoint": "POST /orders/checkout"},
            ),
            ServiceCreate(
                service_key="checkout-service",
                display_name="Checkout Orchestrator",
                service_type="microservice",
                tier="tier-1",
                owner_team="commerce-core",
                metadata_json={"port": 8092, "role": "Distributed transaction coordinator"},
            ),
            ServiceCreate(
                service_key="inventory-service",
                display_name="Inventory Reservation Service",
                service_type="microservice",
                tier="tier-2",
                owner_team="supply-chain",
                metadata_json={"port": 8093, "role": "Stock verification and reservation"},
            ),
            ServiceCreate(
                service_key="payment-simulator",
                display_name="Payment Gateway Simulator",
                service_type="external_simulator",
                tier="tier-2",
                owner_team="payments-eng",
                metadata_json={"port": 8094, "role": "Payment authorization & clearing simulator"},
            ),
            ServiceCreate(
                service_key="order-database-sim",
                display_name="Order & Inventory Database Simulator",
                service_type="database",
                tier="tier-3",
                owner_team="data-infrastructure",
                metadata_json={"port": 8095, "engine": "transactional-kv-simulator"},
            ),
        ]
        for svc_spec in services_spec:
            await RegistryService.register_service(
                db, system.id, svc_spec, actor=actor, correlation_id=correlation_id
            )

        declared_edges: list[DependencyCreate] = [
            DependencyCreate(
                source_service_key="api-gateway",
                target_service_key="checkout-service",
                protocol="http",
                metadata_json={"route": "POST /internal/checkout"},
            ),
            DependencyCreate(
                source_service_key="checkout-service",
                target_service_key="inventory-service",
                protocol="http",
                metadata_json={"route": "POST /internal/inventory/reserve"},
            ),
            DependencyCreate(
                source_service_key="checkout-service",
                target_service_key="payment-simulator",
                protocol="http",
                metadata_json={"route": "POST /internal/payments/authorize"},
            ),
            DependencyCreate(
                source_service_key="checkout-service",
                target_service_key="order-database-sim",
                protocol="sql",
                metadata_json={"query": "INSERT INTO orders"},
            ),
        ]
        for edge_spec in declared_edges:
            await RegistryService.register_dependency(
                db, system.id, edge_spec, actor=actor, correlation_id=correlation_id
            )

        await db.commit()
        return system.id

    @staticmethod
    async def execute_instrumented_transaction(
        db: AsyncSession,
        profile: LabProfileType | None = None,
        intervention: InterventionType = "none",
        experiment_arm: str = "observational",
        sku: str = "ORIGIN-QUANTUM-SENSOR-X1",
        amount_usd: float = 249.0,
        rng_seed: int | None = None,
    ) -> LabTransactionTraceSummary:
        """Execute a real instrumented request traversing all 5 laboratory services.

        If `profile` is explicitly passed (and not in blinded mode), updates the lab state.
        During a blinded benchmark or experimental trial, uses the active `_PRIVATE_STATE`
        and applies the allowlisted `intervention` physics without leaking `_PRIVATE_STATE.profile`.
        """
        if intervention not in ALLOWLISTED_INTERVENTIONS:
            raise ValueError(f"Unsupported or unsafe intervention: {intervention}")

        if profile is not None and not _PRIVATE_STATE.blinded:
            set_lab_profile(profile, blinded=False)

        state = _PRIVATE_STATE
        rng = random.Random(rng_seed) if rng_seed is not None else random.Random()

        trace_id = (
            uuid.UUID(int=rng.getrandbits(128), version=4).hex
            if rng_seed is not None
            else uuid.uuid4().hex
        )
        correlation_id = f"lab-corr-{trace_id[:16]}"
        t0 = time.perf_counter()
        base_ts = datetime.now(UTC)

        # Compute effective fault physics under active intervention and runtime config
        rt_cfg = _LAB_RUNTIME_CONFIG
        eff_db_latency = state.db_added_latency_ms
        eff_db_sat = state.db_lock_saturation_pct
        if (
            intervention == "relieve_db_lock_contention"
            or rt_cfg.db_lock_relief_enabled
            or rt_cfg.db_connection_capacity >= 100.0
        ):
            eff_db_latency = eff_db_latency * 0.04
            eff_db_sat = min(eff_db_sat, 22.0)

        eff_pay_latency = state.payment_added_latency_ms
        eff_pay_fail_prob = state.payment_failure_probability
        if (
            intervention == "isolate_payment_fastpath"
            or rt_cfg.payment_fastpath_enabled
            or "payment-simulator" in rt_cfg.restarted_services
        ):
            eff_pay_latency = eff_pay_latency * 0.03
            eff_pay_fail_prob = 0.0
        elif rt_cfg.circuit_breakers.get("checkout-service", False):
            eff_pay_latency = min(eff_pay_latency, 12.0)
            eff_pay_fail_prob = min(eff_pay_fail_prob, 0.04)

        eff_inv_latency = state.inventory_added_latency_ms
        if (
            intervention == "scale_inventory_workers"
            or rt_cfg.service_replicas.get("inventory-service", 2) >= 4
            or "inventory-service" in rt_cfg.restarted_services
        ):
            eff_inv_latency = eff_inv_latency * 0.04

        if rt_cfg.rate_limit_factor < 0.85:
            eff_pay_latency *= rt_cfg.rate_limit_factor
            eff_db_latency *= rt_cfg.rate_limit_factor
            eff_inv_latency *= rt_cfg.rate_limit_factor

        # Uncorrelated stochastic noise when noisy_ambiguous_jitter is active
        # Notice that no single-service intervention removes noisy_ambiguous_jitter!
        jitter_pay = (
            rng.uniform(10.0, state.ambiguous_jitter_ms) if state.ambiguous_jitter_ms > 0 else 0.0
        )
        jitter_db = (
            rng.uniform(10.0, state.ambiguous_jitter_ms) if state.ambiguous_jitter_ms > 0 else 0.0
        )
        jitter_inv = (
            rng.uniform(10.0, state.ambiguous_jitter_ms) if state.ambiguous_jitter_ms > 0 else 0.0
        )

        # Span IDs for the 5-service call hierarchy
        gw_span_id = f"{rng.getrandbits(64):016x}"
        chk_span_id = f"{rng.getrandbits(64):016x}"
        inv_span_id = f"{rng.getrandbits(64):016x}"
        db_inv_span_id = f"{rng.getrandbits(64):016x}"
        pay_span_id = f"{rng.getrandbits(64):016x}"
        db_ord_span_id = f"{rng.getrandbits(64):016x}"

        # 1. Inventory -> Database Simulator query
        await asyncio.sleep(0.001)
        db_inv_dur = round(
            rng.uniform(8.5, 15.5) + eff_db_latency * rng.uniform(0.88, 1.12) + jitter_db * 0.5,
            2,
        )

        # 2. Inventory Service reservation (includes DB call + local stock compute)
        inv_local_dur = round(
            rng.uniform(11.0, 19.5) + eff_inv_latency * rng.uniform(0.90, 1.12) + jitter_inv,
            2,
        )
        inv_total_dur = round(db_inv_dur + inv_local_dur, 2)

        # 3. Payment Simulator authorization
        await asyncio.sleep(0.001)
        pay_dur = round(
            rng.uniform(24.0, 39.0) + eff_pay_latency * rng.uniform(0.92, 1.18) + jitter_pay,
            2,
        )
        pay_failed = rng.random() < eff_pay_fail_prob
        pay_http_status = 503 if pay_failed else 200
        pay_status_code: Literal["OK", "ERROR"] = "ERROR" if pay_failed else "OK"

        # 4. Checkout -> Database Simulator order commit
        db_ord_dur = round(
            rng.uniform(10.0, 18.0) + eff_db_latency * rng.uniform(0.90, 1.15) + jitter_db * 0.5,
            2,
        )
        db_failed = eff_db_sat >= 88.0 and rng.random() < 0.14
        db_http_status = 504 if db_failed else 200
        db_status_code: Literal["OK", "ERROR"] = "ERROR" if db_failed else "OK"

        # 5. Checkout Orchestrator total duration & status
        chk_overhead = round(rng.uniform(9.5, 16.5) + _LAB_RUNTIME_CONFIG.regression_penalty_ms, 2)
        if (
            intervention == "hedged_concurrency_limiter"
            or _LAB_RUNTIME_CONFIG.concurrency_limits.get("checkout-service", 30) >= 60
        ):
            chk_overhead = round(max(4.0, chk_overhead * 0.65), 2)
        chk_total_dur = round(inv_total_dur + pay_dur + db_ord_dur + chk_overhead, 2)
        chk_failed = pay_failed or db_failed
        chk_http_status = 502 if chk_failed else 200
        chk_status_code: Literal["OK", "ERROR"] = "ERROR" if chk_failed else "OK"

        # 6. API Gateway total duration & status
        gw_overhead = round(rng.uniform(6.0, 11.5), 2)
        gw_total_dur = round(chk_total_dur + gw_overhead, 2)
        gw_http_status = 502 if chk_failed else 200

        _ = time.perf_counter() - t0

        # IMPORTANT: Never include ground-truth fault profile in span or metric attributes!
        common_span_attrs: dict[str, Any] = {
            "experiment.intervention": intervention,
            "experiment.arm": experiment_arm,
            "telemetry.environment": "synthetic-lab",
        }

        otlp_payload = OTLPTracesPayload(
            resourceSpans=[
                OTLPResourceSpans(
                    resource=OTLPResource(
                        attributes=[
                            OTLPKeyValue(
                                key="service.name",
                                value={"stringValue": "api-gateway"},
                            ),
                            OTLPKeyValue(
                                key="origin.system.slug",
                                value={"stringValue": LAB_SYSTEM_SLUG},
                            ),
                            OTLPKeyValue(
                                key="origin.is_synthetic",
                                value={"boolValue": True},
                            ),
                        ]
                    ),
                    scopeSpans=[
                        OTLPScopeSpans(
                            scope={"name": "origin.lab.tracer", "version": "0.2.0"},
                            spans=[
                                OTLPSpan(
                                    traceId=trace_id,
                                    spanId=gw_span_id,
                                    parentSpanId=None,
                                    name="POST /orders/checkout",
                                    attributes=[
                                        OTLPKeyValue(
                                            key="origin.correlation_id",
                                            value={"stringValue": correlation_id},
                                        ),
                                        OTLPKeyValue(
                                            key="origin.duration_ms",
                                            value={"doubleValue": gw_total_dur},
                                        ),
                                        OTLPKeyValue(
                                            key="http.status_code",
                                            value={"intValue": gw_http_status},
                                        ),
                                        OTLPKeyValue(
                                            key="experiment.intervention",
                                            value={"stringValue": intervention},
                                        ),
                                        OTLPKeyValue(
                                            key="order.sku",
                                            value={"stringValue": sku},
                                        ),
                                    ],
                                    status={"code": 2 if chk_failed else 1},
                                )
                            ],
                        )
                    ],
                )
            ]
        )
        await TelemetryService.ingest_otlp_traces(
            db, otlp_payload, default_system_slug=LAB_SYSTEM_SLUG
        )

        db_avg_dur = round((db_inv_dur + db_ord_dur) / 2.0, 2)

        batch = TelemetryBatchIn(
            system_slug=LAB_SYSTEM_SLUG,
            source_name="origin-lab-otel-sdk",
            exporter_protocol="otlp-http-json",
            sdk_version="opentelemetry-python-1.27",
            is_synthetic=True,
            spans=[
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=chk_span_id,
                    parent_span_id=gw_span_id,
                    correlation_id=correlation_id,
                    service_key="checkout-service",
                    parent_service_key="api-gateway",
                    operation_name="POST /internal/checkout",
                    span_kind="SERVER",
                    status_code=chk_status_code,
                    http_status=chk_http_status,
                    duration_ms=chk_total_dur,
                    attributes_json={
                        **common_span_attrs,
                        "order.amount_usd": amount_usd,
                        "rpc.system": "http",
                    },
                    started_at=base_ts,
                ),
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=inv_span_id,
                    parent_span_id=chk_span_id,
                    correlation_id=correlation_id,
                    service_key="inventory-service",
                    parent_service_key="checkout-service",
                    operation_name="POST /internal/inventory/reserve",
                    span_kind="SERVER",
                    status_code="OK",
                    http_status=200,
                    duration_ms=inv_total_dur,
                    attributes_json={
                        **common_span_attrs,
                        "inventory.local_compute_ms": inv_local_dur,
                        "inventory.sku": sku,
                        "rpc.system": "http",
                    },
                    started_at=base_ts,
                ),
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=db_inv_span_id,
                    parent_span_id=inv_span_id,
                    correlation_id=correlation_id,
                    service_key="order-database-sim",
                    parent_service_key="inventory-service",
                    operation_name="SELECT FOR UPDATE inventory_stock",
                    span_kind="SERVER",
                    status_code=db_status_code,
                    http_status=db_http_status,
                    duration_ms=db_inv_dur,
                    attributes_json={
                        **common_span_attrs,
                        "db.operation": "SELECT_FOR_UPDATE",
                        "rpc.system": "sql",
                    },
                    started_at=base_ts,
                ),
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=pay_span_id,
                    parent_span_id=chk_span_id,
                    correlation_id=correlation_id,
                    service_key="payment-simulator",
                    parent_service_key="checkout-service",
                    operation_name="POST /internal/payments/authorize",
                    span_kind="SERVER",
                    status_code=pay_status_code,
                    http_status=pay_http_status,
                    duration_ms=pay_dur,
                    attributes_json={
                        **common_span_attrs,
                        "payment.amount_usd": amount_usd,
                        "rpc.system": "http",
                    },
                    started_at=base_ts,
                ),
                SpanObservationIn(
                    trace_id=trace_id,
                    span_id=db_ord_span_id,
                    parent_span_id=chk_span_id,
                    correlation_id=correlation_id,
                    service_key="order-database-sim",
                    parent_service_key="checkout-service",
                    operation_name="INSERT INTO orders",
                    span_kind="SERVER",
                    status_code=db_status_code,
                    http_status=db_http_status,
                    duration_ms=db_ord_dur,
                    attributes_json={
                        **common_span_attrs,
                        "db.operation": "INSERT",
                        "rpc.system": "sql",
                    },
                    started_at=base_ts,
                ),
            ],
            metrics=[
                MetricObservationIn(
                    service_key="checkout-service",
                    metric_name="request_latency_ms",
                    metric_unit="ms",
                    value=chk_total_dur,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json=common_span_attrs,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="inventory-service",
                    metric_name="request_latency_ms",
                    metric_unit="ms",
                    value=inv_total_dur,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json=common_span_attrs,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="payment-simulator",
                    metric_name="request_latency_ms",
                    metric_unit="ms",
                    value=pay_dur,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json=common_span_attrs,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="order-database-sim",
                    metric_name="request_latency_ms",
                    metric_unit="ms",
                    value=db_avg_dur,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json=common_span_attrs,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="api-gateway",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        min(99.0, 20.0 + (gw_total_dur / 18.0) + rng.uniform(-2.0, 3.0)),
                        2,
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json=common_span_attrs,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="checkout-service",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        min(99.0, 24.0 + (chk_total_dur / 15.0) + rng.uniform(-2.0, 3.0)),
                        2,
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json=common_span_attrs,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="inventory-service",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        min(99.0, 18.0 + (inv_total_dur / 10.0) + rng.uniform(-2.0, 3.0)),
                        2,
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json=common_span_attrs,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="payment-simulator",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        min(99.0, 19.0 + (pay_dur / 9.0) + rng.uniform(-2.0, 3.0)),
                        2,
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json=common_span_attrs,
                    observed_at=base_ts,
                ),
                MetricObservationIn(
                    service_key="order-database-sim",
                    metric_name="saturation_pct",
                    metric_unit="%",
                    value=round(
                        min(99.0, eff_db_sat + rng.uniform(-3.0, 4.0)),
                        2,
                    ),
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    attributes_json=common_span_attrs,
                    observed_at=base_ts,
                ),
            ],
        )

        receipt = await TelemetryService.ingest_batch(db, batch)
        public_profile = get_lab_state().profile
        return LabTransactionTraceSummary(
            correlation_id=correlation_id,
            trace_id=trace_id,
            profile=public_profile,
            intervention=intervention,
            gateway_status=gw_http_status,
            total_duration_ms=gw_total_dur,
            service_latencies_ms={
                "api-gateway": gw_total_dur,
                "checkout-service": chk_total_dur,
                "inventory-service": inv_total_dur,
                "payment-simulator": pay_dur,
                "order-database-sim": db_avg_dur,
            },
            services_traversed=[
                "api-gateway",
                "checkout-service",
                "inventory-service",
                "payment-simulator",
                "order-database-sim",
            ],
            spans_emitted=receipt.spans_ingested + 1,
            metrics_emitted=receipt.metrics_ingested + 1,
        )

    @staticmethod
    async def run_workload(
        db: AsyncSession,
        request: LabTransactionRequest,
        actor: str = "operator",
        correlation_id: str | None = None,
    ) -> LabExecutionResult:
        """Execute a laboratory workload via the isolated lab container or embedded runner."""
        system_id = await SyntheticLabOrchestrator.ensure_lab_registered(
            db, actor=actor, correlation_id=correlation_id
        )
        if request.profile is not None and not _PRIVATE_STATE.blinded:
            set_lab_profile(request.profile, blinded=False)

        settings = get_settings()
        execution_mode = "embedded_instrumented_pipeline"
        traces: list[LabTransactionTraceSummary] = []

        # Only delegate to external lab HTTP container if not running a blinded benchmark,
        # seeded intervention trial, or custom remediation runtime configuration
        if (
            not _PRIVATE_STATE.blinded
            and request.intervention == "none"
            and LabRuntimeConfiguration() == _LAB_RUNTIME_CONFIG
        ):
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(
                        f"{settings.lab_controller_url}/internal/lab/execute",
                        json={
                            "iterations": request.iterations,
                            "profile": _PRIVATE_STATE.profile,
                            "sku": request.sku,
                            "amount_usd": request.amount_usd,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        execution_mode = "isolated_lab_container_http"
                        traces = [LabTransactionTraceSummary(**t) for t in data.get("traces", [])]
            except Exception:
                pass

        if not traces:
            for _ in range(request.iterations):
                summary = await SyntheticLabOrchestrator.execute_instrumented_transaction(
                    db,
                    profile=None,
                    intervention=request.intervention,
                    sku=request.sku,
                    amount_usd=request.amount_usd,
                )
                traces.append(summary)

        public_state = get_lab_state()
        await AuditService.record_event(
            db,
            system_id=system_id,
            actor=actor,
            action="laboratory.workload_executed",
            resource_type="synthetic_laboratory",
            resource_id=LAB_SYSTEM_SLUG,
            severity="info",
            correlation_id=correlation_id or (traces[0].correlation_id if traces else None),
            details={
                "public_profile": public_state.profile,
                "intervention": request.intervention,
                "iterations": request.iterations,
                "execution_mode": execution_mode,
                "trace_ids": [t.trace_id for t in traces],
            },
        )
        await db.commit()

        return LabExecutionResult(
            system_slug=LAB_SYSTEM_SLUG,
            execution_mode=execution_mode,
            active_profile=public_state.profile,
            transactions_executed=len(traces),
            total_spans_ingested=sum(t.spans_emitted for t in traces),
            total_metrics_ingested=sum(t.metrics_emitted for t in traces),
            traces=traces,
        )
