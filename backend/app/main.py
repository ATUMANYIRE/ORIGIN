"""ORIGIN FastAPI Application Entrypoint."""

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy import func, select

from app.api.router import api_router
from app.core.config import get_settings
from app.db.models import Base, SpanObservation
from app.db.session import AsyncSessionLocal, engine
from app.modules.laboratory.orchestrator import (
    LabTransactionRequest,
    SyntheticLabOrchestrator,
)

settings = get_settings()

# Configure OpenTelemetry SDK TracerProvider for ORIGIN backend itself
resource = Resource.create(
    {
        "service.name": "origin-intelligence-backend",
        "service.version": "0.1.0",
        "deployment.environment": settings.origin_env,
    }
)
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize schema and seed baseline Synthetic Laboratory telemetry on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if settings.lab_auto_seed:
        async with AsyncSessionLocal() as session:
            sys_id = await SyntheticLabOrchestrator.ensure_lab_registered(
                session, actor="startup-lifecycle"
            )
            existing_spans = (
                await session.execute(
                    select(func.count(SpanObservation.id)).where(
                        SpanObservation.system_id == sys_id
                    )
                )
            ).scalar_one()
            if int(existing_spans) == 0:
                await SyntheticLabOrchestrator.run_workload(
                    session,
                    request=LabTransactionRequest(iterations=4, profile="normal"),
                    actor="startup-seed",
                    correlation_id="corr-startup-seed",
                )
    yield
    await engine.dispose()


app = FastAPI(
    title="ORIGIN — Autonomous Scientific Intelligence Platform",
    description=(
        "Give software the ability to understand itself. "
        "(Milestone 05/05 — Independent Verification, Hardening & Submission)"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Hardened CORS: Restrict to configured origins in production, reject wildcard credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.origin_env == "production" else ["*"],
    allow_credentials=settings.origin_env == "production",
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach X-Correlation-ID to every request and response."""
    corr_id = request.headers.get("X-Correlation-ID") or f"corr-{uuid.uuid4().hex[:16]}"
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    return response


app.include_router(api_router)

FastAPIInstrumentor.instrument_app(app)
