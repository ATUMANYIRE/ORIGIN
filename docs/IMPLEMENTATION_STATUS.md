# ORIGIN — Implementation Status Matrix (`Milestone 01/05`)

| Component / Capability | Status | Verification Evidence |
| :--- | :--- | :--- |
| **1. API & Authentication (`app/modules/auth`, `app/api`)** | **Implemented & Verified** | `test_registry_and_auth.py` verifies `X-Origin-Key`, `X-Correlation-ID`, and REST/SSE routing. |
| **2. System, Service & Dependency Registry (`app/modules/registry`)** | **Implemented & Verified** | `test_registry_and_auth.py` verifies CRUD, self-dependency rejection (`422`), and live DB stats. |
| **3. OpenTelemetry Ingestion & Queries (`app/modules/telemetry`)** | **Implemented & Verified** | `test_telemetry_and_topology.py` verifies OTLP JSON `v1/traces`, `v1/metrics`, structured batches, and `p95`/`mean` time-series queries. |
| **4. Provenance Topology Discovery (`app/modules/topology`)** | **Implemented & Verified** | `test_telemetry_and_topology.py` verifies `registered`, `observed`, and `registered_and_observed` edges with zero unestablished inference. |
| **5. Controlled Experimentation (`app/modules/experimentation`)** | **Contract & DB Schema Only** | `experiment_definitions` & `experiment_runs` migrated (`0001_initial_schema.py`); execution scheduled for Milestone 03/05. |
| **6. Counterfactual Simulation (`app/modules/simulation`)** | **Contract Only** | `SimulationEngineProtocol` & `SimulationScenarioContract` defined; solver scheduled for Milestone 03/05. |
| **7. Agent Orchestration (`app/modules/agents`)** | **Contract Only** | `AgentOrchestratorProtocol` defined; multi-agent loops scheduled for Milestone 04/05. |
| **8. Scientific Evidence & Hypotheses (`app/modules/evidence`)** | **Contract & DB Schema Only** | `hypotheses` & `evidence_records` migrated (`0001_initial_schema.py`); causal engine scheduled for Milestone 02/05. |
| **9. Safety & Audit (`app/modules/safety`)** | **Implemented Audit + Guard Contract** | `AuditService` actively records immutable `audit_events`; `SafetyEnvelopeContract` defined for Milestone 03/05. |
| **Synthetic Distributed System Laboratory (`lab/`)** | **Implemented & Verified** | 5 instrumented services (`api-gateway`, `checkout-service`, `inventory-service`, `payment-simulator`, `order-database-sim`) + load/fault controller (`normal`, `payment_latency_spike`, `db_lock_contention`). |
| **Frontend Product Experience (`frontend/`)** | **Implemented & Verified** | Warm-white Next.js App Router UI (`/`, `/dashboard`, `/topology`, `/telemetry`, `/systems/[slug]`, `/research`) with React Flow, Recharts, and SSE. |
