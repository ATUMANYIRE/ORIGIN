FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" pydantic pydantic-settings \
    "sqlalchemy[asyncio]" alembic asyncpg aiosqlite greenlet \
    redis httpx opentelemetry-api opentelemetry-sdk \
    opentelemetry-instrumentation-fastapi

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
