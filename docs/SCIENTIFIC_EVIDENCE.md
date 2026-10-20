# ORIGIN Statistical Evaluation & Scientific Evidence (`docs/SCIENTIFIC_EVIDENCE.md`)

**Milestone:** 02/05 — Autonomous Causal Scientist & Experimental Discovery Engine  
**Primary Modules:**
- `backend/app/modules/experimentation/engine.py` (`compute_experiment_statistics`)
- `backend/app/modules/evidence/hypothesis_engine.py` (`HypothesisEngine.evaluate_experiment_outcome`)

---

## 1. Statistical Comparison Methodology

Every completed `ExperimentRun` computes a rigorous two-sample comparison between the Control arm ($C = \{c_1, \dots, c_{n_c}\}$) and Treatment arm ($T = \{t_1, \dots, t_{n_t}\}$) using pure mathematical formulas in `compute_experiment_statistics`:

1. **Sample Means, Medians, and Standard Deviations**:
   $$\bar{y}_C = \frac{1}{n_c}\sum_{i=1}^{n_c} c_i, \quad \bar{y}_T = \frac{1}{n_t}\sum_{j=1}^{n_t} t_j$$
   $$s_C = \sqrt{\frac{1}{n_c - 1}\sum_{i=1}^{n_c}(c_i - \bar{y}_C)^2}, \quad s_T = \sqrt{\frac{1}{n_t - 1}\sum_{j=1}^{n_t}(t_j - \bar{y}_T)^2}$$

2. **Absolute and Relative Effect Sizes**:
   $$\Delta_{\text{abs}} = \bar{y}_T - \bar{y}_C \text{ (ms)}, \quad \Delta_{\text{rel}} = \frac{\bar{y}_T - \bar{y}_C}{\bar{y}_C} \times 100\%$$

3. **Welch's Two-Sample $t$-Statistic & Welch–Satterthwaite Degrees of Freedom**:
   $$\text{SE} = \sqrt{\frac{s_T^2}{n_t} + \frac{s_C^2}{n_c}}, \quad t = \frac{\Delta_{\text{abs}}}{\text{SE}}$$
   $$\nu = \frac{\left(\frac{s_T^2}{n_t} + \frac{s_C^2}{n_c}\right)^2}{\frac{(s_T^2 / n_t)^2}{n_t - 1} + \frac{(s_C^2 / n_c)^2}{n_c - 1}}$$

4. **95% Confidence Interval for $\Delta_{\text{abs}}$**:
   $$\text{CI}_{95\%} = \left[\Delta_{\text{abs}} - t_{0.975, \nu}\cdot\text{SE}, \; \Delta_{\text{abs}} + t_{0.975, \nu}\cdot\text{SE}\right]$$

5. **Standardized Effect Size (Cohen's $d$)**:
   $$s_{\text{pooled}} = \sqrt{\frac{(n_c - 1)s_C^2 + (n_t - 1)s_T^2}{n_c + n_t - 2}}, \quad d = \frac{\Delta_{\text{abs}}}{s_{\text{pooled}}}$$

---

## 2. Joint Statistical & Practical Significance Thresholds

To prevent overclaiming causality from minor random fluctuations, an experiment is classified as supporting a causal hypothesis (`status = "supported"`) **if and only if all four criteria hold**:
1. `is_statistically_significant == True` ($|t| \ge 2.20$ and the 95% CI excludes $[-20\text{ ms}, +20\text{ ms}]$).
2. Relative latency reduction is at least `min_expected_reduction_pct` ($\ge 25\%$ reduction in `checkout-service` latency).
3. The upper bound of the 95% confidence interval (`ci_upper_95_ms`) is $< -25.0\text{ ms}$.
4. Standardized effect magnitude $|d| \ge 1.0$.

### Outcome Classification
- **`supported`**: All statistical and practical criteria are met. Posterior empirical support score is updated into $[0.82, 0.98]$ based on effect magnitude.
- **`refuted`**: Relative latency reduction is $< 15\%$ or `ci_upper_95_ms >= 0.0` (degradation persisted despite the intervention). Posterior score drops to $\max(0.05, 0.22 \times \text{prior})$, and the investigator moves to the next competing hypothesis if budget permits.
- **`inconclusive`**: Partial effect observed ($15\% \le \text{reduction} < 35\%$ or wide confidence interval under high variance such as `noisy_ambiguous_jitter`). Posterior score is capped at $\le 0.49$, and the investigation terminates honestly as `INCONCLUSIVE` rather than fabricating a root-cause claim.

---

## 3. Immutable Evidence Ledger (`evidence_records`)

Every observational correlation and every controlled experiment produces an immutable `EvidenceRecord` row in PostgreSQL linking:
- `investigation_id`, `hypothesis_id`, and `experiment_run_id`
- `evidence_type` (`"observational_correlation"` vs. `"controlled_experiment"`)
- `direction` (`"supporting"`, `"contradicting"`, `"inconclusive"`)
- `effect_size`, `ci_lower`, `ci_upper`, `sample_size`, and `correlation_id`
- Full `artifact_payload_json` containing all raw trial correlation IDs and statistical parameters.
