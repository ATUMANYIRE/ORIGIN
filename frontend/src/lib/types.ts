export type LabProfileType =
  | "normal"
  | "payment_latency_spike"
  | "db_lock_contention"
  | "inventory_cpu_throttling"
  | "noisy_ambiguous_jitter";

export type InvestigationStatusType =
  | "CREATED"
  | "OBSERVING"
  | "HYPOTHESIZING"
  | "PLANNING"
  | "EXPERIMENTING"
  | "EVALUATING"
  | "CONCLUDED"
  | "INCONCLUSIVE"
  | "FAILED"
  | "CANCELLED";

export interface SystemSummaryStats {
  service_count: number;
  dependency_count: number;
  observed_dependency_count: number;
  metric_observation_count: number;
  span_observation_count: number;
  telemetry_source_count: number;
  healthy_service_count: number;
  degraded_service_count: number;
}

export interface SystemRead {
  id: string;
  slug: string;
  name: string;
  environment: string;
  description: string;
  is_synthetic_lab: boolean;
  status: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  stats: SystemSummaryStats | null;
}

export interface ServiceRead {
  id: string;
  system_id: string;
  service_key: string;
  display_name: string;
  service_type: string;
  tier: string;
  owner_team: string;
  registration_source: "registered" | "observed" | "registered_and_observed";
  health_status: "healthy" | "degraded" | "critical" | "unknown";
  metadata_json: Record<string, unknown>;
  last_seen_at: string | null;
  created_at: string;
}

