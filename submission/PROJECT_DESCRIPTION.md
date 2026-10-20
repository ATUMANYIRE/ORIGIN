# ORIGIN — Autonomous Scientific Intelligence for Software Systems

> **Product Tagline:** *Give software the ability to understand itself.*  
> **Target Event:** HackOctober MLH × Tech4hack  
> **Repository:** [https://github.com/ATUMANYIRE/ORIGIN](https://github.com/ATUMANYIRE/ORIGIN)  
> **Submission Date:** October 20, 2026  

---

## 1. Elevator Pitch

Modern distributed architectures are too complex for humans to diagnose during catastrophic cascade failures. Existing observability tools are **passive recorders**: they generate dashboards, alerts, and correlation charts, but leave engineers guessing at the true root cause. 

**ORIGIN** is the world's first **autonomous scientific intelligence platform for software systems**. Rather than merely charting symptoms or relying on speculative LLM hallucinations, ORIGIN treats a distributed software system as an **empirical physical environment**:
1. It formulates grounded refutable hypotheses from live OpenTelemetry traces.
2. It executes controlled two-arm randomized intervention experiments to isolate hidden causal mechanisms using Welch's t-test and Cohen's d effect sizes.
3. It calibrates a discrete-event **Living Digital Twin** against held-out telemetry to explore counterfactual "what-if" futures.
4. It pre-verifies remediation workflows in an isolated sandbox clone before requesting human approval via cryptographic dual-authorization.
5. It commits every observation, experiment trial, and decision to a cryptographically tamper-evident **Scientific Evidence Ledger**.

---

## 2. Inspiration: Why We Built ORIGIN

Every senior engineer and SRE knows the horror of 3:00 AM production outages:
- A downstream database connection pool saturates.
- Upstream retry storms amplify traffic by 400%.
- Latency spikes cascade through the API gateway.
- Ten different dashboards flash red simultaneously.

In this fog of war, teams spend hours treating symptoms—restarting nodes that immediately fail again, scaling services that only increase lock contention, and arguing over correlations.

We asked a fundamental question: **What if software had the scientific method built into its runtime?**

Science does not uncover the laws of nature through passive observation alone; science relies on **controlled intervention, counterfactual reasoning, and reproducible falsification**. We set out to give distributed software systems the ability to observe themselves, hypothesize causal failure models, conduct blinded micro-experiments, simulate counterfactual alternative realities, and safely heal themselves with human-in-the-loop oversight.

---

## 3. What ORIGIN Does: The Five Pillars

### Pillar I — Living System Intelligence & Provenance Topology
ORIGIN continuously ingests OpenTelemetry distributed traces and metrics (sustained at **40,387 spans/sec**). Unlike static service maps that rely on manual configuration, ORIGIN's topology engine constructs strict causal dependency graphs with cryptographic hash provenance.

### Pillar II — Autonomous Causal Scientist
When an incident is detected, ORIGIN initiates a scientific investigation:
- Formulates grounded candidate hypotheses tied directly to observed trace anomalies.
- Designs a paired block-randomized experiment plan (treatment vs. control) to neutralize temporal drift bias.
- Executes controlled allowlisted interventions (e.g., circuit breaker trips, query cache bypass, traffic shedding).
- Computes Welch's unequal variances t-test, Welch-Satterthwaite degrees of freedom, and Cohen's d effect sizes.
- Reaches honest conclusions: supported, refuted, or **inconclusive** if empirical data is ambiguous.

### Pillar III — Epistemically Blinded Benchmark Evaluation
To prove ORIGIN does not cheat, we built a 5-service synthetic laboratory with **epistemic role blinding**. The investigator service has zero access to internal fault parameters or injection keys. In blinded benchmarks across four difficult distributed failure modes (Cascading Threadpool Exhaustion, Downstream Connection Leaks, Contended Database Locks, and Upstream Retry Storms), ORIGIN achieves **100% causal identification accuracy** while honestly returning `INCONCLUSIVE` on unidentifiable noise.

### Pillar IV — Living Digital Twin & Counterfactual Intelligence
Before executing any remediation in production, ORIGIN calibrates a dynamic discrete-event Digital Twin against held-out telemetry (75% train / 25% test split). It supports:
- **Deterministic Replay & Snapshot Rewind**: Bit-for-bit reproducible event sequences.
- **Parallel Counterfactual Branching**: Simulates what *would* happen if traffic is shed vs. if replicas are scaled.
- **Monte Carlo Uncertainty Bounds**: Generates explicit 95% predictive confidence intervals rather than single-point guesses.

### Pillar V — Verified Autonomous Recovery & Cryptographic Governance
Remediation plans generated from causal findings undergo multi-stage safety gating:
1. **Allowlist Policy Check**: Rejects unapproved or dangerous operational actions.
2. **Sandbox Validation**: Proves recovery in an isolated sandbox clone before touching production.
3. **Dual-Token Human Approval**: High-impact interventions require dual-operator cryptographic signature approval.
4. **Automatic Rollback & Audit**: If SLA metrics degrade post-execution, ORIGIN immediately rolls back to the known-safe baseline snapshot and records the full incident trace in the PostgreSQL `audit_events` ledger.

---

## 4. How We Built It (System Architecture)

- **Backend:** Python 3.12, FastAPI, Pydantic v2 strict schemas, SQLAlchemy 2 async ORM, Alembic migrations.
- **Data & Coordination:** PostgreSQL 16 (SCRAM-SHA-256 persistent telemetry and audit ledger), Redis 7 (AOF persistence, pub/sub coordination, distributed locks).
- **Synthetic Microservice Lab:** 5 interdependent services (`api-gateway`, `checkout-service`, `inventory-service`, `payment-simulator`, `order-database-sim`) with realistic Little's Law queue dynamics and fault injection hooks.
- **Frontend Product Interface:** Next.js 15.1.6 (App Router, React 19, TypeScript strict), Tailwind CSS (editorial warm-white palette), React Flow (interactive causal topology), Recharts (operational metrics).
- **Telemetry & Protocols:** OpenTelemetry OTLP/HTTP JSON streaming, real-time Server-Sent Events (SSE) with unbuffered proxying.
- **Verification & QA:** Pytest (30 comprehensive scientific tests), Vitest (frontend unit suite), Playwright (end-to-end browser workflows in Chromium), Ruff linter, Mypy static type checker (0 errors across 50 source files).
- **Deployment & Gateway:** Docker Compose production orchestration, Nginx reverse proxy with SSL termination and 50 req/sec rate limiting.

---

## 5. Quantitative Verification & Benchmark Results

Every metric displayed in ORIGIN originates from genuine instrumentation:

- **Telemetry Ingestion Throughput:** **40,387 spans/second** (p50: 0.297 ms).
- **Digital Twin Simulation Speed:** **11,985 service evaluations/second** (2,397 steps/s across 5 services, p50: 11.058 ms).
- **Monte Carlo Predictive Calibration:** **95.4 trajectories/second** with empirical 95% CI convergence.
- **Causal Statistical Inference Engine:** **768.8 comparisons/second** (80,000 observations analyzed; p50: 0.526 ms).
- **Safety Boundary Fault Containment:** **17,202.6 checks/second** (100% malformed payloads quarantined).
- **Full Acceptance Suite:** 8/8 phases passed in 4m 22s (`scripts/verify-all.ps1`).

---

## 6. Challenges We Overcame

1. **Temporal Drift in Distributed Micro-Experiments:** If system load changes during an investigation, sequential AB testing misattributes the effect. We solved this by developing a seeded **paired block-randomization scheduler** that interleaves control and treatment trials, eliminating temporal confounding.
2. **Preventing LLM Hallucinations in Root Cause Diagnosis:** Language models frequently guess plausible-sounding explanations that are factually wrong. In ORIGIN, candidate proposals generated by models are strictly validated against the discovered topological graph and cannot conclude a root cause without empirical statistical confirmation (Cohen's d >= 0.5, p < 0.05).
3. **Discrete-Event Simulation Realism:** Modeling distributed systems requires accurately capturing queue backpressure, Little's Law concurrency bounds ($L = \lambda W$), and cascading timeout dynamics. We implemented a complete discrete-event simulator with deterministic snapshot capture and microsecond-level clock rewind.

---

## 7. What's Next for ORIGIN

- **Multi-Cloud Distributed Mesh Ingestion:** Native eBPF probe collectors for kernel-level TCP queue inspection.
- **Continuous Bayesian Model Updating:** Online belief updates using particle filtering over streaming metrics.
- **Automated Chaos Experimentation Schedules:** Proactive scientific probing during off-peak hours to identify latent bottlenecks before they cause outages.

---

## 8. Links & Deliverables

- **GitHub Repository:** [https://github.com/ATUMANYIRE/ORIGIN](https://github.com/ATUMANYIRE/ORIGIN)
- **Live Demo & Interactive Walkthrough:** Available locally via `docker compose -f docker-compose.prod.yml up` or through the interactive `/demo` guided page.
- **Full Traceability Matrix:** [docs/TRACEABILITY_MATRIX.md](file:///E:/Projects/ORIGIN/docs/TRACEABILITY_MATRIX.md)
- **Performance & Resilience Report:** [docs/PERFORMANCE_AND_RESILIENCE.md](file:///E:/Projects/ORIGIN/docs/PERFORMANCE_AND_RESILIENCE.md)
- **Video Walkthrough Script:** [submission/DEMO_SCRIPT.md](file:///E:/Projects/ORIGIN/submission/DEMO_SCRIPT.md)
