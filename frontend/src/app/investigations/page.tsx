"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  FlaskConical,
  GitCommit,
  HelpCircle,
  Microscope,
  Play,
  RefreshCw,
  Scale,
  ShieldAlert,
  Sparkles,
  XCircle,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppShell } from "@/components/AppShell";
import {
  cancelInvestigation,
  createInvestigation,
  exportInvestigationReport,
  fetchInvestigationDetail,
  fetchInvestigations,
  formatHypothesisStatusBadge,
  triggerLabWorkload,
} from "@/lib/api";
import type {
  ExperimentRunRead,
  HypothesisRead,
  InvestigationDetailRead,
  InvestigationRead,
  InvestigationStatusType,
  LabProfileType,
} from "@/lib/types";

const LIFECYCLE_STAGES: InvestigationStatusType[] = [
  "CREATED",
  "OBSERVING",
  "HYPOTHESIZING",
  "PLANNING",
  "EXPERIMENTING",
  "EVALUATING",
  "CONCLUDED",
];

function getStatusBadgeStyle(status: InvestigationStatusType): string {
  switch (status) {
    case "CONCLUDED":
      return "bg-emerald-50 text-emerald-900 border-emerald-300";
    case "INCONCLUSIVE":
      return "bg-amber-50 text-amber-900 border-amber-300";
    case "FAILED":
    case "CANCELLED":
      return "bg-rose-50 text-rose-900 border-rose-300";
    default:
      return "bg-navy-900 text-ivory-50 border-navy-900";
  }
}

