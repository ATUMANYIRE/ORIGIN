"""API authentication and correlation ID resolution."""

import secrets
import uuid

from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings


class AuthenticatedPrincipal(BaseModel):
    """Represents a verified caller identity."""

    actor: str
    role: str
    authenticated: bool


async def get_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
) -> str:
    """Extract or generate a request correlation ID."""
    if x_correlation_id and x_correlation_id.strip():
        return x_correlation_id.strip()[:120]
    return f"corr-{uuid.uuid4().hex[:16]}"


async def verify_api_key(
    x_origin_api_key: str | None = Header(default=None, alias="X-Origin-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedPrincipal:
    """Validate API key when supplied, or allow local dev operator in development mode."""
    settings = get_settings()
    token = x_origin_api_key
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if token:
        if secrets.compare_digest(token, settings.origin_api_key):
            return AuthenticatedPrincipal(
                actor="authenticated-operator",
                role="scientific-admin",
                authenticated=True,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Origin-Key or Bearer token.",
        )

    if settings.origin_env in ("development", "test"):
        return AuthenticatedPrincipal(
            actor="local-operator",
            role="operator",
            authenticated=False,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials (X-Origin-Key header required).",
    )


async def verify_benchmark_controller(
    x_benchmark_key: str | None = Header(
        default=None, alias="X-Benchmark-Controller-Key"
    ),
    x_origin_api_key: str | None = Header(default=None, alias="X-Origin-Key"),
) -> AuthenticatedPrincipal:
    """Strictly verify Benchmark Controller credentials.

    Ordinary Investigator credentials (X-Origin-Key) are explicitly rejected (403 Forbidden)
    to enforce strict epistemic separation between the Investigator and hidden ground truth.
    """
    settings = get_settings()
    if not x_benchmark_key:
        if x_origin_api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Access Denied: Investigator credentials cannot access private "
                    "Benchmark Controller or ground-truth endpoints."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-Benchmark-Controller-Key header for Benchmark Controller.",
        )

    if not secrets.compare_digest(
        x_benchmark_key, settings.origin_benchmark_controller_key
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-Benchmark-Controller-Key.",
        )

    return AuthenticatedPrincipal(
        actor="benchmark-controller",
        role="benchmark-evaluator",
        authenticated=True,
    )
