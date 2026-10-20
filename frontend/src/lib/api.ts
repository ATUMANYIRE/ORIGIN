import type {
  AuditEventRead,
  DependencyRead,
  LabExecutionResult,
  LabFaultState,
  LabProfileType,
  MetricPointRead,
  MetricSeriesSummary,
  ModuleBoundaryStatus,
  ServiceRead,
  SpanRead,
  SystemDetailRead,
  SystemRead,
  TopologyGraphResponse,
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
  laboratory_profile: LabProfileType;
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
