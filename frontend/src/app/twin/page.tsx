"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  BookOpen,
  Camera,
  CheckCircle2,
  Clock,
  Download,
  FastForward,
  FileText,
  FlaskConical,
  GitBranch,
  History,
  Layers,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  Sliders,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import {
  calibrateDigitalTwin,
  compareSimulationBranches,
  createSimulationBranch,
  createSimulationSnapshot,
  exportSimulationBranchReport,
  fetchDigitalTwins,
  fetchScientificMemory,
  fetchSimulationBranches,
  fetchSimulationSnapshots,
  fetchTwinCalibrations,
  runDigitalTwinBenchmarks,
  triggerLabWorkload,
} from "@/lib/api";
import type {
  BranchComparisonResponse,
  CalibrationRunRead,
  DigitalTwinModelRead,
  LabProfileType,
  ScientificMemoryEntryRead,
  SimulationBenchmarkSuiteResponse,
  SimulationBranchRead,
  SimulationSnapshotRead,
  TwinInterventionType,
} from "@/lib/types";

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  "api-gateway": { x: 40, y: 120 },
  "checkout-service": { x: 290, y: 120 },
  "inventory-service": { x: 560, y: 20 },
  "payment-simulator": { x: 560, y: 130 },
  "order-database-sim": { x: 560, y: 240 },
};

const EDGES_CONFIG: Array<{ source: string; target: string }> = [
  { source: "api-gateway", target: "checkout-service" },
  { source: "checkout-service", target: "inventory-service" },
  { source: "checkout-service", target: "payment-simulator" },
  { source: "checkout-service", target: "order-database-sim" },
  { source: "inventory-service", target: "order-database-sim" },
];

