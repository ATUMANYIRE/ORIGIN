"""Pydantic v2 schemas for topology graph nodes, edges, and provenance metadata."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TopologyNodeMetrics(BaseModel):
    """Live telemetry metrics attached to a service topology node."""

    observed_span_count: int = 0
    mean_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    error_rate_pct: float = 0.0
    saturation_pct: float | None = None


class TopologyNode(BaseModel):
    """Node in the system topology graph."""

    id: str
    service_key: str
    display_name: str
    service_type: str
    tier: str
    owner_team: str
    registration_source: str  # "registered" | "observed" | "registered_and_observed"
    health_status: str  # "healthy" | "degraded" | "critical" | "unknown"
    position_x: float
    position_y: float
    last_seen_at: datetime | None = None
    metrics: TopologyNodeMetrics = Field(default_factory=TopologyNodeMetrics)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    """Directed dependency edge in the system topology graph with strict provenance."""

    id: str
    source: str
    target: str
    protocol: str
    discovery_source: str  # "registered" | "observed" | "registered_and_observed"
    verified_by_observation: bool
    observation_count: int
    error_count: int
    error_rate_pct: float
    last_latency_ms: float | None = None
    last_observed_at: datetime | None = None


class TopologyGraphResponse(BaseModel):
    """Complete system topology graph and provenance summary."""

    system_id: str
    system_slug: str
    system_name: str
    is_synthetic_lab: bool
    generated_at: datetime
    total_nodes: int
    total_edges: int
    registered_only_edges: int
    observed_only_edges: int
    verified_edges: int
    provenance_notice: str
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
