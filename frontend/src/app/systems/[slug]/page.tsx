"use client";

import React, { use, useCallback, useEffect, useState } from "react";
import {
  Cpu,
  FlaskConical,
  Plus,
  Radio,
  RefreshCw,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import {
  fetchAuditEvents,
  fetchSystemDetail,
  formatProvenanceBadge,
  registerDependencyApi,
  registerServiceApi,
} from "@/lib/api";
import type { AuditEventRead, SystemDetailRead } from "@/lib/types";

export default function SystemDetailViewPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const [detail, setDetail] = useState<SystemDetailRead | null>(null);
  const [audits, setAudits] = useState<AuditEventRead[]>([]);
  const [newServiceKey, setNewServiceKey] = useState<string>("");
  const [newServiceName, setNewServiceName] = useState<string>("");
  const [newServiceType, setNewServiceType] = useState<string>("microservice");
  const [newServiceTier, setNewServiceTier] = useState<string>("tier-1");
  const [depSource, setDepSource] = useState<string>("");
  const [depTarget, setDepTarget] = useState<string>("");
  const [depProtocol, setDepProtocol] = useState<string>("http");
  const [formFeedback, setFormFeedback] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    try {
      const sys = await fetchSystemDetail(slug);
      setDetail(sys);
      const evs = await fetchAuditEvents(sys.id);
      setAudits(evs.slice(0, 15));
    } catch {
      // ignore initial offline
    }
  }, [slug]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const handleRegisterService = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newServiceKey.trim() || !newServiceName.trim()) return;
    try {
      await registerServiceApi(slug, {
        service_key: newServiceKey.trim().toLowerCase(),
        display_name: newServiceName.trim(),
        service_type: newServiceType,
        tier: newServiceTier,
        owner_team: "platform-engineering",
      });
      setNewServiceKey("");
      setNewServiceName("");
      setFormFeedback("Service registered in system catalog.");
      await loadDetail();
    } catch (err) {
      setFormFeedback(
        err instanceof Error ? err.message : "Failed to register service."
      );
    }
  };

  const handleRegisterDependency = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!depSource || !depTarget) return;
    try {
      await registerDependencyApi(slug, {
        source_service_key: depSource,
        target_service_key: depTarget,
        protocol: depProtocol,
      });
      setFormFeedback(
        `Declared dependency ${depSource} -> ${depTarget} (${depProtocol}).`
      );
      await loadDetail();
    } catch (err) {
      setFormFeedback(
        err instanceof Error ? err.message : "Failed to declare dependency."
      );
    }
  };

  return (
    <AppShell onTelemetryEvent={loadDetail}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E4DFD7] pb-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-slate-500">
              <Cpu className="w-3.5 h-3.5 text-[#0F1E36]" />
              SYSTEM REGISTRY & PROVENANCE LEDGER
            </div>
            <h1 className="font-serif text-2xl font-bold text-[#0F1E36]">
              {detail?.name || slug}
            </h1>
            <p className="text-xs text-slate-600 mt-0.5">
              {detail?.description}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {detail?.is_synthetic_lab && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-amber-50 border border-amber-300 text-amber-900 text-[11px] font-mono">
                <FlaskConical className="w-3.5 h-3.5" />
                SYNTHETIC LAB
              </span>
            )}
            <button
              type="button"
              onClick={() => void loadDetail()}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-white border border-[#E4DFD7] text-xs font-mono text-[#0F1E36] hover:bg-[#F3EFEA] cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reload
            </button>
          </div>
        </div>

        {formFeedback && (
          <div className="p-3 rounded bg-[#FAF8F5] border border-[#0F1E36] text-xs font-mono text-[#0F1E36] flex items-center justify-between">
            <span>{formFeedback}</span>
            <button
              type="button"
              onClick={() => setFormFeedback(null)}
              className="underline cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Services & Dependencies Tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Services Catalog */}
          <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-4">
            <h2 className="font-serif text-base font-bold text-[#0F1E36]">
              Registered & Observed Services ({detail?.services.length ?? 0})
            </h2>
            <div className="space-y-2">
              {detail?.services.map((svc) => {
                const prov = formatProvenanceBadge(svc.registration_source);
                return (
                  <div
                    key={svc.id}
                    className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7] flex items-center justify-between gap-2 text-xs"
                  >
                    <div>
                      <div className="font-serif font-bold text-[#0F1E36]">
                        {svc.display_name}{" "}
                        <span className="font-mono font-normal text-slate-500">
                          ({svc.service_key})
                        </span>
                      </div>
                      <div className="font-mono text-[11px] text-slate-500 mt-0.5">
                        {svc.tier} · {svc.service_type} · Owner:{" "}
                        {svc.owner_team}
                      </div>
                    </div>
                    <span
                      className={`font-mono text-[10px] px-2 py-0.5 rounded border ${prov.badgeClass}`}
                    >
                      {prov.label}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Interactive Register Service Form */}
            <form
              onSubmit={(e) => void handleRegisterService(e)}
              className="pt-3 border-t border-[#E4DFD7] space-y-2.5"
            >
              <div className="text-[11px] font-mono uppercase text-slate-500">
                Declare New Service in Registry
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="service-key (e.g. fraud-engine)"
                  value={newServiceKey}
                  onChange={(e) => setNewServiceKey(e.target.value)}
                  className="px-2.5 py-1.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono"
                />
                <input
                  type="text"
                  placeholder="Display Name"
                  value={newServiceName}
                  onChange={(e) => setNewServiceName(e.target.value)}
                  className="px-2.5 py-1.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs"
                />
              </div>
              <div className="flex items-center gap-2">
                <select
                  aria-label="Service Type"
                  value={newServiceType}
                  onChange={(e) => setNewServiceType(e.target.value)}
                  className="px-2.5 py-1.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono"
                >
                  <option value="microservice">microservice</option>
                  <option value="gateway">gateway</option>
                  <option value="database">database</option>
                  <option value="worker">worker</option>
                </select>
                <select
                  aria-label="Service Tier"
                  value={newServiceTier}
                  onChange={(e) => setNewServiceTier(e.target.value)}
                  className="px-2.5 py-1.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono"
                >
                  <option value="tier-0">tier-0</option>
                  <option value="tier-1">tier-1</option>
                  <option value="tier-2">tier-2</option>
                  <option value="tier-3">tier-3</option>
                </select>
                <button
                  type="submit"
                  className="ml-auto inline-flex items-center gap-1 px-3 py-1.5 rounded bg-[#0F1E36] text-[#FAF8F5] text-xs font-medium hover:bg-[#1B365D] cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Register Service
                </button>
              </div>
            </form>
          </section>

          {/* Dependency Provenance Ledger */}
          <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-4">
            <h2 className="font-serif text-base font-bold text-[#0F1E36]">
              Dependency Edges & Observation Provenance (
              {detail?.dependencies.length ?? 0})
            </h2>
            <div className="space-y-2">
              {detail?.dependencies.map((dep) => {
                const prov = formatProvenanceBadge(dep.discovery_source);
                return (
                  <div
                    key={dep.id}
                    className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7] flex items-center justify-between gap-2 text-xs font-mono"
                  >
                    <div>
                      <div className="font-bold text-[#0F1E36]">
                        {dep.source_service_key} → {dep.target_service_key}
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5">
                        Protocol: {dep.protocol.toUpperCase()} · Observations:{" "}
                        {dep.observation_count} · Last Latency:{" "}
                        {dep.last_latency_ms !== null
                          ? `${dep.last_latency_ms}ms`
                          : "—"}
                      </div>
                    </div>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded border ${prov.badgeClass}`}
                    >
                      {prov.label}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Interactive Declare Dependency Form */}
            <form
              onSubmit={(e) => void handleRegisterDependency(e)}
              className="pt-3 border-t border-[#E4DFD7] space-y-2.5"
            >
              <div className="text-[11px] font-mono uppercase text-slate-500">
                Declare Explicit Service Dependency
              </div>
              <div className="grid grid-cols-3 gap-2">
                <select
                  aria-label="Source Service"
                  value={depSource}
                  onChange={(e) => setDepSource(e.target.value)}
                  className="px-2 py-1.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono"
                >
                  <option value="">Source service...</option>
                  {detail?.services.map((s) => (
                    <option key={s.service_key} value={s.service_key}>
                      {s.service_key}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Target Service"
                  value={depTarget}
                  onChange={(e) => setDepTarget(e.target.value)}
                  className="px-2 py-1.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono"
                >
                  <option value="">Target service...</option>
                  {detail?.services.map((s) => (
                    <option key={s.service_key} value={s.service_key}>
                      {s.service_key}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Dependency Protocol"
                  value={depProtocol}
                  onChange={(e) => setDepProtocol(e.target.value)}
                  className="px-2 py-1.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono"
                >
                  <option value="http">HTTP</option>
                  <option value="grpc">gRPC</option>
                  <option value="sql">SQL</option>
                  <option value="redis">Redis</option>
                </select>
              </div>
              <div className="flex justify-end">
                <button
                  type="submit"
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-[#0F1E36] text-[#FAF8F5] text-xs font-medium hover:bg-[#1B365D] cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Declare Dependency
                </button>
              </div>
            </form>
          </section>
        </div>

        {/* Active Telemetry Sources & System Audit Trail */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs">
            <h2 className="font-serif text-base font-bold text-[#0F1E36] mb-3">
              Active OpenTelemetry Exporters (
              {detail?.telemetry_sources.length ?? 0})
            </h2>
            <div className="space-y-2.5">
              {detail?.telemetry_sources.map((src) => (
                <div
                  key={src.id}
                  className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7] flex items-center justify-between text-xs font-mono"
                >
                  <div className="flex items-center gap-2">
                    <Radio className="w-4 h-4 text-emerald-700" />
                    <div>
                      <div className="font-bold text-[#0F1E36]">
                        {src.source_name}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Protocol: {src.exporter_protocol} · SDK:{" "}
                        {src.sdk_version}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-[#0F1E36]">
                      {src.total_batches_ingested} batches
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {src.is_synthetic ? "Synthetic Lab" : "Production"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs">
            <h2 className="font-serif text-base font-bold text-[#0F1E36] mb-3">
              System Audit Events ({audits.length})
            </h2>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {audits.map((ev) => (
                <div
                  key={ev.id}
                  className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono flex items-center justify-between"
                >
                  <div>
                    <span className="font-bold text-[#0F1E36]">
                      {ev.action}
                    </span>{" "}
                    <span className="text-slate-600">→ {ev.resource_id}</span>
                  </div>
                  <span className="text-[10px] text-slate-500">
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
