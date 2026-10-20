# ORIGIN — Persistent Scientific Memory (`Milestone 03/05`)

## 1. Institutional Scientific Memory
The `scientific_memory_entries` table (`ScientificMemoryEntryRecord`) stores structured, provenance-linked scientific records across sessions so ORIGIN accumulates institutional knowledge over time.

Every memory entry carries a mandatory `epistemic_kind` classification:
1. `historical_observation` — Direct telemetry and observational evidence from investigations.
2. `experimental_evidence` — Controlled randomized A/B experiment results with Welch's $t$-test and Cohen's $d$.
3. `calibrated_model` — Versioned Digital Twin models with held-out validation `MAE`, `RMSE`, and `NRMSE`.
4. `counterfactual_prediction` — Simulated counterfactual branch outcomes and uncertainty intervals.
5. `prediction_validation` — Comparisons between simulated counterfactual predictions and empirical investigation findings (`POST /api/v1/investigations/{id}/simulate`).

---

## 2. Triple Epistemic Disclosure in Causal + Twin Integration
When an operator or investigator calls `POST /api/v1/investigations/{investigation_id}/simulate`, the response explicitly separates:
- `observed_evidence` (`epistemic_status: "historical_observation"`)
- `experimental_evidence` (`epistemic_status: "experimental_evidence"`)
- `simulated_prediction` (`epistemic_status: "counterfactual_prediction"`)

Furthermore, simulating a hypothesis **never** mutates or appends synthetic predictions into the investigation's empirical `evidence_records` ledger.
