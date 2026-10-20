export type LabProfileType = "normal" | "payment_latency_spike" | "db_lock_contention";

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
  profile: LabProfileType;
  payment_added_latency_ms: number;
  payment_failure_probability: number;
  db_added_latency_ms: number;
  db_lock_saturation_pct: number;
  updated_at: string;
}

export interface LabTransactionTraceSummary {
  correlation_id: string;
  trace_id: string;
  profile: LabProfileType;
  gateway_status: number;
  total_duration_ms: number;
  services_traversed: string[];
  spans_emitted: number;
  metrics_emitted: number;
}

export interface LabExecutionResult {
  system_slug: string;
  execution_mode: string;
  active_profile: LabProfileType;
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
