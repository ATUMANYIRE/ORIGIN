# ORIGIN — System Architecture (`01/05`)

## 1. High-Level Architecture

```mermaid
flowchart TB
    subgraph Lab["Isolated Synthetic Distributed System Laboratory (Internal Network Only)"]
        LG["Load & Fault Controller"] --> GW["api-gateway"]
        GW --> CHK["checkout-service"]
        CHK --> INV["inventory-service"]
        CHK --> PAY["payment-simulator"]
        CHK --> DB["order-database-sim"]
        INV --> DB
    end

    subgraph Backend["ORIGIN Living System Intelligence Backend (FastAPI + Python 3.12)"]
        B1["1. API & Auth Middleware"]
        B2["2. System & Service Registry"]
        B3["3. OpenTelemetry Ingestion & Queries"]
        B4["4. Provenance Topology Discovery"]
        B5["5. Experimentation Contract (M03)"]
        B6["6. Simulation Contract (M03)"]
        B7["7. Agent Orchestration Contract (M04)"]
        B8["8. Scientific Evidence Contract (M02)"]
        B9["9. Safety Envelope & Audit Trail"]
    end

    subgraph Storage["Persistence & Coordination"]
        PG[("PostgreSQL 16\n(SQLAlchemy 2 Async + Alembic)")]
        RD[("Redis 7\n(Pub/Sub & Event Coordination)")]
    end

    subgraph Frontend["ORIGIN Scientific Instrument UI (Next.js App Router)"]
        UI_HOME["Landing Overview (/)"]
        UI_DASH["System Matrix (/dashboard)"]
        UI_TOPO["Topology Explorer (/topology)\nReact Flow"]
        UI_TELEM["Telemetry Workspace (/telemetry)\nRecharts + Trace Waterfall"]
        UI_SYS["System Detail (/systems/[slug])"]
        UI_RES["Research Contracts (/research)"]
    end

    GW & CHK & INV & PAY & DB -- "OTLP/HTTP JSON + Correlated Spans & Metrics" --> B3
    B1 --> B2 & B3 & B4 & B9
    B2 & B3 & B4 & B9 --> PG
    B3 --> RD
    B3 -- "SSE Real-Time Stream (/api/v1/telemetry/stream)" --> Frontend
    Frontend -- "REST Queries & Lab Workload Triggers" --> B1
    B1 -- "Internal Workload Control" --> LG
```

## 2. The Nine Architectural Boundaries

| Boundary | Package Path | Milestone 01/05 Status | Responsibility |
| :--- | :--- | :--- | :--- |
| **1. API & Auth** | `backend/app/modules/auth/`, `backend/app/api/` | **Implemented** | `X-Origin-Key` / Bearer token verification, `X-Correlation-ID` propagation, REST/OTLP/SSE routing. |
| **2. System Registry** | `backend/app/modules/registry/` | **Implemented** | Registration of systems, services, tiers, and declared dependencies. |
| **3. Telemetry Ingestion** | `backend/app/modules/telemetry/` | **Implemented** | OpenTelemetry OTLP/HTTP JSON (`traces` & `metrics`) and native batch ingestion, time-series statistical queries (`mean`, `p95`, `min`, `max`), SSE broadcast. |
| **4. Topology Discovery** | `backend/app/modules/topology/` | **Implemented** | Synthesizes directed service graphs combining declared dependencies with observed parent→child span calls, enforcing strict provenance. |
| **5. Experimentation** | `backend/app/modules/experimentation/` | **Contract & Schema Only** | `ExperimentProposalContract`, `ExperimentEngineProtocol`, and DB tables (`experiment_definitions`, `experiment_runs`) for Milestone 03/05. |
| **6. Simulation** | `backend/app/modules/simulation/` | **Contract Only** | `SimulationScenarioContract` and `SimulationEngineProtocol` for Milestone 03/05 counterfactual evaluation. |
| **7. Agent Orchestration** | `backend/app/modules/agents/` | **Contract Only** | `ScientificInvestigationTaskContract` and `AgentOrchestratorProtocol` for Milestone 04/05 multi-agent reasoning. |
| **8. Scientific Evidence** | `backend/app/modules/evidence/` | **Contract & Schema Only** | `HypothesisSubmissionContract`, `ScientificEvidenceLedgerProtocol`, and DB tables (`hypotheses`, `evidence_records`) for Milestone 02/05. |
| **9. Safety & Audit** | `backend/app/modules/safety/` | **Implemented Audit + Safety Contract** | Active `AuditService` persisting `audit_events` for all state mutations + `SafetyEnvelopeContract` for future experiments. |
