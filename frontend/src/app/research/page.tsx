"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, Lock, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { fetchArchitectureModules } from "@/lib/api";
import type { ModuleBoundaryStatus } from "@/lib/types";

export default function ResearchModulesPage() {
  const [boundaries, setBoundaries] = useState<ModuleBoundaryStatus[]>([]);

  useEffect(() => {
    fetchArchitectureModules()
      .then((res) => setBoundaries(res.boundaries))
      .catch(() => {
        /* ignore offline */
      });
  }, []);

  const implemented = boundaries.filter((b) =>
    b.status.startsWith("implemented")
  );
  const contractsOnly = boundaries.filter(
    (b) => b.status === "architecture_contract_only"
  );

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="border-b border-[#E4DFD7] pb-4">
          <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-slate-500">
            <ShieldCheck className="w-3.5 h-3.5 text-[#0F1E36]" />
            ARCHITECTURAL BOUNDARIES & SCIENTIFIC INTEGRITY
          </div>
          <h1 className="font-serif text-2xl font-bold text-[#0F1E36]">
            Modular Architecture & Future Research Contracts
          </h1>
          <p className="text-xs text-slate-600 mt-1 max-w-3xl">
            ORIGIN enforces strict modular boundaries across 9 domain modules.
            Through Milestone 02/05, the Living System Intelligence Engine and
            Autonomous Causal Scientist (Modules 1–5 and 7–9) are fully
            implemented and verified. Module 6 (Digital Twin Simulation) exposes
            an explicit typed contract without pretending to execute
            unimplemented simulation loops.
          </p>
        </div>

        {/* Future Research Modules (Contract-Only in Milestone 01/05) */}
        <section className="space-y-3">
          <h2 className="font-serif text-lg font-bold text-[#0F1E36]">
            Scheduled Scientific Research Modules (Interfaces & DB Schema
            Provisioned)
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {contractsOnly.map((mod) => (
              <div
                key={mod.boundary_number}
                data-testid={`research-contract-${mod.module}`}
                className="bg-white border border-[#E4DFD7] rounded-md p-5 shadow-2xs space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-slate-500">
                    BOUNDARY 0{mod.boundary_number} ·{" "}
                    {mod.module.toUpperCase()}
                  </span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 border border-amber-300 text-amber-900 text-[10px] font-mono">
                    <Lock className="w-3 h-3" />
                    CONTRACT ONLY IN M01/05
                  </span>
                </div>

                <div>
                  <h3 className="font-serif text-base font-bold text-[#0F1E36]">
                    {mod.target_milestone}
                  </h3>
                  <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                    {mod.notice}
                  </p>
                </div>

                <div className="p-3 rounded bg-[#FAF8F5] border border-[#E4DFD7] text-xs font-mono space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Execution Enabled:</span>
                    <span className="font-semibold text-slate-700">
                      FALSE (Disabled until target milestone)
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">
                      Provisioned DB Tables:
                    </span>
                    <span className="font-semibold text-[#0F1E36]">
                      {mod.database_tables_provisioned &&
                      mod.database_tables_provisioned.length > 0
                        ? mod.database_tables_provisioned.join(", ")
                        : "Protocol Interface Only"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Active Milestone 01/05 Modules */}
        <section className="space-y-3">
          <h2 className="font-serif text-lg font-bold text-[#0F1E36]">
            Active & Verified Milestone 01/05 Modules
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {implemented.map((mod) => (
              <div
                key={mod.boundary_number}
                data-testid={`implemented-module-${mod.module}`}
                className="bg-white border border-[#D6CFC4] rounded-md p-4 shadow-2xs space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-slate-500">
                    BOUNDARY 0{mod.boundary_number}
                  </span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#0F1E36] text-[#FAF8F5] text-[10px] font-mono">
                    <CheckCircle2 className="w-3 h-3" />
                    IMPLEMENTED & VERIFIED
                  </span>
                </div>
                <div className="font-serif font-bold text-sm text-[#0F1E36]">
                  {mod.module.replace(/_/g, " ").toUpperCase()}
                </div>
                <ul className="text-xs text-slate-600 space-y-1 list-disc list-inside">
                  {mod.capabilities?.map((cap) => (
                    <li key={cap}>{cap}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
