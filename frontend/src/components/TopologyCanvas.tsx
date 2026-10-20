"use client";

import React, { useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type {
  TopologyEdge,
  TopologyGraphResponse,
  TopologyNode,
} from "@/lib/types";
import { formatProvenanceBadge } from "@/lib/api";

interface ServiceNodeData extends Record<string, unknown> {
  node: TopologyNode;
}

function ServiceInstrumentNode({ data }: NodeProps<Node<ServiceNodeData>>) {
  const svc = data.node;
  const prov = formatProvenanceBadge(svc.registration_source);

  const healthStyles: Record<
    string,
    { dot: string; border: string; badge: string }
  > = {
    healthy: {
      dot: "bg-emerald-600",
      border: "border-[#D6CFC4] hover:border-[#0F1E36]",
      badge: "bg-emerald-50 text-emerald-800 border-emerald-200",
    },
    degraded: {
      dot: "bg-amber-500 animate-pulse",
      border: "border-amber-400",
      badge: "bg-amber-50 text-amber-900 border-amber-300",
    },
    critical: {
      dot: "bg-rose-600 animate-ping",
      border: "border-rose-500",
      badge: "bg-rose-50 text-rose-900 border-rose-300",
    },
    unknown: {
      dot: "bg-slate-400",
      border: "border-slate-300",
      badge: "bg-slate-100 text-slate-700 border-slate-300",
    },
  };

  const st = healthStyles[svc.health_status] ?? healthStyles.unknown!;

  return (
    <div
      data-testid={`topology-node-${svc.service_key}`}
      className={`w-64 rounded-md bg-white border-2 ${st.border} shadow-xs p-3 text-left transition-all`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-2.5 !bg-[#0F1E36]"
      />
      <div className="flex items-center justify-between gap-1 mb-1">
        <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
          {svc.tier} · {svc.service_type}
        </span>
        <span
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border ${st.badge}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
          {svc.health_status.toUpperCase()}
        </span>
      </div>

      <div className="font-serif font-bold text-sm text-[#0F1E36] truncate">
        {svc.display_name}
      </div>
      <div className="font-mono text-[11px] text-slate-500 mb-2">
        {svc.service_key}
      </div>

      <div className="grid grid-cols-3 gap-1.5 pt-2 border-t border-[#F3EFEA] text-[10px] font-mono">
        <div>
          <span className="text-slate-400 block">P95 LAT</span>
          <span className="font-semibold text-[#0F1E36]">
            {svc.metrics.p95_latency_ms !== null
              ? `${svc.metrics.p95_latency_ms}ms`
              : "—"}
          </span>
        </div>
        <div>
          <span className="text-slate-400 block">ERR RATE</span>
          <span
            className={`font-semibold ${
              svc.metrics.error_rate_pct > 0
                ? "text-rose-700"
                : "text-[#0F1E36]"
            }`}
          >
            {svc.metrics.error_rate_pct}%
          </span>
        </div>
        <div>
          <span className="text-slate-400 block">SPANS</span>
          <span className="font-semibold text-[#0F1E36]">
            {svc.metrics.observed_span_count}
          </span>
        </div>
      </div>

      <div className="mt-2 pt-1.5 border-t border-[#F3EFEA] flex items-center justify-between">
        <span
          className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${prov.badgeClass}`}
        >
          {prov.label}
        </span>
        {svc.metrics.saturation_pct !== null && (
          <span className="text-[10px] font-mono text-slate-600">
            SAT: {svc.metrics.saturation_pct}%
          </span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-2.5 !bg-[#0F1E36]"
      />
    </div>
  );
}

const nodeTypes = {
  serviceInstrument: ServiceInstrumentNode,
};

interface TopologyCanvasProps {
  graph: TopologyGraphResponse;
}

export function TopologyCanvas({ graph }: TopologyCanvasProps) {
  const [selectedNode, setSelectedNode] = useState<TopologyNode | null>(
    graph.nodes[0] || null
  );
  const [selectedEdge, setSelectedEdge] = useState<TopologyEdge | null>(null);

  const flowNodes: Node<ServiceNodeData>[] = useMemo(
    () =>
      graph.nodes.map((n) => ({
        id: n.id,
        type: "serviceInstrument",
        position: { x: n.position_x, y: n.position_y },
        data: { node: n },
      })),
    [graph.nodes]
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      graph.edges.map((e) => {
        const isObservedOnly = e.discovery_source === "observed";
        const isRegisteredOnly = e.discovery_source === "registered";
        const strokeColor = isObservedOnly
          ? "#047857"
          : isRegisteredOnly
          ? "#64748B"
          : "#0F1E36";
        const strokeDasharray = isObservedOnly
          ? "6 4"
          : isRegisteredOnly
          ? "3 3"
          : undefined;

        const latencyLabel =
          e.last_latency_ms !== null ? ` · ${e.last_latency_ms}ms` : "";
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          label: `${e.protocol.toUpperCase()} (${e.observation_count} obs${latencyLabel})`,
          animated: e.verified_by_observation,
          style: {
            stroke: strokeColor,
            strokeWidth: e.verified_by_observation ? 2.2 : 1.5,
            strokeDasharray,
          },
          labelStyle: {
            fill: "#0F1E36",
            fontWeight: 600,
            fontSize: 10,
            fontFamily: "monospace",
          },
          labelBgStyle: {
            fill: "#FAF8F5",
            fillOpacity: 0.92,
            stroke: "#E4DFD7",
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: strokeColor,
          },
        };
      }),
    [graph.edges]
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
      {/* Main React Flow Interactive Canvas */}
      <div className="lg:col-span-3 bg-white border border-[#E4DFD7] rounded-md overflow-hidden shadow-2xs flex flex-col">
        <div className="px-4 py-2.5 border-b border-[#E4DFD7] bg-[#F3EFEA]/50 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-3 font-mono text-[11px]">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-4 h-0.5 bg-[#0F1E36] inline-block" />
              Verified (Declared + Observed):{" "}
              <strong>
                {graph.edges.filter(
                  (e) => e.discovery_source === "registered_and_observed"
                ).length}
              </strong>
            </span>
            <span className="inline-flex items-center gap-1.5 text-emerald-800">
              <span className="w-4 h-0.5 border-b-2 border-dashed border-emerald-700 inline-block" />
              Observed Only:{" "}
              <strong>{graph.observed_only_edges}</strong>
            </span>
            <span className="inline-flex items-center gap-1.5 text-slate-600">
              <span className="w-4 h-0.5 border-b-2 border-dotted border-slate-500 inline-block" />
              Declared Only:{" "}
              <strong>{graph.registered_only_edges}</strong>
            </span>
          </div>
          <span className="font-mono text-[11px] text-slate-500">
            Nodes: {graph.total_nodes} · Edges: {graph.total_edges}
          </span>
        </div>

        <div className="h-[580px] w-full scientific-grid">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.22 }}
            onNodeClick={(_ev, node) => {
              setSelectedEdge(null);
              setSelectedNode(node.data.node);
            }}
            onEdgeClick={(_ev, edge) => {
              const found = graph.edges.find((item) => item.id === edge.id);
              if (found) {
                setSelectedNode(null);
                setSelectedEdge(found);
              }
            }}
          >
            <Background color="#D6CFC4" gap={20} size={1} />
            <Controls />
          </ReactFlow>
        </div>
      </div>

      {/* Scientific Provenance & Telemetry Inspector Panel */}
      <div className="bg-white border border-[#E4DFD7] rounded-md p-4 shadow-2xs flex flex-col justify-between">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-1">
            TOPOLOGY INSPECTOR
          </div>
          {selectedNode && (
            <div className="space-y-3">
              <div>
                <h3 className="font-serif text-base font-bold text-[#0F1E36]">
                  {selectedNode.display_name}
                </h3>
                <p className="font-mono text-xs text-slate-600">
                  {selectedNode.service_key}
                </p>
              </div>

              <div className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Provenance:</span>
                  <span className="font-mono font-semibold text-[#0F1E36]">
                    {selectedNode.registration_source}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Health Status:</span>
                  <span className="font-mono font-semibold uppercase">
                    {selectedNode.health_status}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Tier / Type:</span>
                  <span className="font-mono">
                    {selectedNode.tier} · {selectedNode.service_type}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Owner Team:</span>
                  <span className="font-mono">{selectedNode.owner_team}</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="text-[11px] font-mono uppercase text-slate-500">
                  Observed Telemetry Metrics
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                    <span className="text-[10px] text-slate-500 block">
                      MEAN LATENCY
                    </span>
                    <span className="text-sm font-bold text-[#0F1E36]">
                      {selectedNode.metrics.mean_latency_ms !== null
                        ? `${selectedNode.metrics.mean_latency_ms} ms`
                        : "—"}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                    <span className="text-[10px] text-slate-500 block">
                      P95 LATENCY
                    </span>
                    <span className="text-sm font-bold text-[#0F1E36]">
                      {selectedNode.metrics.p95_latency_ms !== null
                        ? `${selectedNode.metrics.p95_latency_ms} ms`
                        : "—"}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                    <span className="text-[10px] text-slate-500 block">
                      ERROR RATE
                    </span>
                    <span className="text-sm font-bold text-[#0F1E36]">
                      {selectedNode.metrics.error_rate_pct}%
                    </span>
                  </div>
                  <div className="p-2 rounded bg-[#FAF8F5] border border-[#E4DFD7]">
                    <span className="text-[10px] text-slate-500 block">
                      OBSERVED SPANS
                    </span>
                    <span className="text-sm font-bold text-[#0F1E36]">
                      {selectedNode.metrics.observed_span_count}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {selectedEdge && (
            <div className="space-y-3">
              <div>
                <h3 className="font-serif text-base font-bold text-[#0F1E36]">
                  Dependency Edge
                </h3>
                <p className="font-mono text-xs text-slate-700">
                  {selectedEdge.source} → {selectedEdge.target}
                </p>
              </div>
              <div className="p-2.5 rounded bg-[#FAF8F5] border border-[#E4DFD7] space-y-1.5 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">Discovery Source:</span>
                  <span className="font-semibold">
                    {selectedEdge.discovery_source}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Verified by Spans:</span>
                  <span className="font-semibold">
                    {selectedEdge.verified_by_observation ? "YES" : "NO"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Observations:</span>
                  <span className="font-semibold">
                    {selectedEdge.observation_count}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Last Latency:</span>
                  <span className="font-semibold">
                    {selectedEdge.last_latency_ms !== null
                      ? `${selectedEdge.last_latency_ms} ms`
                      : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Error Rate:</span>
                  <span className="font-semibold">
                    {selectedEdge.error_rate_pct}%
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="mt-6 pt-3 border-t border-[#E4DFD7] text-[11px] text-slate-600 leading-relaxed">
          <div className="font-mono font-semibold text-[#0F1E36] mb-1">
            SCIENTIFIC PROVENANCE GUARANTEE
          </div>
          {graph.provenance_notice}
        </div>
      </div>
    </div>
  );
}
