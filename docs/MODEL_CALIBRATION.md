# ORIGIN — Evidence-Based Model Calibration (`Milestone 03/05`)

## 1. Calibration Methodology
Implemented in [`TwinCalibrationEngine`](../backend/app/modules/simulation/calibration.py), calibration estimates Digital Twin parameters from stored OpenTelemetry `SpanObservation`, `MetricObservation`, and `ExperimentRun` records.

### Step 1: Minimum Data Sufficiency Check
- Before estimating parameters, the engine verifies `total_span_count >= min_required_observations` and at least 2 distinct multi-service transaction `correlation_id` groups.
- When `strict_rejection=True` and data is insufficient, the API rejects calibration with `HTTP 422 Unprocessable Content`. When `strict_rejection=False`, the model is marked `rejected_insufficient_data` with explicit warnings.

### Step 2: Strict Train (75%) vs. Held-Out Validation (25%) Split
- Recent transaction correlation groups are partitioned into a **Training Set** (`train_correlation_ids_json`) and a **Held-Out Validation Set** (`validation_correlation_ids_json`).
- Validation traces are **never** used during parameter estimation.

### Step 3: Intrinsic Latency Decomposition & Uncertainty Estimation
- For each service in the training traces, child span durations are subtracted from parent span durations to isolate intrinsic service latency:
  $$L_{\text{intrinsic}, i} = \max\left(3.0\text{ ms}, \, L_{\text{total}, i} - \sum_{j \in \text{children}(i)} L_{\text{total}, j}\right)$$
- Sample mean, sample standard deviation, standard error ($SE = s / \sqrt{n}$), and 95% confidence bounds ($\bar{x} \pm 1.96 \cdot SE$) are persisted in `parameter_uncertainty_json`.
- For `order-database-sim`, elevated intrinsic latency ($> 80\text{ ms}$) or saturation ($> 65\%$) calibrates `db_lock_contention_factor` and `db_connection_capacity`.

### Step 4: Held-Out Validation Metrics
- The calibrated Digital Twin is simulated and compared against the held-out validation traces per service, computing:
  - **Mean Absolute Error (`mae_ms`)**
  - **Root Mean Squared Error (`rmse_ms`)**
  - **Normalized Root Mean Squared Error (`normalized_error_pct`)**
  - **Per-Service Residuals (`residuals_json`)**
