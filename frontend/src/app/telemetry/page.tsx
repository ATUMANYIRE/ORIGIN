"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Activity, Filter, RefreshCw, Search } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import {
  fetchMetricSeries,
  fetchRecentSpans,
  groupMetricPointsByTimestamp,
} from "@/lib/api";
import type { MetricSeriesSummary, SpanRead } from "@/lib/types";

const SERVICE_COLORS: Record<string, string> = {
  "api-gateway": "#0F1E36",
  "checkout-service": "#2563EB",
  "inventory-service": "#059669",
  "payment-simulator": "#D97706",
  "order-database-sim": "#9333EA",
};

export default function TelemetryWorkspacePage() {
  const [selectedMetric, setSelectedMetric] = useState<string>(
    "request_latency_ms"
  );
  const [selectedService, setSelectedService] = useState<string>("");
  const [correlationFilter, setCorrelationFilter] = useState<string>("");
  const [metricSummary, setMetricSummary] =
    useState<MetricSeriesSummary | null>(null);
  const [spans, setSpans] = useState<SpanRead[]>([]);

  const loadTelemetry = useCallback(async () => {
    try {
      const [mData, sData] = await Promise.all([
        fetchMetricSeries({
          systemId: "origin-synthetic-lab",
          metricName: selectedMetric,
          serviceKey: selectedService || undefined,
          limit: 150,
        }),
        fetchRecentSpans({
          systemId: "origin-synthetic-lab",
          correlationId: correlationFilter.trim() || undefined,
          serviceKey: selectedService || undefined,
          limit: 80,
        }),
      ]);
      setMetricSummary(mData);
      setSpans(sData);
    } catch {
      // ignore initial offline
    }
  }, [selectedMetric, selectedService, correlationFilter]);

  useEffect(() => {
    void loadTelemetry();
  }, [loadTelemetry]);

  const chartData = useMemo(() => {
    if (!metricSummary) return [];
    return groupMetricPointsByTimestamp(metricSummary.points);
  }, [metricSummary]);

  const uniqueCorrelationIds = useMemo(() => {
    const set = new Set<string>();
    for (const sp of spans) {
      set.add(sp.correlation_id);
    }
    return Array.from(set).slice(0, 8);
  }, [spans]);

  return (
    <AppShell onTelemetryEvent={loadTelemetry}>
      <div className="space-y-6">
        {/* Header & Filter Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#E4DFD7] pb-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-slate-500">
              <Activity className="w-3.5 h-3.5 text-[#0F1E36]" />
              OPENTELEMETRY TIME-SERIES & DISTRIBUTED TRACE CORRELATION
            </div>
            <h1 className="font-serif text-2xl font-bold text-[#0F1E36]">
              Operational Telemetry Workspace
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-1.5 bg-white border border-[#E4DFD7] rounded px-2.5 py-1 text-xs font-mono">
              <Filter className="w-3.5 h-3.5 text-slate-500" />
              <label htmlFor="telemetry-metric-select" className="sr-only">
                Metric Name
              </label>
              <select
                id="telemetry-metric-select"
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
                className="bg-transparent text-[#0F1E36] focus:outline-none cursor-pointer"
              >
                <option value="request_latency_ms">
                  Metric: request_latency_ms (ms)
                </option>
                <option value="saturation_pct">
                  Metric: saturation_pct (%)
                </option>
              </select>
            </div>

            <div className="inline-flex items-center gap-1.5 bg-white border border-[#E4DFD7] rounded px-2.5 py-1 text-xs font-mono">
              <label htmlFor="telemetry-service-select" className="sr-only">
                Service Filter
              </label>
              <select
                id="telemetry-service-select"
                value={selectedService}
                onChange={(e) => setSelectedService(e.target.value)}
                className="bg-transparent text-[#0F1E36] focus:outline-none cursor-pointer"
              >
                <option value="">All Services (5)</option>
                <option value="api-gateway">api-gateway</option>
                <option value="checkout-service">checkout-service</option>
                <option value="inventory-service">inventory-service</option>
                <option value="payment-simulator">payment-simulator</option>
                <option value="order-database-sim">order-database-sim</option>
              </select>
            </div>

            <button
              type="button"
              onClick={() => void loadTelemetry()}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-white border border-[#E4DFD7] text-xs font-mono text-[#0F1E36] hover:bg-[#F3EFEA] cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
          </div>
        </div>

        {/* Statistical Aggregations (Computed from Stored DB Points) */}
        <section className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
            <span className="text-[10px] font-mono uppercase text-slate-500 block">
              SAMPLE COUNT
            </span>
            <span
              data-testid="telemetry-sample-count"
              className="mt-1 font-mono text-lg font-bold text-[#0F1E36] block"
            >
              {metricSummary?.sample_count ?? 0}
            </span>
          </div>
          <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
            <span className="text-[10px] font-mono uppercase text-slate-500 block">
              MEAN ({metricSummary?.metric_unit || "ms"})
            </span>
            <span
              data-testid="telemetry-mean-val"
              className="mt-1 font-mono text-lg font-bold text-[#0F1E36] block"
            >
              {metricSummary?.mean_value ?? "—"}
            </span>
          </div>
          <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
            <span className="text-[10px] font-mono uppercase text-slate-500 block">
              P95 ({metricSummary?.metric_unit || "ms"})
            </span>
            <span
              data-testid="telemetry-p95-val"
              className="mt-1 font-mono text-lg font-bold text-[#0F1E36] block"
            >
              {metricSummary?.p95_value ?? "—"}
            </span>
          </div>
          <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
            <span className="text-[10px] font-mono uppercase text-slate-500 block">
              MIN / MAX
            </span>
            <span className="mt-1 font-mono text-sm font-bold text-[#0F1E36] block">
              {metricSummary?.min_value ?? "—"} /{" "}
              {metricSummary?.max_value ?? "—"}
            </span>
          </div>
          <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
            <span className="text-[10px] font-mono uppercase text-slate-500 block">
              LATEST OBSERVED
            </span>
            <span className="mt-1 font-mono text-lg font-bold text-[#0F1E36] block">
              {metricSummary?.latest_value ?? "—"}
            </span>
          </div>
        </section>

        {/* Recharts Time-Series Panel */}
        <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-serif text-base font-bold text-[#0F1E36]">
                Time-Series Observation Plot:{" "}
                <span className="font-mono text-sm">{selectedMetric}</span>
              </h2>
              <p className="text-xs text-slate-600">
                Real-time operational measurements grouped by request
                correlation window.
              </p>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-slate-600">
              Source: PostgreSQL metric_observations
            </span>
          </div>

          <div className="h-72 w-full">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={chartData}
                  margin={{ top: 10, right: 20, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#E4DFD7" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 10, fill: "#475569" }}
                  />
                  <YAxis tick={{ fontSize: 10, fill: "#475569" }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#FAF8F5",
                      borderColor: "#E4DFD7",
                      fontSize: "11px",
                      fontFamily: "monospace",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "11px" }} />
                  {Object.entries(SERVICE_COLORS)
                    .filter(
                      ([svcKey]) =>
                        !selectedService || selectedService === svcKey
                    )
                    .map(([svcKey, color]) => (
                      <Line
                        key={svcKey}
                        type="monotone"
                        dataKey={svcKey}
                        stroke={color}
                        strokeWidth={2}
                        dot={{ r: 2.5 }}
                        connectNulls
                      />
                    ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center font-mono text-xs text-slate-500">
                No time-series points matched the current filter.
              </div>
            )}
          </div>
        </section>

        {/* Distributed Trace & Correlation ID Waterfall Inspector */}
        <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="font-serif text-base font-bold text-[#0F1E36]">
                Distributed Trace & Correlation ID Span Ledger
              </h2>
              <p className="text-xs text-slate-600">
                Click any correlation chip or enter a Correlation ID to inspect
                the multi-service call cascade.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
                <input
                  type="text"
                  aria-label="Filter by Correlation ID"
                  placeholder="Filter by correlation_id..."
                  value={correlationFilter}
                  onChange={(e) => setCorrelationFilter(e.target.value)}
                  className="pl-8 pr-3 py-1 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono text-[#0F1E36] focus:outline-none focus:border-[#0F1E36]"
                />
              </div>
              {correlationFilter && (
                <button
                  type="button"
                  onClick={() => setCorrelationFilter("")}
                  className="text-xs font-mono text-slate-600 underline cursor-pointer"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {uniqueCorrelationIds.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mb-4">
              <span className="text-[10px] font-mono uppercase text-slate-500 mr-1">
                Recent Correlation IDs:
              </span>
              {uniqueCorrelationIds.map((cid) => (
                <button
                  key={cid}
                  type="button"
                  onClick={() =>
                    setCorrelationFilter(cid === correlationFilter ? "" : cid)
                  }
                  className={`px-2 py-0.5 rounded text-[11px] font-mono border transition-colors cursor-pointer ${
                    correlationFilter === cid
                      ? "bg-[#0F1E36] text-[#FAF8F5] border-[#0F1E36]"
                      : "bg-[#FAF8F5] text-[#0F1E36] border-[#E4DFD7] hover:bg-[#F3EFEA]"
                  }`}
                >
                  {cid}
                </button>
              ))}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs font-mono">
              <thead>
                <tr className="border-b border-[#E4DFD7] bg-[#FAF8F5] text-[10px] uppercase text-slate-500">
                  <th className="py-2 px-3">Correlation ID</th>
                  <th className="py-2 px-3">Service → Operation</th>
                  <th className="py-2 px-3">Parent Service</th>
                  <th className="py-2 px-3">HTTP / Status</th>
                  <th className="py-2 px-3">Duration</th>
                  <th className="py-2 px-3">Timestamp (UTC)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F3EFEA]">
                {spans.map((sp) => (
                  <tr
                    key={sp.id}
                    data-testid={`span-row-${sp.service_key}`}
                    className="hover:bg-[#FAF8F5]"
                  >
                    <td className="py-2 px-3 font-semibold text-[#0F1E36]">
                      <button
                        type="button"
                        onClick={() => setCorrelationFilter(sp.correlation_id)}
                        className="hover:underline cursor-pointer"
                      >
                        {sp.correlation_id}
                      </button>
                    </td>
                    <td className="py-2 px-3">
                      <span className="font-bold text-[#0F1E36]">
                        {sp.service_key}
                      </span>{" "}
                      <span className="text-slate-600">
                        · {sp.operation_name}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-600">
                      {sp.parent_service_key || "root (entrypoint)"}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          sp.http_status >= 500 || sp.status_code === "ERROR"
                            ? "bg-rose-100 text-rose-800"
                            : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {sp.http_status} {sp.status_code}
                      </span>
                    </td>
                    <td className="py-2 px-3 font-semibold">
                      {sp.duration_ms} ms
                    </td>
                    <td className="py-2 px-3 text-slate-500">
                      {new Date(sp.started_at).toISOString().slice(11, 23)}Z
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
