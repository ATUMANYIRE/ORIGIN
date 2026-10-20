"use client";

import React, { useCallback, useEffect, useState } from "react";
import { FlaskConical, GitBranch, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { TopologyCanvas } from "@/components/TopologyCanvas";
import { fetchSystemTopology, fetchSystems } from "@/lib/api";
import type { SystemRead, TopologyGraphResponse } from "@/lib/types";

export default function TopologyExplorerPage() {
  const [systems, setSystems] = useState<SystemRead[]>([]);
  const [selectedSystemSlug, setSelectedSystemSlug] = useState<string>(
    "origin-synthetic-lab"
  );
  const [graph, setGraph] = useState<TopologyGraphResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadGraph = useCallback(async () => {
    try {
      const [sysList, topoData] = await Promise.all([
        fetchSystems(),
        fetchSystemTopology(selectedSystemSlug),
      ]);
      setSystems(sysList);
      setGraph(topoData);
    } catch {
      // ignore offline
    } finally {
      setLoading(false);
    }
  }, [selectedSystemSlug]);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  return (
    <AppShell onTelemetryEvent={loadGraph}>
      <div className="space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E4DFD7] pb-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-slate-500">
              <GitBranch className="w-3.5 h-3.5 text-[#0F1E36]" />
              PROVENANCE-VERIFIED TOPOLOGY DISCOVERY
            </div>
            <h1 className="font-serif text-2xl font-bold text-[#0F1E36]">
              Interactive System Topology Explorer
            </h1>
          </div>

          <div className="flex items-center gap-2.5">
            {graph?.is_synthetic_lab && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-amber-50 border border-amber-300 text-amber-900 text-[11px] font-mono">
                <FlaskConical className="w-3.5 h-3.5" />
                SYNTHETIC LAB ENVIRONMENT
              </span>
            )}
            <label htmlFor="topology-system-select" className="sr-only">
              Select System
            </label>
            <select
              id="topology-system-select"
              value={selectedSystemSlug}
              onChange={(e) => setSelectedSystemSlug(e.target.value)}
              className="px-3 py-1.5 rounded bg-white border border-[#E4DFD7] text-xs font-mono text-[#0F1E36]"
            >
              {systems.length === 0 ? (
                <option value="origin-synthetic-lab">
                  origin-synthetic-lab
                </option>
              ) : (
                systems.map((s) => (
                  <option key={s.slug} value={s.slug}>
                    {s.name} ({s.slug})
                  </option>
                ))
              )}
            </select>

            <button
              type="button"
              onClick={() => void loadGraph()}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-white border border-[#E4DFD7] text-xs font-mono text-[#0F1E36] hover:bg-[#F3EFEA] cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Sync Graph
            </button>
          </div>
        </div>

        {loading && !graph ? (
          <div className="h-[580px] rounded-md bg-white border border-[#E4DFD7] flex items-center justify-center font-mono text-xs text-slate-500">
            Synthesizing topology graph from registered declarations and
            observed spans...
          </div>
        ) : graph ? (
          <TopologyCanvas graph={graph} />
        ) : (
          <div className="p-6 bg-white border border-[#E4DFD7] rounded-md text-xs font-mono text-slate-600">
            No topology graph available yet. Click &ldquo;Emit Lab Traffic&rdquo;
            in the header to populate live observations.
          </div>
        )}
      </div>
    </AppShell>
  );
}
