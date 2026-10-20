# ORIGIN — Production Deployment & Operational Runbook

*Product tagline: Give software the ability to understand itself.*

This document details the multi-container production deployment architecture, security hardening, cloud deployment pathways, and operational runbooks for ORIGIN.

---

## 1. Production Architecture Overview

ORIGIN is engineered with strict module isolation and role separation:

```
[ Internet / Browser Clients ]
             │
             ▼ :80 / :443
┌────────────────────────────────────────────────────────┐
│                   Nginx Gateway                        │
│   - Rate Limiting (50 r/s)                             │
│   - Security Headers (nosniff, frameguard)             │
│   - Unbuffered SSE Proxy for /api/v1/telemetry/stream  │
│   - Gzip compression                                   │
└────────────┬─────────────────────────────┬─────────────┘
             │                             │
             │ :3000                       │ :8000
             ▼                             ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│      Next.js Frontend     │ │      FastAPI Backend     │
│   - Node.js 22 Standalone │ │   - Python 3.12          │
│   - React 19 / App Router │ │   - 4 Uvicorn Workers    │
│   - Tailwind CSS          │ │   - OpenTelemetry Ingest │
│   - React Flow & Recharts │ │   - Digital Twin & Causal│
└───────────────────────────┘ └────────────┬─────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼ :5432                ▼ :6379                ▼ :8099
┌───────────────────────────┐ ┌──────────────────────────┐ ┌──────────────────────────┐
│       PostgreSQL 16       │ │          Redis 7         │ │  Synthetic Lab Container │
│   - SCRAM-SHA-256 Auth    │ │   - AOF Persistence      │ │   - 5 Microservices      │
│   - AsyncPG Connection    │ │   - Pub/Sub Coordination │ │   - Epistemic Isolation  │
│   - Persistent Volume     │ │   - Task Locks           │ │   - Internal Network Only│
└───────────────────────────┘ └──────────────────────────┘ └──────────────────────────┘
```

---

## 2. Fast Production Quickstart (Docker Compose)

### 2.1 Clone and Configure Environment

```bash
git clone https://github.com/ATUMANYIRE/ORIGIN.git
cd ORIGIN

# Copy production environment template
cp .env.production.example .env.production
```

Edit `.env.production` to supply cryptographically secure passwords:
- `POSTGRES_PASSWORD`: SCRAM-SHA-256 DB credential.
- `REDIS_PASSWORD`: Redis coordination auth key.
- `ORIGIN_API_KEY`: API authentication key.

### 2.2 Launch Production Stack

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

### 2.3 Verify Stack Health

```bash
docker compose -f docker-compose.prod.yml ps
```

Expected output:
- `origin-prod-gateway`: `Up (healthy)` (port 80)
- `origin-prod-frontend`: `Up (healthy)`
- `origin-prod-backend`: `Up (healthy)`
- `origin-prod-lab`: `Up (healthy)`
- `origin-prod-postgres`: `Up (healthy)`
- `origin-prod-redis`: `Up (healthy)`

Test HTTP Gateway:
```bash
curl -I http://localhost/healthz
# HTTP/1.1 200 OK
```

---

## 3. Cloud Deployment Recipes

### 3.1 AWS ECS (Elastic Container Service) Fargate

1. **Database & Cache**:
   - Provision an Amazon RDS PostgreSQL 16 instance.
   - Provision an Amazon ElastiCache for Redis cluster.
2. **Task Definitions**:
   - Create an ECS Task Definition with `origin-backend` and `origin-frontend`.
   - Store sensitive credentials in AWS Secrets Manager and reference them via `secrets` in the container definition.
3. **Application Load Balancer (ALB)**:
   - Route path `/api/*` to the backend target group.
   - Route path `/*` to the frontend target group.
   - Enable HTTP/2 and configure target group health checks (`/api/v1/health` and `/`).

### 3.2 DigitalOcean Droplet / Ubuntu 24.04 LTS (Single Node)

```bash
# 1. Update and install Docker Engine & Compose
sudo apt-get update && sudo apt-get install -y docker-ce docker-compose-plugin

# 2. Clone repository and start
git clone https://github.com/ATUMANYIRE/ORIGIN.git /opt/origin
cd /opt/origin
cp .env.production.example .env.production
# Edit credentials
nano .env.production

# 3. Launch with systemd restart policy
sudo docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

### 3.3 GCP Cloud Run (Serverless Multi-Service)

1. Deploy `origin-backend` to Cloud Run with Cloud SQL connection.
2. Deploy `origin-frontend` to Cloud Run with `NEXT_PUBLIC_API_URL` pointing to backend Cloud Run URL.
3. Provision Memorystore for Redis for distributed task locks.

---

## 4. Database Migrations

ORIGIN uses Alembic for schema migrations. The backend production entrypoint automatically executes:

```bash
alembic upgrade head
```

To run migrations manually:

```bash
docker compose -f docker-compose.prod.yml exec origin-backend alembic upgrade head
```

To check migration history:

```bash
docker compose -f docker-compose.prod.yml exec origin-backend alembic history --verbose
```

---

## 5. Security Runbook

1. **Epistemic Role Blinding**: Ensure the synthetic lab container (`origin-lab`) is never attached to `origin_public_net`. It must remain exclusively on `origin_internal_net`.
2. **Reverse Proxy Buffering**: Do not enable Nginx `proxy_buffering` on `/api/v1/telemetry/stream`. Disabling buffering is necessary for instant Server-Sent Events delivery.
3. **Key Rotation**: Rotate `ORIGIN_API_KEY` by updating `.env.production` and executing `docker compose -f docker-compose.prod.yml restart origin-backend`.
4. **Audit Logging**: All human approvals, intervention creations, and sandbox restorations are durably logged to the PostgreSQL `audit_events` ledger. Query via:
   ```sql
   SELECT created_at, actor, action, resource_type, severity, details_json 
   FROM audit_events ORDER BY created_at DESC LIMIT 50;
   ```
