# ORIGIN 8-Role Bounded Deterministic Agent Orchestrator (`docs/AGENT_ORCHESTRATION.md`)

**Milestone:** `04/05 — Verified Autonomous Recovery, Agent Orchestration & Operational Safety`  
**Contract & Implementation:** [`backend/app/modules/agents/contract.py`](file:///E:/Projects/ORIGIN/backend/app/modules/agents/contract.py), [`backend/app/modules/recovery/service.py`](file:///E:/Projects/ORIGIN/backend/app/modules/recovery/service.py)

---

## 1. Eight Specialized Software Agent Roles

ORIGIN coordinates eight bounded, deterministic software agent roles across the autonomous operations loop:

| Role | Lifecycle Phase | Core Responsibility | Mutates Lab State? |
|---|---|---|---|
| **1. `Observer`** | `DETECTED`, `OBSERVING` | Collects OpenTelemetry spans/metrics, computes baseline and post-execution latency/error rates, and evaluates guardrail thresholds. | No (Read-Only) |
| **2. `Investigator`** | `INVESTIGATING` | Executes or validates causal root-cause investigations (`AutonomousInvestigatorService`) and verifies minimum causal confidence ($\ge 0.55$) and evidence count ($\ge 1$). | Controlled A/B Only |
| **3. `Simulator`** | `SIMULATING` | Calibrates the `DigitalTwinService` against observed telemetry and runs counterfactual simulation branches for each candidate remediation. | No (In-Memory Twin) |
| **4. `RecoveryPlanner`** | `PROPOSING` | Synthesizes bounded remediation candidates from allowlisted actions, ranks them by simulated latency reduction minus error/risk penalties, and computes the SHA-256 `plan_hash`. | No |
| **5. `Verifier`** | `SANDBOX_VERIFYING` | Runs before/after experimental trials in the isolated Synthetic Laboratory, computes Welch's $t$-test, detects Twin vs. Sandbox disagreement, and verifies laboratory restoration. | Temporary Sandbox + Mandatory Restore |
| **6. `SafetyGovernor`** | All Policy Gates | Evaluates fail-closed operational safety policies (`SafetyPolicyEngine`), enforces environment restrictions (`synthetic-lab` only), validates human approval tokens/hashes, and locks the lab if restoration fails. | No (Policy Gate) |
| **7. `ExecutionController`** | `EXECUTING`, `ROLLED_BACK` | Acquires the per-system concurrency mutex lock, consumes the single-use approval token, applies the approved remediation, and triggers automatic rollback on guardrail violations or timeouts. | Yes (With Approval Token) |
| **8. `EvidenceAuditor`** | `RECOVERED` | Records verified recovery outcomes into `ScientificMemoryEntryRecord`, persists immutable `AuditEvent` entries, and compiles reproducible Markdown/JSON recovery reports. | No (Append-Only Ledger) |

---

## 2. Optional Constrained Model Gateway (`RecoveryExplanationGatewayProtocol`)

- By default, ORIGIN uses `DeterministicRecoveryExplanationGateway`, requiring **zero external paid LLM APIs**.
- Any optional model gateway implementation is strictly constrained to natural-language rationale summarization; it cannot invent non-allowlisted actions, bypass `SafetyPolicyEngine`, or grant execution permissions.