export default function DigitalTwinWorkspacePage() {
  const [twins, setTwins] = useState<DigitalTwinModelRead[]>([]);
  const [selectedTwin, setSelectedTwin] = useState<DigitalTwinModelRead | null>(
    null
  );
  const [calibrationRun, setCalibrationRun] =
    useState<CalibrationRunRead | null>(null);
  const [snapshots, setSnapshots] = useState<SimulationSnapshotRead[]>([]);
  const [branches, setBranches] = useState<SimulationBranchRead[]>([]);
  const [baselineBranch, setBaselineBranch] =
    useState<SimulationBranchRead | null>(null);
  const [activeBranch, setActiveBranch] = useState<SimulationBranchRead | null>(
    null
  );
  const [comparison, setComparison] =
    useState<BranchComparisonResponse | null>(null);
  const [memoryEntries, setMemoryEntries] = useState<
    ScientificMemoryEntryRead[]
  >([]);
  const [benchmarkSuite, setBenchmarkSuite] =
    useState<SimulationBenchmarkSuiteResponse | null>(null);

  // Time Machine playback state
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string>("");

  // Calibration & Branch Builder Controls
  const [calibProfile, setCalibProfile] = useState<LabProfileType>(
    "payment_latency_spike"
  );
  const [branchName, setBranchName] = useState<string>(
    "Counterfactual: Fast-Path Payment Isolation"
  );
  const [interventionType, setInterventionType] =
    useState<TwinInterventionType>("reduce_downstream_latency");
  const [targetService, setTargetService] =
    useState<string>("payment-simulator");
  const [interventionValue, setInterventionValue] = useState<number>(0.15);
  const [applyAtSec, setApplyAtSec] = useState<number>(2.0);
  const [randomSeed, setRandomSeed] = useState<number>(42);
  const [horizonSeconds, setHorizonSeconds] = useState<number>(20);

  // Loading & modal states
  const [isBusy, setIsBusy] = useState<boolean>(false);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);
  const [exportedMarkdown, setExportedMarkdown] = useState<string | null>(null);

  const loadWorkspaceData = useCallback(async (preferredTwinId?: string) => {
    try {
      const [twinList, memList] = await Promise.all([
        fetchDigitalTwins(),
        fetchScientificMemory(),
      ]);
      setTwins(twinList);
      setMemoryEntries(memList);

      const targetTwin =
        twinList.find((t) => t.id === preferredTwinId) || twinList[0] || null;
      if (targetTwin) {
        setSelectedTwin(targetTwin);
        const [cals, snaps, brs] = await Promise.all([
          fetchTwinCalibrations(targetTwin.id),
          fetchSimulationSnapshots(targetTwin.id),
          fetchSimulationBranches(targetTwin.id),
        ]);
        setCalibrationRun(cals[0] || null);
        setSnapshots(snaps);
        if (snaps[0]) {
          setSelectedSnapshotId(snaps[0].id);
        }
        setBranches(brs);

        const baseBr =
          brs.find((b) => b.branch_type === "baseline") ||
          brs[brs.length - 1] ||
          null;
        const altBr =
          brs.find((b) => b.id !== baseBr?.id) || baseBr || null;
        setBaselineBranch(baseBr);
        setActiveBranch(altBr);

        if (baseBr && altBr && baseBr.id !== altBr.id) {
          const comp = await compareSimulationBranches(baseBr.id, altBr.id);
          setComparison(comp);
        } else {
          setComparison(null);
        }
      }
    } catch {
      /* ignore initial empty state */
    }
  }, []);

  useEffect(() => {
    loadWorkspaceData();
  }, [loadWorkspaceData]);

  // Time Machine playback timer
  const trajectory = useMemo(
    () => activeBranch?.trajectory_json || [],
    [activeBranch]
  );
  const maxStepIndex = Math.max(0, trajectory.length - 1);

  useEffect(() => {
    if (!isPlaying || maxStepIndex === 0) return;
    const intervalMs = Math.max(150, Math.round(650 / playbackSpeed));
    const timer = setInterval(() => {
      setCurrentStepIndex((prev) => {
        if (prev >= maxStepIndex) {
          setIsPlaying(false);
          return maxStepIndex;
        }
        return prev + 1;
      });
    }, intervalMs);
    return () => clearInterval(timer);
  }, [isPlaying, maxStepIndex, playbackSpeed]);

  // Handle Calibrate + Baseline Run
  const handleCalibrateAndInitialize = async () => {
    setIsBusy(true);
    setStatusBanner(
      `Emitting Synthetic Lab observations (${calibProfile}) and calibrating Digital Twin with 75%/25% held-out validation...`
    );
    try {
      await triggerLabWorkload({ iterations: 5, profile: calibProfile });
      const calRes = await calibrateDigitalTwin({
        system_slug: "origin-synthetic-lab",
        min_required_observations: 12,
      });
      const twinId = calRes.twin_model.id;
      const snap = await createSimulationSnapshot({
        twin_model_id: twinId,
        step_index: 0,
        label: `Initial Calibrated Snapshot (${calibProfile}, t=0s)`,
        random_seed: randomSeed,
      });
      const baseBr = await createSimulationBranch({
        twin_model_id: twinId,
        name: `Baseline Trajectory (${calibProfile})`,
        branch_type: "baseline",
        initial_snapshot_id: snap.id,
        random_seed: randomSeed,
        horizon_seconds: horizonSeconds,
      });
      setSelectedSnapshotId(snap.id);
      setCurrentStepIndex(0);
      await loadWorkspaceData(twinId);
      setBaselineBranch(baseBr);
      setActiveBranch(baseBr);
      setStatusBanner(
        `Calibrated ${calRes.twin_model.version_tag} (Held-Out MAE: ${calRes.calibration_run.mae_ms}ms, RMSE: ${calRes.calibration_run.rmse_ms}ms)`
      );
    } catch (err) {
      setStatusBanner(
        err instanceof Error ? err.message : "Calibration failed"
      );
    } finally {
      setIsBusy(false);
    }
  };

  // Capture Snapshot at current step
  const handleCaptureSnapshot = async () => {
    if (!selectedTwin) return;
    setIsBusy(true);
    try {
      const snap = await createSimulationSnapshot({
        twin_model_id: selectedTwin.id,
        branch_id: activeBranch?.id,
        step_index: currentStepIndex,
        label: `Checkpoint t=${currentStepIndex}s (${
          activeBranch?.name || "Twin"
        })`,
        random_seed: randomSeed,
      });
      const updatedSnaps = await fetchSimulationSnapshots(selectedTwin.id);
      setSnapshots(updatedSnaps);
      setSelectedSnapshotId(snap.id);
      setStatusBanner(
        `Captured deterministic state snapshot "${snap.label}" at t=${snap.sim_clock_sec}s`
      );
    } catch (err) {
      setStatusBanner(
        err instanceof Error ? err.message : "Snapshot capture failed"
      );
    } finally {
      setIsBusy(false);
    }
  };

  // Rewind to selected snapshot
  const handleRewindToSnapshot = () => {
    const snap = snapshots.find((s) => s.id === selectedSnapshotId);
    if (!snap) {
      setCurrentStepIndex(0);
      setIsPlaying(false);
      return;
    }
    setIsPlaying(false);
    setCurrentStepIndex(Math.min(maxStepIndex, snap.step_index));
    setStatusBanner(
      `Rewound Time Machine clock to snapshot "${snap.label}" (t=${snap.sim_clock_sec}s, Seed ${snap.random_seed})`
    );
  };

  // Launch Counterfactual Branch
  const handleRunCounterfactualBranch = async () => {
    if (!selectedTwin) return;
    setIsBusy(true);
    setStatusBanner(
      `Executing Counterfactual Branch "${branchName}" (${interventionType} on ${targetService})...`
    );
    try {
      const newBr = await createSimulationBranch({
        twin_model_id: selectedTwin.id,
        name: branchName,
        branch_type: "counterfactual",
        parent_branch_id: baselineBranch?.id,
        initial_snapshot_id: selectedSnapshotId || undefined,
        random_seed: randomSeed,
        horizon_seconds: horizonSeconds,
        interventions: [
          {
            intervention_type: interventionType,
            target_service_key: targetService,
            value: interventionValue,
            apply_at_sec: applyAtSec,
            description: `${interventionType} (${interventionValue}) on ${targetService} at t=${applyAtSec}s`,
          },
        ],
      });
      const brs = await fetchSimulationBranches(selectedTwin.id);
      setBranches(brs);
      setActiveBranch(newBr);
      setCurrentStepIndex(0);
      if (baselineBranch) {
        const comp = await compareSimulationBranches(
          baselineBranch.id,
          newBr.id
        );
        setComparison(comp);
      }
      const mem = await fetchScientificMemory();
      setMemoryEntries(mem);
      setStatusBanner(
        `Completed Counterfactual Branch "${newBr.name}" — Mean Latency: ${newBr.outcome_summary_json.mean_latency_ms}ms`
      );
    } catch (err) {
      setStatusBanner(
        err instanceof Error ? err.message : "Counterfactual simulation failed"
      );
    } finally {
      setIsBusy(false);
    }
  };

  // Run all 4 Canonical Digital Twin Benchmarks
  const handleRunBenchmarkSuite = async () => {
    setIsBusy(true);
    setStatusBanner(
      "Executing all 4 Canonical Milestone 03/05 Digital Twin Benchmarks (A: Payment, B: DB Contention, C: Surge, D: Circuit Breaker)..."
    );
    try {
      const suite = await runDigitalTwinBenchmarks(2026);
      setBenchmarkSuite(suite);
      await loadWorkspaceData(suite.benchmarks[0]?.twin_model_id);
      setStatusBanner(
        `Benchmark Suite Complete: ${suite.passed_count}/${suite.total_benchmarks} scientific benchmarks verified.`
      );
    } catch (err) {
      setStatusBanner(
        err instanceof Error ? err.message : "Benchmark suite execution failed"
      );
    } finally {
      setIsBusy(false);
    }
  };

  // Export Markdown Report
  const handleExportReport = async () => {
    if (!activeBranch) return;
    try {
      const res = await exportSimulationBranchReport(
        activeBranch.id,
        baselineBranch && baselineBranch.id !== activeBranch.id
          ? baselineBranch.id
          : undefined,
        "markdown"
      );
      setExportedMarkdown(res.markdown);
    } catch (err) {
      setStatusBanner(
        err instanceof Error ? err.message : "Report export failed"
      );
    }
  };

  // Current simulation step state
  const currentStep = trajectory[currentStepIndex] || trajectory[0] || null;

  // Build React Flow nodes & edges for the Living Architecture canvas
  const flowNodes: Node[] = useMemo(() => {
    const servicesMap = currentStep?.services || {};
    const serviceKeys = [
      "api-gateway",
      "checkout-service",
      "inventory-service",
      "payment-simulator",
      "order-database-sim",
    ];
    return serviceKeys.map((svcKey) => {
      const st = servicesMap[svcKey];
      const lat = st ? st.mean_latency_ms : 18.0;
      const sat = st ? st.saturation_pct : 25.0;
      const qDepth = st ? st.queue_depth : 0.0;
      const replicas = st ? st.replica_count : 2;
      const cbState = st ? st.circuit_breaker_state : "CLOSED";
      const isBottleneck =
        currentStep?.primary_bottleneck_service === svcKey && lat > 80;

      const borderClass = isBottleneck
        ? "border-2 border-rose-600 bg-rose-50/95"
        : cbState === "OPEN"
        ? "border-2 border-amber-500 bg-amber-50/95"
        : "border border-[#0F1E36]/30 bg-white";

      return {
        id: svcKey,
        position: NODE_POSITIONS[svcKey] || { x: 0, y: 0 },
        data: {
          label: (
            <div
              data-testid={`twin-node-${svcKey}`}
              className={`p-2.5 rounded text-left min-w-[185px] shadow-2xs ${borderClass}`}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="font-mono text-[11px] font-bold text-[#0F1E36]">
                  {svcKey}
                </span>
                <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-[#F3EFEA] text-slate-700">
                  {replicas} rep
                </span>
              </div>
              <div className="mt-1.5 grid grid-cols-2 gap-1 text-[10px] font-mono">
                <div>
                  <span className="text-slate-500">Lat:</span>{" "}
                  <strong
                    className={
                      lat > 140 ? "text-rose-700" : "text-[#0F1E36]"
                    }
                  >
                    {lat.toFixed(1)}ms
                  </strong>
                </div>
                <div>
                  <span className="text-slate-500">Sat:</span>{" "}
                  <strong
                    className={
                      sat > 85 ? "text-amber-700" : "text-[#0F1E36]"
                    }
                  >
                    {sat.toFixed(0)}%
                  </strong>
                </div>
                <div>
                  <span className="text-slate-500">Queue:</span>{" "}
                  <strong>{qDepth.toFixed(1)}</strong>
                </div>
                <div>
                  <span className="text-slate-500">CB:</span>{" "}
                  <strong
                    className={
                      cbState === "OPEN"
                        ? "text-amber-800"
                        : "text-emerald-700"
                    }
                  >
                    {cbState}
                  </strong>
                </div>
              </div>
              {isBottleneck && (
                <div className="mt-1 text-[9px] font-mono uppercase tracking-wider text-rose-800 bg-rose-100 px-1.5 py-0.5 rounded">
                  PRIMARY BOTTLENECK
                </div>
              )}
            </div>
          ),
        },
        style: {
          background: "transparent",
          border: "none",
          padding: 0,
        },
      };
    });
  }, [currentStep]);

  const flowEdges: Edge[] = useMemo(() => {
    return EDGES_CONFIG.map((e) => ({
      id: `${e.source}->${e.target}`,
      source: e.source,
      target: e.target,
      animated: isPlaying,
      style: { stroke: "#0F1E36", strokeWidth: 1.5 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: "#0F1E36",
      },
    }));
  }, [isPlaying]);

  // Build Parallel Futures chart data
  const comparisonChartData = useMemo(() => {
    const baseTraj = baselineBranch?.trajectory_json || [];
    const altTraj = activeBranch?.trajectory_json || [];
    const altBands = activeBranch?.uncertainty_json?.step_bands || [];
    const len = Math.max(baseTraj.length, altTraj.length);
    const rows: Array<Record<string, number | string>> = [];
    for (let i = 0; i < len; i++) {
      const bPt = baseTraj[i];
      const aPt = altTraj[i];
      const band = altBands[i];
      rows.push({
        timeLabel: `${aPt?.timestamp_sec ?? bPt?.timestamp_sec ?? i + 1}s`,
        baselineLatency: bPt?.system_mean_latency_ms ?? 0,
        counterfactualLatency: aPt?.system_mean_latency_ms ?? 0,
        ciLower: band?.latency_lower_95_ms ?? aPt?.system_mean_latency_ms ?? 0,
        ciUpper: band?.latency_upper_95_ms ?? aPt?.system_mean_latency_ms ?? 0,
        baselineError: bPt?.system_error_rate_pct ?? 0,
        counterfactualError: aPt?.system_error_rate_pct ?? 0,
        baselineQueue: bPt?.max_queue_depth ?? 0,
        counterfactualQueue: aPt?.max_queue_depth ?? 0,
      });
    }
    return rows;
  }, [baselineBranch, activeBranch]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Workspace Header & Epistemic Separation Banner */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-[#E4DFD7] pb-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-slate-500">
              <History className="w-3.5 h-3.5 text-[#0F1E36]" />
              MILESTONE 03/05 · LIVING DIGITAL TWIN, TIME MACHINE & PARALLEL
              FUTURES
            </div>
            <h1 className="font-serif text-2xl font-bold text-[#0F1E36] mt-0.5">
              Living Digital Twin & Counterfactual Intelligence
            </h1>
            <p className="text-xs text-slate-600 mt-1 max-w-3xl">
              Calibrate versioned computational models from empirical telemetry
              with strict train/held-out validation separation, rewind system
              snapshots, and evaluate counterfactual interventions with Monte
              Carlo uncertainty bands.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Calibration Fault Scenario"
              data-testid="twin-calib-profile-select"
              value={calibProfile}
              onChange={(e) =>
                setCalibProfile(e.target.value as LabProfileType)
              }
              className="text-xs font-mono bg-white border border-[#D6CFC4] rounded px-2.5 py-1.5 text-[#0F1E36]"
            >
              <option value="payment_latency_spike">
                Scenario: Payment Latency Spike
              </option>
              <option value="db_lock_contention">
                Scenario: Shared DB Lock Contention
              </option>
              <option value="inventory_cpu_throttling">
                Scenario: Inventory CPU Starvation
              </option>
              <option value="normal">Scenario: Nominal Operation</option>
            </select>

            <button
              type="button"
              data-testid="calibrate-twin-btn"
              disabled={isBusy}
              onClick={handleCalibrateAndInitialize}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${isBusy ? "animate-spin" : ""}`}
              />
              Calibrate Twin from Evidence
            </button>

            <button
              type="button"
              data-testid="run-twin-benchmarks-btn"
              disabled={isBusy}
              onClick={handleRunBenchmarkSuite}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-[#F3EFEA] border border-[#D6CFC4] text-[#0F1E36] hover:bg-[#E6E0D6] disabled:opacity-50 cursor-pointer"
            >
              <FlaskConical className="w-3.5 h-3.5" />
              Run 4 Twin Benchmarks (A–D)
            </button>
          </div>
        </div>

        {/* Epistemic Disclosure Bar */}
        <div
          data-testid="epistemic-separation-banner"
          className="bg-[#F3EFEA] border border-[#D6CFC4] rounded-md px-4 py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
        >
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-[#0F1E36] text-[#FAF8F5]">
              EPISTEMIC CLASSIFICATION: COUNTERFACTUAL PREDICTION
            </span>
            <span className="text-slate-700">
              Simulated trajectories are conditioned on calibrated model
              parameters and never overwrite historical observations or
              experimental evidence.
            </span>
          </div>
          {statusBanner && (
            <span
              data-testid="twin-status-banner"
              className="font-mono text-[11px] text-emerald-900 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded"
            >
              {statusBanner}
            </span>
          )}
        </div>

        {/* Top Grid: A. Living Architecture (React Flow) + B. Time Machine & Counterfactual Branch Controls */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* A. Living Architecture Canvas */}
          <div className="lg:col-span-7 bg-white border border-[#E4DFD7] rounded-md p-4 shadow-2xs flex flex-col justify-between space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-serif text-base font-bold text-[#0F1E36] flex items-center gap-2">
                  <Layers className="w-4 h-4" />
                  A. Living System Digital Twin Topology
                </h2>
                <p className="text-[11px] text-slate-500">
                  Step-by-step service latency, queue depth, saturation, replica
                  availability, and circuit-breaker states.
                </p>
              </div>
              {currentStep && (
                <div className="text-right font-mono text-xs">
                  <span
                    data-testid="twin-clock-readout"
                    className="px-2 py-0.5 rounded bg-[#0F1E36] text-[#FAF8F5]"
                  >
                    t = {currentStep.timestamp_sec}s (Step{" "}
                    {currentStep.step_index})
                  </span>
                </div>
              )}
            </div>

            <div className="h-[340px] w-full rounded border border-[#E4DFD7] bg-[#FAF8F5]">
              <ReactFlow
                nodes={flowNodes}
                edges={flowEdges}
                fitView
                proOptions={{ hideAttribution: true }}
              >
                <Background color="#D6CFC4" gap={18} />
                <Controls showInteractive={false} />
              </ReactFlow>
            </div>

            {/* Instantaneous Step Summary Bar */}
            {currentStep && (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-1 text-xs font-mono">
                <div className="p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                  <div className="text-[10px] text-slate-500">E2E Latency</div>
                  <div
                    data-testid="step-e2e-latency"
                    className="font-bold text-[#0F1E36]"
                  >
                    {currentStep.system_mean_latency_ms} ms
                  </div>
                </div>
                <div className="p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                  <div className="text-[10px] text-slate-500">Error Rate</div>
                  <div className="font-bold text-[#0F1E36]">
                    {currentStep.system_error_rate_pct}%
                  </div>
                </div>
                <div className="p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                  <div className="text-[10px] text-slate-500">Throughput</div>
                  <div className="font-bold text-[#0F1E36]">
                    {currentStep.system_throughput_rps} req/s
                  </div>
                </div>
                <div className="p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                  <div className="text-[10px] text-slate-500">Max Queue</div>
                  <div className="font-bold text-[#0F1E36]">
                    {currentStep.max_queue_depth}
                  </div>
                </div>
                <div className="p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                  <div className="text-[10px] text-slate-500">Bottleneck</div>
                  <div className="font-bold text-rose-800 truncate">
                    {currentStep.primary_bottleneck_service}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* B. Time Machine & Counterfactual Intervention Studio */}
          <div className="lg:col-span-5 bg-white border border-[#E4DFD7] rounded-md p-4 shadow-2xs space-y-4">
            <div>
              <h2 className="font-serif text-base font-bold text-[#0F1E36] flex items-center gap-2">
                <Clock className="w-4 h-4" />
                B. Time Machine & Counterfactual Branch Studio
              </h2>
              <p className="text-[11px] text-slate-500">
                Scrub through simulation time, capture serializable state
                snapshots, rewind RNG/event queues, and spawn parallel futures.
              </p>
            </div>

            {/* Playback & Scrubber Bar */}
            <div className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7] space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    data-testid="time-machine-play-pause"
                    onClick={() => setIsPlaying((p) => !p)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] cursor-pointer"
                  >
                    {isPlaying ? (
                      <>
                        <Pause className="w-3 h-3" /> Pause
                      </>
                    ) : (
                      <>
                        <Play className="w-3 h-3" /> Play
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    data-testid="time-machine-step-btn"
                    onClick={() => {
                      setIsPlaying(false);
                      setCurrentStepIndex((i) => Math.min(maxStepIndex, i + 1));
                    }}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-mono border border-[#D6CFC4] bg-white text-[#0F1E36] cursor-pointer"
                  >
                    <FastForward className="w-3 h-3" /> Step +1s
                  </button>
                  <button
                    type="button"
                    data-testid="time-machine-rewind-btn"
                    onClick={handleRewindToSnapshot}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-mono border border-[#D6CFC4] bg-white text-[#0F1E36] cursor-pointer"
                  >
                    <RotateCcw className="w-3 h-3" /> Rewind
                  </button>
                </div>

                <div className="flex items-center gap-1 text-xs font-mono">
                  <span className="text-slate-500">Speed:</span>
                  {[0.5, 1, 2].map((spd) => (
                    <button
                      key={spd}
                      type="button"
                      onClick={() => setPlaybackSpeed(spd)}
                      className={`px-1.5 py-0.5 rounded ${
                        playbackSpeed === spd
                          ? "bg-[#0F1E36] text-white"
                          : "bg-white border border-[#D6CFC4] text-slate-700"
                      }`}
                    >
                      {spd}x
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-[11px] font-mono text-slate-600">
                  <span>Timeline Scrubber</span>
                  <span>
                    Step {currentStepIndex} / {maxStepIndex}
                  </span>
                </div>
                <input
                  type="range"
                  aria-label="Simulation Timeline Scrubber"
                  data-testid="time-machine-scrubber"
                  min={0}
                  max={maxStepIndex}
                  value={currentStepIndex}
                  onChange={(e) => {
                    setIsPlaying(false);
                    setCurrentStepIndex(Number(e.target.value));
                  }}
                  className="w-full accent-[#0F1E36] cursor-pointer"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <select
                  aria-label="Snapshot Selector"
                  data-testid="snapshot-select"
                  value={selectedSnapshotId}
                  onChange={(e) => setSelectedSnapshotId(e.target.value)}
                  className="flex-1 text-xs font-mono bg-white border border-[#D6CFC4] rounded px-2 py-1"
                >
                  {snapshots.length === 0 && (
                    <option value="">No snapshots captured yet</option>
                  )}
                  {snapshots.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label} (t={s.sim_clock_sec}s · seed {s.random_seed})
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  data-testid="capture-snapshot-btn"
                  disabled={!selectedTwin || isBusy}
                  onClick={handleCaptureSnapshot}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono bg-white border border-[#0F1E36] text-[#0F1E36] hover:bg-[#F3EFEA] cursor-pointer"
                >
                  <Camera className="w-3 h-3" /> Snapshot
                </button>
              </div>
            </div>

            {/* Counterfactual Branch Form */}
            <div className="space-y-2.5 pt-1">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-wider text-slate-600 flex items-center gap-1">
                  <Sliders className="w-3.5 h-3.5" /> Spawn Counterfactual
                  Branch
                </span>
                <span className="font-mono text-[10px] text-slate-500">
                  Allowlisted Interventions Only
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div className="sm:col-span-2">
                  <label
                    htmlFor="branch-name-input"
                    className="block text-[11px] font-mono text-slate-600 mb-0.5"
                  >
                    Branch Name
                  </label>
                  <input
                    id="branch-name-input"
                    data-testid="branch-name-input"
                    type="text"
                    value={branchName}
                    onChange={(e) => setBranchName(e.target.value)}
                    className="w-full border border-[#D6CFC4] rounded px-2.5 py-1 font-mono text-xs bg-white"
                  />
                </div>

                <div>
                  <label
                    htmlFor="intervention-type-select"
                    className="block text-[11px] font-mono text-slate-600 mb-0.5"
                  >
                    Intervention Type
                  </label>
                  <select
                    id="intervention-type-select"
                    data-testid="twin-intervention-select"
                    value={interventionType}
                    onChange={(e) =>
                      setInterventionType(
                        e.target.value as TwinInterventionType
                      )
                    }
                    className="w-full border border-[#D6CFC4] rounded px-2 py-1 font-mono text-xs bg-white"
                  >
                    <option value="reduce_downstream_latency">
                      reduce_downstream_latency
                    </option>
                    <option value="increase_replicas">increase_replicas</option>
                    <option value="adjust_db_connection_capacity">
                      adjust_db_connection_capacity
                    </option>
                    <option value="enable_circuit_breaker">
                      enable_circuit_breaker
                    </option>
                    <option value="reduce_incoming_traffic">
                      reduce_incoming_traffic
                    </option>
                    <option value="adjust_concurrency_limit">
                      adjust_concurrency_limit
                    </option>
                    <option value="simulate_dependency_failure">
                      simulate_dependency_failure
                    </option>
                    <option value="restore_configuration">
                      restore_configuration
                    </option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="target-service-select"
                    className="block text-[11px] font-mono text-slate-600 mb-0.5"
                  >
                    Target Service
                  </label>
                  <select
                    id="target-service-select"
                    data-testid="twin-target-service-select"
                    value={targetService}
                    onChange={(e) => setTargetService(e.target.value)}
                    className="w-full border border-[#D6CFC4] rounded px-2 py-1 font-mono text-xs bg-white"
                  >
                    <option value="payment-simulator">payment-simulator</option>
                    <option value="checkout-service">checkout-service</option>
                    <option value="order-database-sim">
                      order-database-sim
                    </option>
                    <option value="inventory-service">inventory-service</option>
                    <option value="api-gateway">api-gateway</option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="intervention-val-input"
                    className="block text-[11px] font-mono text-slate-600 mb-0.5"
                  >
                    Parameter Value / Factor
                  </label>
                  <input
                    id="intervention-val-input"
                    data-testid="twin-intervention-value"
                    type="number"
                    step="0.05"
                    value={interventionValue}
                    onChange={(e) =>
                      setInterventionValue(Number(e.target.value))
                    }
                    className="w-full border border-[#D6CFC4] rounded px-2 py-1 font-mono text-xs bg-white"
                  />
                </div>

                <div>
                  <label
                    htmlFor="random-seed-input"
                    className="block text-[11px] font-mono text-slate-600 mb-0.5"
                  >
                    Deterministic Seed / Apply@s
                  </label>
                  <div className="flex gap-1">
                    <input
                      id="random-seed-input"
                      type="number"
                      value={randomSeed}
                      onChange={(e) => setRandomSeed(Number(e.target.value))}
                      className="w-1/2 border border-[#D6CFC4] rounded px-2 py-1 font-mono text-xs bg-white"
                      title="Random Seed"
                    />
                    <input
                      type="number"
                      value={applyAtSec}
                      onChange={(e) => setApplyAtSec(Number(e.target.value))}
                      className="w-1/2 border border-[#D6CFC4] rounded px-2 py-1 font-mono text-xs bg-white"
                      title="Apply at seconds"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  data-testid="spawn-counterfactual-btn"
                  disabled={!selectedTwin || isBusy}
                  onClick={handleRunCounterfactualBranch}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] disabled:opacity-50 cursor-pointer"
                >
                  <GitBranch className="w-3.5 h-3.5" />
                  Simulate Counterfactual Branch
                </button>
                <button
                  type="button"
                  data-testid="export-twin-report-btn"
                  disabled={!activeBranch}
                  onClick={handleExportReport}
                  className="inline-flex items-center gap-1 px-3 py-2 rounded text-xs font-mono border border-[#D6CFC4] bg-[#F3EFEA] text-[#0F1E36] hover:bg-[#E6E0D6] disabled:opacity-50 cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export Report
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* C. Parallel Futures Comparison Section */}
        <section
          data-testid="parallel-futures-section"
          className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-4"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E4DFD7] pb-3">
            <div>
              <h2 className="font-serif text-lg font-bold text-[#0F1E36] flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                C. Parallel Futures Comparison & Monte Carlo Uncertainty
              </h2>
              <p className="text-xs text-slate-600">
                Side-by-side counterfactual trajectories comparing Baseline
                Future vs. Intervention Branch with 95% stochastic prediction
                intervals.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
              <label className="flex items-center gap-1">
                <span className="text-slate-500">Baseline:</span>
                <select
                  aria-label="Baseline Branch Select"
                  value={baselineBranch?.id || ""}
                  onChange={async (e) => {
                    const br =
                      branches.find((b) => b.id === e.target.value) || null;
                    setBaselineBranch(br);
                    if (br && activeBranch && br.id !== activeBranch.id) {
                      const comp = await compareSimulationBranches(
                        br.id,
                        activeBranch.id
                      );
                      setComparison(comp);
                    }
                  }}
                  className="border border-[#D6CFC4] rounded px-2 py-1 bg-[#FAF8F5]"
                >
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name} ({b.outcome_summary_json.mean_latency_ms}ms)
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex items-center gap-1">
                <span className="text-slate-500">Alternative:</span>
                <select
                  aria-label="Alternative Branch Select"
                  data-testid="active-branch-select"
                  value={activeBranch?.id || ""}
                  onChange={async (e) => {
                    const br =
                      branches.find((b) => b.id === e.target.value) || null;
                    setActiveBranch(br);
                    setCurrentStepIndex(0);
                    if (baselineBranch && br && baselineBranch.id !== br.id) {
                      const comp = await compareSimulationBranches(
                        baselineBranch.id,
                        br.id
                      );
                      setComparison(comp);
                    }
                  }}
                  className="border border-[#D6CFC4] rounded px-2 py-1 bg-[#FAF8F5]"
                >
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name} ({b.outcome_summary_json.mean_latency_ms}ms)
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {/* Delta Comparison KPI Cards */}
          {comparison && (
            <div
              data-testid="branch-comparison-deltas"
              className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono"
            >
              <div className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                <div className="text-slate-500">Latency Delta (vs Base)</div>
                <div
                  data-testid="comparison-latency-delta"
                  className={`text-sm font-bold mt-0.5 ${
                    comparison.delta_metrics.latency_delta_ms < 0
                      ? "text-emerald-800"
                      : "text-rose-800"
                  }`}
                >
                  {comparison.delta_metrics.latency_delta_ms > 0 ? "+" : ""}
                  {comparison.delta_metrics.latency_delta_ms} ms (
                  {comparison.delta_metrics.latency_reduction_pct ?? 0}% red.)
                </div>
              </div>

              <div className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                <div className="text-slate-500">Error Rate Delta</div>
                <div className="text-sm font-bold text-[#0F1E36] mt-0.5">
                  {comparison.delta_metrics.error_rate_delta_pct > 0
                    ? "+"
                    : ""}
                  {comparison.delta_metrics.error_rate_delta_pct}%
                </div>
              </div>

              <div className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                <div className="text-slate-500">Throughput Delta</div>
                <div className="text-sm font-bold text-[#0F1E36] mt-0.5">
                  {comparison.delta_metrics.throughput_delta_rps > 0
                    ? "+"
                    : ""}
                  {comparison.delta_metrics.throughput_delta_rps} req/s
                </div>
              </div>

              <div className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                <div className="text-slate-500">Max Queue Delta</div>
                <div className="text-sm font-bold text-[#0F1E36] mt-0.5">
                  {comparison.delta_metrics.max_queue_delta > 0 ? "+" : ""}
                  {comparison.delta_metrics.max_queue_delta} requests
                </div>
              </div>
            </div>
          )}

          {/* Shared Bottleneck & Tradeoff Warnings */}
          {comparison &&
            (comparison.shared_bottleneck_warnings.length > 0 ||
              comparison.tradeoff_analysis.length > 0) && (
              <div className="p-3 rounded bg-amber-50/80 border border-amber-300 space-y-1 text-xs">
                {comparison.shared_bottleneck_warnings.map((w) => (
                  <div
                    key={w}
                    className="flex items-start gap-1.5 text-amber-950 font-medium"
                  >
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-700" />
                    <span>{w}</span>
                  </div>
                ))}
                {comparison.tradeoff_analysis.map((t) => (
                  <div key={t} className="text-slate-700 font-mono text-[11px]">
                    · {t}
                  </div>
                ))}
              </div>
            )}

          {/* Recharts Side-by-Side Trajectory Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="p-3 rounded border border-[#E4DFD7] bg-[#FAF8F5]">
              <div className="text-xs font-mono font-semibold text-[#0F1E36] mb-2">
                End-to-End Latency Trajectory (ms) & 95% Prediction Band
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={comparisonChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E4DFD7" />
                    <XAxis dataKey="timeLabel" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Area
                      type="monotone"
                      dataKey="ciUpper"
                      name="95% Band Upper (ms)"
                      stroke="none"
                      fill="#94A3B8"
                      fillOpacity={0.2}
                    />
                    <Line
                      type="monotone"
                      dataKey="baselineLatency"
                      name="Baseline Latency (ms)"
                      stroke="#991B1B"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="counterfactualLatency"
                      name="Counterfactual Latency (ms)"
                      stroke="#0F1E36"
                      strokeWidth={2.5}
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="p-3 rounded border border-[#E4DFD7] bg-[#FAF8F5]">
              <div className="text-xs font-mono font-semibold text-[#0F1E36] mb-2">
                Queue Depth & Error Rate (%) Comparison
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={comparisonChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E4DFD7" />
                    <XAxis dataKey="timeLabel" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line
                      type="monotone"
                      dataKey="baselineQueue"
                      name="Baseline Max Queue"
                      stroke="#B45309"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="counterfactualQueue"
                      name="Counterfactual Max Queue"
                      stroke="#047857"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="counterfactualError"
                      name="Counterfactual Error (%)"
                      stroke="#4F46E5"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </section>

        {/* D. Scientific Inspector, Held-Out Calibration Residuals, 4 Benchmarks & Scientific Memory */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Calibration Quality & Residuals Inspector */}
          <div
            data-testid="scientific-inspector-panel"
            className="lg:col-span-6 bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-4"
          >
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-2.5">
              <div>
                <h2 className="font-serif text-base font-bold text-[#0F1E36] flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4" />
                  D1. Evidence-Based Calibration & Held-Out Validation
                </h2>
                <p className="text-[11px] text-slate-500">
                  Provenance-linked parameter estimates and residuals evaluated
                  strictly on held-out validation traces.
                </p>
              </div>
              {selectedTwin && (
                <span
                  data-testid="twin-version-badge"
                  className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#0F1E36] text-[#FAF8F5]"
                >
                  {selectedTwin.version_tag}
                </span>
              )}
            </div>

            {calibrationRun ? (
              <div className="space-y-3 text-xs">
                <div className="grid grid-cols-3 gap-2 font-mono">
                  <div className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                    <div className="text-[10px] text-slate-500">
                      Held-Out MAE
                    </div>
                    <div
                      data-testid="calibration-mae-readout"
                      className="font-bold text-[#0F1E36]"
                    >
                      {calibrationRun.mae_ms} ms
                    </div>
                  </div>
                  <div className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                    <div className="text-[10px] text-slate-500">
                      Held-Out RMSE
                    </div>
                    <div className="font-bold text-[#0F1E36]">
                      {calibrationRun.rmse_ms} ms
                    </div>
                  </div>
                  <div className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                    <div className="text-[10px] text-slate-500">
                      Train / Val Split
                    </div>
                    <div className="font-bold text-[#0F1E36]">
                      {calibrationRun.train_sample_count} /{" "}
                      {calibrationRun.validation_sample_count} traces
                    </div>
                  </div>
                </div>

                {/* Held-out residual table */}
                <div className="overflow-x-auto border border-[#E4DFD7] rounded">
                  <table className="w-full text-left font-mono text-[11px]">
                    <thead className="bg-[#F3EFEA] text-slate-700">
                      <tr>
                        <th className="px-2.5 py-1.5">Service</th>
                        <th className="px-2.5 py-1.5">Obs Mean (ms)</th>
                        <th className="px-2.5 py-1.5">Sim Mean (ms)</th>
                        <th className="px-2.5 py-1.5">Residual</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E4DFD7]">
                      {calibrationRun.residuals_json.map((r) => (
                        <tr key={r.service_key}>
                          <td className="px-2.5 py-1.5 font-semibold">
                            {r.service_key}
                          </td>
                          <td className="px-2.5 py-1.5">
                            {r.observed_mean_latency_ms}
                          </td>
                          <td className="px-2.5 py-1.5">
                            {r.simulated_mean_latency_ms}
                          </td>
                          <td className="px-2.5 py-1.5">
                            {r.residual_ms > 0 ? "+" : ""}
                            {r.residual_ms} ms ({r.relative_error_pct}%)
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Assumptions & Warnings */}
                <div className="space-y-1 text-[11px] font-mono text-slate-600">
                  {selectedTwin?.assumptions_json.slice(0, 3).map((a) => (
                    <div key={a}>· Assumption: {a}</div>
                  ))}
                  {calibrationRun.warnings_json.map((w) => (
                    <div key={w} className="text-amber-800">
                      · Warning: {w}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 font-mono py-8 text-center">
                Click &ldquo;Calibrate Twin from Evidence&rdquo; to calibrate a
                Digital Twin model from real laboratory telemetry.
              </div>
            )}
          </div>

          {/* D2. Persistent Scientific Memory Ledger */}
          <div
            data-testid="scientific-memory-panel"
            className="lg:col-span-6 bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-4"
          >
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-2.5">
              <div>
                <h2 className="font-serif text-base font-bold text-[#0F1E36] flex items-center gap-2">
                  <BookOpen className="w-4 h-4" />
                  D2. Persistent Scientific Memory Ledger
                </h2>
                <p className="text-[11px] text-slate-500">
                  Cross-session institutional memory preserving strict epistemic
                  separation between observations, experiments, calibrated
                  models, and predictions.
                </p>
              </div>
              <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#F3EFEA] border border-[#D6CFC4] text-[#0F1E36]">
                {memoryEntries.length} entries
              </span>
            </div>

            <div className="space-y-2 max-h-[310px] overflow-y-auto pr-1">
              {memoryEntries.slice(0, 12).map((entry) => (
                <div
                  key={entry.id}
                  data-testid={`memory-entry-${entry.epistemic_kind}`}
                  className="p-2.5 rounded border border-[#E4DFD7] bg-[#FAF8F5] space-y-1"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#0F1E36] text-[#FAF8F5]">
                      {entry.epistemic_kind}
                    </span>
                    <span className="font-mono text-[10px] text-slate-500">
                      {new Date(entry.created_at).toLocaleTimeString([], {
                        hour12: false,
                      })}
                    </span>
                  </div>
                  <div className="font-serif font-bold text-xs text-[#0F1E36]">
                    {entry.title}
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    {entry.summary}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Canonical 4 Simulation Benchmarks Matrix Results */}
        {benchmarkSuite && (
          <section
            data-testid="twin-benchmark-suite-results"
            className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-4"
          >
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-3">
              <div>
                <h2 className="font-serif text-lg font-bold text-[#0F1E36]">
                  Milestone 03/05 Digital Twin Benchmark Suite (A, B, C, D)
                </h2>
                <p className="text-xs text-slate-600">
                  Reproducible verification across Payment Degradation, Shared
                  Database Lock Contention, Traffic Surge, and Cascading Circuit
                  Breaker Protection.
                </p>
              </div>
              <span
                data-testid="twin-benchmark-pass-badge"
                className="font-mono text-xs px-3 py-1 rounded bg-emerald-50 border border-emerald-300 text-emerald-900 font-bold"
              >
                PASSED: {benchmarkSuite.passed_count} /{" "}
                {benchmarkSuite.total_benchmarks}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {benchmarkSuite.benchmarks.map((b) => (
                <div
                  key={b.benchmark_key}
                  data-testid={`benchmark-card-${b.benchmark_key}`}
                  className="p-4 rounded border border-[#D6CFC4] bg-[#FAF8F5] space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-serif font-bold text-sm text-[#0F1E36]">
                      {b.title}
                    </span>
                    <span className="inline-flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-900">
                      <CheckCircle2 className="w-3 h-3" />
                      {b.passed_verification ? "VERIFIED" : "CHECK"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700">
                    {b.key_scientific_finding}
                  </p>
                  <div className="text-[11px] font-mono text-slate-500">
                    Model: {b.model_version_tag} · Held-Out MAE:{" "}
                    {b.calibration_mae_ms}ms · RMSE: {b.calibration_rmse_ms}ms
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Exported Reproducible Markdown Report Modal */}
        {exportedMarkdown && (
          <div className="bg-white border-2 border-[#0F1E36] rounded-md p-5 shadow-md space-y-3">
            <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-2">
              <div className="flex items-center gap-2 font-serif font-bold text-sm text-[#0F1E36]">
                <FileText className="w-4 h-4" />
                Reproducible Counterfactual Simulation Report (Markdown)
              </div>
              <button
                type="button"
                onClick={() => setExportedMarkdown(null)}
                className="text-xs font-mono px-2 py-0.5 rounded border border-[#D6CFC4] hover:bg-[#F3EFEA]"
              >
                Close
              </button>
            </div>
            <pre
              data-testid="twin-report-markdown"
              className="text-xs font-mono bg-[#FAF8F5] p-4 rounded border border-[#E4DFD7] overflow-x-auto whitespace-pre-wrap max-h-96"
            >
              {exportedMarkdown}
            </pre>
          </div>
        )}
      </div>
    </AppShell>
  );
}
