"use client";

/**
 * DependencyGraph.tsx — DEADLOCK Real Dependency Graph Renderer
 *
 * Renders graph data from the backend API using React Flow.
 * NO hardcoded demo nodes/edges.
 * NO fake status assignments based on seeded IDs (pr_11, issue_11, etc.).
 * Node status is derived purely from backend node data.
 *
 * Backend node schema:
 *   { id: "type:rawId", type: "pull_request"|"issue"|..., label: string, data: {...} }
 * Backend edge schema:
 *   { source: "type:rawId", target: "type:rawId", relation: string, data: {...} }
 */

import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  useReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
// Base styles loaded globally via app/globals.css
import { fetchGraphData } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";import {
  RefreshCw,
  FolderGit2,
  Search,
  AlertCircle,
  Info,
  GitPullRequest,
  CircleDot,
  GitCommit,
  Users,
  Flag,
  Milestone,
  Package,
} from "lucide-react";

// ============================================================
// Types
// ============================================================

type RawBackendNode = {
  id: string;          // "type:rawId"  e.g. "pull_request:12345"
  type: string;        // "pull_request" | "issue" | "developer" | ...
  label: string;
  repo?: string;       // "owner/repo" — present in combined workspace nodes
  data: Record<string, unknown>;
};

type RawBackendEdge = {
  source: string;
  target: string;
  relation: string;
  data?: Record<string, unknown>;
};

type NodeStatus =
  | "open"
  | "closed"
  | "merged"
  | "draft"
  | "blocking"
  | "overdue"
  | "healthy"
  | "unknown";

type DeadlockNodeData = {
  label: string;
  nodeType: string;
  status: NodeStatus;
  rawId: string;
  metadata: Record<string, unknown>;
};

type DeadlockNode = Node<DeadlockNodeData, "deadlock">;

// ============================================================
// Derive status from real backend node data
// ============================================================

function deriveStatus(nodeType: string, data: Record<string, unknown>): NodeStatus {
  const state = String(data.state || data.status || "").toLowerCase();
  if (nodeType === "pull_request") {
    if (data.draft) return "draft";
    if (state === "merged" || data.merged_at) return "merged";
    if (state === "closed") return "closed";
    return "open";
  }
  if (nodeType === "issue") {
    if (state === "closed") return "closed";
    return "open";
  }
  if (nodeType === "milestone") {
    if (state === "closed") return "closed";
    // overdue: due_on in the past
    const due = data.due_on || data.due_date;
    if (due && new Date(String(due)) < new Date()) return "overdue";
    return "open";
  }
  if (nodeType === "commit") return "healthy";
  if (nodeType === "developer") return "healthy";
  return "unknown";
}

// ============================================================
// Status → colour tokens
// ============================================================

const STATUS_BORDER: Record<NodeStatus, string> = {
  open:     "border-cyan-500/50",
  closed:   "border-zinc-600/40",
  merged:   "border-purple-500/50",
  draft:    "border-zinc-500/40",
  blocking: "border-red-500/70",
  overdue:  "border-amber-500/70",
  healthy:  "border-emerald-500/40",
  unknown:  "border-white/15",
};

const STATUS_BADGE: Record<NodeStatus, string> = {
  open:     "text-cyan-400 bg-cyan-500/10 border border-cyan-500/20",
  closed:   "text-zinc-400 bg-zinc-700/30 border border-zinc-600/20",
  merged:   "text-purple-300 bg-purple-500/10 border border-purple-500/30",
  draft:    "text-zinc-400 bg-zinc-700/20 border border-zinc-600/20",
  blocking: "text-red-300 bg-red-500/15 border border-red-500/30",
  overdue:  "text-amber-300 bg-amber-500/10 border border-amber-500/30",
  healthy:  "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20",
  unknown:  "text-zinc-500 bg-zinc-800/40",
};

const TYPE_ICON: Record<string, React.ElementType> = {
  pull_request: GitPullRequest,
  issue:        CircleDot,
  commit:       GitCommit,
  developer:    Users,
  deadline:     Flag,
  milestone:    Milestone,
  deployment:   Package,
};

// ============================================================
// Custom React Flow node component
// ============================================================

