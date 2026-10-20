# ORIGIN Autonomous Causal Scientist & Investigation Engine (`docs/CAUSAL_ENGINE.md`)

**Milestone:** 02/05 — Autonomous Causal Scientist & Experimental Discovery Engine  
**Primary Modules:**
- `backend/app/modules/agents/investigator.py` (`AutonomousInvestigatorService`)
- `backend/app/modules/evidence/hypothesis_engine.py` (`HypothesisEngine`)
- `backend/app/modules/agents/model_gateway.py` (`ModelGatewayProtocol`, `validate_candidate_proposal`)

---

## 1. Investigation Lifecycle State Machine

Every autonomous investigation in ORIGIN executes a deterministic, persisted state machine stored in PostgreSQL (`investigations` table) with full transition history (`lifecycle_history_json`) and reasoning step logs (`decision_history_json`):

```
CREATED → OBSERVING → HYPOTHESIZING → PLANNING → EXPERIMENTING → EVALUATING → CONCLUDED / INCONCLUSIVE / FAILED / CANCELLED
```

### Valid State Transitions (`VALID_LIFECYCLE_TRANSITIONS`)
| From State | Permitted Target States | Purpose |
| :--- | :--- | :--- |
| `CREATED` | `OBSERVING`, `CANCELLED`, `FAILED` | Initializes investigation budget, random seed, target service, and safety envelope. |
| `OBSERVING` | `HYPOTHESIZING`, `CONCLUDED`, `CANCELLED`, `FAILED` | Gathers live OpenTelemetry spans/metrics and provenance-verified topology. If target behavior is nominal ($\le 145\text{ ms}$), concludes healthy operation immediately without wasting experiment budget. |
| `HYPOTHESIZING` | `PLANNING`, `INCONCLUSIVE`, `CANCELLED`, `FAILED` | Synthesizes competing falsifiable causal hypotheses from observed downstream anomalies and topology reachability. |
| `PLANNING` | `EXPERIMENTING`, `CONCLUDED`, `INCONCLUSIVE`, `CANCELLED`, `FAILED` | Ranks untested hypotheses by information value and selects the next allowlisted intervention within the remaining `experiment_budget`. |
| `EXPERIMENTING` | `EVALUATING`, `CANCELLED`, `FAILED` | Executes a seeded, block-randomized controlled experiment comparing Control vs. Treatment trials in the isolated laboratory. |
| `EVALUATING` | `PLANNING`, `CONCLUDED`, `INCONCLUSIVE`, `CANCELLED`, `FAILED` | Evaluates Welch's two-sample t-test, 95% confidence interval, and Cohen's $d$; updates hypothesis support scores and either concludes or loops back to `PLANNING` if the hypothesis was refuted and budget remains. |

---

## 2. Deterministic Evidence-Driven Hypothesis Generation

ORIGIN does not rely on paid external LLMs or hallucinated confidence scores. By default, `HypothesisEngine.generate_competing_hypotheses` deterministically inspects:
1. **Provenance-Verified Topology (`TopologyService`)**: Identifies all downstream dependencies reachable from `target_service_key` (e.g., `checkout-service` $\rightarrow$ `payment-simulator`, `order-database-sim`, `inventory-service`).
2. **Stored Span & Metric Observations**: Compares observed p95 latency, error rate, and lock/CPU saturation against nominal reference baselines (`NOMINAL_SERVICE_LATENCY_MS`).

### Supported Causal Mechanisms
1. **`payment_gateway_latency_propagation`** (`payment-simulator` $\rightarrow$ `checkout-service`): Synchronous payment authorization blocking upstream checkout completion. Recommended intervention: `isolate_payment_fastpath`.
2. **`database_lock_contention`** (`order-database-sim` $\rightarrow$ `checkout-service`): Exclusive row-lock queuing on order persistence transactions. Recommended intervention: `relieve_db_lock_contention`.
3. **`inventory_worker_starvation`** (`inventory-service` $\rightarrow$ `checkout-service`): CPU worker pool exhaustion during stock reservation checks. Recommended intervention: `scale_inventory_workers`.
4. **`concurrency_queue_accumulation`** (`checkout-service` internal): Request concurrency saturation or multi-service cascading jitter. Recommended intervention: `hedged_concurrency_limiter`.

### Epistemic Prior Cap ($\le 0.65$)
Observational telemetry alone can never establish causal proof due to confounding from shared upstream traffic and cascading calls. Therefore:
- Every hypothesis generated during `HYPOTHESIZING` has its initial confidence score **strictly capped at $\le 0.65$** (`MAX_OBSERVATIONAL_PRIOR = 0.65`).
- Scores $> 0.65$ can **only** be achieved after a controlled intervention produces a statistically and practically significant latency reduction in `EVALUATING`.

---

## 3. Optional Constrained Model Gateway (`ModelGatewayProtocol`)

While ORIGIN's core causal engine is 100% deterministic, `backend/app/modules/agents/model_gateway.py` defines a strict protocol (`ModelGatewayProtocol`) for optional AI-assisted candidate hypothesis generation. Every candidate proposal must pass `validate_candidate_proposal(proposal, reachable_services)`:
- `root_cause_service_key` **must** exist in the observed/registered topology reachable set.
- `recommended_intervention` **must** belong to `ALLOWLISTED_INTERVENTIONS` and cannot be `"none"` or any shell/code string.
