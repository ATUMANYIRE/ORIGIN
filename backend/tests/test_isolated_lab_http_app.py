"""Tests for the isolated Synthetic Distributed System Laboratory HTTP service endpoints."""

import importlib.util
from pathlib import Path

from httpx import ASGITransport, AsyncClient

LAB_APP_PATH = Path(__file__).resolve().parents[2] / "lab" / "app.py"
_spec = importlib.util.spec_from_file_location("origin_lab_app", LAB_APP_PATH)
assert _spec is not None and _spec.loader is not None
_lab_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lab_module)
lab_app = _lab_module.app


async def test_isolated_lab_internal_health_and_service_endpoints() -> None:
    """Verify the isolated lab container application exposes all 5 service endpoints internally."""
    transport = ASGITransport(app=lab_app)
    async with AsyncClient(transport=transport, base_url="http://labserver") as ac:
        health = await ac.get("/internal/lab/health")
        assert health.status_code == 200
        h_data = health.json()
        assert h_data["status"] == "healthy"
        assert "api-gateway" in h_data["services"]
        assert "order-database-sim" in h_data["services"]

        # Direct call to database simulator and payment simulator with trace correlation headers
        db_resp = await ac.post(
            "/services/database/query",
            json={"operation": "SELECT FOR UPDATE inventory_stock"},
            headers={
                "X-Trace-ID": "trace-lab-direct-001",
                "X-Correlation-ID": "corr-lab-direct-001",
                "X-Parent-Span-ID": "parent-001",
                "X-Parent-Service": "inventory-service",
            },
        )
        assert db_resp.status_code == 200
        db_span = db_resp.json()["spans"][0]
        assert db_span["service_key"] == "order-database-sim"
        assert db_span["parent_service_key"] == "inventory-service"
        assert db_span["correlation_id"] == "corr-lab-direct-001"

        pay_resp = await ac.post(
            "/services/payment/authorize",
            json={"sku": "ORIGIN-SENSOR", "amount_usd": 199.0},
            headers={
                "X-Trace-ID": "trace-lab-direct-001",
                "X-Correlation-ID": "corr-lab-direct-001",
                "X-Parent-Span-ID": "parent-002",
                "X-Parent-Service": "checkout-service",
            },
        )
        assert pay_resp.status_code == 200
        pay_span = pay_resp.json()["spans"][0]
        assert pay_span["service_key"] == "payment-simulator"
        assert pay_span["parent_service_key"] == "checkout-service"
