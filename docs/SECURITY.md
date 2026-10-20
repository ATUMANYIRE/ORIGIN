# ORIGIN — Security, Isolation & Safety Architecture

## 1. Zero Untrusted Code Execution

ORIGIN never evaluates or executes arbitrary user-supplied scripts, expressions, or shell commands (`allow_untrusted_code_execution = False` in `SafetyEnvelopeContract`). All system registration, dependency declarations, and laboratory fault profiles are constrained by strict Pydantic v2 schemas (`pattern=r"^[a-z0-9][a-z0-9\-_]*$"` and literal enumerations).

## 2. Internal Laboratory Network Isolation

Per Milestone 01/05 safety requirements, **internal laboratory services are never exposed publicly**:
- In `docker-compose.yml`, `origin-lab` is attached exclusively to `origin_internal_net` using `expose: ["8099"]` with **no host port bindings** (`ports:` is omitted).
- Only `origin-backend` can communicate with `origin-lab` over the internal Docker bridge network.
- Public host bindings (`origin-backend` on `127.0.0.1:8000` and `origin-frontend` on `127.0.0.1:3000`) are bound to loopback (`127.0.0.1`) rather than `0.0.0.0`.

## 3. Authentication & Secrets Hygiene

- State-mutating API endpoints verify `X-Origin-Key` or `Authorization: Bearer <token>` using constant-time comparison (`secrets.compare_digest`).
- No credentials or API tokens are committed to source control. `.gitignore` excludes `.env`, `.env.*`, `*.pem`, `*.key`, and local SQLite databases, while `.env.example` documents required environment variables.

## 4. Immutable Audit Trail

Every state mutation (`system.registered`, `service.registered`, `dependency.registered`, `laboratory.profile_changed`, `laboratory.workload_executed`) is recorded in the `audit_events` table with `actor`, `action`, `resource_type`, `resource_id`, `severity`, `correlation_id`, and `created_at`.
