"""Tests for API authentication, correlation IDs, system registry, and audit events."""

from httpx import AsyncClient


async def test_health_and_correlation_id_propagation(client: AsyncClient) -> None:
    """Verify /api/v1/health responds and echoes X-Correlation-ID."""
    resp = await client.get(
        "/api/v1/health",
        headers={"X-Correlation-ID": "corr-custom-check-001"},
    )
    assert resp.status_code == 200
    assert resp.headers["X-Correlation-ID"] == "corr-custom-check-001"
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["database_connected"] is True
    assert body["tagline"] == "Give software the ability to understand itself."


async def test_invalid_api_key_rejected(client: AsyncClient) -> None:
    """Verify supplying an invalid X-Origin-Key returns 401 Unauthorized."""
    resp = await client.post(
        "/api/v1/systems",
        headers={"X-Origin-Key": "wrong-key-value"},
        json={
            "slug": "unauthorized-system",
            "name": "Unauthorized System",
        },
    )
    assert resp.status_code == 401


async def test_system_service_dependency_registry_and_audit(client: AsyncClient) -> None:
    """Verify registering a system, services, and dependencies persists records and audit events."""
    sys_resp = await client.post(
        "/api/v1/systems",
        headers={
            "X-Origin-Key": "origin-dev-scientific-key-2026",
            "X-Correlation-ID": "corr-reg-test-1",
        },
        json={
            "slug": "core-billing-cluster",
            "name": "Core Billing Cluster",
            "environment": "staging",
            "description": "Distributed billing ledger",
            "is_synthetic_lab": False,
        },
    )
    assert sys_resp.status_code == 201
    sys_data = sys_resp.json()
    system_id = sys_data["id"]
    assert sys_data["slug"] == "core-billing-cluster"

    # Register two services
    for svc_key, name, stype, tier in [
        ("billing-api", "Billing API", "gateway", "tier-0"),
        ("ledger-writer", "Ledger Writer", "microservice", "tier-1"),
    ]:
        s_resp = await client.post(
            f"/api/v1/systems/{system_id}/services",
            json={
                "service_key": svc_key,
                "display_name": name,
                "service_type": stype,
                "tier": tier,
                "owner_team": "fin-eng",
            },
        )
        assert s_resp.status_code == 201
        assert s_resp.json()["registration_source"] == "registered"

    # Self-dependency must be rejected with 422
    self_dep = await client.post(
        f"/api/v1/systems/{system_id}/dependencies",
        json={
            "source_service_key": "billing-api",
            "target_service_key": "billing-api",
            "protocol": "http",
        },
    )
    assert self_dep.status_code == 422

    # Valid dependency
    dep_resp = await client.post(
        f"/api/v1/systems/{system_id}/dependencies",
        json={
            "source_service_key": "billing-api",
            "target_service_key": "ledger-writer",
            "protocol": "grpc",
        },
    )
    assert dep_resp.status_code == 201
    assert dep_resp.json()["discovery_source"] == "registered"

    # Verify detail view
    detail_resp = await client.get(f"/api/v1/systems/{system_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["stats"]["service_count"] == 2
    assert detail["stats"]["dependency_count"] == 1
    assert detail["stats"]["observed_dependency_count"] == 0

    # Verify audit trail recorded all registration actions
    audit_resp = await client.get(f"/api/v1/safety/audit-events?system_id={system_id}")
    assert audit_resp.status_code == 200
    actions = [e["action"] for e in audit_resp.json()]
    assert "system.registered" in actions
    assert "service.registered" in actions
    assert "dependency.registered" in actions
