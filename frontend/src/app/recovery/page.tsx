"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileCode2,
  FlaskConical,
  KeyRound,
  Lock,
  Microscope,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Unlock,
  XCircle,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import {
  approveOrRejectRecoveryPlan,
  cancelRecoveryPlan,
  clearLabUnsafeLock,
  createInvestigation,
  createRecoveryPlan,
  executeApprovedRecoveryPlan,
  exportRecoveryPlanReport,
  fetchInvestigations,
  fetchRecoveryPlanDetail,
  fetchRecoveryPlans,
  fetchSafetyPolicies,
  generateRecoveryCandidates,
  mutateRecoveryPlan,
  rollbackRecoveryPlan,
  triggerLabWorkload,
  verifyRecoveryCandidateInSandbox,
} from "@/lib/api";
import type {
  InvestigationRead,
  RecoveryLifecycleState,
  RecoveryPlanDetailRead,
  RecoveryPlanRead,
  SafetyPolicySpecResponse,
} from "@/lib/types";

const LIFECYCLE_PHASES: RecoveryLifecycleState[] = [
  "DETECTED",
  "INVESTIGATING",
  "SIMULATING",
  "PROPOSING",
  "SANDBOX_VERIFYING",
  "AWAITING_APPROVAL",
  "APPROVED",
  "EXECUTING",
  "OBSERVING",
  "RECOVERED",
];

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case "RECOVERED":
    case "APPROVED":
    case "COMPLETED":
    case "sandbox_verified":
      return "bg-emerald-50 text-emerald-900 border-emerald-300";
    case "AWAITING_APPROVAL":
    case "SANDBOX_VERIFYING":
    case "SIMULATING":
    case "PROPOSING":
    case "simulated_only":
      return "bg-amber-50 text-amber-900 border-amber-300";
    case "ROLLED_BACK":
    case "REJECTED":
    case "REVOKED":
      return "bg-orange-50 text-orange-900 border-orange-300";
    case "FAILED":
    case "RESTORATION_FAILED":
    case "MANUAL_INTERVENTION_REQUIRED":
    case "sandbox_failed":
    case "policy_rejected":
      return "bg-rose-50 text-rose-900 border-rose-300";
    default:
      return "bg-[#F3EFEA] text-[#0F1E36] border-[#E4DFD7]";
  }
}

