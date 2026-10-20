"""Pydantic v2 schemas for the System & Service Registry."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SystemCreate(BaseModel):
    """Payload to register a new system in ORIGIN."""

    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9\-_]*$")
    name: str = Field(..., min_length=2, max_length=200)
    environment: str = Field(default="synthetic-lab", min_length=2, max_length=64)
    description: str = Field(default="", max_length=2000)
    is_synthetic_lab: bool = Field(default=False)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ServiceCreate(BaseModel):
    """Payload to register or update a service within a system."""

    service_key: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9\-_]*$")
    display_name: str = Field(..., min_length=2, max_length=200)
    service_type: Literal["gateway", "microservice", "database", "external_simulator", "worker"] = (
        "microservice"
    )
    tier: Literal["tier-0", "tier-1", "tier-2", "tier-3"] = "tier-1"
    owner_team: str = Field(default="platform", min_length=1, max_length=120)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DependencyCreate(BaseModel):
    """Payload to declare an explicit service-to-service dependency."""

    source_service_key: str = Field(
        ..., min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9\-_]*$"
    )
    target_service_key: str = Field(
        ..., min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9\-_]*$"
    )
    protocol: Literal["http", "grpc", "sql", "redis", "tcp"] = "http"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ServiceRead(BaseModel):
    """Serialized service record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    service_key: str
    display_name: str
    service_type: str
    tier: str
    owner_team: str
    registration_source: str
    health_status: str
    metadata_json: dict[str, Any]
    last_seen_at: datetime | None
    created_at: datetime


class DependencyRead(BaseModel):
    """Serialized service dependency edge."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    source_service_key: str
    target_service_key: str
    protocol: str
    discovery_source: str
    observation_count: int
    error_count: int
    last_latency_ms: float | None
    last_observed_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime


class TelemetrySourceRead(BaseModel):
    """Serialized telemetry source record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str
    source_name: str
    exporter_protocol: str
    sdk_version: str
    is_synthetic: bool
    total_batches_ingested: int
    last_ingested_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime


class SystemSummaryStats(BaseModel):
    """Live operational counts for a registered system."""

    service_count: int
    dependency_count: int
    observed_dependency_count: int
    metric_observation_count: int
    span_observation_count: int
    telemetry_source_count: int
    healthy_service_count: int
    degraded_service_count: int


class SystemRead(BaseModel):
    """Serialized system with live operational summary."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    environment: str
    description: str
    is_synthetic_lab: bool
    status: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    stats: SystemSummaryStats | None = None


class SystemDetailRead(SystemRead):
    """Full system detail including services, dependencies, and telemetry sources."""

    services: list[ServiceRead] = Field(default_factory=list)
    dependencies: list[DependencyRead] = Field(default_factory=list)
    telemetry_sources: list[TelemetrySourceRead] = Field(default_factory=list)
