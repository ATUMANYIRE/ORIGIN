# ORIGIN — Technical Architecture & Scientific Design Document

> **Product Tagline:** *Give software the ability to understand itself.*  
> **Repository:** [https://github.com/ATUMANYIRE/ORIGIN](https://github.com/ATUMANYIRE/ORIGIN)  

---

## 1. Architectural Philosophy & The 9 Strict Boundaries

ORIGIN is engineered with strict modular boundaries to guarantee scientific integrity, epistemic blinding, and operational safety:

```mermaid
flowchart TD
    subgraph Edge ["External Boundary & Clients"]
        Client[Browser / Next.js 15 UI]
        OTelAgent[OTel Collectors / App Traces]
        GW[Nginx Gateway :80]
    end

    subgraph Core ["ORIGIN Core Architecture"]
        B1["1. API & Auth (FastAPI)"]
        B2["2. System & Service Registry"]
        B3["3. Telemetry Ingestion (OTLP/SSE)"]
        B4["4. Topology Discovery Engine"]
        B5["5. Autonomous Causal Scientist"]
        B6["6. Living Digital Twin Simulator"]
        B7["7. Recovery Orchestrator & Watchdog"]
        B8["8. Scientific Evidence Ledger"]
        B9["9. Safety Envelope & Audit"]
    end

    subgraph Data ["Persistence & Cache"]
        PG[(PostgreSQL 16)]
        RD[(Redis 7 Pub/Sub)]
    end

    subgraph Lab ["Synthetic Microservice Lab (Epistemically Blinded)"]
        S1[api-gateway]
        S2[checkout-service]
        S3[inventory-service]
        S4[payment-simulator]
        S5[order-database-sim]
    end

    Client -->|HTTP/SSE| GW
    OTelAgent -->|OTLP JSON| GW
    GW --> B1
    B1 --> B2 & B3 & B4 & B5 & B6 & B7 & B8 & B9
    B3 --> PG & RD
    B4 --> PG
    B5 -->|Interventions| Lab
    B6 -.->|Calibrate Heldout| B3
    B7 -->|Pre-verify| Lab
    B8 --> PG
    B9 --> PG
```

### Module Boundary Directory
1. **API & Authentication (`app.api`, `app.core`):** Bearer token authentication, API key validation, CORS origin enforcement, standard error envelope.
2. **System Registry (`app.modules.registry`):** Service registry, dependency metadata, environment labels, deployment tracking.
3. **Telemetry Ingestion (`app.modules.telemetry`):** Native OpenTelemetry OTLP JSON parser, Redis streaming pub/sub, SSE broadcast hub (benchmarked at 40,387 spans/sec).
4. **Topology Discovery (`app.modules.topology`):** Cryptographic hash provenance-aware causal graph builder from live distributed span parent-child relationships.
5. **Autonomous Causal Scientist (`app.modules.experimentation`, `app.modules.agents`):** Hypothesis formulation, paired block-randomized trial generation, controlled allowlisted interventions, Welch's t-test and Cohen's d effect size evaluation.
6. **Living Digital Twin (`app.modules.simulation`):** Discrete-event simulation engine, Little's Law queues, deterministic snapshot rewind, held-out model calibration, counterfactual branching, Monte Carlo predictive uncertainty.
7. **Recovery Orchestrator (`app.modules.recovery`):** Autonomous recovery lifecycle, sandbox pre-verification, automatic rollback watchdog, SLA post-recovery monitoring.
8. **Scientific Evidence Ledger (`app.modules.evidence`):** Peer-reviewable evidence chain, observation lineage, hypothesis revision history, exportable Markdown reports.
9. **Safety & Audit (`app.modules.safety`):** Dual-operator cryptographic signature approval, allowlisted intervention policy enforcement, immutable audit events.

---

## 2. Scientific Lifecycle State Machine

ORIGIN's causal investigation and recovery intelligence operate as finite state machines with explicit transition guards:

```mermaid
stateDiagram-v2
    [*] --> CREATED: Incident Triggered
    CREATED --> OBSERVING: Ingest Telemetry
    OBSERVING --> HYPOTHESIZING: Ground Hypotheses in Traces
    HYPOTHESIZING --> PLANNING: Select Allowlisted Intervention
    PLANNING --> EXPERIMENTING: Paired Block-Randomized Trials
    EXPERIMENTING --> EVALUATING: Welch t-test & Cohen's d
    
    state EVALUATING {
        [*] --> CheckEvidence
        CheckEvidence --> Confirmed: 95% CI != 0 & |d| >= 0.5
        CheckEvidence --> Refuted: Effect <= 0 or opposite
        CheckEvidence --> Inconclusive: Ambiguous / High Noise
    }
    
    Confirmed --> SIMULATING: Pass Finding to Digital Twin
    SIMULATING --> PROPOSING: Parallel Counterfactual Forecast
    PROPOSING --> SANDBOX_VERIFYING: Isolated Test Clone
    SANDBOX_VERIFYING --> AWAITING_APPROVAL: Sandbox Passed
    SANDBOX_VERIFYING --> FAILED: Sandbox Degraded
    
    AWAITING_APPROVAL --> APPROVED: Dual Cryptographic Signatures
    AWAITING_APPROVAL --> CANCELLED: Human Rejected
    
    APPROVED --> EXECUTING: Apply Allowlisted Remediation
    EXECUTING --> OBSERVING_POST: Active Watchdog SLA Check
    
    OBSERVING_POST --> RECOVERED: System Metrics Restored
    OBSERVING_POST --> ROLLING_BACK: SLA Violation Detected
    ROLLING_BACK --> RECOVERY_FAILED: Baseline Reverted
    
    RECOVERED --> [*]
    Inconclusive --> [*]
    FAILED --> [*]
    RECOVERY_FAILED --> [*]
```

---

## 3. Mathematical & Empirical Formulations

### 3.1 Causal Statistical Inference Engine
To avoid false conclusions caused by unequal variances between control and treatment arms, ORIGIN uses **Welch's two-sample t-test**:

$$t = \frac{\bar{X}_t - \bar{X}_c}{\sqrt{\frac{s_t^2}{N_t} + \frac{s_c^2}{N_c}}}$$

Degrees of freedom are computed analytically using the **Welch–Satterthwaite equation**:

$$\nu \approx \frac{\left(\frac{s_t^2}{N_t} + \frac{s_c^2}{N_c}\right)^2}{\frac{(s_t^2/N_t)^2}{N_t - 1} + \frac{(s_c^2/N_c)^2}{N_c - 1}}$$

Practical effect magnitude is measured via **Cohen's d**:

$$d = \frac{\bar{X}_t - \bar{X}_c}{s_{\text{pooled}}}, \quad \text{where } s_{\text{pooled}} = \sqrt{\frac{(N_c - 1)s_c^2 + (N_t - 1)s_t^2}{N_c + N_t - 2}}$$

An intervention is confirmed as statistically and practically significant only when:
1. Two-sided 95% confidence interval excludes zero ($[CI_{\text{lower}}, CI_{\text{upper}}] \cap \{0\} = \emptyset$).
2. Practical effect threshold is met ($|\Delta_{\text{relative}}| \ge 25\%$).
3. Absolute Welch t-statistic $|t| \ge 2.20$.

### 3.2 Discrete-Event Physics & Little's Law
Inside the Living Digital Twin, each service node implements physical queueing transitions:

$$L = \lambda \cdot W \quad \text{(Little's Law for active concurrency)}$$

$$Q_{t+1} = \max\left(0, \min\left(Q_{\max}, Q_t + (\lambda - \mu_{\text{eff}})\cdot \Delta t\right)\right)$$

Where:
- $\lambda$: request arrival rate (RPS) subject to Gaussian stochastic jitter.
- $\mu_{\text{eff}}$: effective service rate bounded by replica count $R$, concurrency limits $C$, and downstream dependency response times.
- Downstream database contention incorporates a quadratic contention penalty factor $k_{\text{contention}} \cdot R_{\text{checkout}}^2$ to accurately capture shared lock saturation.

---

## 4. Epistemic Role Blinding

In traditional observability benchmarks, algorithms often "cheat" by reading internal simulator flags. ORIGIN enforces **absolute epistemic blinding**:
- The synthetic microservice laboratory is hosted on an isolated Docker network (`origin_internal_net`).
- Internal fault parameters (e.g., `payment_added_latency_ms`) are strictly stripped before returning traces to the causal scientist.
- All hypothesis formulation and evidence evaluation operate exclusively on observable OpenTelemetry span durations, HTTP status codes, and metric distributions.
- Causal discovery benchmark tests (`test_full_hidden_fault_benchmark_matrix`) verify that the investigator isolates failure mechanisms without ever receiving ground-truth labels.
