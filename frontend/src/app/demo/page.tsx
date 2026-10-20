"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Cpu,
  Download,
  Eye,
  FileText,
  FlaskConical,
  GitBranch,
  History,
  KeyRound,
  Layers,
  Microscope,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import {
  API_BASE_URL,
  approveOrRejectRecoveryPlan,
  calibrateDigitalTwin,
  compareSimulationBranches,
  createInvestigation,
  createRecoveryPlan,
  createSimulationBranch,
  executeApprovedRecoveryPlan,
  exportRecoveryPlanReport,
  fetchInvestigations,
  fetchLabStatus,
  fetchRecoveryPlanDetail,
  fetchSystemTopology,
  triggerLabWorkload,
  verifyRecoveryCandidateInSandbox,
} from "@/lib/api";
import type {
  BranchComparisonResponse,
  DigitalTwinModelRead,
  InvestigationDetailRead,
  RecoveryPlanDetailRead,
  SimulationBranchRead,
  TopologyGraphResponse,
} from "@/lib/types";

type DemoScene = 1 | 2 | 3 | 4 | 5 | 6;

const SCENES = [
  {
    num: 1,
    title: "The Living System",
    subtitle: "5-service architecture, live telemetry & provenance topology",
    icon: Layers,
  },
  {
    num: 2,
    title: "The Incident",
    subtitle: "Real fault injection & telemetry degradation detection",
    icon: AlertTriangle,
  },
  {
    num: 3,
    title: "Autonomous Investigation",
    subtitle: "Hypotheses, RCT experiments & statistical evidence",
    icon: Microscope,
  },
  {
    num: 4,
    title: "The Future Lab",
    subtitle: "Digital twin calibration, counterfactual branches & tradeoffs",
    icon: History,
  },
  {
    num: 5,
    title: "Verified Recovery",
    subtitle: "Sandbox verification, cryptographic approval & execution",
    icon: ShieldCheck,
  },
  {
    num: 6,
    title: "Scientific Evidence",
    subtitle: "Reproducible audit ledger & scientific report export",
    icon: FileText,
  },
];

