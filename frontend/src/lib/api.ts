import type {
  AuditEventRead,
  BranchComparisonResponse,
  CalibrationRunRead,
  DependencyRead,
  DigitalTwinModelRead,
  EvidenceRead,
  ExperimentDefinitionRead,
  ExperimentRunRead,
  HypothesisRead,
  InvestigationCreatePayload,
  InvestigationDetailRead,
  InvestigationRead,
  LabExecutionResult,
  LabFaultState,
  LabProfileType,
  MetricPointRead,
  MetricSeriesSummary,
  ModuleBoundaryStatus,
  ScientificMemoryEntryRead,
  ServiceRead,
  SimulationBenchmarkSuiteResponse,
  SimulationBranchRead,
  SimulationSnapshotRead,
  SpanRead,
  SystemDetailRead,
  SystemRead,
  TopologyGraphResponse,
  TwinInterventionSpec,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`API ${response.status}: ${errText}`);
  }
  return (await response.json()) as T;
}

export async function fetchHealth(): Promise<{
  status: string;
  platform: string;
  tagline: string;
  milestone: string;
  database_connected: boolean;
  laboratory_profile: LabProfileType | "blinded_benchmark_mode";
}> {
  return apiFetch("/api/v1/health");
}

export async function fetchSystems(): Promise<SystemRead[]> {
  return apiFetch("/api/v1/systems");
}

export async function fetchSystemDetail(slugOrId: string): Promise<SystemDetailRead> {
  return apiFetch(`/api/v1/systems/${encodeURIComponent(slugOrId)}`);
}

export async function fetchSystemTopology(
  slugOrId: string
): Promise<TopologyGraphResponse> {
  return apiFetch(`/api/v1/systems/${encodeURIComponent(slugOrId)}/topology`);
}

export async function fetchMetricSeries(params: {
  systemId?: string;
  metricName?: string;
  serviceKey?: string;
  limit?: number;
}): Promise<MetricSeriesSummary> {
  const qs = new URLSearchParams();
  qs.set("system_id", params.systemId || "origin-synthetic-lab");
  qs.set("metric_name", params.metricName || "request_latency_ms");
  if (params.serviceKey) {
    qs.set("service_key", params.serviceKey);
  }
  if (params.limit) {
    qs.set("limit", String(params.limit));
  }
  return apiFetch(`/api/v1/telemetry/metrics?${qs.toString()}`);
}

export async function fetchRecentSpans(params: {
  systemId?: string;
  correlationId?: string;
  traceId?: string;
  serviceKey?: string;
  limit?: number;
}): Promise<SpanRead[]> {
  const qs = new URLSearchParams();
  qs.set("system_id", params.systemId || "origin-synthetic-lab");
  if (params.correlationId) qs.set("correlation_id", params.correlationId);
  if (params.traceId) qs.set("trace_id", params.traceId);
  if (params.serviceKey) qs.set("service_key", params.serviceKey);
  qs.set("limit", String(params.limit || 60));
  return apiFetch(`/api/v1/telemetry/spans?${qs.toString()}`);
}

export async function fetchLabStatus(): Promise<LabFaultState> {
  return apiFetch("/api/v1/lab/status");
}

