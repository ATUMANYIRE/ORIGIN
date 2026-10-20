"""Business logic for system, service, and dependency registration."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    MetricObservation,
    RegisteredSystem,
    ServiceDependency,
    ServiceRecord,
    SpanObservation,
    TelemetrySource,
)
from app.modules.registry.schemas import (
    DependencyCreate,
    DependencyRead,
    ServiceCreate,
    ServiceRead,
    SystemCreate,
    SystemDetailRead,
    SystemRead,
    SystemSummaryStats,
    TelemetrySourceRead,
)
from app.modules.safety.service import AuditService


class RegistryService:
    """Manages registered systems, services, and declared dependencies."""

    @staticmethod
    async def create_or_get_system(
        db: AsyncSession,
        payload: SystemCreate,
        actor: str = "system",
        correlation_id: str | None = None,
    ) -> RegisteredSystem:
        """Create a system or update metadata if slug already exists."""
        stmt = select(RegisteredSystem).where(RegisteredSystem.slug == payload.slug)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.name = payload.name
            existing.environment = payload.environment
            existing.description = payload.description
            existing.is_synthetic_lab = payload.is_synthetic_lab
            existing.metadata_json = payload.metadata_json
            await db.flush()
            return existing

        system = RegisteredSystem(
            slug=payload.slug,
            name=payload.name,
            environment=payload.environment,
            description=payload.description,
            is_synthetic_lab=payload.is_synthetic_lab,
            status="active",
            metadata_json=payload.metadata_json,
        )
        db.add(system)
        await db.flush()

        await AuditService.record_event(
            db,
            system_id=system.id,
            actor=actor,
            action="system.registered",
            resource_type="registered_system",
            resource_id=system.id,
            correlation_id=correlation_id,
            details={"slug": system.slug, "is_synthetic_lab": system.is_synthetic_lab},
        )
        return system

    @staticmethod
    async def get_system_by_id_or_slug(db: AsyncSession, identifier: str) -> RegisteredSystem:
        """Look up a system by UUID or slug."""
        stmt = select(RegisteredSystem).where(
            (RegisteredSystem.id == identifier) | (RegisteredSystem.slug == identifier)
        )
        system = (await db.execute(stmt)).scalar_one_or_none()
        if system is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Registered system '{identifier}' not found.",
            )
        return system

    @staticmethod
    async def compute_system_stats(db: AsyncSession, system_id: str) -> SystemSummaryStats:
        """Compute exact live operational counts from persistent database tables."""
        svc_count = (
            await db.execute(
                select(func.count(ServiceRecord.id)).where(ServiceRecord.system_id == system_id)
            )
        ).scalar_one()

        healthy_count = (
            await db.execute(
                select(func.count(ServiceRecord.id)).where(
                    ServiceRecord.system_id == system_id,
                    ServiceRecord.health_status == "healthy",
                )
            )
        ).scalar_one()

        degraded_count = (
            await db.execute(
                select(func.count(ServiceRecord.id)).where(
                    ServiceRecord.system_id == system_id,
                    ServiceRecord.health_status.in_(["degraded", "critical"]),
                )
            )
        ).scalar_one()

        dep_count = (
            await db.execute(
                select(func.count(ServiceDependency.id)).where(
                    ServiceDependency.system_id == system_id
                )
            )
        ).scalar_one()

        obs_dep_count = (
            await db.execute(
                select(func.count(ServiceDependency.id)).where(
                    ServiceDependency.system_id == system_id,
                    ServiceDependency.discovery_source.in_(["observed", "registered_and_observed"]),
                )
            )
        ).scalar_one()

        metric_count = (
            await db.execute(
                select(func.count(MetricObservation.id)).where(
                    MetricObservation.system_id == system_id
                )
            )
        ).scalar_one()

        span_count = (
            await db.execute(
                select(func.count(SpanObservation.id)).where(SpanObservation.system_id == system_id)
            )
        ).scalar_one()

        source_count = (
            await db.execute(
                select(func.count(TelemetrySource.id)).where(TelemetrySource.system_id == system_id)
            )
        ).scalar_one()

        return SystemSummaryStats(
            service_count=int(svc_count),
            dependency_count=int(dep_count),
            observed_dependency_count=int(obs_dep_count),
            metric_observation_count=int(metric_count),
            span_observation_count=int(span_count),
            telemetry_source_count=int(source_count),
            healthy_service_count=int(healthy_count),
            degraded_service_count=int(degraded_count),
        )

    @staticmethod
    async def list_systems(db: AsyncSession) -> list[SystemRead]:
        """List all registered systems with live summary counts."""
        stmt = select(RegisteredSystem).order_by(RegisteredSystem.created_at.asc())
        systems = list((await db.execute(stmt)).scalars().all())
        results: list[SystemRead] = []
        for sys_obj in systems:
            stats = await RegistryService.compute_system_stats(db, sys_obj.id)
            read_obj = SystemRead.model_validate(sys_obj)
            read_obj.stats = stats
            results.append(read_obj)
        return results

    @staticmethod
    async def get_system_detail(db: AsyncSession, identifier: str) -> SystemDetailRead:
        """Retrieve a system along with its services, dependencies, and telemetry sources."""
        system = await RegistryService.get_system_by_id_or_slug(db, identifier)
        stats = await RegistryService.compute_system_stats(db, system.id)

        services = list(
            (
                await db.execute(
                    select(ServiceRecord)
                    .where(ServiceRecord.system_id == system.id)
                    .order_by(ServiceRecord.service_key.asc())
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
        sources = list(
            (
                await db.execute(
                    select(TelemetrySource)
                    .where(TelemetrySource.system_id == system.id)
                    .order_by(TelemetrySource.source_name.asc())
                )
            )
            .scalars()
            .all()
        )

        base_read = SystemRead.model_validate(system)
        return SystemDetailRead(
            **base_read.model_dump(exclude={"stats"}),
            stats=stats,
            services=[ServiceRead.model_validate(s) for s in services],
            dependencies=[DependencyRead.model_validate(d) for d in dependencies],
            telemetry_sources=[TelemetrySourceRead.model_validate(t) for t in sources],
        )

    @staticmethod
    async def register_service(
        db: AsyncSession,
        system_identifier: str,
        payload: ServiceCreate,
        actor: str = "system",
        correlation_id: str | None = None,
    ) -> ServiceRecord:
        """Register or update a service record in a system."""
        system = await RegistryService.get_system_by_id_or_slug(db, system_identifier)
        stmt = select(ServiceRecord).where(
            ServiceRecord.system_id == system.id,
            ServiceRecord.service_key == payload.service_key,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.display_name = payload.display_name
            existing.service_type = payload.service_type
            existing.tier = payload.tier
            existing.owner_team = payload.owner_team
            existing.metadata_json = payload.metadata_json
            if existing.registration_source == "observed":
                existing.registration_source = "registered_and_observed"
            await db.flush()
            return existing

        svc = ServiceRecord(
            system_id=system.id,
            service_key=payload.service_key,
            display_name=payload.display_name,
            service_type=payload.service_type,
            tier=payload.tier,
            owner_team=payload.owner_team,
            registration_source="registered",
            health_status="unknown",
            metadata_json=payload.metadata_json,
        )
        db.add(svc)
        await db.flush()

        await AuditService.record_event(
            db,
            system_id=system.id,
            actor=actor,
            action="service.registered",
            resource_type="service",
            resource_id=svc.service_key,
            correlation_id=correlation_id,
            details={"service_type": svc.service_type, "tier": svc.tier},
        )
        return svc

    @staticmethod
    async def register_dependency(
        db: AsyncSession,
        system_identifier: str,
        payload: DependencyCreate,
        actor: str = "system",
        correlation_id: str | None = None,
    ) -> ServiceDependency:
        """Register an explicit service dependency edge."""
        if payload.source_service_key == payload.target_service_key:
            raise HTTPException(
                status_code=422,
                detail="Self-referential service dependencies are not permitted.",
            )

        system = await RegistryService.get_system_by_id_or_slug(db, system_identifier)
        stmt = select(ServiceDependency).where(
            ServiceDependency.system_id == system.id,
            ServiceDependency.source_service_key == payload.source_service_key,
            ServiceDependency.target_service_key == payload.target_service_key,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.protocol = payload.protocol
            existing.metadata_json = payload.metadata_json
            if existing.discovery_source == "observed":
                existing.discovery_source = "registered_and_observed"
            await db.flush()
            return existing

        dep = ServiceDependency(
            system_id=system.id,
            source_service_key=payload.source_service_key,
            target_service_key=payload.target_service_key,
            protocol=payload.protocol,
            discovery_source="registered",
            observation_count=0,
            error_count=0,
            metadata_json=payload.metadata_json,
        )
        db.add(dep)
        await db.flush()

        await AuditService.record_event(
            db,
            system_id=system.id,
            actor=actor,
            action="dependency.registered",
            resource_type="service_dependency",
            resource_id=f"{payload.source_service_key}->{payload.target_service_key}",
            correlation_id=correlation_id,
            details={"protocol": payload.protocol},
        )
        return dep