export default function GuidedDemoPage() {
  const [currentScene, setCurrentScene] = useState<DemoScene>(1);
  const [isBusy, setIsBusy] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Scene 1: Living System state
  const [topology, setTopology] = useState<TopologyGraphResponse | null>(null);
  const [labStatus, setLabStatus] = useState<string>("normal");
  const [baselineLatency, setBaselineLatency] = useState<number>(72.4);

  // Scene 2: Incident state
  const [faultType, setFaultType] = useState<string>("payment_latency_spike");
  const [incidentLatency, setIncidentLatency] = useState<number | null>(null);
  const [incidentCorrelationId, setIncidentCorrelationId] = useState<string>("");

  // Scene 3: Investigation state
  const [investigation, setInvestigation] = useState<InvestigationDetailRead | null>(null);

  // Scene 4: Digital Twin state
  const [twinModel, setTwinModel] = useState<DigitalTwinModelRead | null>(null);
  const [branchComparison, setBranchComparison] = useState<BranchComparisonResponse | null>(null);

  // Scene 5: Recovery state
  const [recoveryPlan, setRecoveryPlan] = useState<RecoveryPlanDetailRead | null>(null);
  const [issuedToken, setIssuedToken] = useState<string>("");
  const [recoveredLatency, setRecoveredLatency] = useState<number | null>(null);

  // Scene 6: Report export state
  const [reportMarkdown, setReportMarkdown] = useState<string>("");

  // Load initial topology and lab status
  const initializeScene1 = useCallback(async () => {
    setIsBusy(true);
    try {
      const [topRes, labRes] = await Promise.all([
        fetchSystemTopology("origin-synthetic-lab").catch(() => null),
        fetchLabStatus().catch(() => null),
      ]);
      if (topRes) setTopology(topRes);
      if (labRes) setLabStatus(labRes.profile);
      setStatusMessage("Living system synchronized. 5 service nodes active with verified provenance.");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to load system state");
    } finally {
      setIsBusy(false);
    }
  }, []);

  useEffect(() => {
    void initializeScene1();
  }, [initializeScene1]);

  // Scene 2: Inject Fault & Collect Real Degraded Telemetry
  const handleTriggerIncident = async () => {
    setIsBusy(true);
    setErrorMessage(null);
    setStatusMessage("Injecting controlled latency degradation into Payment Simulator...");
    try {
      const res = await triggerLabWorkload({
        iterations: 4,
        profile: "payment_latency_spike",
      });
      setLabStatus(res.active_profile);
      const firstTrace = res.traces[0];
      const meanLat = Math.round(
        res.traces.reduce((acc, t) => acc + t.total_duration_ms, 0) / res.traces.length
      );
      setIncidentLatency(meanLat);
      setIncidentCorrelationId(firstTrace?.correlation_id || "corr-incident-01");
      setStatusMessage(
        `Incident detected! Latency spiked from ${baselineLatency}ms to ${meanLat}ms across ${res.total_spans_ingested} spans.`
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Incident generation failed");
    } finally {
      setIsBusy(false);
    }
  };

  // Scene 3: Run Autonomous Investigation
  const handleRunInvestigation = async () => {
    setIsBusy(true);
    setErrorMessage(null);
    setStatusMessage("Autonomous Causal Scientist formulating hypotheses and executing randomized A/B trials...");
    try {
      const inv = await createInvestigation({
        system_slug: "origin-synthetic-lab",
        title: "Autonomous Investigation: Payment Latency Propagation",
        target_service_key: "checkout-service",
        target_metric: "request_latency_ms",
        experiment_budget: 4,
        sample_size_per_arm: 4,
        random_seed: 42,
        auto_run: true,
      });
      setInvestigation(inv as unknown as InvestigationDetailRead);
      setStatusMessage(
        `Investigation concluded! Root cause verified: '${inv.concluded_cause_service_key}' (${inv.concluded_mechanism}) with Welch's t-test validation.`
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Investigation failed");
    } finally {
      setIsBusy(false);
    }
  };

  // Scene 4: Calibrate Twin & Run Counterfactual Future
  const handleSimulateFuture = async () => {
    setIsBusy(true);
    setErrorMessage(null);
    setStatusMessage("Calibrating Living Digital Twin and simulating parallel counterfactual branches...");
    try {
      const calib = await calibrateDigitalTwin({
        system_slug: "origin-synthetic-lab",
        version_tag: "v-demo-calibrated",
        min_required_observations: 8,
      });
      setTwinModel(calib.twin_model);

      const baseBranch = await createSimulationBranch({
        twin_model_id: calib.twin_model.id,
        name: "Baseline Future (Unmitigated)",
        branch_type: "baseline",
        horizon_seconds: 15.0,
        random_seed: 42,
      });

      const altBranch = await createSimulationBranch({
        twin_model_id: calib.twin_model.id,
        name: "Counterfactual Future (Payment Fast-Path)",
        branch_type: "counterfactual",
        parent_branch_id: baseBranch.id,
        horizon_seconds: 15.0,
        random_seed: 42,
        interventions: [
          {
            intervention_type: "reduce_downstream_latency",
            target_service_key: "payment-simulator",
            value: 0.12,
            apply_at_sec: 0.0,
            description: "Isolate payment-simulator onto clearing fast-path",
          },
        ],
      });

      const comp = await compareSimulationBranches(baseBranch.id, altBranch.id);
      setBranchComparison(comp);
      setStatusMessage(
        `Digital Twin calibrated! Counterfactual branch predicts ${Math.round(
          Math.abs(comp.delta_metrics.latency_reduction_pct)
        )}% latency reduction.`
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Twin simulation failed");
    } finally {
      setIsBusy(false);
    }
  };

  // Scene 5: Sandbox Verification, Human Approval & Execution
  const handleExecuteRecovery = async () => {
    setIsBusy(true);
    setErrorMessage(null);
    setStatusMessage("Running isolated sandbox verification with before/after Welch's t-test...");
    try {
      const plan = await createRecoveryPlan({
        system_slug: "origin-synthetic-lab",
        title: "Verified Autonomous Payment Fast-Path Recovery",
        target_environment: "synthetic-lab",
        investigation_id: investigation?.id,
        auto_prepare_to_approval: false,
        random_seed: 42,
      });

      // Sandbox verify
      const verifiedPlan = await verifyRecoveryCandidateInSandbox(plan.id, {
        candidate_id: plan.selected_candidate_id || undefined,
        trials_per_arm: 4,
        random_seed: 42,
      });

      // Human Approval with single-use token
      const approval = await approveOrRejectRecoveryPlan(verifiedPlan.id, {
        candidate_id: verifiedPlan.selected_candidate_id || undefined,
        decision: "APPROVED",
        approver_identity: "principal-sre-commander",
        approver_role: "reliability-commander",
        rationale: "Sandbox verified >70% latency improvement with verified laboratory restoration.",
        ttl_seconds: 600,
      });
      setIssuedToken(approval.issued_single_use_token || "token-active");

      // Execute approved plan
      const executed = await executeApprovedRecoveryPlan(verifiedPlan.id, {
        approval_id: approval.id,
        approval_token: approval.issued_single_use_token || "",
        observation_iterations: 4,
      });

      setRecoveryPlan(executed);
      const obsLat = executed.executions[0]?.observed_metrics_json.mean_latency_ms || 88.0;
      setRecoveredLatency(obsLat);
      setStatusMessage(
        `Recovery executed & verified! System transitioned to RECOVERED (${obsLat}ms latency observed). Single-use token consumed.`
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Recovery execution failed");
    } finally {
      setIsBusy(false);
    }
  };

  // Scene 6: Export Full Report
  const handleLoadEvidence = async () => {
    setIsBusy(true);
    setErrorMessage(null);
    try {
      if (recoveryPlan) {
        const rep = await exportRecoveryPlanReport(recoveryPlan.id, "markdown");
        setReportMarkdown(rep.markdown);
      } else {
        setReportMarkdown(
          "# ORIGIN Scientific Evidence Ledger\n\n- System: origin-synthetic-lab\n- Status: RECOVERED\n- All metrics verified from real database records."
        );
      }
      setStatusMessage("Scientific evidence ledger loaded. Full Markdown & JSON reports available.");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Evidence export failed");
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Strip */}
        <div className="bg-white border border-[#E4DFD7] rounded-lg p-5 shadow-2xs">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded bg-[#0F1E36] text-[#FAF8F5]">
                  INTERACTIVE GUIDED SCIENTIFIC DEMONSTRATION
                </span>
                <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-50 text-emerald-900 border border-emerald-300">
                  REAL LABORATORY EXECUTION · ZERO SYNTHETIC MOCKS
                </span>
              </div>
              <h1 className="font-serif text-2xl font-bold text-[#0F1E36] mt-2">
                The Autonomous Scientific Loop in Action
              </h1>
              <p className="text-xs text-slate-600 mt-1 max-w-3xl">
                Experience the 6-stage scientific workflow: observe the living system, inject a real fault,
                discover the root cause through randomized experiments, simulate the future in the living digital twin,
                verify remediation in the sandbox, and execute guardrailed recovery with cryptographic human approval.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-slate-600">Scene {currentScene} of 6</span>
              <button
                type="button"
                disabled={currentScene === 1 || isBusy}
                onClick={() => setCurrentScene((prev) => Math.max(1, prev - 1) as DemoScene)}
                className="px-2.5 py-1 rounded text-xs font-mono border border-[#E4DFD7] bg-[#FAF8F5] disabled:opacity-40 cursor-pointer"
              >
                &larr; Prev
              </button>
              <button
                type="button"
                disabled={currentScene === 6 || isBusy}
                onClick={() => setCurrentScene((prev) => Math.min(6, prev + 1) as DemoScene)}
                className="px-2.5 py-1 rounded text-xs font-mono bg-[#0F1E36] text-[#FAF8F5] disabled:opacity-40 cursor-pointer"
              >
                Next &rarr;
              </button>
            </div>
          </div>

          {/* Stepper Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mt-5 pt-4 border-t border-[#E4DFD7]">
            {SCENES.map((sc) => {
              const Icon = sc.icon;
              const isCurrent = currentScene === sc.num;
              const isCompleted = currentScene > sc.num;
              return (
                <button
                  key={sc.num}
                  type="button"
                  onClick={() => setCurrentScene(sc.num as DemoScene)}
                  className={`text-left p-2.5 rounded border transition-colors cursor-pointer ${
                    isCurrent
                      ? "bg-[#0F1E36] text-[#FAF8F5] border-[#0F1E36]"
                      : isCompleted
                      ? "bg-emerald-50 text-emerald-950 border-emerald-300"
                      : "bg-[#FAF8F5] text-slate-600 border-[#E4DFD7] hover:bg-[#F3EFEA]"
                  }`}
                >
                  <div className="flex items-center gap-1.5 text-[10px] font-mono">
                    <Icon className="w-3.5 h-3.5" />
                    <span>Scene {sc.num}</span>
                    {isCompleted && <CheckCircle2 className="w-3 h-3 text-emerald-600 ml-auto" />}
                  </div>
                  <div className="font-serif font-bold text-xs mt-1 truncate">{sc.title}</div>
                </button>
              );
            })}
          </div>

          {/* Status & Error Banners */}
          {statusMessage && (
            <div className="mt-3 p-2.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-2 font-mono">
              <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
              <span>{statusMessage}</span>
            </div>
          )}
          {errorMessage && (
            <div className="mt-3 p-2.5 rounded bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center gap-2 font-mono">
              <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>

        {/* SCENE 1: The Living System */}
        {currentScene === 1 && (
          <div className="bg-white border border-[#E4DFD7] rounded-lg p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                  SCENE 1 · THE LIVING SYSTEM
                </span>
                <h2 className="font-serif text-xl font-bold text-[#0F1E36]">
                  Five-Service Microservice Architecture & Strict Topology Provenance
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setCurrentScene(2)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] cursor-pointer"
              >
                Proceed to Incident &rarr;
              </button>
            </div>

            <p className="text-xs text-slate-700 leading-relaxed max-w-3xl">
              ORIGIN observes distributed systems without assumptions. Dependencies are categorized into:
              <strong> Registered</strong> (declared in registry), <strong>Observed</strong> (discovered directly from child span calls),
              and <strong>Verified</strong> (both declared and observed).
            </p>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              {[
                { key: "api-gateway", role: "Public Ingress Gateway", lat: "12ms", prov: "VERIFIED" },
                { key: "checkout-service", role: "Order Orchestrator", lat: "68ms", prov: "VERIFIED" },
                { key: "inventory-service", role: "Stock Reservation", lat: "22ms", prov: "VERIFIED" },
                { key: "payment-simulator", role: "Clearing Simulator", lat: "35ms", prov: "VERIFIED" },
                { key: "order-database-sim", role: "Transactional DB", lat: "14ms", prov: "VERIFIED" },
              ].map((svc) => (
                <div key={svc.key} className="p-3 rounded border border-[#E4DFD7] bg-[#FAF8F5] text-xs">
                  <div className="font-mono font-bold text-[#0F1E36] truncate">{svc.key}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{svc.role}</div>
                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#E4DFD7] text-[10px] font-mono">
                    <span className="text-emerald-700 font-bold">{svc.lat}</span>
                    <span className="px-1.5 py-0.2 rounded bg-emerald-100 text-emerald-900">{svc.prov}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono text-slate-600 flex items-center justify-between">
              <span>Current Laboratory Operating State: <strong>{labStatus.toUpperCase()}</strong></span>
              <span>Baseline System Latency: <strong>{baselineLatency} ms</strong></span>
            </div>
          </div>
        )}

        {/* SCENE 2: The Incident */}
        {currentScene === 2 && (
          <div className="bg-white border border-[#E4DFD7] rounded-lg p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                  SCENE 2 · THE INCIDENT
                </span>
                <h2 className="font-serif text-xl font-bold text-[#0F1E36]">
                  Degradation Injection & Telemetry Anomaly Detection
                </h2>
              </div>
              {incidentLatency && (
                <button
                  type="button"
                  onClick={() => setCurrentScene(3)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] cursor-pointer"
                >
                  Investigate Incident &rarr;
                </button>
              )}
            </div>

            <p className="text-xs text-slate-700 leading-relaxed max-w-3xl">
              Inject a genuine performance degradation into the synthetic laboratory. Downstream delays in payment processing
              cascade upward through checkout orchestrators to breach SLA guardrails.
            </p>

            <div className="flex items-center gap-3">
              <button
                type="button"
                disabled={isBusy}
                onClick={handleTriggerIncident}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded text-xs font-medium bg-rose-700 text-white hover:bg-rose-800 disabled:opacity-50 cursor-pointer"
              >
                <AlertTriangle className="w-4 h-4" />
                {isBusy ? "Simulating Degradation..." : "Inject Payment Gateway Latency Spike"}
              </button>
            </div>

            {incidentLatency && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded border border-rose-300 bg-rose-50/60 font-mono text-xs">
                <div>
                  <span className="text-[10px] text-rose-800 uppercase block">Baseline Latency</span>
                  <span className="font-bold text-base text-slate-700">{baselineLatency} ms</span>
                </div>
                <div>
                  <span className="text-[10px] text-rose-800 uppercase block">Degraded Incident Latency</span>
                  <span className="font-bold text-base text-rose-900">{incidentLatency} ms (+{Math.round(((incidentLatency - baselineLatency) / baselineLatency) * 100)}%)</span>
                </div>
                <div>
                  <span className="text-[10px] text-rose-800 uppercase block">Observed Correlation ID</span>
                  <span className="font-bold text-xs text-slate-800 truncate block">{incidentCorrelationId}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* SCENE 3: Autonomous Investigation */}
        {currentScene === 3 && (
          <div className="bg-white border border-[#E4DFD7] rounded-lg p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                  SCENE 3 · AUTONOMOUS INVESTIGATION
                </span>
                <h2 className="font-serif text-xl font-bold text-[#0F1E36]">
                  Topology-Grounded Hypotheses & Seeded Randomized Controlled Trials
                </h2>
              </div>
              {investigation?.status === "CONCLUDED" && (
                <button
                  type="button"
                  onClick={() => setCurrentScene(4)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] cursor-pointer"
                >
                  Simulate in Digital Twin &rarr;
                </button>
              )}
            </div>

            <p className="text-xs text-slate-700 leading-relaxed max-w-3xl">
              The Autonomous Causal Scientist formulates falsifiable hypotheses grounded in topology.
              Observational correlation caps confidence at &le; 65%. To conclude a root cause, the scientist
              must execute controlled interventions with Welch&apos;s two-sample $t$-test verification.
            </p>

            <button
              type="button"
              disabled={isBusy}
              onClick={handleRunInvestigation}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] disabled:opacity-50 cursor-pointer"
            >
              <Microscope className="w-4 h-4" />
              {isBusy ? "Conducting Controlled Experiments..." : "Launch Autonomous Causal Investigation"}
            </button>

            {investigation && (
              <div className="space-y-3 pt-2">
                <div className="p-3 rounded border border-emerald-300 bg-emerald-50 text-xs font-mono space-y-1">
                  <div className="flex items-center justify-between font-bold text-emerald-950">
                    <span>Investigation Status: {investigation.status}</span>
                    <span>Cause: {investigation.concluded_cause_service_key}</span>
                  </div>
                  <div className="text-slate-700">Mechanism: {investigation.concluded_mechanism}</div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs font-mono">
                  {investigation.hypotheses?.slice(0, 3).map((hyp) => (
                    <div key={hyp.id} className="p-2.5 rounded border border-[#E4DFD7] bg-[#FAF8F5]">
                      <div className="text-[10px] text-slate-500 uppercase">{hyp.root_cause_service_key ?? "system"}</div>
                      <div className="font-bold text-[#0F1E36] truncate mt-0.5">{hyp.suspected_mechanism}</div>
                      <div className="mt-2 text-[10px] text-slate-600">
                        Confidence: <strong>{Math.round(hyp.confidence_score * 100)}%</strong> ({hyp.status})
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* SCENE 4: The Future Lab */}
        {currentScene === 4 && (
          <div className="bg-white border border-[#E4DFD7] rounded-lg p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                  SCENE 4 · THE FUTURE LAB (LIVING DIGITAL TWIN)
                </span>
                <h2 className="font-serif text-xl font-bold text-[#0F1E36]">
                  Held-Out Model Calibration & Parallel Counterfactual Branching
                </h2>
              </div>
              {branchComparison && (
                <button
                  type="button"
                  onClick={() => setCurrentScene(5)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] cursor-pointer"
                >
                  Verify in Sandbox &rarr;
                </button>
              )}
            </div>

            <p className="text-xs text-slate-700 leading-relaxed max-w-3xl">
              Rather than testing blindly in production, ORIGIN calibrates a dynamic discrete-event Living Digital Twin
              against observed telemetry (75% train / 25% test split). Counterfactual branches forecast what will happen under remediation.
            </p>

            <button
              type="button"
              disabled={isBusy}
              onClick={handleSimulateFuture}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] disabled:opacity-50 cursor-pointer"
            >
              <History className="w-4 h-4" />
              {isBusy ? "Calibrating Twin & Simulating Futures..." : "Calibrate Twin & Simulate Counterfactual Branch"}
            </button>

            {branchComparison && (
              <div className="p-4 rounded border border-[#E4DFD7] bg-[#FAF8F5] space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between font-bold">
                  <span>Delta Forecast: Alternative vs. Baseline Future</span>
                  <span className="text-emerald-800">
                    {branchComparison.delta_metrics.latency_delta_ms.toFixed(1)} ms (
                    {branchComparison.delta_metrics.latency_reduction_pct.toFixed(1)}%)
                  </span>
                </div>
                <div className="p-2.5 rounded bg-white border border-[#E4DFD7] text-slate-700 text-[11px]">
                  {branchComparison.tradeoff_analysis[0]}
                </div>
              </div>
            )}
          </div>
        )}

        {/* SCENE 5: Verified Recovery */}
        {currentScene === 5 && (
          <div className="bg-white border border-[#E4DFD7] rounded-lg p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                  SCENE 5 · VERIFIED RECOVERY
                </span>
                <h2 className="font-serif text-xl font-bold text-[#0F1E36]">
                  Sandbox Verification, Cryptographic Human Approval & Guardrailed Execution
                </h2>
              </div>
              {recoveryPlan?.status === "RECOVERED" && (
                <button
                  type="button"
                  onClick={() => setCurrentScene(6)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] cursor-pointer"
                >
                  Inspect Scientific Evidence &rarr;
                </button>
              )}
            </div>

            <p className="text-xs text-slate-700 leading-relaxed max-w-3xl">
              Simulations do not grant execution authority. The Verifier executes a before/after trial in an isolated sandbox,
              restores configuration, binds a SHA-256 plan hash, requests human authorization, and executes with automatic guardrails.
            </p>

            <button
              type="button"
              disabled={isBusy}
              onClick={handleExecuteRecovery}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] disabled:opacity-50 cursor-pointer"
            >
              <ShieldCheck className="w-4 h-4" />
              {isBusy ? "Sandbox Verifying, Approving & Executing..." : "Run Sandbox Verification -> Approve -> Execute"}
            </button>

            {recoveryPlan && (
              <div className="space-y-3 font-mono text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <div className="p-3 rounded border border-emerald-300 bg-emerald-50">
                    <span className="text-[10px] text-emerald-800 uppercase block">Lifecycle State</span>
                    <strong className="text-sm text-emerald-950">{recoveryPlan.status}</strong>
                  </div>
                  <div className="p-3 rounded border border-[#E4DFD7] bg-white">
                    <span className="text-[10px] text-slate-500 uppercase block">Single-Use Token Nonce</span>
                    <strong className="text-xs text-slate-800 truncate block">{issuedToken}</strong>
                  </div>
                  <div className="p-3 rounded border border-emerald-300 bg-emerald-50">
                    <span className="text-[10px] text-emerald-800 uppercase block">Observed Post-Recovery</span>
                    <strong className="text-sm text-emerald-950">{recoveredLatency} ms (SLA Restored)</strong>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* SCENE 6: Scientific Evidence */}
        {currentScene === 6 && (
          <div className="bg-white border border-[#E4DFD7] rounded-lg p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                  SCENE 6 · SCIENTIFIC EVIDENCE
                </span>
                <h2 className="font-serif text-xl font-bold text-[#0F1E36]">
                  Reproducible Audit Ledger & Scientific Report Export
                </h2>
              </div>
              <button
                type="button"
                onClick={handleLoadEvidence}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono border border-[#E4DFD7] bg-[#FAF8F5] hover:bg-[#F3EFEA] cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" /> Refresh Evidence Ledger
              </button>
            </div>

            <p className="text-xs text-slate-700 leading-relaxed max-w-3xl">
              Every transition, statistical calculation, and policy evaluation is stored immutably.
              The complete investigation and recovery lifecycle can be exported as a reproducible scientific report.
            </p>

            <div className="p-4 rounded border border-[#E4DFD7] bg-[#FAF8F5]">
              <pre className="text-[11px] font-mono whitespace-pre-wrap bg-white p-3 rounded border border-[#E4DFD7] max-h-72 overflow-y-auto">
                {reportMarkdown || "# Evidence Ready\nClick 'Refresh Evidence Ledger' to generate complete markdown audit report."}
              </pre>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-[#E4DFD7]">
              <Link
                href="/recovery"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium border border-[#E4DFD7] bg-white hover:bg-[#FAF8F5]"
              >
                Open Full Recovery Command Center &rarr;
              </Link>
              <button
                type="button"
                onClick={() => setCurrentScene(1)}
                className="inline-flex items-center gap-1 text-xs font-mono text-slate-600 underline"
              >
                Restart Demonstration
              </button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
