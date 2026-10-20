"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Cpu,
  FlaskConical,
  GitBranch,
  Layers,
  ShieldCheck,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import {
  fetchArchitectureModules,
  fetchHealth,
  fetchSystems,
} from "@/lib/api";
import type { ModuleBoundaryStatus, SystemRead } from "@/lib/types";

export default function LandingPage() {
  const [systems, setSystems] = useState<SystemRead[]>([]);
  const [boundaries, setBoundaries] = useState<ModuleBoundaryStatus[]>([]);
  const [healthStatus, setHealthStatus] = useState<{
    status: string;
    database_connected: boolean;
    laboratory_profile: string;
  } | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = useCallback(async () => {
    try {
      const [sysData, healthData, archData] = await Promise.all([
        fetchSystems(),
        fetchHealth(),
        fetchArchitectureModules(),
      ]);
      setSystems(sysData);
      setHealthStatus(healthData);
      setBoundaries(archData.boundaries);
    } catch {
      // Handle initial load gracefully
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const primaryLab = systems.find((s) => s.slug === "origin-synthetic-lab") || systems[0];

  return (
    <AppShell onTelemetryEvent={loadData}>
      <div className="space-y-8">
        {/* Editorial Hero Banner */}
        <section className="bg-white border border-[#E4DFD7] rounded-md p-6 sm:p-8 shadow-2xs relative overflow-hidden">
          <div className="max-w-3xl space-y-4">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-[#F3EFEA] border border-[#E4DFD7] text-[11px] font-mono text-[#0F1E36]">
              <span>SCIENTIFIC INSTRUMENTATION</span>
              <span>·</span>
              <span>MILESTONE 01/05 VERIFIED</span>
            </div>

            <h1 className="font-serif text-3xl sm:text-4xl font-bold tracking-tight text-[#0F1E36] leading-tight">
              Give software the ability to understand itself.
            </h1>

            <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
              ORIGIN is an autonomous scientific intelligence platform for
              distributed software systems. Every metric, span, and dependency
              edge rendered in this instrument originates from real
              OpenTelemetry instrumentation, stored database observations, or the
              isolated 5-service{" "}
              <strong className="text-[#0F1E36] font-medium">
                Synthetic Distributed System Laboratory
              </strong>
              .
            </p>

            <div className="pt-2 flex flex-wrap items-center gap-3">
              <Link
                href="/topology"
                className="inline-flex items-center gap-2 px-4 py-2 rounded bg-[#0F1E36] text-[#FAF8F5] text-xs font-medium hover:bg-[#1B365D] transition-colors"
              >
                <GitBranch className="w-4 h-4" />
                Launch Topology Explorer
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
              <Link
                href="/telemetry"
                className="inline-flex items-center gap-2 px-4 py-2 rounded bg-white border border-[#E4DFD7] text-[#0F1E36] text-xs font-medium hover:bg-[#F3EFEA] transition-colors"
              >
                <Activity className="w-4 h-4" />
                Open Telemetry Workspace
              </Link>
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 px-4 py-2 rounded bg-white border border-[#E4DFD7] text-slate-700 text-xs font-medium hover:bg-[#F3EFEA] transition-colors"
              >
                <Layers className="w-4 h-4" />
                System Health Matrix
              </Link>
            </div>
          </div>
        </section>

        {/* Live Operational Telemetry Summary Strip (Zero Hardcoded Figures) */}
        <section aria-label="Live Operational Figures">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="font-serif text-lg font-bold text-[#0F1E36]">
                Live Living System Telemetry Ledger
              </h2>
              <p className="text-xs text-slate-600">
                Direct database counts from PostgreSQL/SQLAlchemy async store for{" "}
                <span className="font-mono text-[#0F1E36]">
                  {primaryLab?.slug || "origin-synthetic-lab"}
                </span>
              </p>
            </div>
            {primaryLab?.is_synthetic_lab && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-50 border border-amber-300 text-amber-900 text-[11px] font-mono">
                <FlaskConical className="w-3.5 h-3.5" />
                EXPLICIT LABEL: SYNTHETIC DISTRIBUTED LABORATORY
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
              <span className="text-[10px] font-mono uppercase text-slate-500 block">
                ENGINE HEALTH
              </span>
              <span
                data-testid="landing-engine-health"
                className="mt-1 font-mono text-lg font-bold text-[#0F1E36] block uppercase"
              >
                {loading ? "..." : healthStatus?.status || "OFFLINE"}
              </span>
              <span className="text-[11px] text-slate-500">
                DB: {healthStatus?.database_connected ? "Connected" : "Checking"}
              </span>
            </div>

            <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
              <span className="text-[10px] font-mono uppercase text-slate-500 block">
                INSTRUMENTED SERVICES
              </span>
              <span
                data-testid="landing-service-count"
                className="mt-1 font-mono text-lg font-bold text-[#0F1E36] block"
              >
                {loading ? "..." : primaryLab?.stats?.service_count ?? 0}
              </span>
              <span className="text-[11px] text-emerald-700 font-mono">
                {primaryLab?.stats?.healthy_service_count ?? 0} healthy /{" "}
                {primaryLab?.stats?.degraded_service_count ?? 0} degraded
              </span>
            </div>

            <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
              <span className="text-[10px] font-mono uppercase text-slate-500 block">
                VERIFIED DEPENDENCIES
              </span>
              <span
                data-testid="landing-observed-edges"
                className="mt-1 font-mono text-lg font-bold text-[#0F1E36] block"
              >
                {loading
                  ? "..."
                  : `${primaryLab?.stats?.observed_dependency_count ?? 0} / ${
                      primaryLab?.stats?.dependency_count ?? 0
                    }`}
              </span>
              <span className="text-[11px] text-slate-500">
                Confirmed by spans
              </span>
            </div>

            <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
              <span className="text-[10px] font-mono uppercase text-slate-500 block">
                STORED TRACE SPANS
              </span>
              <span
                data-testid="landing-span-count"
                className="mt-1 font-mono text-lg font-bold text-[#0F1E36] block"
              >
                {loading ? "..." : primaryLab?.stats?.span_observation_count ?? 0}
              </span>
              <span className="text-[11px] text-slate-500">
                OTLP & Native spans
              </span>
            </div>

            <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
              <span className="text-[10px] font-mono uppercase text-slate-500 block">
                METRIC OBSERVATIONS
              </span>
              <span
                data-testid="landing-metric-count"
                className="mt-1 font-mono text-lg font-bold text-[#0F1E36] block"
              >
                {loading
                  ? "..."
                  : primaryLab?.stats?.metric_observation_count ?? 0}
              </span>
              <span className="text-[11px] text-slate-500">
                Time-series samples
              </span>
            </div>

            <div className="bg-white border border-[#E4DFD7] rounded p-3.5">
              <span className="text-[10px] font-mono uppercase text-slate-500 block">
                LAB FAULT PROFILE
              </span>
              <span
                data-testid="landing-lab-profile"
                className="mt-1 font-mono text-sm font-bold text-[#0F1E36] block truncate"
              >
                {loading ? "..." : healthStatus?.laboratory_profile || "normal"}
              </span>
              <span className="text-[11px] text-slate-500">
                Active lab mode
              </span>
            </div>
          </div>
        </section>

        {/* 9 Modular Architectural Boundaries Overview */}
        <section className="bg-white border border-[#E4DFD7] rounded-md p-6 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#E4DFD7]">
            <div>
              <h2 className="font-serif text-lg font-bold text-[#0F1E36]">
                Modular Architecture & Scientific Honesty Matrix (9 Boundaries)
              </h2>
              <p className="text-xs text-slate-600">
                Clear separation between active Milestone 01/05 Living System
                modules and future research contracts.
              </p>
            </div>
            <Link
              href="/research"
              className="text-xs font-mono text-[#0F1E36] underline hover:text-slate-700"
            >
              Inspect Full Module Contracts →
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
            {boundaries.map((b) => {
              const isImplemented = b.status.startsWith("implemented");
              return (
                <div
                  key={b.boundary_number}
                  className={`p-3.5 rounded border ${
                    isImplemented
                      ? "bg-[#FAF8F5] border-[#D6CFC4]"
                      : "bg-[#F3EFEA]/40 border-[#E4DFD7]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="font-mono text-[10px] text-slate-500">
                      BOUNDARY 0{b.boundary_number}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono ${
                        isImplemented
                          ? "bg-[#0F1E36] text-[#FAF8F5]"
                          : "bg-slate-200 text-slate-700"
                      }`}
                    >
                      {isImplemented ? (
                        <>
                          <CheckCircle2 className="w-2.5 h-2.5" />
                          ACTIVE M01/05
                        </>
                      ) : (
                        <>
                          <ShieldCheck className="w-2.5 h-2.5" />
                          CONTRACT ONLY
                        </>
                      )}
                    </span>
                  </div>
                  <div className="font-serif font-bold text-sm text-[#0F1E36]">
                    {b.module.replace(/_/g, " ").toUpperCase()}
                  </div>
                  <p className="text-[11px] text-slate-600 mt-1 leading-relaxed">
                    {b.capabilities
                      ? b.capabilities.join(" · ")
                      : b.notice || b.target_milestone}
                  </p>
                </div>
              );
            })}
          </div>
        </section>

        {/* Quick Navigation Cards to Instrument Workspaces */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link
            href="/topology"
            className="group bg-white border border-[#E4DFD7] hover:border-[#0F1E36] rounded-md p-5 transition-all shadow-2xs"
          >
            <div className="flex items-center justify-between mb-2">
              <GitBranch className="w-5 h-5 text-[#0F1E36]" />
              <span className="font-mono text-[10px] uppercase text-slate-500">
                React Flow · Provenance
              </span>
            </div>
            <h3 className="font-serif text-base font-bold text-[#0F1E36] group-hover:underline">
              Topology Explorer
            </h3>
            <p className="text-xs text-slate-600 mt-1">
              Interactive service dependency graph distinguishing declared edges
              from live span-verified observations.
            </p>
          </Link>

          <Link
            href="/telemetry"
            className="group bg-white border border-[#E4DFD7] hover:border-[#0F1E36] rounded-md p-5 transition-all shadow-2xs"
          >
            <div className="flex items-center justify-between mb-2">
              <Activity className="w-5 h-5 text-[#0F1E36]" />
              <span className="font-mono text-[10px] uppercase text-slate-500">
                Recharts · OTLP Spans
              </span>
            </div>
            <h3 className="font-serif text-base font-bold text-[#0F1E36] group-hover:underline">
              Telemetry & Trace Workspace
            </h3>
            <p className="text-xs text-slate-600 mt-1">
              Time-series operational metrics (latency, saturation) and
              correlation-ID trace waterfall inspection.
            </p>
          </Link>

          <Link
            href="/systems/origin-synthetic-lab"
            className="group bg-white border border-[#E4DFD7] hover:border-[#0F1E36] rounded-md p-5 transition-all shadow-2xs"
          >
            <div className="flex items-center justify-between mb-2">
              <Cpu className="w-5 h-5 text-[#0F1E36]" />
              <span className="font-mono text-[10px] uppercase text-slate-500">
                Registry · Audit Log
              </span>
            </div>
            <h3 className="font-serif text-base font-bold text-[#0F1E36] group-hover:underline">
              System Detail & Registry
            </h3>
            <p className="text-xs text-slate-600 mt-1">
              Inspect registered services, declare new dependencies, verify
              OTLP exporters, and audit system mutations.
            </p>
          </Link>
        </section>
      </div>
    </AppShell>
  );
}
