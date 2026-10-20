"""Tests for Synthetic Distributed System Laboratory workloads and architectural contracts."""

from httpx import AsyncClient


async def test_synthetic_laboratory_normal_and_degraded_execution(
    client: AsyncClient,
) -> None:
    """Verify multi-service requests traverse all 5 lab services under both profiles."""
    # 1. Execute normal baseline workload
    norm_resp = await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 3, "profile": "normal"},
    )
    assert norm_resp.status_code == 200
    norm_data = norm_resp.json()
    assert norm_data["active_profile"] == "normal"
    assert norm_data["transactions_executed"] == 3
    assert norm_data["total_spans_ingested"] == 18  # 6 spans per transaction * 3
    assert len(norm_data["traces"]) == 3
    first_trace = norm_data["traces"][0]
    assert set(first_trace["services_traversed"]) == {
        "api-gateway",
        "checkout-service",
        "inventory-service",
        "payment-simulator",
        "order-database-sim",
    }

    # Verify topology after normal traffic:
    # 4 edges are 'registered_and_observed', and 1 edge is 'observed'
    topo_norm = (
        await client.get("/api/v1/systems/origin-synthetic-lab/topology")
    ).json()
    assert topo_norm["total_nodes"] == 5
    assert topo_norm["total_edges"] == 5
    assert topo_norm["verified_edges"] == 5
    edge_map = {e["id"]: e for e in topo_norm["edges"]}
    assert (
        edge_map["inventory-service->order-database-sim"]["discovery_source"]
        == "observed"
    )
    assert (
        edge_map["api-gateway->checkout-service"]["discovery_source"]
        == "registered_and_observed"
    )

    # 2. Switch to payment_latency_spike degradation profile and run workload
    deg_resp = await client.post(
        "/api/v1/lab/execute",
        json={"iterations": 4, "profile": "payment_latency_spike"},
    )
    assert deg_resp.status_code == 200
    deg_data = deg_resp.json()
    assert deg_data["active_profile"] == "payment_latency_spike"

    # Verify payment-simulator latency spiked significantly compared to normal
    pay_metrics = (
        await client.get(
            "/api/v1/telemetry/metrics?system_id=origin-synthetic-lab"
            "&service_key=payment-simulator&metric_name=request_latency_ms"
        )
    ).json()
    assert pay_metrics["sample_count"] == 7
    assert pay_metrics["max_value"] > 350.0

    # Verify topology marks payment-simulator and upstream checkout-service as degraded/critical
    topo_deg = (
        await client.get("/api/v1/systems/origin-synthetic-lab/topology")
    ).json()
    node_health = {n["service_key"]: n["health_status"] for n in topo_deg["nodes"]}
    assert node_health["payment-simulator"] in ("degraded", "critical")
    assert node_health["checkout-service"] in ("degraded", "critical")


async def test_architectural_module_contracts_truthfulness(client: AsyncClient) -> None:
    """Verify /api/v1/architecture/modules reports truthful status for all 9 boundaries."""
    resp = await client.get("/api/v1/architecture/modules")
    assert resp.status_code == 200
    data = resp.json()
    boundaries = {b["boundary_number"]: b for b in data["boundaries"]}
    assert len(boundaries) == 9

    # First 4 are implemented
    for b_num in (1, 2, 3, 4):
        assert boundaries[b_num]["status"] == "implemented"

    # Modules 5, 6, 7, 8 explicitly state they are architecture contracts only
    for b_num in (5, 6, 7, 8):
        assert boundaries[b_num]["status"] == "architecture_contract_only"
        assert boundaries[b_num]["execution_enabled"] is False

    # Module 9 has active audit events + future safety guard contract
    assert boundaries[9]["status"] == "implemented_with_future_guard_contract"