export async function triggerLabWorkload(params: {
  iterations: number;
  profile: LabProfileType;
}): Promise<LabExecutionResult> {
  return apiFetch("/api/v1/lab/execute", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function registerServiceApi(
  systemSlug: string,
  payload: {
    service_key: string;
    display_name: string;
    service_type: string;
    tier: string;
    owner_team: string;
  }
): Promise<ServiceRead> {
  return apiFetch(`/api/v1/systems/${encodeURIComponent(systemSlug)}/services`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function registerDependencyApi(
  systemSlug: string,
  payload: {
    source_service_key: string;
    target_service_key: string;
    protocol: string;
  }
): Promise<DependencyRead> {
  return apiFetch(
    `/api/v1/systems/${encodeURIComponent(systemSlug)}/dependencies`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function fetchAuditEvents(
  systemId?: string
): Promise<AuditEventRead[]> {
  const qs = systemId ? `?system_id=${encodeURIComponent(systemId)}` : "";
  return apiFetch(`/api/v1/safety/audit-events${qs}`);
}

export async function fetchArchitectureModules(): Promise<{
  milestone: string;
  boundaries: ModuleBoundaryStatus[];
}> {
  return apiFetch("/api/v1/architecture/modules");
}

// ---------------------------------------------------------------------------
// Milestone 02/05: Autonomous Causal Scientist & Investigation API Client
// ---------------------------------------------------------------------------

export async function createInvestigation(
  payload: InvestigationCreatePayload
): Promise<InvestigationDetailRead> {
  return apiFetch("/api/v1/investigations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchInvestigations(
  systemId?: string
): Promise<InvestigationRead[]> {
  const qs = systemId ? `?system_id=${encodeURIComponent(systemId)}` : "";
  return apiFetch(`/api/v1/investigations${qs}`);
}

export async function fetchInvestigationDetail(
  investigationId: string
): Promise<InvestigationDetailRead> {
  return apiFetch(
    `/api/v1/investigations/${encodeURIComponent(investigationId)}`
  );
}

export async function startInvestigation(
  investigationId: string
): Promise<InvestigationDetailRead> {
  return apiFetch(
    `/api/v1/investigations/${encodeURIComponent(investigationId)}/start`,
    { method: "POST" }
  );
}

export async function cancelInvestigation(
  investigationId: string
): Promise<InvestigationRead> {
  return apiFetch(
    `/api/v1/investigations/${encodeURIComponent(investigationId)}/cancel`,
    { method: "POST" }
  );
}

export async function fetchInvestigationHypotheses(
  investigationId: string
): Promise<HypothesisRead[]> {
  return apiFetch(
    `/api/v1/investigations/${encodeURIComponent(investigationId)}/hypotheses`
  );
}

export async function fetchInvestigationExperiments(
  investigationId: string
): Promise<{
  investigation_id: string;
  experiment_plans: ExperimentDefinitionRead[];
  experiment_runs: ExperimentRunRead[];
}> {
  return apiFetch(
    `/api/v1/investigations/${encodeURIComponent(investigationId)}/experiments`
  );
}

export async function fetchInvestigationEvidence(
  investigationId: string
): Promise<EvidenceRead[]> {
  return apiFetch(
    `/api/v1/investigations/${encodeURIComponent(investigationId)}/evidence`
  );
}

export async function exportInvestigationReport(
  investigationId: string,
  format: "markdown" | "json" = "markdown"
): Promise<{
  investigation_id: string;
  status: string;
  markdown: string;
  report: Record<string, unknown>;
}> {
  return apiFetch(
    `/api/v1/investigations/${encodeURIComponent(
      investigationId
    )}/export?format=${format}`
  );
}

// ---------------------------------------------------------------------------
// Milestone 03/05: Living Digital Twin, Counterfactuals & Scientific Memory API
// ---------------------------------------------------------------------------

export async function calibrateDigitalTwin(payload: {
  system_slug?: string;
  investigation_id?: string;
  version_tag?: string;
  min_required_observations?: number;
  validation_split_ratio?: number;
  strict_rejection?: boolean;
}): Promise<{
  twin_model: DigitalTwinModelRead;
  calibration_run: CalibrationRunRead;
  epistemic_label: string;
}> {
  return apiFetch("/api/v1/twins/calibrate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchDigitalTwins(
  systemId?: string
): Promise<DigitalTwinModelRead[]> {
  const qs = systemId ? `?system_id=${encodeURIComponent(systemId)}` : "";
  return apiFetch(`/api/v1/twins${qs}`);
}

export async function fetchTwinCalibrations(
  twinModelId: string
): Promise<CalibrationRunRead[]> {
  return apiFetch(
    `/api/v1/twins/${encodeURIComponent(twinModelId)}/calibrations`
  );
}

export async function createSimulationSnapshot(payload: {
  twin_model_id: string;
  branch_id?: string;
  step_index?: number;
  label?: string;
  random_seed?: number;
}): Promise<SimulationSnapshotRead> {
  return apiFetch("/api/v1/simulations/snapshots", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchSimulationSnapshots(
  twinModelId?: string
): Promise<SimulationSnapshotRead[]> {
  const qs = twinModelId
    ? `?twin_model_id=${encodeURIComponent(twinModelId)}`
    : "";
  return apiFetch(`/api/v1/simulations/snapshots${qs}`);
}

export async function createSimulationBranch(payload: {
  twin_model_id: string;
  name: string;
  branch_type?: "baseline" | "counterfactual" | "hypothesis_test" | "benchmark";
  parent_branch_id?: string;
  initial_snapshot_id?: string;
  investigation_id?: string;
  hypothesis_id?: string;
  random_seed?: number;
  horizon_seconds?: number;
  dt_seconds?: number;
  incoming_traffic_rps?: number;
  monte_carlo_runs?: number;
  interventions?: TwinInterventionSpec[];
}): Promise<SimulationBranchRead> {
  return apiFetch("/api/v1/simulations/branches", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchSimulationBranches(
  twinModelId?: string
): Promise<SimulationBranchRead[]> {
  const qs = twinModelId
    ? `?twin_model_id=${encodeURIComponent(twinModelId)}`
    : "";
  return apiFetch(`/api/v1/simulations/branches${qs}`);
}

export async function compareSimulationBranches(
  baselineBranchId: string,
  alternativeBranchId: string
): Promise<BranchComparisonResponse> {
  return apiFetch(
    `/api/v1/simulations/compare?baseline_branch_id=${encodeURIComponent(
      baselineBranchId
    )}&alternative_branch_id=${encodeURIComponent(alternativeBranchId)}`
  );
}

export async function exportSimulationBranchReport(
  branchId: string,
  compareWithBranchId?: string,
  format: "markdown" | "json" = "markdown"
): Promise<{
  branch_id: string;
  format: string;
  markdown: string;
  report: Record<string, unknown>;
}> {
  const compareQs = compareWithBranchId
    ? `&compare_with_branch_id=${encodeURIComponent(compareWithBranchId)}`
    : "";
  return apiFetch(
    `/api/v1/simulations/branches/${encodeURIComponent(
      branchId
    )}/export?format=${format}${compareQs}`
  );
}

export async function runDigitalTwinBenchmarks(
  randomSeed = 2026
): Promise<SimulationBenchmarkSuiteResponse> {
  return apiFetch(`/api/v1/simulations/benchmarks/run?random_seed=${randomSeed}`, {
    method: "POST",
  });
}

export async function fetchScientificMemory(
  epistemicKind?: string
): Promise<ScientificMemoryEntryRead[]> {
  const qs = epistemicKind
    ? `?epistemic_kind=${encodeURIComponent(epistemicKind)}`
    : "";
  return apiFetch(`/api/v1/memory/entries${qs}`);
}

export function formatProvenanceBadge(
  source: "registered" | "observed" | "registered_and_observed"
): { label: string; badgeClass: string; description: string } {
  switch (source) {
    case "registered_and_observed":
      return {
        label: "VERIFIED (REG + OBS)",
        badgeClass:
          "bg-navy-900 text-ivory-50 border-navy-900",
        description:
          "Explicitly declared in registry and confirmed by live OpenTelemetry spans.",
      };
    case "observed":
      return {
        label: "OBSERVED ONLY",
        badgeClass:
          "bg-emerald-50 text-emerald-900 border-emerald-300",
        description:
          "Discovered directly from parent->child span observations without prior declaration.",
      };
    case "registered":
      return {
        label: "DECLARED ONLY",
        badgeClass:
          "bg-slate-100 text-slate-700 border-slate-300",
        description:
          "Declared in system registry, awaiting confirmation from live span telemetry.",
      };
  }
}

export function formatHypothesisStatusBadge(
  status: "proposed" | "testing" | "supported" | "refuted" | "inconclusive"
): { label: string; badgeClass: string } {
  switch (status) {
    case "supported":
      return {
        label: "SUPPORTED BY INTERVENTION",
        badgeClass: "bg-emerald-50 text-emerald-900 border-emerald-300",
      };
    case "refuted":
      return {
        label: "REFUTED BY INTERVENTION",
        badgeClass: "bg-rose-50 text-rose-900 border-rose-300",
      };
    case "testing":
      return {
        label: "UNDER EXPERIMENTATION",
        badgeClass: "bg-amber-50 text-amber-900 border-amber-300",
      };
    case "inconclusive":
      return {
        label: "INCONCLUSIVE EVIDENCE",
        badgeClass: "bg-slate-100 text-slate-700 border-slate-300",
      };
    default:
      return {
        label: "OBSERVATIONAL CANDIDATE",
        badgeClass: "bg-[#F3EFEA] text-[#0F1E36] border-[#E4DFD7]",
      };
  }
}

export function groupMetricPointsByTimestamp(
  points: MetricPointRead[]
): Array<Record<string, string | number>> {
  const buckets = new Map<string, Record<string, string | number>>();
  for (const pt of points) {
    const timeLabel = new Date(pt.observed_at).toLocaleTimeString([], {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    const key = `${pt.correlation_id || pt.id.slice(0, 6)}-${timeLabel}`;
    const existing = buckets.get(key) || { time: timeLabel, correlationId: pt.correlation_id || "" };
    existing[pt.service_key] = pt.value;
    buckets.set(key, existing);
  }
  return Array.from(buckets.values()).slice(-30);
}
