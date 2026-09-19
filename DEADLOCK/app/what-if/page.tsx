"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Play, AlertTriangle, ArrowRight, FolderGit2, Network } from "lucide-react";
import { runSimulation, fetchGraphData, formatNodeLabel } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

type ScenarioType = "PR_DELAY" | "TASK_DELAY" | "SERVICE_FAILURE" | "TIMEOUT" | "LATENCY" | "DEPLOYMENT_FAILURE";

type SimulationResult = {
  scenario?: string;
  root_node?: string;
  affected_nodes?: string[];
  unaffected_nodes?: string[];
  propagation_paths?: string[][];
  before?: { risk_score?: number };
  after?: { risk_score?: number };
  risk_before?: number;
  risk_after?: number;
  recommendation?: string;
  causal_chain?: string[];
  warnings?: string[];
};

type TargetOption = { id: string; label: string; repo?: string };

function WhatIfContent() {
  const searchParams = useSearchParams();
  const initialNode = searchParams.get("node") || "";
  const { activeRepo, combinedWorkspace } = useWorkspace();

  const [scenario, setScenario] = useState<ScenarioType>("PR_DELAY");
  const [target, setTarget] = useState("");
  const [customTarget, setCustomTarget] = useState("");
  const [delayDays, setDelayDays] = useState("3");
  const [latencyMs, setLatencyMs] = useState("2000");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [availableTargets, setAvailableTargets] = useState<TargetOption[]>([]);
  const [selectedSimRepo, setSelectedSimRepo] = useState<string>("");

  const isCombinedMode = !!combinedWorkspace;

  // Load target nodes: from combined workspace or from active repo graph
  const loadTargetNodes = useCallback(async () => {
    if (isCombinedMode && combinedWorkspace) {
      // Use combined workspace nodes — filter to meaningful types
      const targets: TargetOption[] = combinedWorkspace.nodes
        .filter((n) => ["pull_request", "issue", "milestone", "commit", "file"].includes(n.type))
        .slice(0, 60)
        .map((n) => ({
          id: n.id,
          repo: n.repo,
          label: `[${n.repo?.split("/")[1] ?? n.repo}] ${n.type.toUpperCase()}: ${(n.label || "").slice(0, 50)} (${n.id})`,
        }));
      setAvailableTargets(targets);
      if (targets.length > 0) setTarget(initialNode || targets[0].id);
      return;
    }

    if (!activeRepo || activeRepo.source === "seeded") {
      setAvailableTargets([]);
      return;
    }

    try {
      const graph = await fetchGraphData(activeRepo.owner, activeRepo.repo);
      if (graph.nodes && graph.nodes.length > 0) {
        const mapped = graph.nodes
          .filter((n: Record<string, unknown>) =>
            ["pull_request", "issue", "milestone", "deployment", "commit"].includes(String(n.type || ""))
          )
          .slice(0, 50)
          .map((n: Record<string, unknown>) => ({
            id: String(n.id),
            repo: activeRepo.id,
            label: `${String(n.type || "node").toUpperCase()}: ${String(n.label || formatNodeLabel(String(n.id)))} (${n.id})`,
          }));
        setAvailableTargets(mapped);
        if (mapped.length > 0) setTarget(initialNode || mapped[0].id);
      } else {
        setAvailableTargets([]);
      }
    } catch {
      setAvailableTargets([]);
    }
  }, [activeRepo, isCombinedMode, combinedWorkspace, initialNode]);

  useEffect(() => { loadTargetNodes(); }, [loadTargetNodes]);

  const isDelay   = scenario === "PR_DELAY" || scenario === "TASK_DELAY";
  const isLatency = scenario === "LATENCY";

  const executeSimulation = async () => {
    setLoading(true); setError(""); setResult(null);
    const effectiveTarget = customTarget.trim() ? customTarget.trim() : target;
    if (!effectiveTarget) { setError("Select a target node first."); setLoading(false); return; }

    try {
      const payload: Record<string, unknown> = { node_id: effectiveTarget, event_type: scenario };
      if (isDelay) payload.delay_days = parseInt(delayDays, 10) || 3;
      if (isLatency) payload.latency_ms = parseInt(latencyMs, 10) || 2000;

      // Determine which repo to run simulation against
      let simOwner: string | undefined;
      let simRepo:  string | undefined;

      if (isCombinedMode && combinedWorkspace) {
        // Find which repo the selected node belongs to
        const nodeRepo = selectedSimRepo ||
          combinedWorkspace.nodes.find((n) => n.id === effectiveTarget)?.repo ||
          combinedWorkspace.repositories[0];
        if (nodeRepo) {
          const [o, r] = nodeRepo.split("/");
          simOwner = o; simRepo = r;
        }
      } else if (activeRepo && activeRepo.source !== "seeded") {
        simOwner = activeRepo.owner; simRepo = activeRepo.repo;
      }

      const data = await runSimulation(payload as Parameters<typeof runSimulation>[0], simOwner, simRepo);
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Simulation failed.");
    } finally { setLoading(false); }
  };

  const scoreBefore = result?.before?.risk_score ?? result?.risk_before ?? 0;
  const scoreAfter  = result?.after?.risk_score  ?? result?.risk_after  ?? 0;
  const scoreDelta  = scoreAfter - scoreBefore;

  // Group targets by repo for display in combined mode
  const repoGroups = isCombinedMode
    ? Array.from(new Set(availableTargets.map((t) => t.repo).filter(Boolean))) as string[]
    : [];

  const contextLabel = isCombinedMode
    ? `Combined: ${combinedWorkspace!.repositories.map((r) => r.split("/")[1]).join(" + ")}`
    : activeRepo ? activeRepo.fullName : "No repo selected";

  return (
    <div className="space-y-8 pb-12">
      {/* HEADER */}
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11px] font-medium tracking-[0.2em] text-cyan-400">IMPACT SIMULATION STUDIO</span>
          <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300 border border-cyan-500/20 flex items-center gap-1">
            {isCombinedMode ? <Network size={11} /> : <FolderGit2 size={11} />}
            {contextLabel}
          </span>
          {isCombinedMode && (
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300 border border-amber-500/20">
              {combinedWorkspace!.cross_repo_edge_count > 0 ? `${combinedWorkspace!.cross_repo_edge_count} cross-repo edges` : "No cross-repo edges"}
            </span>
          )}
        </div>
        <h1 className="mt-2 text-3xl font-bold text-white lg:text-4xl">What-If Failure Propagation</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">
          {isCombinedMode
            ? "Simulate failures across all selected repositories using the combined dependency graph."
            : `Test hypothetical delays or failures against the real project graph for ${activeRepo?.fullName ?? "the active repository"}.`}
        </p>
      </div>

      {/* CONTROLS */}
      <div className="rounded-xl border border-white/10 bg-[#111113] p-6 shadow-xl">
        <h2 className="text-base font-semibold text-white">Configure Simulation Event</h2>

        <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-3">
          {/* Event type */}
          <div>
            <label className="text-xs font-medium text-zinc-400">Event Type</label>
            <select value={scenario} onChange={(e) => setScenario(e.target.value as ScenarioType)}
              className="mt-2 w-full rounded-lg border border-white/10 bg-[#09090b] px-3 py-2.5 text-xs text-white focus:border-cyan-400/50 focus:outline-none">
              <option value="PR_DELAY">PR Delay</option>
              <option value="TASK_DELAY">Task / Issue Delay</option>
              <option value="SERVICE_FAILURE">Service Outage</option>
              <option value="LATENCY">API Latency Spike</option>
              <option value="DEPLOYMENT_FAILURE">Deployment Failure</option>
              <option value="TIMEOUT">Gateway Timeout</option>
            </select>
          </div>

          {/* Target node */}
          <div>
            <label className="text-xs font-medium text-zinc-400">
              Target Node {isCombinedMode ? "(Combined Graph)" : "(Active Graph)"}
            </label>
            {availableTargets.length > 0 ? (
              <select value={target} onChange={(e) => { setTarget(e.target.value); setCustomTarget(""); }}
                className="mt-2 w-full rounded-lg border border-white/10 bg-[#09090b] px-3 py-2.5 text-xs text-white focus:border-cyan-400/50 focus:outline-none">
                {isCombinedMode
                  ? repoGroups.map((repo) => (
                      <optgroup key={repo} label={repo}>
                        {availableTargets.filter((t) => t.repo === repo).map((t) => (
                          <option key={t.id} value={t.id}>{t.label}</option>
                        ))}
                      </optgroup>
                    ))
                  : availableTargets.map((t) => (
                      <option key={t.id} value={t.id}>{t.label}</option>
                    ))}
              </select>
            ) : (
              <div className="mt-2 rounded-lg border border-white/10 bg-[#09090b] px-3 py-2.5 text-xs text-zinc-500">
                {isCombinedMode ? "No nodes in combined graph" : "Sync a repository first"}
              </div>
            )}
            <input type="text" placeholder="Or custom node ID (e.g. pull_request:12345)"
              value={customTarget} onChange={(e) => setCustomTarget(e.target.value)}
              className="mt-2 w-full rounded-md border border-white/10 bg-[#09090b] px-2.5 py-1 text-[11px] text-zinc-300 placeholder:text-zinc-600 focus:border-cyan-400 focus:outline-none" />
          </div>

          {/* Params */}
          <div>
            {isDelay && (
              <>
                <label className="text-xs font-medium text-zinc-400">Delay Duration (Days)</label>
                <input type="number" min="1" max="30" value={delayDays} onChange={(e) => setDelayDays(e.target.value)}
                  className="mt-2 w-full rounded-lg border border-white/10 bg-[#09090b] px-3 py-2 text-xs text-white focus:border-cyan-400/50 focus:outline-none" />
              </>
            )}
            {isLatency && (
              <>
                <label className="text-xs font-medium text-zinc-400">Latency Spike (ms)</label>
                <input type="number" min="100" step="500" value={latencyMs} onChange={(e) => setLatencyMs(e.target.value)}
                  className="mt-2 w-full rounded-lg border border-white/10 bg-[#09090b] px-3 py-2 text-xs text-white focus:border-cyan-400/50 focus:outline-none" />
              </>
            )}
            {!isDelay && !isLatency && (
              <div className="mt-6">
                <label className="text-xs font-medium text-zinc-400">Severity</label>
                <div className="mt-2 rounded-lg border border-red-500/20 bg-red-950/10 px-3 py-2 text-xs font-medium text-red-400">CRITICAL SHUTDOWN</div>
              </div>
            )}
            {isCombinedMode && (
              <div className="mt-3">
                <label className="text-xs font-medium text-zinc-400">Simulation Scope</label>
                <select value={selectedSimRepo} onChange={(e) => setSelectedSimRepo(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-white/10 bg-[#09090b] px-3 py-1.5 text-xs text-white focus:border-cyan-400/50 focus:outline-none">
                  <option value="">Auto-detect from node</option>
                  {combinedWorkspace!.repositories.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between border-t border-white/10 pt-4 flex-wrap gap-3">
          <div className="text-xs text-zinc-500">
            Target: <span className="font-semibold text-cyan-400">{customTarget || target || "none"}</span>
            {" "}| Type: {scenario}
          </div>
          <button onClick={executeSimulation} disabled={loading || (!target && !customTarget.trim())}
            className="flex items-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/15 px-5 py-2.5 text-xs font-medium text-cyan-200 transition hover:bg-cyan-400/25 disabled:opacity-50">
            <Play size={13} className={loading ? "animate-spin" : ""} />
            {loading ? "Executing…" : "Execute Simulation"}
          </button>
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
            <AlertTriangle size={15} /> {error}
          </div>
        )}
      </div>

      {/* RESULTS */}
      {result && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
              <div className="text-xs font-medium text-zinc-500">BASELINE RISK SCORE</div>
              <div className="mt-2 text-3xl font-bold text-white">{scoreBefore} / 100</div>
              <div className="mt-1 text-xs text-zinc-500">Pre-simulation</div>
            </div>
            <div className="rounded-xl border border-red-500/30 bg-red-950/10 p-5">
              <div className="text-xs font-medium text-red-400">SIMULATED RISK SCORE</div>
              <div className="mt-2 text-3xl font-bold text-red-400">{scoreAfter} / 100</div>
              <div className="mt-1 text-xs text-red-300">Delta: +{scoreDelta}</div>
            </div>
            <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
              <div className="text-xs font-medium text-zinc-500">DOWNSTREAM AFFECTED</div>
              <div className="mt-2 text-3xl font-bold text-cyan-400">
                {(result.affected_nodes ?? []).filter((n) => n !== result.root_node).length} Nodes
              </div>
              <div className="mt-1 text-xs text-zinc-500">In propagation path</div>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-[#111113] p-6">
            <div className="text-[10px] font-semibold tracking-wider text-cyan-400 uppercase">PROPAGATION SUMMARY</div>
            <h3 className="mt-1 text-base font-semibold text-white">{result.scenario || "Controlled Failure Simulation"}</h3>
            {result.recommendation && (
              <div className="mt-3 rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-3 text-xs leading-5 text-cyan-200">
                <strong>Mitigation: </strong>{result.recommendation}
              </div>
            )}
            {result.warnings && result.warnings.length > 0 && (
              <div className="mt-2 text-xs text-amber-400">{result.warnings.join(" | ")}</div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-semibold text-white">Affected Components</h4>
                <span className="rounded bg-red-500/10 px-2 py-0.5 text-[10px] font-bold text-red-400">
                  {(result.affected_nodes ?? []).filter((n) => n !== result.root_node).length} impacted
                </span>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {(result.affected_nodes ?? []).length === 0
                  ? <p className="text-xs text-zinc-500 py-4 text-center">No downstream impact detected.</p>
                  : (result.affected_nodes ?? []).map((n) => (
                      <div key={n} className="flex items-center justify-between rounded-lg border border-red-500/20 bg-red-950/10 px-3 py-2 text-xs">
                        <span className="text-zinc-200 font-mono text-[10px]">{formatNodeLabel(n)}</span>
                        <span className="font-mono text-[10px] text-red-400">AT RISK</span>
                      </div>
                    ))}
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-[#111113] p-5">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-semibold text-white">Unaffected</h4>
                <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-400">
                  {result.unaffected_nodes?.length || 0} safe
                </span>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {(result.unaffected_nodes ?? []).slice(0, 15).map((n) => (
                  <div key={n} className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-xs">
                    <span className="text-zinc-400 font-mono text-[10px]">{formatNodeLabel(n)}</span>
                    <span className="font-mono text-[10px] text-emerald-400">HEALTHY</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {result.propagation_paths && result.propagation_paths.length > 0 && (
            <div className="rounded-xl border border-white/10 bg-[#111113] p-6">
              <h4 className="text-sm font-semibold text-white">Propagation Paths</h4>
              <p className="mt-1 text-xs text-zinc-500">Causal chains from graph traversal</p>
              <div className="mt-4 space-y-3">
                {result.propagation_paths.slice(0, 5).map((path, idx) => (
                  <div key={idx} className="flex flex-wrap items-center gap-1.5 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-xs">
                    {path.map((step, si) => (
                      <div key={`${step}-${si}`} className="flex items-center gap-1.5">
                        <span className={`rounded px-2 py-1 font-mono text-[11px] ${
                          si === 0 ? "bg-cyan-500/20 text-cyan-300 font-bold"
                          : si === path.length - 1 ? "bg-red-500/20 text-red-300 font-bold"
                          : "bg-white/5 text-zinc-300"}`}>
                          {formatNodeLabel(step)}
                        </span>
                        {si < path.length - 1 && <ArrowRight size={12} className="text-zinc-600" />}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function WhatIfPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[50vh] items-center justify-center"><div className="h-6 w-6 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" /></div>}>
      <WhatIfContent />
    </Suspense>
  );
}
