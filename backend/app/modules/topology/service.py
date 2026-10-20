"""Topology graph construction combining registered and observed service relationships."""

import math
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    MetricObservation,
    ServiceDependency,
    ServiceRecord,
    SpanObservation,
)
from app.modules.registry.service import RegistryService
from app.modules.topology.schemas import (
    TopologyEdge,
    TopologyGraphResponse,
    TopologyNode,
    TopologyNodeMetrics,
)

TIER_Y_COORDS: dict[str, float] = {
    "tier-0": 60.0,
    "tier-1": 230.0,
    "tier-2": 400.0,
    "tier-3": 570.0,
}


class TopologyService:
    """Synthesizes topology graphs from registered declarations and observed telemetry."""

    @staticmethod
    async def build_topology_graph(
        db: AsyncSession,
        system_identifier: str,
    ) -> TopologyGraphResponse:
        """Generate the live topology graph for a registered system."""
        system = await RegistryService.get_system_by_id_or_slug(db, system_identifier)

        services = list(
            (
                await db.execute(
                    select(ServiceRecord)
                    .where(ServiceRecord.system_id == system.id)
                    .order_by(ServiceRecord.tier.asc(), ServiceRecord.service_key.asc())
                )
            )
            .scalars()
            .all()
        )
        dependencies = list(
            (
                await db.execute(
                    select(ServiceDependency)
                    .where(ServiceDependency.system_id == system.id)
                    .order_by(
                        ServiceDependency.source_service_key.asc(),
                        ServiceDependency.target_service_key.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )

        # Fetch recent spans (up to 500) to compute per-service live metrics
        recent_spans = list(
            (
                await db.execute(
                    select(SpanObservation)
                    .where(SpanObservation.system_id == system.id)
                    .order_by(SpanObservation.started_at.desc())
                    .limit(500)
                )
            )
            .scalars()
            .all()
        )

        # Fetch recent saturation metrics if available
        recent_saturation = list(
            (
                await db.execute(
                    select(MetricObservation)
                    .where(
                        MetricObservation.system_id == system.id,
                        MetricObservation.metric_name == "saturation_pct",
                    )
                    .order_by(MetricObservation.observed_at.desc())
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        latest_sat_by_svc: dict[str, float] = {}
        for sat in recent_saturation:
            if sat.service_key not in latest_sat_by_svc:
                latest_sat_by_svc[sat.service_key] = round(sat.value, 2)

        spans_by_service: dict[str, list[SpanObservation]] = {}
        for sp in recent_spans:
            spans_by_service.setdefault(sp.service_key, []).append(sp)

        # Group services by tier for clean horizontal layout
        services_by_tier: dict[str, list[ServiceRecord]] = {}
        for svc in services:
            tier_key = svc.tier
            if svc.service_type == "gateway":
                tier_key = "tier-0"
            elif svc.service_type in ("database", "external_simulator") and svc.tier == "tier-1":
                tier_key = "tier-2"
            services_by_tier.setdefault(tier_key, []).append(svc)

        nodes: list[TopologyNode] = []
        for tier_key, tier_services in services_by_tier.items():
            y_pos = TIER_Y_COORDS.get(tier_key, 250.0)
            count = len(tier_services)
            spacing = 300.0
            start_x = 450.0 - ((count - 1) * spacing) / 2.0
            for idx, svc in enumerate(tier_services):
                x_pos = start_x + idx * spacing
                svc_spans = spans_by_service.get(svc.service_key, [])
                if svc_spans:
                    durations = sorted(s.duration_ms for s in svc_spans)
                    err_count = sum(
                        1
                        for s in svc_spans
                        if s.status_code == "ERROR" or s.http_status >= 500
                    )
                    p95_idx = min(
                        len(durations) - 1,
                        max(0, math.ceil(0.95 * len(durations)) - 1),
                    )
                    mean_lat = round(sum(durations) / len(durations), 2)
                    p95_lat = round(durations[p95_idx], 2)
                    err_rate = round((err_count / len(svc_spans)) * 100.0, 2)

                    # Compute live health status from recent window (most recent 15 spans)
                    recent_window = svc_spans[:15]
                    win_durations = sorted(s.duration_ms for s in recent_window)
                    win_err = sum(
                        1
                        for s in recent_window
                        if s.status_code == "ERROR" or s.http_status >= 500
                    )
                    win_err_rate = (win_err / len(recent_window)) * 100.0
                    win_p95 = win_durations[
                        min(
                            len(win_durations) - 1,
                            max(0, math.ceil(0.95 * len(win_durations)) - 1),
                        )
                    ]
                    if win_err_rate >= 15.0 or win_p95 >= 600.0:
                        computed_health = "critical"
                    elif win_err_rate > 0.0 or win_p95 >= 220.0:
                        computed_health = "degraded"
                    else:
                        computed_health = "healthy"
                    svc.health_status = computed_health

                    metrics = TopologyNodeMetrics(
                        observed_span_count=len(svc_spans),
                        mean_latency_ms=mean_lat,
                        p95_latency_ms=p95_lat,
                        error_rate_pct=err_rate,
                        saturation_pct=latest_sat_by_svc.get(svc.service_key),
                    )
                else:
                    metrics = TopologyNodeMetrics(
                        observed_span_count=0,
                        saturation_pct=latest_sat_by_svc.get(svc.service_key),
                    )

                nodes.append(
                    TopologyNode(
                        id=svc.service_key,
                        service_key=svc.service_key,
                        display_name=svc.display_name,
                        service_type=svc.service_type,
                        tier=svc.tier,
                        owner_team=svc.owner_team,
                        registration_source=svc.registration_source,
                        health_status=svc.health_status,
                        position_x=x_pos,
                        position_y=y_pos,
                        last_seen_at=svc.last_seen_at,
                        metrics=metrics,
                        metadata_json=svc.metadata_json,
                    )
                )

        edges: list[TopologyEdge] = []
        reg_only = 0
        obs_only = 0
        verified = 0

        for dep in dependencies:
            is_verified = dep.observation_count > 0 and dep.discovery_source in (
                "observed",
                "registered_and_observed",
            )
            if dep.discovery_source == "registered":
                reg_only += 1
            elif dep.discovery_source == "observed":
                obs_only += 1
                verified += 1
            else:
                verified += 1

            err_pct = (
                round((dep.error_count / dep.observation_count) * 100.0, 2)
                if dep.observation_count > 0
                else 0.0
            )
            edges.append(
                TopologyEdge(
                    id=f"{dep.source_service_key}->{dep.target_service_key}",
                    source=dep.source_service_key,
                    target=dep.target_service_key,
                    protocol=dep.protocol,
                    discovery_source=dep.discovery_source,
                    verified_by_observation=is_verified,
                    observation_count=dep.observation_count,
                    error_count=dep.error_count,
                    error_rate_pct=err_pct,
                    last_latency_ms=(
                        round(dep.last_latency_ms, 2)
                        if dep.last_latency_ms is not None
                        else None
                    ),
                    last_observed_at=dep.last_observed_at,
                )
            )

        return TopologyGraphResponse(
            system_id=system.id,
            system_slug=system.slug,
            system_name=system.name,
            is_synthetic_lab=system.is_synthetic_lab,
            generated_at=datetime.now(UTC),
            total_nodes=len(nodes),
            total_edges=len(edges),
            registered_only_edges=reg_only,
            observed_only_edges=obs_only,
            verified_edges=verified,
            provenance_notice=(
                "ORIGIN never infers unestablished dependencies. Every edge is explicitly "
                "classified as 'registered' (declared only), 'observed' (directly established "
                "from distributed trace parent->child spans), or 'registered_and_observed' "
                "(declared and confirmed by live instrumentation)."
            ),
            nodes=nodes,
            edges=edges,
        )
