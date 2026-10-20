"""Audit event persistence and safety envelope contract."""

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent


class SafetyEnvelopeContract(BaseModel):
    """Contract defining operational guardrails for future autonomous experiments."""

    max_error_rate_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    max_p95_latency_ms: float = Field(default=1200.0, gt=0.0)
    allow_untrusted_code_execution: bool = Field(default=False)
    require_isolated_network: bool = Field(default=True)


class SafetyGuardProtocol(Protocol):
    """Protocol for pre-flight and live experiment safety validation (Milestone 03/05)."""

    async def evaluate_envelope(
        self, system_id: str, envelope: SafetyEnvelopeContract
    ) -> dict[str, Any]:
        """Evaluate whether a system is within safe operational bounds."""


class AuditEventRead(BaseModel):
    """Serialized audit event record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    system_id: str | None
    actor: str
    action: str
    resource_type: str
    resource_id: str | None
    severity: str
    correlation_id: str | None
    details_json: dict[str, Any]
    created_at: datetime


class AuditService:
    """Service for recording and querying immutable operational audit events."""

    @staticmethod
    async def record_event(
        db: AsyncSession,
        *,
        action: str,
        resource_type: str,
        actor: str = "system",
        system_id: str | None = None,
        resource_id: str | None = None,
        severity: str = "info",
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Persist an audit event within the current transaction."""
        event = AuditEvent(
            system_id=system_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            severity=severity,
            correlation_id=correlation_id,
            details_json=details or {},
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def list_events(
        db: AsyncSession,
        system_id: str | None = None,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """List recent audit events ordered newest first."""
        stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
        if system_id:
            stmt = stmt.where(AuditEvent.system_id == system_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())