export interface DependencyRead {
  id: string;
  system_id: string;
  source_service_key: string;
  target_service_key: string;
  protocol: string;
  discovery_source: "registered" | "observed" | "registered_and_observed";
  observation_count: number;
  error_count: number;
  last_latency_ms: number | null;
  last_observed_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface TelemetrySourceRead {
  id: string;
  system_id: string;
  source_name: string;
  exporter_protocol: string;
  sdk_version: string;
  is_synthetic: boolean;
  total_batches_ingested: number;
  last_ingested_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface SystemDetailRead extends SystemRead {
  services: ServiceRead[];
  dependencies: DependencyRead[];
  telemetry_sources: TelemetrySourceRead[];
}

export interface TopologyNodeMetrics {
  observed_span_count: number;
  mean_latency_ms: number | null;
  p95_latency_ms: number | null;
  error_rate_pct: number;
  saturation_pct: number | null;
}

export interface TopologyNode {
  id: string;
  service_key: string;
  display_name: string;
  service_type: string;
  tier: string;
  owner_team: string;
  registration_source: "registered" | "observed" | "registered_and_observed";
  health_status: "healthy" | "degraded" | "critical" | "unknown";
  position_x: number;
  position_y: number;
  last_seen_at: string | null;
  metrics: TopologyNodeMetrics;
  metadata_json: Record<string, unknown>;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  protocol: string;
  discovery_source: "registered" | "observed" | "registered_and_observed";
  verified_by_observation: boolean;
  observation_count: number;
  error_count: number;
  error_rate_pct: number;
  last_latency_ms: number | null;
  last_observed_at: string | null;
}

export interface TopologyGraphResponse {
  system_id: string;
  system_slug: string;
  system_name: string;
  is_synthetic_lab: boolean;
  generated_at: string;
  total_nodes: number;
  total_edges: number;
  registered_only_edges: number;
  observed_only_edges: number;
  verified_edges: number;
  provenance_notice: string;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface MetricPointRead {
  id: string;
  system_id: string;
  service_key: string;
  metric_name: string;
  metric_unit: string;
  value: number;
  correlation_id: string | null;
  trace_id: string | null;
  is_synthetic: boolean;
  attributes_json: Record<string, unknown>;
  observed_at: string;
}

export interface MetricSeriesSummary {
  system_id: string;
  service_key: string | null;
  metric_name: string;
  metric_unit: string;
  sample_count: number;
  min_value: number | null;
  max_value: number | null;
  mean_value: number | null;
  p95_value: number | null;
  latest_value: number | null;
  points: MetricPointRead[];
}

export interface SpanRead {
  id: string;
  system_id: string;
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  correlation_id: string;
  service_key: string;
  parent_service_key: string | null;
  operation_name: string;
  span_kind: string;
  status_code: string;
  http_status: number;
  duration_ms: number;
  is_synthetic: boolean;
  attributes_json: Record<string, unknown>;
  started_at: string;
}

export interface LabFaultState {
  profile: LabProfileType | "blinded_benchmark_mode";
  blinded: boolean;
  payment_added_latency_ms: number | null;
  payment_failure_probability: number | null;
  db_added_latency_ms: number | null;
  db_lock_saturation_pct: number | null;
  inventory_cpu_latency_ms?: number | null;
  inventory_cpu_saturation_pct?: number | null;
  updated_at: string;
}

export interface LabTransactionTraceSummary {
  correlation_id: string;
  trace_id: string;
  profile: string;
  intervention?: string;
  experiment_arm?: string;
  gateway_status: number;
  total_duration_ms: number;
  services_traversed: string[];
  service_latencies_ms?: Record<string, number>;
  spans_emitted: number;
  metrics_emitted: number;
}

export interface LabExecutionResult {
  system_slug: string;
  execution_mode: string;
  active_profile: LabProfileType | "blinded_benchmark_mode";
  active_intervention?: string;
  transactions_executed: number;
  total_spans_ingested: number;
  total_metrics_ingested: number;
  traces: LabTransactionTraceSummary[];
}

export interface AuditEventRead {
  id: string;
  system_id: string | null;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  severity: string;
  correlation_id: string | null;
  details_json: Record<string, unknown>;
  created_at: string;
}

export interface ModuleBoundaryStatus {
  boundary_number: number;
  module: string;
  status: string;
  target_milestone?: string;
  capabilities?: string[];
  database_tables_provisioned?: string[];
  execution_enabled?: boolean;
  notice?: string;
}

// ---------------------------------------------------------------------------
// Milestone 02/05: Autonomous Causal Scientist & Experimental Discovery Types
// ---------------------------------------------------------------------------

export interface ObservationReference {
  service_key: string;
  metric_name: string;
  observed_value: number;
  baseline_reference: number;
  unit: string;
  correlation_ids: string[];
  note: string;
}

export interface ExpectedInterventionEffect {
  intervention_type: string;
  target_service_key: string;
  target_metric: string;
  expected_direction: string;
  min_expected_reduction_pct: number;
  rationale: string;
}

export interface HypothesisRevisionEntry {
  timestamp: string;
  phase?: string;
  experiment_run_id?: string;
  score?: number;
  prior_score?: number;
  posterior_score?: number;
  status: string;
  reason?: string;
}

export interface HypothesisRead {
  id: string;
  system_id: string;
  investigation_id: string | null;
  statement: string;
  suspected_mechanism: string;
  root_cause_service_key: string | null;
  affected_service_key: string | null;
  target_metric: string;
  recommended_intervention: string;
  supporting_observations_json: ObservationReference[];
  contradicting_observations_json: ObservationReference[];
  expected_intervention_effect_json: ExpectedInterventionEffect;
  alternative_explanations_json: string[];
  confidence_score: number;
  score_interpretation: string;
  status: "proposed" | "testing" | "supported" | "refuted" | "inconclusive";
  revision_history_json: HypothesisRevisionEntry[];
  created_at: string;
}

export interface TrialObservation {
  trial_index: number;
  arm: "control" | "treatment";
  intervention: string;
  correlation_id: string;
  trace_id: string;
  target_service_key: string;
  target_metric_value_ms: number;
  focal_service_key: string;
  focal_service_latency_ms: number;
  gateway_status: number;
  observed_at: string;
}

export interface StatisticalComparison {
  measurement_unit: string;
  control_n: number;
  treatment_n: number;
  control_mean_ms: number;
  control_median_ms: number;
  control_std_ms: number;
  treatment_mean_ms: number;
  treatment_median_ms: number;
  treatment_std_ms: number;
  absolute_effect_size_ms: number;
  median_effect_size_ms: number;
  relative_effect_pct: number;
  standard_error_ms: number;
  welch_t_stat: number;
  degrees_of_freedom: number;
  ci_lower_95_ms: number;
  ci_upper_95_ms: number;
  cohens_d: number;
  is_statistically_significant: boolean;
  trial_correlation_ids: string[];
  methodology_note: string;
}

export interface ExperimentDefinitionRead {
  id: string;
  system_id: string;
  investigation_id: string | null;
  hypothesis_id: string | null;
  name: string;
  target_service_key: string;
  target_metric: string;
  measurement_unit: string;
  perturbation_type: string;
  treatment_condition_json: Record<string, unknown>;
  control_condition_json: Record<string, unknown>;
  sample_size_per_arm: number;
  random_seed: number;
  budget_cost: number;
  selection_score: number;
  selection_reason: string;
  safety_envelope_json: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface ExperimentRunRead {
  id: string;
  experiment_id: string;
  system_id: string;
  investigation_id: string | null;
  hypothesis_id: string | null;
  status: string;
  AbortReason: string | null;
  assignment_order_json: string[];
  trial_observations_json: TrialObservation[];
  metrics_summary_json: StatisticalComparison;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface EvidenceRead {
  id: string;
  system_id: string;
  investigation_id: string | null;
  experiment_run_id: string | null;
  hypothesis_id: string | null;
  evidence_type: string;
  direction: "supporting" | "contradicting" | "inconclusive";
  summary: string;
  correlation_id: string | null;
  effect_size: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  sample_size: number;
  artifact_payload_json: Record<string, unknown>;
  created_at: string;
}

export interface LifecycleHistoryEntry {
  from_state: string | null;
  to_state: InvestigationStatusType;
  timestamp: string;
  actor: string;
  note: string;
}

export interface DecisionHistoryEntry {
  step: number;
  timestamp: string;
  phase: string;
  selected_hypothesis_id?: string;
  selected_intervention?: string;
  rationale: string;
  outcome?: string;
  effect_size_ms?: number;
  relative_effect_pct?: number;
}

export interface InvestigationRead {
  id: string;
  system_id: string;
  title: string;
  target_service_key: string;
  target_metric: string;
  status: InvestigationStatusType;
  experiment_budget: number;
  experiments_used: number;
  sample_size_per_arm: number;
  random_seed: number;
  timeout_seconds: number;
  cancel_requested: boolean;
  concluded_cause_service_key: string | null;
  concluded_mechanism: string | null;
  conclusion_summary: string | null;
  uncertainty_summary: string | null;
  failure_reason: string | null;
  baseline_summary_json: Record<string, unknown>;
  lifecycle_history_json: LifecycleHistoryEntry[];
  decision_history_json: DecisionHistoryEntry[];
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestigationDetailRead extends InvestigationRead {
  hypotheses: HypothesisRead[];
  experiment_plans: ExperimentDefinitionRead[];
  experiment_runs: ExperimentRunRead[];
  evidence_records: EvidenceRead[];
}

export interface InvestigationCreatePayload {
  system_slug?: string;
  title?: string;
  target_service_key?: string;
  target_metric?: string;
  experiment_budget?: number;
  sample_size_per_arm?: number;
  random_seed?: number;
  timeout_seconds?: number;
  auto_run?: boolean;
}