export default function CausalInvestigationsPage() {
  const [investigations, setInvestigations] = useState<InvestigationRead[]>([]);
  const [activeDetail, setActiveDetail] =
    useState<InvestigationDetailRead | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [launching, setLaunching] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Launcher configuration state
  const [title, setTitle] = useState<string>(
    "Autonomous Checkout Latency Investigation"
  );
  const [targetService, setTargetService] =
    useState<string>("checkout-service");
  const [budget, setBudget] = useState<number>(3);
  const [sampleSize, setSampleSize] = useState<number>(5);
  const [randomSeed, setRandomSeed] = useState<number>(42);
  const [preFaultProfile, setPreFaultProfile] = useState<
    LabProfileType | "keep_current"
  >("payment_latency_spike");

  // Report viewer state
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null);
  const [showReportModal, setShowReportModal] = useState<boolean>(false);

  const loadInvestigations = useCallback(async (selectId?: string) => {
    try {
      setError(null);
      const list = await fetchInvestigations();
      setInvestigations(list);
      const targetId = selectId || list[0]?.id;
      if (targetId) {
        const detail = await fetchInvestigationDetail(targetId);
        setActiveDetail(detail);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load causal investigations"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadInvestigations();
  }, [loadInvestigations]);

  const handleLaunchInvestigation = async (e: React.FormEvent) => {
    e.preventDefault();
    setLaunching(true);
    setError(null);
    try {
      if (preFaultProfile !== "keep_current") {
        await triggerLabWorkload({
          iterations: 3,
          profile: preFaultProfile,
        });
      }
      const created = await createInvestigation({
        system_slug: "origin-synthetic-lab",
        title,
        target_service_key: targetService,
        target_metric: "request_latency_ms",
        experiment_budget: budget,
        sample_size_per_arm: sampleSize,
        random_seed: randomSeed,
        timeout_seconds: 60,
        auto_run: true,
      });
      setActiveDetail(created);
      await loadInvestigations(created.id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to run investigation"
      );
    } finally {
      setLaunching(false);
    }
  };

  const handleCancel = async () => {
    if (!activeDetail) return;
    try {
      await cancelInvestigation(activeDetail.id);
      await loadInvestigations(activeDetail.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancellation failed");
    }
  };

  const handleExportReport = async (format: "markdown" | "json") => {
    if (!activeDetail) return;
    try {
      const exported = await exportInvestigationReport(activeDetail.id, format);
      if (format === "markdown") {
        setReportMarkdown(exported.markdown);
        setShowReportModal(true);
      } else {
        const blob = new Blob([JSON.stringify(exported.report, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `origin-investigation-${activeDetail.id.slice(0, 8)}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  };

  const handleDownloadMarkdownFile = () => {
    if (!reportMarkdown || !activeDetail) return;
    const blob = new Blob([reportMarkdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `origin-investigation-${activeDetail.id.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const completedStages = new Set(
    (activeDetail?.lifecycle_history_json || []).map((t) => t.to_state)
  );

  const handleTelemetryRefresh = useCallback(() => {
    if (!launching) {
      void loadInvestigations(activeDetail?.id);
    }
  }, [launching, loadInvestigations, activeDetail?.id]);

  return (
    <AppShell onTelemetryEvent={handleTelemetryRefresh}>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-[#E4DFD7] pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-slate-500">
              <Microscope className="w-3.5 h-3.5 text-[#0F1E36]" />
              <span>
                Milestone 02/05 · Autonomous Causal Scientist & Experimental
                Discovery
              </span>
            </div>
            <h1 className="font-serif text-2xl sm:text-3xl font-bold text-[#0F1E36] mt-1">
              Causal Investigation Laboratory
            </h1>
            <p className="text-xs sm:text-sm text-slate-600 mt-1 max-w-3xl">
              Autonomous root-cause discovery through real telemetry
              observation, competing causal hypothesis generation, seeded
              block-randomized interventions, and Welch two-sample statistical
              evaluation.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void loadInvestigations(activeDetail?.id)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-[#E4DFD7] bg-white text-xs font-medium text-[#0F1E36] hover:bg-[#F3EFEA] transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
            {activeDetail && (
              <>
                <button
                  type="button"
                  data-testid="export-markdown-btn"
                  onClick={() => void handleExportReport("markdown")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-[#E4DFD7] bg-white text-xs font-medium text-[#0F1E36] hover:bg-[#F3EFEA] transition-colors cursor-pointer"
                >
                  <FileText className="w-3.5 h-3.5" />
                  Scientific Report (.md)
                </button>
                <button
                  type="button"
                  data-testid="export-json-btn"
                  onClick={() => void handleExportReport("json")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-[#E4DFD7] bg-white text-xs font-medium text-[#0F1E36] hover:bg-[#F3EFEA] transition-colors cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export JSON
                </button>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="rounded border border-rose-300 bg-rose-50 px-4 py-3 text-xs text-rose-900 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Top Grid: Investigation Launcher + History Sidebar */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Launcher Form */}
          <form
            onSubmit={handleLaunchInvestigation}
            className="lg:col-span-8 bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-4"
          >
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
              <div className="flex items-center gap-2">
                <FlaskConical className="w-4 h-4 text-[#0F1E36]" />
                <h2 className="font-serif text-base font-bold text-[#0F1E36]">
                  Launch Autonomous Scientific Investigation
                </h2>
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                Deterministic Hypothesis + Seeded RCT Engine
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              <div className="sm:col-span-2">
                <label
                  htmlFor="inv-title"
                  className="block text-[11px] font-mono uppercase text-slate-600 mb-1"
                >
                  Investigation Title
                </label>
                <input
                  id="inv-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs border border-[#E4DFD7] rounded bg-[#FAF8F5] text-[#0F1E36] focus:outline-none focus:border-[#0F1E36]"
                />
              </div>

              <div>
                <label
                  htmlFor="inv-target-service"
                  className="block text-[11px] font-mono uppercase text-slate-600 mb-1"
                >
                  Symptom Target Service
                </label>
                <select
                  id="inv-target-service"
                  value={targetService}
                  onChange={(e) => setTargetService(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs font-mono border border-[#E4DFD7] rounded bg-[#FAF8F5] text-[#0F1E36]"
                >
                  <option value="checkout-service">checkout-service</option>
                  <option value="api-gateway">api-gateway</option>
                  <option value="payment-simulator">payment-simulator</option>
                  <option value="inventory-service">inventory-service</option>
                  <option value="order-database-sim">order-database-sim</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="inv-fault-stage"
                  className="block text-[11px] font-mono uppercase text-slate-600 mb-1"
                >
                  Stage Laboratory Condition
                </label>
                <select
                  id="inv-fault-stage"
                  data-testid="inv-fault-stage-select"
                  value={preFaultProfile}
                  onChange={(e) =>
                    setPreFaultProfile(
                      e.target.value as LabProfileType | "keep_current"
                    )
                  }
                  className="w-full px-2.5 py-1.5 text-xs font-mono border border-[#E4DFD7] rounded bg-[#FAF8F5] text-[#0F1E36]"
                >
                  <option value="payment_latency_spike">
                    Stage: Payment Latency Spike
                  </option>
                  <option value="db_lock_contention">
                    Stage: Database Lock Contention
                  </option>
                  <option value="inventory_cpu_throttling">
                    Stage: Inventory CPU Starvation
                  </option>
                  <option value="noisy_ambiguous_jitter">
                    Stage: Ambiguous Noise (Inconclusive)
                  </option>
                  <option value="normal">Stage: Healthy Baseline</option>
                  <option value="keep_current">Keep Current Lab State</option>
                </select>
              </div>

              <div className="grid grid-cols-3 gap-2 sm:col-span-2">
                <div>
                  <label
                    htmlFor="inv-budget"
                    className="block text-[11px] font-mono uppercase text-slate-600 mb-1"
                  >
                    Exp Budget
                  </label>
                  <input
                    id="inv-budget"
                    type="number"
                    min={1}
                    max={6}
                    value={budget}
                    onChange={(e) => setBudget(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 text-xs font-mono border border-[#E4DFD7] rounded bg-[#FAF8F5]"
                  />
                </div>
                <div>
                  <label
                    htmlFor="inv-samples"
                    className="block text-[11px] font-mono uppercase text-slate-600 mb-1"
                  >
                    Trials / Arm
                  </label>
                  <input
                    id="inv-samples"
                    type="number"
                    min={3}
                    max={12}
                    value={sampleSize}
                    onChange={(e) => setSampleSize(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 text-xs font-mono border border-[#E4DFD7] rounded bg-[#FAF8F5]"
                  />
                </div>
                <div>
                  <label
                    htmlFor="inv-seed"
                    className="block text-[11px] font-mono uppercase text-slate-600 mb-1"
                  >
                    RNG Seed
                  </label>
                  <input
                    id="inv-seed"
                    type="number"
                    min={1}
                    max={999999}
                    value={randomSeed}
                    onChange={(e) => setRandomSeed(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 text-xs font-mono border border-[#E4DFD7] rounded bg-[#FAF8F5]"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-[#E4DFD7]">
              <p className="text-[11px] text-slate-500">
                Only allowlisted interventions (
                <code className="font-mono text-[#0F1E36]">
                  isolate_payment_fastpath
                </code>
                ,{" "}
                <code className="font-mono text-[#0F1E36]">
                  relieve_db_lock_contention
                </code>
                ,{" "}
                <code className="font-mono text-[#0F1E36]">
                  scale_inventory_workers
                </code>
                ) are permitted.
              </p>
              <button
                type="submit"
                data-testid="launch-investigation-btn"
                disabled={launching}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded bg-[#0F1E36] text-[#FAF8F5] text-xs font-medium hover:bg-[#1B365D] disabled:opacity-50 transition-colors cursor-pointer"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                {launching
                  ? "Running Experiments..."
                  : "Launch Causal Investigation"}
              </button>
            </div>
          </form>

          {/* Investigation History Selector */}
          <div className="lg:col-span-4 bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3 mb-3">
                <h2 className="font-serif text-base font-bold text-[#0F1E36]">
                  Investigation Ledger
                </h2>
                <span className="text-[11px] font-mono text-slate-500">
                  {investigations.length} recorded
                </span>
              </div>
              {loading ? (
                <p className="text-xs text-slate-500 py-6 text-center">
                  Loading investigation ledger...
                </p>
              ) : investigations.length === 0 ? (
                <p className="text-xs text-slate-500 py-6 text-center">
                  No investigations executed yet. Launch your first autonomous
                  investigation on the left.
                </p>
              ) : (
                <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                  {investigations.map((inv) => {
                    const isSelected = activeDetail?.id === inv.id;
                    return (
                      <button
                        key={inv.id}
                        type="button"
                        onClick={() => void loadInvestigations(inv.id)}
                        className={`w-full text-left p-2.5 rounded border transition-colors cursor-pointer ${
                          isSelected
                            ? "border-[#0F1E36] bg-[#F3EFEA]/80"
                            : "border-[#E4DFD7] bg-[#FAF8F5] hover:bg-[#F3EFEA]/40"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-[#0F1E36] truncate">
                            {inv.title}
                          </span>
                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${getStatusBadgeStyle(
                              inv.status
                            )}`}
                          >
                            {inv.status}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 mt-1">
                          <span>
                            Cause:{" "}
                            <strong className="text-[#0F1E36]">
                              {inv.concluded_cause_service_key || "unresolved"}
                            </strong>
                          </span>
                          <span>
                            Exps: {inv.experiments_used}/{inv.experiment_budget}{" "}
                            · Seed {inv.random_seed}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="mt-3 pt-2 border-t border-[#E4DFD7] text-[11px] text-slate-500 flex items-center justify-between">
              <span>Epistemic Policy: Strict RCT Validation</span>
              <span className="font-mono">Observational Prior ≤ 0.65</span>
            </div>
          </div>
        </div>

        {/* Active Investigation Workspace */}
        {activeDetail && (
          <div className="space-y-6" data-testid="active-investigation-detail">
            {/* Lifecycle Progress Bar */}
            <div className="bg-white border border-[#E4DFD7] rounded-md p-4 shadow-2xs">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono uppercase tracking-wider text-slate-500">
                    Investigation Lifecycle
                  </span>
                  <span
                    data-testid="investigation-status-badge"
                    className={`text-[11px] font-mono font-semibold px-2 py-0.5 rounded border ${getStatusBadgeStyle(
                      activeDetail.status
                    )}`}
                  >
                    {activeDetail.status}
                  </span>
                  <span className="text-xs font-mono text-slate-500">
                    ID: {activeDetail.id.slice(0, 8)} · Seed{" "}
                    {activeDetail.random_seed} · Budget{" "}
                    {activeDetail.experiments_used}/
                    {activeDetail.experiment_budget}
                  </span>
                </div>
                {!["CONCLUDED", "INCONCLUSIVE", "FAILED", "CANCELLED"].includes(
                  activeDetail.status
                ) && (
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-rose-300 bg-rose-50 text-rose-900 text-xs font-medium hover:bg-rose-100 cursor-pointer"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    Cancel Investigation
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
                {LIFECYCLE_STAGES.map((stage, idx) => {
                  const isVisited =
                    completedStages.has(stage) ||
                    (stage === "CONCLUDED" &&
                      ["CONCLUDED", "INCONCLUSIVE", "CANCELLED", "FAILED"].includes(
                        activeDetail.status
                      ));
                  const displayStage =
                    stage === "CONCLUDED" &&
                    ["INCONCLUSIVE", "CANCELLED", "FAILED"].includes(
                      activeDetail.status
                    )
                      ? activeDetail.status
                      : stage;
                  return (
                    <div
                      key={stage}
                      className={`p-2 rounded border text-center transition-colors ${
                        isVisited
                          ? "bg-[#0F1E36] text-[#FAF8F5] border-[#0F1E36]"
                          : "bg-[#FAF8F5] text-slate-400 border-[#E4DFD7]"
                      }`}
                    >
                      <div className="text-[10px] font-mono opacity-75">
                        0{idx + 1}
                      </div>
                      <div className="text-[11px] font-mono font-semibold tracking-tight">
                        {displayStage}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Scientific Conclusion, Uncertainty & Causal Reasoning Graph */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Conclusion & Uncertainty Card */}
              <div className="lg:col-span-7 bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-4">
                <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
                  <div className="flex items-center gap-2">
                    {activeDetail.status === "CONCLUDED" ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                    ) : (
                      <HelpCircle className="w-4 h-4 text-amber-700" />
                    )}
                    <h3 className="font-serif text-base font-bold text-[#0F1E36]">
                      Scientific Conclusion & Epistemic Uncertainty
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#F3EFEA] text-[#0F1E36] border border-[#E4DFD7]">
                    Root Cause:{" "}
                    <strong data-testid="concluded-root-cause">
                      {activeDetail.concluded_cause_service_key ||
                        "Inconclusive"}
                    </strong>
                  </span>
                </div>

                <div className="p-3.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] space-y-2">
                  <div className="text-[11px] font-mono uppercase text-slate-500">
                    Validated Mechanism:{" "}
                    <span className="text-[#0F1E36] font-semibold">
                      {activeDetail.concluded_mechanism ||
                        "No single causal mechanism isolated"}
                    </span>
                  </div>
                  <p
                    data-testid="conclusion-summary-text"
                    className="text-xs sm:text-sm text-[#0F1E36] leading-relaxed"
                  >
                    {activeDetail.conclusion_summary ||
                      "Investigation has not yet produced a final conclusion."}
                  </p>
                </div>

                <div className="p-3.5 rounded bg-amber-50/60 border border-amber-200 space-y-1">
                  <div className="flex items-center gap-1.5 text-[11px] font-mono uppercase text-amber-900 font-semibold">
                    <ShieldAlert className="w-3.5 h-3.5" />
                    <span>Remaining Uncertainty & Methodological Scope</span>
                  </div>
                  <p className="text-xs text-amber-950 leading-relaxed">
                    {activeDetail.uncertainty_summary ||
                      "Confidence intervals and alternative explanations are bounded by the synthetic laboratory sample size."}
                  </p>
                </div>

                {/* Decision History Log */}
                {activeDetail.decision_history_json.length > 0 && (
                  <div className="space-y-1.5 pt-2">
                    <div className="text-[11px] font-mono uppercase text-slate-500">
                      Autonomous Investigator Decision Log
                    </div>
                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                      {activeDetail.decision_history_json.map((dec) => (
                        <div
                          key={`${dec.step}-${dec.phase}`}
                          className="text-xs font-mono p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7] flex items-start gap-2"
                        >
                          <span className="px-1.5 py-0.5 rounded bg-[#0F1E36] text-[#FAF8F5] text-[10px]">
                            Step {dec.step}
                          </span>
                          <div className="flex-1">
                            <span className="font-semibold text-[#0F1E36]">
                              [{dec.phase}]
                            </span>{" "}
                            <span className="text-slate-700">
                              {dec.rationale}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Causal Reasoning Propagation Chain */}
              <div className="lg:col-span-5 bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3 mb-4">
                    <div className="flex items-center gap-2">
                      <GitCommit className="w-4 h-4 text-[#0F1E36]" />
                      <h3 className="font-serif text-base font-bold text-[#0F1E36]">
                        Causal Propagation Graph
                      </h3>
                    </div>
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-[#F3EFEA] border border-[#E4DFD7]">
                      Intervention Verified
                    </span>
                  </div>

                  <div className="space-y-3">
                    {activeDetail.hypotheses.map((hyp) => {
                      const badge = formatHypothesisStatusBadge(hyp.status);
                      return (
                        <div
                          key={hyp.id}
                          className={`p-3 rounded border ${
                            hyp.status === "supported"
                              ? "border-emerald-400 bg-emerald-50/40"
                              : "border-[#E4DFD7] bg-[#FAF8F5]"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2 mb-1.5">
                            <span
                              className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${badge.badgeClass}`}
                            >
                              {badge.label}
                            </span>
                            <span className="text-xs font-mono font-bold text-[#0F1E36]">
                              Support: {(hyp.confidence_score * 100).toFixed(0)}
                              %
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-xs font-mono text-[#0F1E36]">
                            <span className="px-2 py-1 rounded bg-white border border-[#E4DFD7] font-semibold">
                              {hyp.root_cause_service_key}
                            </span>
                            <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                            <span className="text-[11px] text-slate-600 truncate">
                              {hyp.suspected_mechanism}
                            </span>
                            <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                            <span className="px-2 py-1 rounded bg-white border border-[#E4DFD7]">
                              {hyp.affected_service_key}
                            </span>
                          </div>
                          <div className="mt-1.5 text-[11px] font-mono text-slate-600 flex items-center justify-between">
                            <span>
                              Intervention:{" "}
                              <strong className="text-[#0F1E36]">
                                {hyp.recommended_intervention}
                              </strong>
                            </span>
                            <span>{hyp.score_interpretation}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#E4DFD7] text-[11px] text-slate-500">
                  Observational correlations never exceed{" "}
                  <strong className="text-[#0F1E36]">65%</strong> prior score.
                  Scores above 65% require statistically significant treatment
                  vs. control reduction.
                </div>
              </div>
            </div>

            {/* Competing Causal Hypotheses Section */}
            <div className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-4">
              <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#0F1E36]" />
                  <h2 className="font-serif text-base font-bold text-[#0F1E36]">
                    Competing Causal Hypotheses ({activeDetail.hypotheses.length}
                    )
                  </h2>
                </div>
                <span className="text-[11px] font-mono text-slate-500">
                  Ranked by Posterior Experimental Support
                </span>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {activeDetail.hypotheses.map((hyp: HypothesisRead) => {
                  const badge = formatHypothesisStatusBadge(hyp.status);
                  const initialPrior =
                    hyp.revision_history_json[0]?.score ??
                    hyp.revision_history_json[0]?.prior_score ??
                    hyp.confidence_score;
                  return (
                    <div
                      key={hyp.id}
                      data-testid={`hypothesis-card-${hyp.root_cause_service_key}`}
                      className="border border-[#E4DFD7] rounded p-4 bg-[#FAF8F5] space-y-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <span
                            className={`inline-block text-[10px] font-mono px-2 py-0.5 rounded border mb-1.5 ${badge.badgeClass}`}
                          >
                            {badge.label}
                          </span>
                          <h3 className="text-sm font-semibold text-[#0F1E36]">
                            {hyp.statement}
                          </h3>
                        </div>
                        <div className="text-right font-mono shrink-0">
                          <div className="text-sm font-bold text-[#0F1E36]">
                            {(hyp.confidence_score * 100).toFixed(1)}%
                          </div>
                          <div className="text-[10px] text-slate-500">
                            Prior: {(initialPrior * 100).toFixed(1)}%
                          </div>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono bg-white p-2.5 rounded border border-[#E4DFD7]">
                        <div>
                          <span className="text-slate-500">Suspected Node:</span>{" "}
                          <strong className="text-[#0F1E36]">
                            {hyp.root_cause_service_key}
                          </strong>
                        </div>
                        <div>
                          <span className="text-slate-500">Intervention:</span>{" "}
                          <strong className="text-[#0F1E36]">
                            {hyp.recommended_intervention}
                          </strong>
                        </div>
                        <div className="col-span-2">
                          <span className="text-slate-500">Mechanism:</span>{" "}
                          <span className="text-[#0F1E36]">
                            {hyp.suspected_mechanism}
                          </span>
                        </div>
                      </div>

                      {/* Supporting Observations */}
                      <div className="space-y-1">
                        <div className="text-[10px] font-mono uppercase text-emerald-800 font-semibold">
                          Supporting Observations (
                          {hyp.supporting_observations_json.length})
                        </div>
                        {hyp.supporting_observations_json.map((obs, i) => (
                          <div
                            key={i}
                            className="text-[11px] bg-white px-2.5 py-1.5 rounded border border-[#E4DFD7] text-slate-700"
                          >
                            <span className="font-mono font-semibold text-[#0F1E36]">
                              {obs.service_key}.{obs.metric_name} ={" "}
                              {obs.observed_value}
                              {obs.unit}
                            </span>{" "}
                            (baseline {obs.baseline_reference}
                            {obs.unit}) — {obs.note}
                          </div>
                        ))}
                      </div>

                      {/* Contradicting Observations & Alternative Explanations */}
                      {hyp.contradicting_observations_json.length > 0 && (
                        <div className="space-y-1">
                          <div className="text-[10px] font-mono uppercase text-rose-800 font-semibold">
                            Contradicting Observations
                          </div>
                          {hyp.contradicting_observations_json.map((obs, i) => (
                            <div
                              key={i}
                              className="text-[11px] bg-rose-50/50 px-2.5 py-1 rounded border border-rose-200 text-rose-950"
                            >
                              {obs.note}
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="text-[11px] text-slate-600 pt-1 border-t border-[#E4DFD7]">
                        <span className="font-mono uppercase text-[10px] text-slate-500">
                          Alternative Explanations:{" "}
                        </span>
                        {hyp.alternative_explanations_json.join(" · ")}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Controlled Experiment Runs & Treatment vs Control Charts */}
            <div className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-5">
              <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
                <div className="flex items-center gap-2">
                  <Scale className="w-4 h-4 text-[#0F1E36]" />
                  <h2 className="font-serif text-base font-bold text-[#0F1E36]">
                    Controlled Experiments & Treatment vs. Control Comparisons (
                    {activeDetail.experiment_runs.length})
                  </h2>
                </div>
                <span className="text-[11px] font-mono text-slate-500">
                  Block-Randomized Trial Execution · Welch Two-Sample t-Test
                </span>
              </div>

              {activeDetail.experiment_runs.length === 0 ? (
                <p className="text-xs text-slate-500 py-4">
                  No controlled experiments were required (system operated
                  within nominal baseline).
                </p>
              ) : (
                <div className="space-y-6">
                  {activeDetail.experiment_runs.map(
                    (run: ExperimentRunRead, idx: number) => {
                      const stats = run.metrics_summary_json;
                      const plan = activeDetail.experiment_plans.find(
                        (p) => p.id === run.experiment_id
                      );
                      const chartData = run.trial_observations_json.map(
                        (t) => ({
                          name: `T${t.trial_index + 1} (${
                            t.arm === "treatment" ? "TRT" : "CTL"
                          })`,
                          arm: t.arm,
                          targetLatency: t.target_metric_value_ms,
                          focalLatency: t.focal_service_latency_ms,
                          correlationId: t.correlation_id,
                        })
                      );

                      return (
                        <div
                          key={run.id}
                          data-testid={`experiment-run-card-${idx}`}
                          className="border border-[#E4DFD7] rounded-md p-4 bg-[#FAF8F5] space-y-4"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E4DFD7] pb-3">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#0F1E36] text-[#FAF8F5]">
                                  Experiment #{idx + 1}
                                </span>
                                <h3 className="text-sm font-bold text-[#0F1E36]">
                                  {plan?.name ||
                                    `Intervention: ${plan?.perturbation_type}`}
                                </h3>
                              </div>
                              <p className="text-[11px] text-slate-600 mt-0.5">
                                {plan?.selection_reason}
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <span
                                className={`text-xs font-mono px-2.5 py-1 rounded border font-semibold ${
                                  stats.is_statistically_significant
                                    ? "bg-emerald-50 text-emerald-900 border-emerald-300"
                                    : "bg-slate-100 text-slate-700 border-slate-300"
                                }`}
                              >
                                {stats.is_statistically_significant
                                  ? "STATISTICALLY SIGNIFICANT CAUSAL EFFECT"
                                  : "NO SIGNIFICANT INTERVENTION EFFECT"}
                              </span>
                            </div>
                          </div>

                          {/* Statistical Summary Metrics Strip */}
                          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
                            <div className="bg-white p-2.5 rounded border border-[#E4DFD7]">
                              <div className="text-[10px] font-mono uppercase text-slate-500">
                                Control Mean (n={stats.control_n})
                              </div>
                              <div className="text-sm font-mono font-bold text-slate-800 mt-0.5">
                                {stats.control_mean_ms.toFixed(1)} ms
                              </div>
                              <div className="text-[10px] font-mono text-slate-500">
                                SD ±{stats.control_std_ms.toFixed(1)} ms
                              </div>
                            </div>

                            <div className="bg-white p-2.5 rounded border border-[#E4DFD7]">
                              <div className="text-[10px] font-mono uppercase text-slate-500">
                                Treatment Mean (n={stats.treatment_n})
                              </div>
                              <div className="text-sm font-mono font-bold text-emerald-800 mt-0.5">
                                {stats.treatment_mean_ms.toFixed(1)} ms
                              </div>
                              <div className="text-[10px] font-mono text-slate-500">
                                SD ±{stats.treatment_std_ms.toFixed(1)} ms
                              </div>
                            </div>

                            <div className="bg-white p-2.5 rounded border border-[#E4DFD7]">
                              <div className="text-[10px] font-mono uppercase text-slate-500">
                                Effect Size (Δ)
                              </div>
                              <div className="text-sm font-mono font-bold text-[#0F1E36] mt-0.5">
                                {stats.absolute_effect_size_ms.toFixed(1)} ms (
                                {stats.relative_effect_pct.toFixed(1)}%)
                              </div>
                              <div className="text-[10px] font-mono text-slate-500">
                                Median Δ {stats.median_effect_size_ms.toFixed(1)}{" "}
                                ms
                              </div>
                            </div>

                            <div className="bg-white p-2.5 rounded border border-[#E4DFD7]">
                              <div className="text-[10px] font-mono uppercase text-slate-500">
                                95% Confidence Interval
                              </div>
                              <div className="text-xs font-mono font-bold text-[#0F1E36] mt-1">
                                [{stats.ci_lower_95_ms.toFixed(1)},{" "}
                                {stats.ci_upper_95_ms.toFixed(1)}] ms
                              </div>
                              <div className="text-[10px] font-mono text-slate-500">
                                SE {stats.standard_error_ms.toFixed(2)} ms
                              </div>
                            </div>

                            <div className="bg-white p-2.5 rounded border border-[#E4DFD7]">
                              <div className="text-[10px] font-mono uppercase text-slate-500">
                                Welch t-Statistic
                              </div>
                              <div className="text-sm font-mono font-bold text-[#0F1E36] mt-0.5">
                                t = {stats.welch_t_stat.toFixed(2)}
                              </div>
                              <div className="text-[10px] font-mono text-slate-500">
                                df = {stats.degrees_of_freedom.toFixed(1)}
                              </div>
                            </div>

                            <div className="bg-white p-2.5 rounded border border-[#E4DFD7]">
                              <div className="text-[10px] font-mono uppercase text-slate-500">
                                Standardized Effect
                              </div>
                              <div className="text-sm font-mono font-bold text-[#0F1E36] mt-0.5">
                                d = {stats.cohens_d.toFixed(2)}
                              </div>
                              <div className="text-[10px] font-mono text-slate-500">
                                Cohen&apos;s d
                              </div>
                            </div>
                          </div>

                          {/* Recharts Trial-by-Trial Comparison */}
                          <div className="bg-white p-3.5 rounded border border-[#E4DFD7]">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs font-mono font-semibold text-[#0F1E36]">
                                Block-Randomized Trial Sequence:{" "}
                                {run.assignment_order_json
                                  .map((a) => (a === "treatment" ? "T" : "C"))
                                  .join(" → ")}
                              </span>
                              <span className="text-[11px] font-mono text-slate-500">
                                Navy = Control (Fault Active) · Emerald =
                                Treatment (Intervention Active)
                              </span>
                            </div>
                            <div className="h-56 w-full">
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={chartData}>
                                  <CartesianGrid
                                    strokeDasharray="3 3"
                                    stroke="#E4DFD7"
                                  />
                                  <XAxis
                                    dataKey="name"
                                    tick={{ fontSize: 10 }}
                                  />
                                  <YAxis
                                    unit="ms"
                                    tick={{ fontSize: 10 }}
                                    width={55}
                                  />
                                  <Tooltip />
                                  <Legend wrapperStyle={{ fontSize: 11 }} />
                                  <Bar
                                    dataKey="targetLatency"
                                    name="Target Service Latency (ms)"
                                    radius={[3, 3, 0, 0]}
                                  >
                                    {chartData.map((entry, index) => (
                                      <Cell
                                        key={`cell-${index}`}
                                        fill={
                                          entry.arm === "treatment"
                                            ? "#059669"
                                            : "#0F1E36"
                                        }
                                      />
                                    ))}
                                  </Bar>
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        </div>
                      );
                    }
                  )}
                </div>
              )}
            </div>

            {/* Scientific Evidence Records */}
            <div className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-3">
              <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-[#0F1E36]" />
                  <h2 className="font-serif text-base font-bold text-[#0F1E36]">
                    Immutable Scientific Evidence Ledger (
                    {activeDetail.evidence_records.length})
                  </h2>
                </div>
                <span className="text-[11px] font-mono text-slate-500">
                  Trace-Correlated Experimental Artifacts
                </span>
              </div>

              <div className="space-y-2">
                {activeDetail.evidence_records.map((ev) => (
                  <div
                    key={ev.id}
                    className="p-3 rounded border border-[#E4DFD7] bg-[#FAF8F5] flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border ${
                            ev.direction === "supporting"
                              ? "bg-emerald-50 text-emerald-900 border-emerald-300"
                              : ev.direction === "contradicting"
                              ? "bg-rose-50 text-rose-900 border-rose-300"
                              : "bg-slate-100 text-slate-700 border-slate-300"
                          }`}
                        >
                          {ev.direction} · {ev.evidence_type}
                        </span>
                        <span className="text-[11px] font-mono text-slate-500">
                          Evidence ID: {ev.id.slice(0, 8)} · Corr:{" "}
                          {ev.correlation_id}
                        </span>
                      </div>
                      <p className="text-xs text-[#0F1E36] font-medium">
                        {ev.summary}
                      </p>
                    </div>
                    {ev.effect_size !== null && (
                      <div className="text-right font-mono text-xs shrink-0 bg-white px-3 py-1.5 rounded border border-[#E4DFD7]">
                        <div className="font-bold text-[#0F1E36]">
                          Δ {ev.effect_size.toFixed(1)} ms
                        </div>
                        <div className="text-[10px] text-slate-500">
                          95% CI [{ev.ci_lower?.toFixed(1)},{" "}
                          {ev.ci_upper?.toFixed(1)}] · N={ev.sample_size}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Scientific Report Markdown Modal */}
        {showReportModal && reportMarkdown && (
          <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
            <div className="bg-white border border-[#E4DFD7] rounded-md max-w-4xl w-full max-h-[85vh] flex flex-col shadow-xl">
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#E4DFD7]">
                <h3 className="font-serif text-base font-bold text-[#0F1E36]">
                  Reproducible Scientific Investigation Report
                </h3>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleDownloadMarkdownFile}
                    className="px-3 py-1 rounded bg-[#0F1E36] text-[#FAF8F5] text-xs font-medium cursor-pointer"
                  >
                    Download .md
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowReportModal(false)}
                    className="px-3 py-1 rounded border border-[#E4DFD7] text-xs font-medium cursor-pointer"
                  >
                    Close
                  </button>
                </div>
              </div>
              <pre
                data-testid="scientific-report-markdown"
                className="p-5 text-xs font-mono overflow-y-auto whitespace-pre-wrap text-[#0F1E36] bg-[#FAF8F5]"
              >
                {reportMarkdown}
              </pre>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
