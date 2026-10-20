"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  Play,
  RefreshCw,
  Server,
  ShieldAlert,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import {
  fetchAuditEvents,
  fetchLabStatus,
  fetchSystemDetail,
  fetchSystems,
  formatProvenanceBadge,
  triggerLabWorkload,
} from "@/lib/api";
import type {
  AuditEventRead,
  LabFaultState,
  LabProfileType,
  LabTransactionTraceSummary,
  SystemDetailRead,
  SystemRead,
} from "@/lib/types";

export default function SystemOverviewDashboard() {
  const [systems, setSystems] = useState<SystemRead[]>([]);
  const [labDetail, setLabDetail] = useState<SystemDetailRead | null>(null);
  const [labState, setLabState] = useState<LabFaultState | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEventRead[]>([]);
  const [recentTraces, setRecentTraces] = useState<LabTransactionTraceSummary[]>(
    []
  );
  const [runningProfile, setRunningProfile] = useState<boolean>(false);

  const loadDashboard = useCallback(async () => {
    try {
      const [sysList, detail, lState, audits] = await Promise.all([
        fetchSystems(),
        fetchSystemDetail("origin-synthetic-lab"),
        fetchLabStatus(),
        fetchAuditEvents(),
      ]);
      setSystems(sysList);
      setLabDetail(detail);
      setLabState(lState);
      setAuditEvents(audits.slice(0, 12));
    } catch {
      // ignore initial offline
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const handleTriggerScenario = async (profile: LabProfileType) => {
    setRunningProfile(true);
    try {
      const result = await triggerLabWorkload({
        iterations: 4,
        profile,
      });
      setRecentTraces(result.traces);
      await loadDashboard();
    } finally {
      setRunningProfile(false);
    }
  };

  return (
    <AppShell onTelemetryEvent={loadDashboard}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E4DFD7] pb-4">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-widest text-slate-500">
              LIVING SYSTEM INTELLIGENCE · OVERVIEW
            </div>
            <h1 className="font-serif text-2xl font-bold text-[#0F1E36]">
              System Health & Synthetic Laboratory Matrix
            </h1>
          </div>
          <button
            type="button"
            onClick={() => void loadDashboard()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-white border border-[#E4DFD7] text-xs font-mono text-[#0F1E36] hover:bg-[#F3EFEA] cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh State
          </button>
        </div>

        {/* Synthetic Distributed System Laboratory Interactive Controller */}
        <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E4DFD7]">
            <div className="space-y-1">
              <div className="inline-flex items-center gap-1.5 text-xs font-mono text-amber-900 bg-amber-50 border border-amber-300 px-2 py-0.5 rounded">
                <FlaskConical className="w-3.5 h-3.5" />
                ISOLATED SYNTHETIC DISTRIBUTED SYSTEM LABORATORY
              </div>
              <h2 className="font-serif text-lg font-bold text-[#0F1E36]">
                Controlled Workload & Performance Degradation Injector
              </h2>
              <p className="text-xs text-slate-600">
                Execute real instrumented checkout transactions across{" "}
                <span className="font-mono">
                  api-gateway → checkout-service → (inventory-service,
                  payment-simulator, order-database-sim)
                </span>
                .
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                data-testid="run-normal-profile-btn"
                disabled={runningProfile}
                onClick={() => void handleTriggerScenario("normal")}
                className={`inline-flex items-center gap-1.5 px-3 py-2 rounded text-xs font-medium border transition-colors cursor-pointer ${
                  labState?.profile === "normal"
                    ? "bg-[#0F1E36] text-[#FAF8F5] border-[#0F1E36]"
                    : "bg-[#FAF8F5] text-[#0F1E36] border-[#D6CFC4] hover:bg-[#F3EFEA]"
                }`}
              >
                <Play className="w-3.5 h-3.5" />
                Normal Operation (4x)
              </button>

              <button
                type="button"
                data-testid="run-payment-spike-btn"
                disabled={runningProfile}
                onClick={() =>
                  void handleTriggerScenario("payment_latency_spike")
                }
                className={`inline-flex items-center gap-1.5 px-3 py-2 rounded text-xs font-medium border transition-colors cursor-pointer ${
                  labState?.profile === "payment_latency_spike"
                    ? "bg-amber-700 text-white border-amber-800"
                    : "bg-amber-50 text-amber-900 border-amber-300 hover:bg-amber-100"
                }`}
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                Inject Payment Latency Spike (4x)
              </button>

              <button
                type="button"
                data-testid="run-db-contention-btn"
                disabled={runningProfile}
                onClick={() => void handleTriggerScenario("db_lock_contention")}
                className={`inline-flex items-center gap-1.5 px-3 py-2 rounded text-xs font-medium border transition-colors cursor-pointer ${
                  labState?.profile === "db_lock_contention"
                    ? "bg-rose-800 text-white border-rose-900"
                    : "bg-rose-50 text-rose-900 border-rose-300 hover:bg-rose-100"
                }`}
              >
                <ShieldAlert className="w-3.5 h-3.5" />
                Inject DB Lock Contention (4x)
              </button>
            </div>
          </div>

          {recentTraces.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] font-mono uppercase text-slate-500 mb-2">
                Latest Executed Multi-Service Transactions
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                {recentTraces.map((tr) => (
                  <div
                    key={tr.trace_id}
                    className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-[#0F1E36] truncate">
                        {tr.correlation_id}
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          tr.gateway_status >= 500
                            ? "bg-rose-100 text-rose-800"
                            : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        HTTP {tr.gateway_status}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-600">
                      End-to-End: <strong>{tr.total_duration_ms} ms</strong> ·{" "}
                      {tr.spans_emitted} spans
                    </div>
                    <div className="text-[10px] text-slate-500 truncate">
                      Services: {tr.services_traversed.length} traversed
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Service Health & Provenance Matrix */}
        <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-serif text-lg font-bold text-[#0F1E36]">
                Observed Service Health & Provenance Matrix
              </h2>
              <p className="text-xs text-slate-600">
                Real-time service health computed from stored OpenTelemetry span
                durations and error statuses.
              </p>
            </div>
            <Link
              href="/topology"
              className="text-xs font-mono text-[#0F1E36] underline"
            >
              View in React Flow Topology →
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#E4DFD7] bg-[#FAF8F5] font-mono text-[10px] uppercase text-slate-500">
                  <th className="py-2.5 px-3">Service Key</th>
                  <th className="py-2.5 px-3">Display Name</th>
                  <th className="py-2.5 px-3">Tier / Type</th>
                  <th className="py-2.5 px-3">Provenance</th>
                  <th className="py-2.5 px-3">Health Status</th>
                  <th className="py-2.5 px-3">Last Observed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F3EFEA]">
                {labDetail?.services.map((svc) => {
                  const prov = formatProvenanceBadge(svc.registration_source);
                  return (
                    <tr
                      key={svc.id}
                      data-testid={`dashboard-service-row-${svc.service_key}`}
                      className="hover:bg-[#FAF8F5]"
                    >
                      <td className="py-2.5 px-3 font-mono font-semibold text-[#0F1E36]">
                        {svc.service_key}
                      </td>
                      <td className="py-2.5 px-3 font-medium">
                        {svc.display_name}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-600">
                        {svc.tier} · {svc.service_type}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`inline-block font-mono text-[10px] px-2 py-0.5 rounded border ${prov.badgeClass}`}
                        >
                          {prov.label}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`inline-flex items-center gap-1 font-mono text-[11px] font-semibold uppercase ${
                            svc.health_status === "healthy"
                              ? "text-emerald-700"
                              : svc.health_status === "degraded"
                              ? "text-amber-700"
                              : svc.health_status === "critical"
                              ? "text-rose-700"
                              : "text-slate-500"
                          }`}
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          {svc.health_status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-500">
                        {svc.last_seen_at
                          ? new Date(svc.last_seen_at).toLocaleTimeString([], {
                              hour12: false,
                            })
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Registered Systems & Safety Audit Log */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Registered Systems */}
          <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs">
            <h2 className="font-serif text-base font-bold text-[#0F1E36] mb-3">
              Registered Systems ({systems.length})
            </h2>
            <div className="space-y-3">
              {systems.map((sys) => (
                <div
                  key={sys.id}
                  className="p-3.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] flex items-center justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Server className="w-4 h-4 text-[#0F1E36]" />
                      <Link
                        href={`/systems/${sys.slug}`}
                        className="font-serif font-bold text-sm text-[#0F1E36] hover:underline"
                      >
                        {sys.name}
                      </Link>
                      {sys.is_synthetic_lab && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-50 border border-amber-300 text-amber-900">
                          SYNTHETIC LAB
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-600 line-clamp-1">
                      {sys.description}
                    </p>
                    <div className="text-[11px] font-mono text-slate-500">
                      Services: {sys.stats?.service_count ?? 0} · Verified
                      Edges: {sys.stats?.observed_dependency_count ?? 0} ·
                      Spans: {sys.stats?.span_observation_count ?? 0}
                    </div>
                  </div>
                  <Link
                    href={`/systems/${sys.slug}`}
                    className="px-2.5 py-1 rounded bg-white border border-[#E4DFD7] text-xs font-mono text-[#0F1E36] hover:bg-[#F3EFEA]"
                  >
                    Inspect
                  </Link>
                </div>
              ))}
            </div>
          </section>

          {/* Safety & Operational Audit Stream */}
          <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs">
            <h2 className="font-serif text-base font-bold text-[#0F1E36] mb-3">
              Safety & Operational Audit Trail
            </h2>
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {auditEvents.map((ev) => (
                <div
                  key={ev.id}
                  className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs flex items-start justify-between gap-2"
                >
                  <div className="font-mono">
                    <span className="font-bold text-[#0F1E36]">
                      {ev.action}
                    </span>{" "}
                    <span className="text-slate-600">
                      ({ev.resource_type}: {ev.resource_id || "n/a"})
                    </span>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      Actor: {ev.actor} · Corr:{" "}
                      {ev.correlation_id || "system-init"}
                    </div>
                  </div>
                  <span className="font-mono text-[10px] text-slate-500 whitespace-nowrap">
                    {new Date(ev.created_at).toLocaleTimeString([], {
                      hour12: false,
                    })}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
