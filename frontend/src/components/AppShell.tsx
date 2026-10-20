"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Cpu,
  FlaskConical,
  GitBranch,
  History,
  Layers,
  Microscope,
  Play,
  Radio,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  API_BASE_URL,
  fetchLabStatus,
  triggerLabWorkload,
} from "@/lib/api";
import type { LabProfileType } from "@/lib/types";

interface AppShellProps {
  children: React.ReactNode;
  onTelemetryEvent?: () => void;
}

const NAV_ITEMS = [
  { href: "/", label: "Instrument Overview", icon: Sparkles },
  { href: "/dashboard", label: "System Matrix", icon: Layers },
  { href: "/topology", label: "Topology Explorer", icon: GitBranch },
  { href: "/telemetry", label: "Telemetry Workspace", icon: Activity },
  { href: "/investigations", label: "Causal Scientist", icon: Microscope },
  { href: "/twin", label: "Living Digital Twin", icon: History },
  {
    href: "/systems/origin-synthetic-lab",
    label: "System Detail & Registry",
    icon: Cpu,
  },
  { href: "/research", label: "Research Contracts", icon: ShieldCheck },
];

export function AppShell({ children, onTelemetryEvent }: AppShellProps) {
  const pathname = usePathname();
  const [sseConnected, setSseConnected] = useState<boolean>(false);
  const [sseEventCount, setSseEventCount] = useState<number>(0);
  const [lastEventTime, setLastEventTime] = useState<string | null>(null);
  const [activeProfile, setActiveProfile] = useState<LabProfileType>("normal");
  const [isExecutingLab, setIsExecutingLab] = useState<boolean>(false);
  const [lastTraceInfo, setLastTraceInfo] = useState<string | null>(null);

  useEffect(() => {
    fetchLabStatus()
      .then((st) => {
        if (st.profile !== "blinded_benchmark_mode") {
          setActiveProfile(st.profile);
        }
      })
      .catch(() => {
        /* ignore offline during static build */
      });
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }
    const source = new EventSource(`${API_BASE_URL}/api/v1/telemetry/stream`);
    source.onopen = () => {
      setSseConnected(true);
    };
    source.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data) as {
          event_type: string;
          timestamp: string;
        };
        if (parsed.event_type === "stream.connected") {
          setSseConnected(true);
        } else if (parsed.event_type === "telemetry.ingested") {
          setSseEventCount((prev) => prev + 1);
          setLastEventTime(
            new Date(parsed.timestamp).toLocaleTimeString([], {
              hour12: false,
            })
          );
          if (onTelemetryEvent) {
            onTelemetryEvent();
          }
        }
      } catch {
        // ignore malformed frame
      }
    };
    source.onerror = () => {
      setSseConnected(false);
    };
    return () => {
      source.close();
    };
  }, [onTelemetryEvent]);

  const handleRunLabBurst = useCallback(
    async (profileOverride?: LabProfileType) => {
      const targetProfile = profileOverride || activeProfile;
      setIsExecutingLab(true);
      try {
        const res = await triggerLabWorkload({
          iterations: 3,
          profile: targetProfile,
        });
        if (res.active_profile !== "blinded_benchmark_mode") {
          setActiveProfile(res.active_profile);
        }
        const firstCorr = res.traces[0]?.correlation_id || "corr-verified";
        setLastTraceInfo(
          `+${res.total_spans_ingested} spans / +${res.total_metrics_ingested} metrics (${firstCorr})`
        );
        if (onTelemetryEvent) {
          onTelemetryEvent();
        }
      } catch (err) {
        setLastTraceInfo(
          err instanceof Error ? err.message : "Lab execution error"
        );
      } finally {
        setIsExecutingLab(false);
      }
    },
    [activeProfile, onTelemetryEvent]
  );

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5] text-[#0F1E36]">
      {/* Top Scientific Instrument Header */}
      <header className="sticky top-0 z-30 bg-[#FAF8F5]/95 backdrop-blur border-b border-[#E4DFD7]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="flex items-center gap-2.5 group focus:outline-none"
            >
              <div className="w-7 h-7 rounded bg-[#0F1E36] text-[#FAF8F5] flex items-center justify-center font-serif font-bold text-sm tracking-wider shadow-sm">
                O
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-serif text-base font-bold tracking-tight text-[#0F1E36]">
                    ORIGIN
                  </span>
                  <span className="text-[10px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded bg-[#F3EFEA] border border-[#E4DFD7] text-slate-700">
                    M03/05 · LIVING DIGITAL TWIN
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 hidden sm:block leading-none mt-0.5">
                  Give software the ability to understand itself.
                </p>
              </div>
            </Link>
          </div>

          {/* Live SSE Telemetry Status & Synthetic Lab Control Bar */}
          <div className="flex items-center gap-3">
            <div
              className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded border border-[#E4DFD7] bg-white text-[11px] font-mono"
              title="Server-Sent Events Real-Time Telemetry Stream"
            >
              <Radio
                className={`w-3.5 h-3.5 ${
                  sseConnected
                    ? "text-emerald-600 animate-pulse"
                    : "text-amber-600"
                }`}
              />
              <span className="text-slate-600">
                SSE:{" "}
                <strong className="text-[#0F1E36]">
                  {sseConnected ? "LIVE" : "POLLING"}
                </strong>
              </span>
              {sseEventCount > 0 && (
                <span className="text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded">
                  +{sseEventCount} batches ({lastEventTime})
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5 bg-white border border-[#E4DFD7] rounded px-2 py-1 shadow-2xs">
              <FlaskConical className="w-3.5 h-3.5 text-[#0F1E36]" />
              <label htmlFor="lab-profile-select" className="sr-only">
                Synthetic Lab Profile
              </label>
              <select
                id="lab-profile-select"
                aria-label="Synthetic Lab Profile"
                value={activeProfile}
                onChange={(e) =>
                  setActiveProfile(e.target.value as LabProfileType)
                }
                className="text-xs font-mono bg-transparent text-[#0F1E36] focus:outline-none cursor-pointer pr-1"
              >
                <option value="normal">Lab: Normal Baseline</option>
                <option value="payment_latency_spike">
                  Lab: Payment Latency Spike
                </option>
                <option value="db_lock_contention">
                  Lab: DB Lock Contention
                </option>
                <option value="inventory_cpu_throttling">
                  Lab: Inventory CPU Starvation
                </option>
                <option value="noisy_ambiguous_jitter">
                  Lab: Ambiguous Multi-Service Jitter
                </option>
              </select>
              <button
                type="button"
                data-testid="global-run-lab-btn"
                disabled={isExecutingLab}
                onClick={() => handleRunLabBurst()}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] disabled:opacity-50 transition-colors cursor-pointer"
              >
                <Play className="w-3 h-3 fill-current" />
                {isExecutingLab ? "Tracing..." : "Emit Lab Traffic"}
              </button>
            </div>
          </div>
        </div>

        {/* Secondary Navigation Strip */}
        <div className="border-t border-[#E4DFD7] bg-[#F3EFEA]/60">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between overflow-x-auto">
            <nav className="flex items-center space-x-1 py-1.5" aria-label="Primary">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname?.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors whitespace-nowrap ${
                      isActive
                        ? "bg-[#0F1E36] text-[#FAF8F5] shadow-2xs"
                        : "text-slate-700 hover:bg-[#E6E0D6]/60 hover:text-[#0F1E36]"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            {lastTraceInfo && (
              <div
                data-testid="lab-burst-receipt"
                className="hidden lg:block text-[11px] font-mono text-emerald-800 bg-emerald-50/90 border border-emerald-200 px-2.5 py-0.5 rounded"
              >
                Observed: {lastTraceInfo}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      {/* Scientific Instrument Footer */}
      <footer className="border-t border-[#E4DFD7] bg-[#F3EFEA]/50 py-4 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-[11px] text-slate-600 gap-2">
          <div className="flex items-center gap-2">
            <span className="font-serif font-semibold text-[#0F1E36]">
              ORIGIN Scientific Intelligence Platform
            </span>
            <span>·</span>
            <span>
              Zero decorative metrics — all figures originate from stored
              observations or explicitly labeled synthetic instrumentation.
            </span>
          </div>
          <div className="font-mono text-[10px] text-slate-500">
            OTLP/HTTP JSON · SQLAlchemy 2 Async · Provenance-Verified Topology
          </div>
        </div>
      </footer>
    </div>
  );
}