function DeadlockNodeComponent({ data, selected }: NodeProps<DeadlockNode>) {
  const { label, nodeType, status, rawId } = data;
  const Icon = TYPE_ICON[nodeType] || Package;

  return (
    <div
      className={`relative w-[220px] rounded-xl border ${STATUS_BORDER[status]} ${
        selected ? "ring-2 ring-cyan-400 ring-offset-1 ring-offset-[#0b0b0d]" : ""
      } bg-[#111113] px-3.5 py-3 shadow-lg transition-all hover:scale-[1.02]`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-0 !bg-cyan-500/60"
      />

      <div className="flex items-center justify-between gap-1.5 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <Icon size={11} className="shrink-0 text-zinc-400" />
          <span className="text-[9px] font-semibold tracking-wider text-zinc-500 uppercase truncate">
            {nodeType.replace(/_/g, " ")}
          </span>
        </div>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[8px] font-bold tracking-wider uppercase ${STATUS_BADGE[status]}`}>
          {status}
        </span>
      </div>

      <div className="text-[11px] font-semibold text-white line-clamp-2 leading-snug">
        {label}
      </div>

      <div className="mt-2 pt-1.5 border-t border-white/5 font-mono text-[9px] text-zinc-600 truncate">
        {rawId}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-0 !bg-cyan-500/60"
      />
    </div>
  );
}

const nodeTypes = { deadlock: DeadlockNodeComponent };

// ============================================================
// Edge colour by relation type
// ============================================================

function edgeStyle(relation: string): React.CSSProperties {
  const r = (relation || "").toLowerCase();
  if (r.includes("resolves") || r.includes("fixes"))  return { stroke: "#a855f7", strokeWidth: 1.5 };
  if (r.includes("depends") || r.includes("blocks"))  return { stroke: "#ef4444", strokeWidth: 1.5 };
  if (r.includes("authored") || r.includes("created")) return { stroke: "#22d3ee", strokeWidth: 1.5 };
  if (r.includes("assigned"))                          return { stroke: "#f59e0b", strokeWidth: 1.5 };
  if (r.includes("modifies") || r.includes("changes")) return { stroke: "#f97316", strokeWidth: 1.5 };
  if (r.includes("reviews"))                           return { stroke: "#84cc16", strokeWidth: 1.5 };
  return { stroke: "#52525b", strokeWidth: 1 };
}

function isAnimated(relation: string): boolean {
  const r = (relation || "").toLowerCase();
  return r.includes("depends") || r.includes("blocks") || r.includes("resolves");
}

// ============================================================
// Layout — simple column layout by node type
// ============================================================

const TYPE_COL: Record<string, number> = {
  pull_request: 0,
  issue:        1,
  milestone:    2,
  developer:    3,
  commit:       4,
  deployment:   5,
  deadline:     5,
  review:       6,
  file:         2,
};

const COL_X = 250; // px between columns

function layoutNodes(nodes: RawBackendNode[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const colCounters: Record<number, number> = {};

  // Separate project root from entity nodes for rendering
  const entityNodes = nodes.filter((n) => n.type !== "project");

  for (const node of entityNodes) {
    const col = TYPE_COL[node.type] ?? 7;
    const count = colCounters[col] ?? 0;
    positions.set(node.id, {
      x: col * COL_X + 30,
      y: count * 170 + 40,
    });
    colCounters[col] = count + 1;
  }

  return positions;
}

// ============================================================
// Auto-fit helper inner component (needs ReactFlowProvider)
// ============================================================

function AutoFitFlow({
  nodes,
  edges,
  onNodeClick,
}: {
  nodes: DeadlockNode[];
  edges: Edge[];
  onNodeClick: (node: DeadlockNode) => void;
}) {
  const { fitView } = useReactFlow();
  const fitted = useRef(false);

  useEffect(() => {
    if (nodes.length > 0 && !fitted.current) {
      setTimeout(() => fitView({ padding: 0.15, duration: 400 }), 60);
      fitted.current = true;
    }
    if (nodes.length === 0) fitted.current = false;
  }, [nodes.length, fitView]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      nodesDraggable
      nodesConnectable={false}
      elementsSelectable
      onNodeClick={(_, node) => onNodeClick(node as DeadlockNode)}
      minZoom={0.1}
      maxZoom={2.0}
    >
      <Background gap={24} size={1} color="#27272a" />
      <Controls className="!bg-[#111113] !border-white/10" />
      <MiniMap
        nodeColor="#27272a"
        maskColor="rgba(0,0,0,0.65)"
        className="!bg-[#09090b] !border !border-white/10 !rounded-lg"
      />
    </ReactFlow>
  );
}

// ============================================================
// Main component
// ============================================================

export default function DependencyGraph() {
  const { activeRepo, combinedWorkspace } = useWorkspace();

  const [rawNodes, setRawNodes]       = useState<RawBackendNode[]>([]);
  const [rawEdges, setRawEdges]       = useState<RawBackendEdge[]>([]);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [totalNodes, setTotalNodes]   = useState(0);
  const [totalEdges, setTotalEdges]   = useState(0);
  const [selectedNode, setSelectedNode] = useState<DeadlockNode | null>(null);
  const [typeFilter, setTypeFilter]   = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const loadGraph = useCallback(async () => {
    // If combined workspace is active, use its nodes/edges directly
    if (combinedWorkspace) {
      setRawNodes(combinedWorkspace.nodes as unknown as RawBackendNode[]);
      setRawEdges([
        ...(combinedWorkspace.edges as unknown as RawBackendEdge[]),
        // cross-repo edges are already included in combined.edges but add a type guard
      ]);
      setTotalNodes(combinedWorkspace.total_nodes);
      setTotalEdges(combinedWorkspace.total_edges);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    try {
      const owner    = activeRepo?.source !== "seeded" ? activeRepo?.owner    : undefined;
      const repoName = activeRepo?.source !== "seeded" ? activeRepo?.repo     : undefined;
      const data = await fetchGraphData(owner, repoName);
      if (!data.isLive && (owner || repoName)) {
        setError("Graph data unavailable — backend may be offline or this repository has not been synced yet.");
        setRawNodes([]); setRawEdges([]);
        return;
      }
      setRawNodes((data.nodes as unknown as RawBackendNode[]) || []);
      setRawEdges((data.edges as unknown as RawBackendEdge[]) || []);
      setTotalNodes(data.nodes.length);
      setTotalEdges(data.edges.length);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load graph";
      setError(msg); setRawNodes([]); setRawEdges([]);
    } finally { setLoading(false); }
  }, [activeRepo, combinedWorkspace]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // --------------------------------------------------------
  // Build ReactFlow nodes + edges from raw backend data
  // --------------------------------------------------------
  const { displayNodes, displayEdges, nodeTypeSet } = useMemo(() => {
    // Filter by type and search
    let filtered = rawNodes.filter((n) => n.type !== "project");
    if (typeFilter !== "ALL") {
      filtered = filtered.filter((n) => n.type === typeFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (n) => n.id.toLowerCase().includes(q) || (n.label || "").toLowerCase().includes(q)
      );
    }
    const visible = filtered.slice(0, 80);
    const positions = layoutNodes(visible);

    // Assign a colour index per repo for combined mode
    const repoList = Array.from(new Set(visible.map((n) => n.repo).filter((r): r is string => !!r)));
    const repoColorIndex: Record<string, number> = {};
    repoList.forEach((r, i) => { repoColorIndex[r] = i; });

    const mappedNodes: DeadlockNode[] = visible.map((n) => {
      const pos    = positions.get(n.id) || { x: 0, y: 0 };
      const status = deriveStatus(n.type, n.data);
      const rawId  = n.id.includes(":") ? n.id.split(":").slice(1).join(":") : n.id;
      const repoKey = n.repo ?? "";
      return {
        id: n.id, type: "deadlock", position: pos,
        data: { label: n.label || rawId, nodeType: n.type, status, rawId,
                metadata: { ...n.data, repo: repoKey, repoColorIndex: repoColorIndex[repoKey] ?? 0 } },
      };
    });

    const visibleIds = new Set(mappedNodes.map((n) => n.id));
    const mappedEdges: Edge[] = rawEdges
      .filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))
      .map((e, idx) => {
        const isCrossRepo = !!(e as RawBackendEdge & { cross_repo?: boolean }).cross_repo;
        return {
          id: `e-${idx}-${e.source}-${e.target}`,
          source: e.source, target: e.target,
          label: (e.relation || "").toUpperCase().replace(/_/g, " "),
          animated: isAnimated(e.relation) || isCrossRepo,
          style: isCrossRepo
            ? { stroke: "#f59e0b", strokeWidth: 2.5, strokeDasharray: "6 3" }
            : edgeStyle(e.relation),
          labelStyle: { fill: isCrossRepo ? "#f59e0b" : "#71717a", fontSize: 8, fontWeight: isCrossRepo ? 700 : 500 },
          labelBgStyle: { fill: "#111113", fillOpacity: 0.85 },
        };
      });

    const nodeTypeSet = Array.from(new Set(rawNodes.map((n) => n.type).filter((t) => t !== "project"))).sort();
    return { displayNodes: mappedNodes, displayEdges: mappedEdges, nodeTypeSet };
  }, [rawNodes, rawEdges, typeFilter, searchQuery]);

  const repoLabel = activeRepo
    ? activeRepo.fullName
    : "No repository selected";

  const isCombinedMode = !!combinedWorkspace;

  return (
    <div className="space-y-4">
      {/* ── TOOLBAR ────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-[#111113] p-4">
        {/* Repo badge + type filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-300 font-medium shrink-0">
            <FolderGit2 size={13} />
            {isCombinedMode
              ? `Combined: ${combinedWorkspace!.repositories.map((r) => r.split("/")[1]).join(" + ")}`
              : repoLabel}
            {isCombinedMode && combinedWorkspace!.cross_repo_edge_count > 0 && (
              <span className="ml-1 rounded bg-amber-500/20 px-1.5 py-0.5 text-[9px] text-amber-300 font-bold">
                {combinedWorkspace!.cross_repo_edge_count} cross-repo
              </span>
            )}
          </div>

          {/* ALL button */}
          <button
            onClick={() => setTypeFilter("ALL")}
            className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
              typeFilter === "ALL"
                ? "bg-white/15 text-white"
                : "text-zinc-500 hover:bg-white/5 hover:text-zinc-300"
            }`}
          >
            All
          </button>

          {/* Dynamic type filter buttons from actual data */}
          {nodeTypeSet.map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                typeFilter === t
                  ? "bg-white/15 text-white"
                  : "text-zinc-500 hover:bg-white/5 hover:text-zinc-300"
              }`}
            >
              {t.replace(/_/g, " ")}
            </button>
          ))}
        </div>

        {/* Search + Reload */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search
              size={12}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500"
            />
            <input
              type="text"
              placeholder="Search nodes…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-44 rounded-lg border border-white/10 bg-[#09090b] py-1.5 pl-7 pr-3 text-xs text-white placeholder:text-zinc-600 focus:border-cyan-400 focus:outline-none"
            />
          </div>

          <button
            onClick={loadGraph}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-zinc-300 hover:bg-white/10 disabled:opacity-50 transition"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            {loading ? "Loading…" : `Reload  (${totalNodes} nodes / ${totalEdges} edges)`}
          </button>
        </div>
      </div>

      {/* ── CANVAS ─────────────────────────────────────────── */}
      <div className="relative h-[780px] w-full overflow-hidden rounded-xl border border-white/10 bg-[#0b0b0d]">
        {loading ? (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <RefreshCw size={28} className="animate-spin text-cyan-400" />
            <p className="text-sm text-zinc-400">Building dependency graph…</p>
          </div>
        ) : error ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center px-8">
            <AlertCircle size={32} className="text-red-500" />
            <h3 className="text-sm font-semibold text-white">Graph unavailable</h3>
            <p className="text-xs text-zinc-500 max-w-md">{error}</p>
            <button
              onClick={loadGraph}
              className="mt-2 rounded-lg border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-zinc-300 hover:bg-white/10"
            >
              Retry
            </button>
          </div>
        ) : displayNodes.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center px-8">
            <Info size={32} className="text-zinc-600" />
            <h3 className="text-sm font-semibold text-white">
              {rawNodes.length > 0
                ? "No nodes match the current filter"
                : activeRepo
                ? `No graph nodes found for ${activeRepo.fullName}`
                : "Select a repository to view its dependency graph"}
            </h3>
            {rawNodes.length > 0 && typeFilter !== "ALL" && (
              <button
                onClick={() => setTypeFilter("ALL")}
                className="text-xs text-cyan-400 hover:underline"
              >
                Clear filter
              </button>
            )}
            {rawNodes.length === 0 && activeRepo && (
              <p className="text-xs text-zinc-500 max-w-sm">
                Sync the repository first to build its dependency graph.
              </p>
            )}
          </div>
        ) : (
          <ReactFlowProvider>
            <AutoFitFlow
              nodes={displayNodes}
              edges={displayEdges}
              onNodeClick={setSelectedNode}
            />
          </ReactFlowProvider>
        )}

        {/* ── NODE INSPECTOR PANEL ─────────────────────────── */}
        {selectedNode && (
          <div className="absolute bottom-4 left-4 z-20 w-80 rounded-xl border border-white/15 bg-[#111113]/96 p-4 shadow-2xl backdrop-blur-md">
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="text-[9px] font-semibold tracking-wider text-cyan-400 uppercase">
                  {selectedNode.data.nodeType.replace(/_/g, " ")}
                </span>
                <h4 className="mt-0.5 text-sm font-semibold text-white leading-snug">
                  {selectedNode.data.label}
                </h4>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="shrink-0 text-xs text-zinc-500 hover:text-white mt-0.5"
              >
                ✕
              </button>
            </div>

            <div className="mt-3 space-y-1.5 text-[11px] text-zinc-400">
              <div className="flex justify-between">
                <span>Status</span>
                <span className="font-medium text-zinc-200 uppercase">{selectedNode.data.status}</span>
              </div>
              <div className="flex justify-between">
                <span>Node ID</span>
                <span className="font-mono text-zinc-500 truncate max-w-[170px]">{selectedNode.id}</span>
              </div>
            </div>

            {/* Key metadata fields */}
            {(() => {
              const meta = selectedNode.data.metadata || {};
              const fields: [string, string][] = [];

              if (meta.state || meta.status)
                fields.push(["State", String(meta.state || meta.status)]);
              if (meta.author || meta.author_id)
                fields.push(["Author", String(meta.author || meta.author_id)]);
              if (meta.assignee || meta.assignee_id)
                fields.push(["Assignee", String(meta.assignee || meta.assignee_id)]);
              if (meta.created_at)
                fields.push(["Created", new Date(String(meta.created_at)).toLocaleDateString()]);
              if (meta.updated_at)
                fields.push(["Updated", new Date(String(meta.updated_at)).toLocaleDateString()]);
              if (meta.due_on || meta.due_date)
                fields.push(["Due", String(meta.due_on || meta.due_date)]);
              if (meta.number)
                fields.push(["Number", String(meta.number)]);

              return fields.length > 0 ? (
                <div className="mt-3 border-t border-white/5 pt-2.5 space-y-1.5 text-[11px]">
                  {fields.map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2">
                      <span className="text-zinc-500 shrink-0">{k}</span>
                      <span className="text-zinc-300 truncate text-right">{v}</span>
                    </div>
                  ))}
                </div>
              ) : null;
            })()}

            {/* GitHub link if we can construct one */}
            {(() => {
              const meta   = selectedNode.data.metadata || {};
              const owner  = activeRepo?.owner;
              const repo   = activeRepo?.repo;
              const type   = selectedNode.data.nodeType;
              const num    = meta.number;
              if (!owner || !repo || !num) return null;
              let path = "";
              if (type === "pull_request") path = `pull/${num}`;
              else if (type === "issue") path = `issues/${num}`;
              else if (type === "milestone") path = `milestone/${num}`;
              if (!path) return null;
              const url = `https://github.com/${owner}/${repo}/${path}`;
              return (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 block text-center text-[10px] text-cyan-400 hover:underline"
                >
                  View on GitHub →
                </a>
              );
            })()}
          </div>
        )}
      </div>

      {/* ── LEGEND ─────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-white/5 bg-[#111113] px-4 py-3">
        <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-wider">
          Edge types
        </span>
        {[
          { color: "#a855f7", label: "Resolves / Fixes" },
          { color: "#ef4444", label: "Depends on / Blocks" },
          { color: "#22d3ee", label: "Authored by" },
          { color: "#f59e0b", label: "Assigned to" },
          { color: "#f97316", label: "Modifies" },
          { color: "#84cc16", label: "Reviews" },
          { color: "#52525b", label: "Other" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="h-px w-6" style={{ backgroundColor: color }} />
            <span className="text-[10px] text-zinc-500">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