export default function RecoveryCommandCenterPage() {
  const [plans, setPlans] = useState<RecoveryPlanRead[]>([]);
  const [selectedPlan, setSelectedPlan] =
    useState<RecoveryPlanDetailRead | null>(null);
  const [investigations, setInvestigations] = useState<InvestigationRead[]>([]);
  const [safetyPolicies, setSafetyPolicies] =
    useState<SafetyPolicySpecResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);

  // Creation form state
  const [newPlanTitle, setNewPlanTitle] = useState<string>(
    "Verified Autonomous Payment Latency Remediation"
  );
  const [selectedInvestigationId, setSelectedInvestigationId] =
    useState<string>("");
  const [faultScenario, setFaultScenario] = useState<
    "payment_latency_spike" | "db_lock_contention" | "inventory_cpu_throttling"
  >("payment_latency_spike");

  // Approval console state
  const [approverIdentity, setApproverIdentity] = useState<string>(
    "principal-sre-commander"
  );
  const [approverRole, setApproverRole] = useState<string>(
    "reliability-commander"
  );
  const [approvalRationale, setApprovalRationale] = useState<string>(
    "Sandbox verification confirmed statistically significant latency recovery and clean restoration."
  );
  const [issuedSingleUseToken, setIssuedSingleUseToken] = useState<string>("");
  const [activeApprovalId, setActiveApprovalId] = useState<string>("");

  // Execution options state
  const [simulateRegression, setSimulateRegression] = useState<boolean>(false);
  const [simulateTimeout, setSimulateTimeout] = useState<boolean>(false);
  const [simulateRollbackFailure, setSimulateRollbackFailure] =
    useState<boolean>(false);

  // Report export state
  const [exportedReport, setExportedReport] = useState<{
    format: string;
    content: string;
  } | null>(null);

  const loadWorkspace = useCallback(async (targetPlanId?: string) => {
    try {
      const [planList, invList, polSpec] = await Promise.all([
        fetchRecoveryPlans("origin-synthetic-lab"),
        fetchInvestigations("origin-synthetic-lab"),
        fetchSafetyPolicies(),
      ]);
      setPlans(planList);
      setInvestigations(invList);
      setSafetyPolicies(polSpec);

      const concludedInv = invList.find(
        (i: InvestigationRead) => i.status === "CONCLUDED"
      );
      if (concludedInv) {
        setSelectedInvestigationId((prev) => prev || concludedInv.id);
      }

      const idToFetch = targetPlanId || planList[0]?.id;
      if (idToFetch) {
        const detail = await fetchRecoveryPlanDetail(idToFetch);
        setSelectedPlan(detail);
        if (detail.active_approval_id) {
          setActiveApprovalId(detail.active_approval_id);
        }
      }
    } catch (err) {
      setErrorBanner(
        err instanceof Error
          ? err.message
          : "Failed to load Recovery Command Center"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const handleRunFullPreparePipeline = async () => {
    setBusyAction("prepare-workflow");
    setErrorBanner(null);
    setStatusBanner(null);
    try {
      // 1. Inject laboratory fault and emit telemetry
      await triggerLabWorkload({
        iterations: 4,
        profile: faultScenario,
      });

      // 2. Run or reuse causal investigation
      let invId = selectedInvestigationId;
      if (!invId) {
        const inv = await createInvestigation({
          system_slug: "origin-synthetic-lab",
          title: `Autonomous Investigation (${faultScenario})`,
          target_service_key: "checkout-service",
          target_metric: "request_latency_ms",
          experiment_budget: 4,
          random_seed: 42,
          auto_run: true,
        });
        invId = inv.id;
        setSelectedInvestigationId(inv.id);
      }

      // 3. Create recovery plan, calibrate twin, simulate candidates, and run sandbox verification
      const detail = await createRecoveryPlan({
        system_slug: "origin-synthetic-lab",
        title: newPlanTitle,
        target_environment: "synthetic-lab",
        investigation_id: invId,
        auto_prepare_to_approval: true,
        sandbox_trials_per_arm: 4,
        random_seed: 42,
      });

      setSelectedPlan(detail);
      setIssuedSingleUseToken("");
      setStatusBanner(
        `Recovery workflow '${detail.title}' prepared through SANDBOX_VERIFYING -> ${detail.status} (Plan Hash: ${detail.plan_hash.slice(
          0,
          16
        )}...).`
      );
      await loadWorkspace(detail.id);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Failed to prepare recovery plan"
      );
    } finally {
      setBusyAction(null);
    }
  };

  const handleGenerateCandidates = async () => {
    if (!selectedPlan) return;
    setBusyAction("generate-candidates");
    setErrorBanner(null);
    try {
      const updated = await generateRecoveryCandidates(selectedPlan.id, {});
      setSelectedPlan(updated);
      setStatusBanner(
        `Generated and simulated ${updated.candidates.length} bounded remediation candidates in Digital Twin.`
      );
      await loadWorkspace(updated.id);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Candidate generation failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  const handleVerifyCandidateInSandbox = async (candidateId?: string) => {
    if (!selectedPlan) return;
    setBusyAction("sandbox-verify");
    setErrorBanner(null);
    try {
      const updated = await verifyRecoveryCandidateInSandbox(selectedPlan.id, {
        candidate_id: candidateId || selectedPlan.selected_candidate_id || undefined,
        trials_per_arm: 4,
        random_seed: 42,
      });
      setSelectedPlan(updated);
      setStatusBanner(
        `Completed real isolated sandbox verification -> status=${updated.status}. Laboratory configuration restored and verified.`
      );
      await loadWorkspace(updated.id);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Sandbox verification failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  const handleMutatePlan = async (candidateId: string) => {
    if (!selectedPlan) return;
    setBusyAction("mutate-plan");
    setErrorBanner(null);
    try {
      const updated = await mutateRecoveryPlan(selectedPlan.id, {
        selected_candidate_id: candidateId,
        reason: "Operator switched candidate in Decision Studio (revokes prior approval)",
      });
      setSelectedPlan(updated);
      setIssuedSingleUseToken("");
      setStatusBanner(
        `Updated plan to v${updated.plan_version} (new hash=${updated.plan_hash.slice(
          0,
          12
        )}...). Any prior approval token was automatically revoked.`
      );
      await loadWorkspace(updated.id);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Plan mutation failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  const handleDecisionApproval = async (decision: "APPROVED" | "REJECTED") => {
    if (!selectedPlan) return;
    setBusyAction(`decision-${decision}`);
    setErrorBanner(null);
    try {
      const approval = await approveOrRejectRecoveryPlan(selectedPlan.id, {
        candidate_id: selectedPlan.selected_candidate_id || undefined,
        decision,
        approver_identity: approverIdentity,
        approver_role: approverRole,
        rationale: approvalRationale,
        ttl_seconds: 900,
      });
      setActiveApprovalId(approval.id);
      if (approval.issued_single_use_token) {
        setIssuedSingleUseToken(approval.issued_single_use_token);
      }
      setStatusBanner(
        decision === "APPROVED"
          ? `Human approval recorded (${approval.id.slice(
              0,
              8
            )}). Single-use cryptographic token issued and bound to plan hash ${approval.plan_hash.slice(
              0,
              14
            )}...`
          : `Recovery plan explicitly REJECTED by ${approverIdentity}.`
      );
      await loadWorkspace(selectedPlan.id);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Approval submission failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  const handleExecuteApprovedPlan = async () => {
    if (!selectedPlan) return;
    const appId = activeApprovalId || selectedPlan.active_approval_id || "";
    if (!appId || !issuedSingleUseToken) {
      setErrorBanner(
        "Execution blocked: Valid Approval ID and Single-Use Authorization Token are required."
      );
      return;
    }
    setBusyAction("execute-recovery");
    setErrorBanner(null);
    try {
      const updated = await executeApprovedRecoveryPlan(selectedPlan.id, {
        approval_id: appId,
        approval_token: issuedSingleUseToken,
        observation_iterations: 4,
        simulate_execution_regression: simulateRegression,
        simulate_timeout: simulateTimeout,
        simulate_rollback_failure: simulateRollbackFailure,
      });
      setSelectedPlan(updated);
      setStatusBanner(
        `Execution completed with lifecycle state: ${updated.status}. Single-use token consumed.`
      );
      await loadWorkspace(updated.id);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Recovery execution failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  const handleManualRollback = async () => {
    if (!selectedPlan) return;
    setBusyAction("manual-rollback");
    setErrorBanner(null);
    try {
      const updated = await rollbackRecoveryPlan(selectedPlan.id, {
        reason: "Operator-initiated manual rollback from Recovery Command Center.",
      });
      setSelectedPlan(updated);
      setStatusBanner(
        `Rollback executed and verified -> plan status=${updated.status}.`
      );
      await loadWorkspace(updated.id);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusyAction(null);
    }
  };

  const handleCancelPlan = async () => {
    if (!selectedPlan) return;
    setBusyAction("cancel-plan");
    setErrorBanner(null);
    try {
      const updated = await cancelRecoveryPlan(selectedPlan.id);
      setSelectedPlan(updated);
      setStatusBanner(`Recovery workflow cancelled -> status=${updated.status}.`);
      await loadWorkspace(updated.id);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setBusyAction(null);
    }
  };

  const handleExportReport = async (format: "markdown" | "json") => {
    if (!selectedPlan) return;
    setBusyAction(`export-${format}`);
    try {
      const res = await exportRecoveryPlanReport(selectedPlan.id, format);
      setExportedReport({
        format,
        content:
          format === "markdown"
            ? res.markdown
            : JSON.stringify(res.report, null, 2),
      });
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Report export failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  const handleClearLabUnsafeLock = async () => {
    setBusyAction("clear-lock");
    try {
      await clearLabUnsafeLock();
      setStatusBanner("Laboratory unsafe lock cleared and restored to normal.");
      await loadWorkspace(selectedPlan?.id);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to clear lock");
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Top Scientific Instrument Header */}
        <div className="bg-white border border-[#E4DFD7] rounded-lg p-5 shadow-2xs">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono uppercase tracking-widest px-2 py-0.5 rounded bg-[#0F1E36] text-[#FAF8F5]">
                  MILESTONE 04/05 · AUTONOMOUS RECOVERY & SAFETY
                </span>
                <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-50 text-emerald-900 border border-emerald-300">
                  ENVIRONMENT: SYNTHETIC-LAB ONLY (PRODUCTION DISABLED)
                </span>
                {safetyPolicies?.lab_unsafe_locked && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-mono uppercase px-2 py-0.5 rounded bg-rose-100 text-rose-900 border border-rose-300">
                    <Lock className="w-3 h-3" /> LAB LOCKED UNSAFE
                  </span>
                )}
              </div>
              <h1 className="font-serif text-2xl font-bold text-[#0F1E36] mt-2">
                Verified Autonomous Recovery Command Center
              </h1>
              <p className="text-xs text-slate-600 mt-1 max-w-3xl">
                Transforms causal investigation evidence and Digital Twin counterfactuals into
                sandbox-verified, cryptographically bound, human-approved remediation workflows
                with automatic guardrail rollback.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {safetyPolicies?.lab_unsafe_locked && (
                <button
                  type="button"
                  onClick={handleClearLabUnsafeLock}
                  disabled={busyAction !== null}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-rose-700 text-white hover:bg-rose-800 cursor-pointer"
                >
                  <Unlock className="w-3.5 h-3.5" />
                  Reset Lab Unsafe Lock
                </button>
              )}
              <select
                aria-label="Fault Scenario for Recovery Pipeline"
                value={faultScenario}
                onChange={(e) =>
                  setFaultScenario(
                    e.target.value as
                      | "payment_latency_spike"
                      | "db_lock_contention"
                      | "inventory_cpu_throttling"
                  )
                }
                className="text-xs font-mono border border-[#E4DFD7] rounded px-2.5 py-1.5 bg-[#FAF8F5] text-[#0F1E36]"
              >
                <option value="payment_latency_spike">
                  Fault: Payment Gateway Latency Spike
                </option>
                <option value="db_lock_contention">
                  Fault: Order DB Lock Contention
                </option>
                <option value="inventory_cpu_throttling">
                  Fault: Inventory CPU Throttling
                </option>
              </select>
              <input
                type="text"
                aria-label="Recovery Workflow Title"
                value={newPlanTitle}
                onChange={(e) => setNewPlanTitle(e.target.value)}
                className="text-xs border border-[#E4DFD7] rounded px-2.5 py-1.5 bg-[#FAF8F5] text-[#0F1E36] w-64"
              />
              <button
                type="button"
                data-testid="launch-recovery-pipeline-btn"
                onClick={handleRunFullPreparePipeline}
                disabled={busyAction !== null}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] disabled:opacity-50 transition-colors cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                {busyAction === "prepare-workflow"
                  ? "Investigating, Simulating & Verifying in Sandbox..."
                  : "Launch Investigate -> Simulate -> Sandbox Verify"}
              </button>
            </div>
          </div>

          {errorBanner && (
            <div
              data-testid="recovery-error-banner"
              className="mt-4 p-3 rounded bg-rose-50 border border-rose-300 text-rose-900 text-xs flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <AlertOctagon className="w-4 h-4 shrink-0" />
                <span>{errorBanner}</span>
              </div>
              <button
                type="button"
                onClick={() => setErrorBanner(null)}
                className="text-[11px] font-mono underline"
              >
                Dismiss
              </button>
            </div>
          )}

          {statusBanner && (
            <div
              data-testid="recovery-status-banner"
              className="mt-4 p-3 rounded bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{statusBanner}</span>
              </div>
              <button
                type="button"
                onClick={() => setStatusBanner(null)}
                className="text-[11px] font-mono underline"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>

        {/* Workflow Selector Strip */}
        <div className="bg-white border border-[#E4DFD7] rounded-lg p-4 shadow-2xs flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-serif font-semibold text-[#0F1E36]">
              Recovery Workflows ({plans.length}):
            </span>
            {plans.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => void loadWorkspace(p.id)}
                className={`px-2.5 py-1 rounded text-xs font-mono border transition-colors cursor-pointer ${
                  selectedPlan?.id === p.id
                    ? "bg-[#0F1E36] text-[#FAF8F5] border-[#0F1E36]"
                    : "bg-[#FAF8F5] text-[#0F1E36] border-[#E4DFD7] hover:bg-[#F3EFEA]"
                }`}
              >
                {p.title.slice(0, 32)} · [{p.status}] (v{p.plan_version})
              </button>
            ))}
            {plans.length === 0 && !loading && (
              <span className="text-xs text-slate-500 italic">
                No recovery workflows recorded yet. Click &ldquo;Launch Investigate -&gt; Simulate -&gt; Sandbox Verify&rdquo; above.
              </span>
            )}
          </div>

          {selectedPlan && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void handleExportReport("markdown")}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono border border-[#E4DFD7] bg-[#FAF8F5] hover:bg-[#F3EFEA] cursor-pointer"
              >
                <Download className="w-3 h-3" /> Export Markdown
              </button>
              <button
                type="button"
                onClick={() => void handleExportReport("json")}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono border border-[#E4DFD7] bg-[#FAF8F5] hover:bg-[#F3EFEA] cursor-pointer"
              >
                <FileCode2 className="w-3 h-3" /> Export JSON
              </button>
              <button
                type="button"
                onClick={handleCancelPlan}
                disabled={busyAction !== null}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono border border-rose-300 bg-rose-50 text-rose-900 hover:bg-rose-100 cursor-pointer"
              >
                <XCircle className="w-3 h-3" /> Cancel Plan
              </button>
            </div>
          )}
        </div>

        {selectedPlan && (
          <>
            {/* SECTION A: Autonomous Operations Timeline & 8-Role Agent Orchestrator */}
            <section
              data-testid="section-operations-timeline"
              className="bg-white border border-[#E4DFD7] rounded-lg p-5 shadow-2xs space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-[#E4DFD7] pb-3">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                    SECTION A · AUTONOMOUS OPERATIONS TIMELINE & 8-ROLE AGENT ORCHESTRATOR
                  </span>
                  <h2 className="font-serif text-lg font-bold text-[#0F1E36]">
                    {selectedPlan.title}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    data-testid="active-plan-status-badge"
                    className={`text-xs font-mono font-semibold px-2.5 py-1 rounded border ${getStatusBadgeClass(
                      selectedPlan.status
                    )}`}
                  >
                    STATE: {selectedPlan.status}
                  </span>
                  <span className="text-[11px] font-mono px-2 py-1 rounded bg-[#F3EFEA] border border-[#E4DFD7]">
                    v{selectedPlan.plan_version} · Hash:{" "}
                    {selectedPlan.plan_hash
                      ? `${selectedPlan.plan_hash.slice(0, 14)}...`
                      : "pending"}
                  </span>
                </div>
              </div>

              {/* State Machine Progress Bar */}
              <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-1.5">
                {LIFECYCLE_PHASES.map((phase) => {
                  const visited = selectedPlan.lifecycle_history_json.some(
                    (h) => h.to_state === phase
                  );
                  const isCurrent = selectedPlan.status === phase;
                  return (
                    <div
                      key={phase}
                      className={`p-2 rounded border text-center transition-colors ${
                        isCurrent
                          ? "bg-[#0F1E36] text-[#FAF8F5] border-[#0F1E36] font-bold"
                          : visited
                          ? "bg-emerald-50/80 text-emerald-950 border-emerald-300"
                          : "bg-[#FAF8F5] text-slate-400 border-[#E4DFD7]"
                      }`}
                    >
                      <div className="text-[10px] font-mono truncate">{phase}</div>
                      <div className="text-[9px] font-mono mt-0.5">
                        {isCurrent ? "ACTIVE" : visited ? "VERIFIED" : "PENDING"}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* 8-Role Agent Decision Strip */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                <div className="border border-[#E4DFD7] rounded p-3 bg-[#FAF8F5]">
                  <h3 className="text-xs font-serif font-bold text-[#0F1E36] mb-2">
                    Lifecycle State Transitions ({selectedPlan.lifecycle_history_json.length})
                  </h3>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {selectedPlan.lifecycle_history_json.map((tr, idx) => (
                      <div
                        key={idx}
                        className="text-[11px] border-l-2 border-[#0F1E36] pl-2 py-0.5 bg-white rounded-r"
                      >
                        <div className="flex items-center justify-between font-mono text-[10px] text-slate-600">
                          <span>
                            {tr.from_state || "INIT"} -&gt;{" "}
                            <strong className="text-[#0F1E36]">{tr.to_state}</strong>
                          </span>
                          <span>
                            [{tr.agent_role}] · {tr.actor}
                          </span>
                        </div>
                        <div className="text-slate-700 mt-0.5">{tr.rationale}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="border border-[#E4DFD7] rounded p-3 bg-[#FAF8F5]">
                  <h3 className="text-xs font-serif font-bold text-[#0F1E36] mb-2">
                    8-Role Bounded Agent Decision Ledger (
                    {selectedPlan.agent_decision_history_json.length})
                  </h3>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {selectedPlan.agent_decision_history_json.map((dec) => (
                      <div
                        key={dec.step}
                        className="text-[11px] bg-white border border-[#E4DFD7] rounded p-2"
                      >
                        <div className="flex items-center justify-between font-mono text-[10px]">
                          <span className="px-1.5 py-0.2 rounded bg-[#0F1E36] text-[#FAF8F5]">
                            #{dec.step} · {dec.agent_role}
                          </span>
                          <span className="text-slate-600">
                            Phase: {dec.phase} · {dec.decision}
                          </span>
                        </div>
                        <p className="text-slate-700 mt-1">{dec.rationale}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            {/* SECTION B & SECTION C Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* SECTION B: Causal Evidence Panel */}
              <section
                data-testid="section-causal-evidence"
                className="bg-white border border-[#E4DFD7] rounded-lg p-5 shadow-2xs space-y-3"
              >
                <div className="border-b border-[#E4DFD7] pb-2">
                  <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                    SECTION B · CAUSAL EVIDENCE PANEL
                  </span>
                  <h2 className="font-serif text-base font-bold text-[#0F1E36] flex items-center gap-1.5">
                    <Microscope className="w-4 h-4" /> Root-Cause Grounding
                  </h2>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                    <div className="text-[10px] font-mono uppercase text-slate-500">
                      Suspected Root-Cause Service
                    </div>
                    <div className="font-mono font-bold text-sm text-[#0F1E36] mt-0.5">
                      {selectedPlan.root_cause_service_key || "Pending"}
                    </div>
                    <div className="text-[11px] font-mono text-slate-600 mt-0.5">
                      Mechanism: {selectedPlan.root_cause_mechanism || "N/A"}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                      <div className="text-[10px] font-mono text-slate-500">
                        Observed Baseline Latency
                      </div>
                      <div className="font-mono font-bold text-sm text-[#0F1E36]">
                        {String(
                          selectedPlan.baseline_metrics_json.mean_latency_ms ??
                            "N/A"
                        )}{" "}
                        ms
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                      <div className="text-[10px] font-mono text-slate-500">
                        Causal Confidence
                      </div>
                      <div className="font-mono font-bold text-sm text-emerald-800">
                        {Math.round(
                          Number(
                            selectedPlan.evidence_summary_json
                              .causal_confidence_score ?? 0
                          ) * 100
                        )}
                        %
                      </div>
                    </div>
                  </div>

                  <div className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-[11px] font-mono space-y-1">
                    <div>
                      Investigation ID:{" "}
                      <span className="text-slate-700">
                        {selectedPlan.investigation_id || "Operator Grounded"}
                      </span>
                    </div>
                    <div>
                      Digital Twin ID:{" "}
                      <span className="text-slate-700">
                        {selectedPlan.twin_model_id || "Not calibrated yet"}
                      </span>
                    </div>
                    <div>
                      Evidence Refs:{" "}
                      <span className="text-slate-700">
                        {Array.isArray(
                          selectedPlan.evidence_summary_json
                            .evidence_reference_ids
                        )
                          ? (
                              selectedPlan.evidence_summary_json
                                .evidence_reference_ids as string[]
                            ).length
                          : 0}{" "}
                        linked records
                      </span>
                    </div>
                  </div>
                </div>
              </section>

              {/* SECTION C: Counterfactual Decision Studio */}
              <section
                data-testid="section-decision-studio"
                className="lg:col-span-2 bg-white border border-[#E4DFD7] rounded-lg p-5 shadow-2xs space-y-3"
              >
                <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-2">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                      SECTION C · COUNTERFACTUAL DECISION STUDIO
                    </span>
                    <h2 className="font-serif text-base font-bold text-[#0F1E36]">
                      Bounded Remediation Candidates ({selectedPlan.candidates.length})
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={handleGenerateCandidates}
                    disabled={busyAction !== null}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono border border-[#E4DFD7] bg-[#FAF8F5] hover:bg-[#F3EFEA] cursor-pointer"
                  >
                    <RefreshCw className="w-3 h-3" /> Regenerate & Simulate
                  </button>
                </div>

                <div className="space-y-2.5">
                  {selectedPlan.candidates.map((cand) => {
                    const isSelected =
                      selectedPlan.selected_candidate_id === cand.id;
                    const simPred = cand.simulation_prediction_json;
                    return (
                      <div
                        key={cand.id}
                        data-testid={`candidate-card-${cand.action_type}`}
                        className={`p-3 rounded border transition-all ${
                          isSelected
                            ? "border-[#0F1E36] bg-[#FAF8F5] ring-1 ring-[#0F1E36]"
                            : "border-[#E4DFD7] bg-white"
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-[#0F1E36]">
                              {cand.action_type}
                            </span>
                            <span className="text-xs font-mono text-slate-600">
                              on <strong>{cand.target_service_key}</strong>
                            </span>
                            <span
                              className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${getStatusBadgeClass(
                                cand.verification_status
                              )}`}
                            >
                              {cand.verification_status === "sandbox_verified"
                                ? "VERIFIED IN SANDBOX"
                                : cand.verification_status === "simulated_only"
                                ? "SIMULATED ONLY (UNVERIFIED)"
                                : cand.verification_status}
                            </span>
                            <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-300">
                              Risk: {cand.risk_classification} · Score:{" "}
                              {cand.rank_score}
                            </span>
                          </div>

                          <div className="flex items-center gap-1.5">
                            {!isSelected && (
                              <button
                                type="button"
                                onClick={() => void handleMutatePlan(cand.id)}
                                disabled={busyAction !== null}
                                className="px-2 py-1 rounded text-[11px] font-mono border border-[#E4DFD7] bg-white hover:bg-[#F3EFEA] cursor-pointer"
                              >
                                Select Candidate (Mutate Plan)
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() =>
                                void handleVerifyCandidateInSandbox(cand.id)
                              }
                              disabled={busyAction !== null}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-mono bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] cursor-pointer"
                            >
                              <FlaskConical className="w-3 h-3" /> Verify in Sandbox
                            </button>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-2 text-[11px] font-mono">
                          <div className="p-2 rounded bg-white border border-[#E4DFD7]">
                            <span className="text-slate-500 block text-[10px]">
                              TWIN PREDICTED LATENCY (SIMULATED)
                            </span>
                            <strong className="text-[#0F1E36]">
                              {String(
                                simPred.baseline_simulated_latency_ms ?? "N/A"
                              )}
                              ms -&gt;{" "}
                              {String(simPred.predicted_mean_latency_ms ?? "N/A")}
                              ms (-
                              {String(
                                simPred.predicted_latency_reduction_pct ?? 0
                              )}
                              %)
                            </strong>
                          </div>
                          <div className="p-2 rounded bg-white border border-[#E4DFD7]">
                            <span className="text-slate-500 block text-[10px]">
                              PARAMETERS (BOUNDED)
                            </span>
                            <span className="text-slate-800">
                              {JSON.stringify(cand.parameters_json)}
                            </span>
                          </div>
                          <div className="p-2 rounded bg-white border border-[#E4DFD7]">
                            <span className="text-slate-500 block text-[10px]">
                              ADVERSE EFFECTS & ROLLBACK
                            </span>
                            <span className="text-slate-700">
                              {cand.adverse_effects_json[0] || "Bounded"}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>

            {/* SECTION D & SECTION E Grid: Sandbox Verification & Human Approval Console */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* SECTION D: Sandbox Verification */}
              <section
                data-testid="section-sandbox-verification"
                className="bg-white border border-[#E4DFD7] rounded-lg p-5 shadow-2xs space-y-3"
              >
                <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-2">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                      SECTION D · ISOLATED LABORATORY SANDBOX VERIFICATION
                    </span>
                    <h2 className="font-serif text-base font-bold text-[#0F1E36] flex items-center gap-1.5">
                      <FlaskConical className="w-4 h-4" /> Real Before/After Sandbox Trials
                    </h2>
                  </div>
                  <button
                    type="button"
                    data-testid="run-sandbox-verify-btn"
                    onClick={() => void handleVerifyCandidateInSandbox()}
                    disabled={busyAction !== null}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] cursor-pointer"
                  >
                    <Play className="w-3 h-3" /> Run Sandbox Trial
                  </button>
                </div>

                {selectedPlan.sandbox_runs.length === 0 ? (
                  <p className="text-xs text-slate-500 italic py-4">
                    No sandbox verification run executed yet. Candidates remain marked as{" "}
                    <code className="font-mono">simulated_only</code> until verified in the isolated laboratory.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {selectedPlan.sandbox_runs.map((srun) => (
                      <div
                        key={srun.id}
                        className="p-3 rounded border border-[#E4DFD7] bg-[#FAF8F5] space-y-2 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-[#0F1E36]">
                            Sandbox Run {srun.id.slice(0, 8)}
                          </span>
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${getStatusBadgeClass(
                                srun.status
                              )}`}
                            >
                              {srun.status}
                            </span>
                            <span
                              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                                srun.restoration_verified
                                  ? "bg-emerald-50 text-emerald-900 border-emerald-300"
                                  : "bg-rose-50 text-rose-900 border-rose-300"
                              }`}
                            >
                              RESTORATION VERIFIED:{" "}
                              {srun.restoration_verified ? "TRUE" : "FALSE"}
                            </span>
                          </div>
                        </div>

                        <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                          <div className="p-2 bg-white rounded border border-[#E4DFD7]">
                            <span className="text-[10px] text-slate-500 block">
                              CONTROL (BASELINE)
                            </span>
                            <strong>
                              {String(
                                srun.baseline_metrics_json.mean_latency_ms
                              )}{" "}
                              ms
                            </strong>
                            <span className="block text-[10px] text-slate-500">
                              Err: {String(srun.baseline_metrics_json.error_rate_pct)}%
                            </span>
                          </div>
                          <div className="p-2 bg-white rounded border border-[#E4DFD7]">
                            <span className="text-[10px] text-slate-500 block">
                              TREATMENT (SANDBOX)
                            </span>
                            <strong className="text-emerald-800">
                              {String(
                                srun.treatment_metrics_json.mean_latency_ms
                              )}{" "}
                              ms
                            </strong>
                            <span className="block text-[10px] text-slate-500">
                              Err:{" "}
                              {String(srun.treatment_metrics_json.error_rate_pct)}%
                            </span>
                          </div>
                          <div className="p-2 bg-white rounded border border-[#E4DFD7]">
                            <span className="text-[10px] text-slate-500 block">
                              WELCH&apos;S T-TEST & EFFECT
                            </span>
                            <strong>
                              {String(
                                srun.statistical_comparison_json
                                  .relative_effect_pct ?? "N/A"
                              )}
                              %
                            </strong>
                            <span className="block text-[10px] text-slate-500">
                              t={" "}
                              {String(
                                srun.statistical_comparison_json.welch_t_stat ??
                                  "N/A"
                              )}
                            </span>
                          </div>
                        </div>

                        <div className="text-[11px] font-mono p-2 rounded bg-white border border-[#E4DFD7]">
                          <span className="text-slate-600">
                            Twin vs. Sandbox Agreement:{" "}
                          </span>
                          <strong className="text-[#0F1E36]">
                            {String(
                              srun.simulation_disagreement_json.note ??
                                "Verified"
                            )}
                          </strong>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* SECTION E: Human Approval Console */}
              <section
                data-testid="section-human-approval-console"
                className="bg-white border border-[#E4DFD7] rounded-lg p-5 shadow-2xs space-y-3"
              >
                <div className="border-b border-[#E4DFD7] pb-2">
                  <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                    SECTION E · HUMAN APPROVAL CONSOLE (SERVER-SIDE ENFORCED)
                  </span>
                  <h2 className="font-serif text-base font-bold text-[#0F1E36] flex items-center gap-1.5">
                    <ClipboardCheck className="w-4 h-4" /> Cryptographic Plan Hash & Single-Use Token Gate
                  </h2>
                </div>

                <div className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs space-y-2">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] font-mono uppercase text-slate-600">
                        Approver Identity
                      </label>
                      <input
                        type="text"
                        value={approverIdentity}
                        onChange={(e) => setApproverIdentity(e.target.value)}
                        className="mt-0.5 w-full text-xs font-mono border border-[#E4DFD7] rounded px-2 py-1 bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-mono uppercase text-slate-600">
                        Approver Role
                      </label>
                      <input
                        type="text"
                        value={approverRole}
                        onChange={(e) => setApproverRole(e.target.value)}
                        className="mt-0.5 w-full text-xs font-mono border border-[#E4DFD7] rounded px-2 py-1 bg-white"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[10px] font-mono uppercase text-slate-600">
                      Approval / Rejection Rationale
                    </label>
                    <input
                      type="text"
                      value={approvalRationale}
                      onChange={(e) => setApprovalRationale(e.target.value)}
                      className="mt-0.5 w-full text-xs border border-[#E4DFD7] rounded px-2 py-1 bg-white"
                    />
                  </div>

                  <div className="text-[11px] font-mono text-slate-600 bg-white p-2 rounded border border-[#E4DFD7]">
                    <div>
                      Binding Plan Version: <strong>v{selectedPlan.plan_version}</strong>
                    </div>
                    <div className="truncate">
                      Binding SHA-256 Plan Hash:{" "}
                      <strong>{selectedPlan.plan_hash || "N/A"}</strong>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      data-testid="approve-recovery-plan-btn"
                      onClick={() => void handleDecisionApproval("APPROVED")}
                      disabled={busyAction !== null}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-emerald-800 text-white hover:bg-emerald-900 disabled:opacity-50 cursor-pointer"
                    >
                      <ShieldCheck className="w-3.5 h-3.5" />
                      Approve & Issue Single-Use Token
                    </button>
                    <button
                      type="button"
                      data-testid="reject-recovery-plan-btn"
                      onClick={() => void handleDecisionApproval("REJECTED")}
                      disabled={busyAction !== null}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-rose-50 text-rose-900 border border-rose-300 hover:bg-rose-100 cursor-pointer"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      Reject Plan
                    </button>
                  </div>
                </div>

                {issuedSingleUseToken && (
                  <div
                    data-testid="issued-single-use-token-box"
                    className="p-2.5 rounded bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs font-mono space-y-1"
                  >
                    <div className="flex items-center gap-1.5 font-bold">
                      <KeyRound className="w-3.5 h-3.5" /> Single-Use Authorization Token Issued:
                    </div>
                    <div className="break-all bg-white p-1.5 rounded border border-emerald-200 text-[11px]">
                      {issuedSingleUseToken}
                    </div>
                  </div>
                )}

                {selectedPlan.approvals.length > 0 && (
                  <div className="space-y-1.5 max-h-36 overflow-y-auto">
                    {selectedPlan.approvals.map((app) => (
                      <div
                        key={app.id}
                        className="text-[11px] font-mono p-2 rounded border border-[#E4DFD7] bg-[#FAF8F5] flex items-center justify-between"
                      >
                        <span>
                          {app.approver_identity} ({app.approver_role}) · v
                          {app.plan_version} · Hash {app.plan_hash.slice(0, 10)}...
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded border text-[10px] ${getStatusBadgeClass(
                            app.decision
                          )}`}
                        >
                          {app.decision} (Token Used: {String(app.token_used)})
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>

            {/* SECTION F: Recovery Execution Timeline & Rollback Controls */}
            <section
              data-testid="section-execution-timeline"
              className="bg-white border border-[#E4DFD7] rounded-lg p-5 shadow-2xs space-y-4"
            >
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 border-b border-[#E4DFD7] pb-3">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                    SECTION F · SAGA RECOVERY EXECUTION & AUTOMATIC ROLLBACK CONTROLLER
                  </span>
                  <h2 className="font-serif text-base font-bold text-[#0F1E36]">
                    Controlled Laboratory Execution & Post-Action Guardrail Observation
                  </h2>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <label className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simulateRegression}
                      onChange={(e) => setSimulateRegression(e.target.checked)}
                    />
                    Simulate Post-Execution Regression (Auto-Rollback)
                  </label>
                  <label className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simulateTimeout}
                      onChange={(e) => setSimulateTimeout(e.target.checked)}
                    />
                    Simulate Timeout
                  </label>
                  <label className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simulateRollbackFailure}
                      onChange={(e) =>
                        setSimulateRollbackFailure(e.target.checked)
                      }
                    />
                    Simulate Rollback Failure
                  </label>

                  <button
                    type="button"
                    data-testid="execute-approved-recovery-btn"
                    onClick={handleExecuteApprovedPlan}
                    disabled={busyAction !== null}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded text-xs font-medium bg-[#0F1E36] text-[#FAF8F5] hover:bg-[#1B365D] disabled:opacity-50 cursor-pointer"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    Execute Approved Recovery Action
                  </button>

                  {selectedPlan.executions.length > 0 && (
                    <button
                      type="button"
                      data-testid="manual-rollback-btn"
                      onClick={handleManualRollback}
                      disabled={busyAction !== null}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-amber-50 text-amber-950 border border-amber-300 hover:bg-amber-100 cursor-pointer"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Trigger Manual Rollback
                    </button>
                  )}
                </div>
              </div>

              {selectedPlan.executions.length === 0 ? (
                <p className="text-xs text-slate-500 italic">
                  No recovery executions have been triggered for this plan yet. Approve a sandbox-verified candidate above to issue a single-use execution token.
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <h3 className="text-xs font-serif font-bold text-[#0F1E36]">
                      Execution Runs ({selectedPlan.executions.length})
                    </h3>
                    {selectedPlan.executions.map((ex) => (
                      <div
                        key={ex.id}
                        data-testid="execution-record-card"
                        className="p-3 rounded border border-[#E4DFD7] bg-[#FAF8F5] text-xs space-y-1.5 font-mono"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold">
                            Exec {ex.id.slice(0, 8)} ·{" "}
                            {String(
                              ex.applied_config_json.action_type ||
                                selectedPlan.candidates.find(
                                  (c) => c.id === ex.candidate_id
                                )?.action_type ||
                                "remediation"
                            )}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded border text-[10px] ${getStatusBadgeClass(
                              ex.status
                            )}`}
                          >
                            {ex.status}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 bg-white p-2 rounded border border-[#E4DFD7]">
                          <div>
                            <span className="text-[10px] text-slate-500 block">
                              BASELINE LATENCY
                            </span>
                            <strong>
                              {String(
                                ex.guardrail_evaluation_json
                                  .baseline_mean_latency_ms ?? "N/A"
                              )}{" "}
                              ms
                            </strong>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500 block">
                              OBSERVED POST-EXEC LATENCY
                            </span>
                            <strong className="text-emerald-800">
                              {String(
                                ex.observed_metrics_json.mean_latency_ms ??
                                  "N/A"
                              )}{" "}
                              ms
                            </strong>
                          </div>
                        </div>
                        <div className="text-[11px] text-slate-600">
                          Verification Passed: {String(ex.verification_passed)} ·
                          Rollback Triggered: {String(ex.rollback_triggered)}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2">
                    <h3 className="text-xs font-serif font-bold text-[#0F1E36]">
                      Rollback Records ({selectedPlan.rollbacks.length})
                    </h3>
                    {selectedPlan.rollbacks.length === 0 ? (
                      <div className="p-3 rounded border border-[#E4DFD7] bg-[#FAF8F5] text-xs text-slate-500 italic">
                        Zero rollbacks triggered — post-execution telemetry remained within all operational safety guardrails.
                      </div>
                    ) : (
                      selectedPlan.rollbacks.map((rb) => (
                        <div
                          key={rb.id}
                          className="p-3 rounded border border-amber-300 bg-amber-50/60 text-xs space-y-1 font-mono"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-amber-950">
                              Rollback {rb.id.slice(0, 8)}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded border text-[10px] ${getStatusBadgeClass(
                                rb.status
                              )}`}
                            >
                              {rb.status} (Verified:{" "}
                              {String(rb.rollback_verified)})
                            </span>
                          </div>
                          <div className="text-amber-900">
                            Trigger: {rb.trigger_reason}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </section>

            {/* SECTION G: Scientific Audit Ledger & Policy Evaluations */}
            <section
              data-testid="section-safety-audit-ledger"
              className="bg-white border border-[#E4DFD7] rounded-lg p-5 shadow-2xs space-y-4"
            >
              <div className="flex items-center justify-between border-b border-[#E4DFD7] pb-2">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                    SECTION G · OPERATIONAL SAFETY POLICY EVALUATIONS & REPRODUCIBLE AUDIT EXPORT
                  </span>
                  <h2 className="font-serif text-base font-bold text-[#0F1E36] flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4" /> SafetyGovernor Policy Ledger (
                    {selectedPlan.policy_evaluations.length} Evaluations)
                  </h2>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-60 overflow-y-auto">
                {selectedPlan.policy_evaluations.map((pe) => (
                  <div
                    key={pe.id}
                    className={`p-2.5 rounded border text-[11px] font-mono ${
                      pe.allowed
                        ? "bg-[#FAF8F5] border-[#E4DFD7]"
                        : "bg-rose-50 border-rose-300 text-rose-950"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold">{pe.policy_stage}</span>
                      <span
                        className={`px-1.5 py-0.2 rounded text-[10px] ${
                          pe.allowed
                            ? "bg-emerald-100 text-emerald-900"
                            : "bg-rose-200 text-rose-950"
                        }`}
                      >
                        {pe.allowed ? "ALLOWED" : "DENIED"} · Risk:{" "}
                        {pe.risk_classification}
                      </span>
                    </div>
                    <div className="text-slate-600 mt-1">
                      Action: {pe.action_type} ({pe.target_environment})
                    </div>
                    {pe.violations_json.length > 0 && (
                      <div className="text-rose-800 mt-1 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 shrink-0" />
                        <span>{pe.violations_json.join("; ")}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {exportedReport && (
                <div
                  data-testid="exported-recovery-report"
                  className="mt-4 p-4 rounded border border-[#0F1E36] bg-[#FAF8F5]"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-mono font-bold text-[#0F1E36]">
                      Reproducible Scientific Recovery Audit Report (
                      {exportedReport.format.toUpperCase()})
                    </span>
                    <button
                      type="button"
                      onClick={() => setExportedReport(null)}
                      className="text-xs font-mono underline"
                    >
                      Close Report
                    </button>
                  </div>
                  <pre className="text-[11px] font-mono whitespace-pre-wrap bg-white p-3 rounded border border-[#E4DFD7] max-h-80 overflow-y-auto">
                    {exportedReport.content}
                  </pre>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}
