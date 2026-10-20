"""Tests for OpenTelemetry OTLP ingestion, queries, and provenance-strict topology."""

from httpx import AsyncClient


async def test_otlp_ingestion_and_strict_topology_provenance(client: AsyncClient) -> None:
    """Verify OTLP traces & metrics update topology without inferring unestablished edges."""
    # 1. Register system with 3 services and 1 declared dependency (edge-gw -> auth-svc),
    # plus 1 declared dependency that is NEVER called (edge-gw -> legacy-vault).
    await client.post(
        "/api/v1/systems",
        json={
            "slug": "provenance-test-sys",
            "name": "Provenance Verification System",
            "environment": "test",
            "is_synthetic_lab": True,
        },
    )
    for key, stype, tier in [
        ("edge-gw", "gateway", "tier-0"),
        ("auth-svc", "microservice", "tier-1"),
        ("legacy-vault", "database", "tier-2"),
    ]:
        await client.post(
            "/api/v1/systems/provenance-test-sys/services",
            json={
                "service_key": key,
                "display_name": key.upper(),
                "service_type": stype,
                "tier": tier,
            },
        )

    # Declare edge-gw -> auth-svc and edge-gw -> legacy-vault
    await client.post(
        "/api/v1/systems/provenance-test-sys/dependencies",
        json={"source_service_key": "edge-gw", "target_service_key": "auth-svc"},
    )
    await client.post(
        "/api/v1/systems/provenance-test-sys/dependencies",
        json={"source_service_key": "edge-gw", "target_service_key": "legacy-vault"},
    )

    # 2. Ingest OTLP Traces where:
    # - edge-gw calls auth-svc (confirms declared edge -> 'registered_and_observed')
    # - auth-svc calls token-cache (undocumented service & edge -> 'observed')
    # - legacy-vault is never called (remains 'registered' with verified_by_observation=False)
    otlp_traces = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "edge-gw"}},
                        {
                            "key": "origin.system.slug",
                            "value": {"stringValue": "provenance-test-sys"},
                        },
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                "spanId": "span0001",
                                "name": "GET /login",
                                "attributes": [
                                    {
                                        "key": "origin.correlation_id",
                                        "value": {"stringValue": "corr-otlp-99"},
                                    },
                                    {
                                        "key": "origin.duration_ms",
                                        "value": {"doubleValue": 48.5},
                                    },
                                ],
                            }
                        ]
                    }
                ],
            },
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "auth-svc"}},
                        {
                            "key": "origin.system.slug",
                            "value": {"stringValue": "provenance-test-sys"},
                        },
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                "spanId": "span0002",
                                "parentSpanId": "span0001",
                                "name": "POST /verify",
                                "attributes": [
                                    {
                                        "key": "origin.correlation_id",
                                        "value": {"stringValue": "corr-otlp-99"},
                                    },
                                    {
                                        "key": "origin.parent_service",
                                        "value": {"stringValue": "edge-gw"},
                                    },
                                    {
                                        "key": "origin.duration_ms",
                                        "value": {"doubleValue": 29.0},
                                    },
                                ],
                            }
                        ]
                    }
                ],
            },
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "token-cache"}},
                        {
                            "key": "origin.system.slug",
                            "value": {"stringValue": "provenance-test-sys"},
                        },
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                "spanId": "span0003",
                                "parentSpanId": "span0002",
                                "name": "GET token",
                                "attributes": [
                                    {
                                        "key": "origin.correlation_id",
                                        "value": {"stringValue": "corr-otlp-99"},
                                    },
                                    {
                                        "key": "origin.parent_service",
                                        "value": {"stringValue": "auth-svc"},
                                    },
                                    {
                                        "key": "origin.duration_ms",
                                        "value": {"doubleValue": 6.4},
                                    },
                                ],
                            }
                        ]
                    }
                ],
            },
        ]
    }
    tr_resp = await client.post("/api/v1/telemetry/otlp/v1/traces", json=otlp_traces)
    assert tr_resp.status_code == 201
    receipts = tr_resp.json()
    assert len(receipts) == 1
    assert receipts[0]["spans_ingested"] == 3
    assert receipts[0]["observed_edges_updated"] == 2

    # 3. Ingest OTLP Metrics
    otlp_metrics = {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "auth-svc"}},
                        {
                            "key": "origin.system.slug",
                            "value": {"stringValue": "provenance-test-sys"},
                        },
                    ]
                },
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "saturation_pct",
                                "unit": "%",
                                "gauge": {
                                    "dataPoints": [
                                        {
                                            "asDouble": 41.5,
                                            "attributes": [
                                                {
                                                    "key": "origin.correlation_id",
                                                    "value": {
                                                        "stringValue": "corr-otlp-99"
                                                    },
                                                }
                                            ],
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                ],
            }
        ]
    }
    m_resp = await client.post("/api/v1/telemetry/otlp/v1/metrics", json=otlp_metrics)
    assert m_resp.status_code == 201

    # 4. Query Topology and verify provenance classifications
    topo_resp = await client.get("/api/v1/systems/provenance-test-sys/topology")
    assert topo_resp.status_code == 200
    topo = topo_resp.json()

    assert topo["total_nodes"] == 4  # 3 registered + 1 observed ('token-cache')
    assert topo["total_edges"] == 3
    assert topo["registered_only_edges"] == 1
    assert topo["observed_only_edges"] == 1
    assert topo["verified_edges"] == 2

    edges_by_id = {e["id"]: e for e in topo["edges"]}
    assert edges_by_id["edge-gw->auth-svc"]["discovery_source"] == "registered_and_observed"
    assert edges_by_id["edge-gw->auth-svc"]["verified_by_observation"] is True

    assert edges_by_id["auth-svc->token-cache"]["discovery_source"] == "observed"
    assert edges_by_id["auth-svc->token-cache"]["verified_by_observation"] is True

    assert edges_by_id["edge-gw->legacy-vault"]["discovery_source"] == "registered"
    assert edges_by_id["edge-gw->legacy-vault"]["verified_by_observation"] is False

    # Verify NO unestablished edge (e.g., token-cache -> legacy-vault) was fabricated
    assert "token-cache->legacy-vault" not in edges_by_id
    assert "auth-svc->legacy-vault" not in edges_by_id

    # 5. Query time-series metrics and correlated spans
    series_resp = await client.get(
        "/api/v1/telemetry/metrics?system_id=provenance-test-sys&metric_name=request_latency_ms"
    )
    assert series_resp.status_code == 200
    series = series_resp.json()
    assert series["sample_count"] == 3
    assert series["p95_value"] is not None

    spans_resp = await client.get(
        "/api/v1/telemetry/spans?system_id=provenance-test-sys&correlation_id=corr-otlp-99"
    )
    assert spans_resp.status_code == 200
    assert len(spans_resp.json()) == 3
