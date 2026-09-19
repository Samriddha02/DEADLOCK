"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  RefreshCw, Play, ArrowRight, ShieldCheck, FolderGit2,
  Plus, Sparkles, Clock, Trash2, CheckSquare, Square,
  Network, AlertCircle, ChevronDown, ChevronUp, ExternalLink,
} from "lucide-react";
import StatCard from "@/components/StatCard";
import RiskCard from "@/components/RiskCard";
import { fetchProjectRisks } from "@/lib/api";
import { ProjectStats, Risk } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace-context";

export default function DashboardPage() {
  const {
    repositories, activeRepo, activeRepoId, setActiveRepoId,
    addRepository, syncRepository, loadDemoProject, removeRepository, aggregatedStats,
    selectedRepoIds, toggleRepoSelection, selectAllRepos, clearSelection,
    combinedWorkspace, combinedLoading, combinedError, analyzeCombined, clearCombined,
  } = useWorkspace();

  const [stats, setStats] = useState<ProjectStats>({ health: 100, criticalRisks: 0, highRisks: 0, blockedTasks: 0, upcomingDeadlines: 0 });
  const [risksList, setRisksList] = useState<Risk[]>([]);
  const [loading, setLoading] = useState(false);
  const [repoUrl, setRepoUrl] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [showCombined, setShowCombined] = useState(false);
  const [combinedRepoFilter, setCombinedRepoFilter] = useState<string>("ALL");

  const loadActiveRepoData = useCallback(async () => {
    if (!activeRepo) return;
    setLoading(true);
    try {
      const owner = activeRepo.source !== "seeded" ? activeRepo.owner : undefined;
      const repo  = activeRepo.source !== "seeded" ? activeRepo.repo  : undefined;
      const res = await fetchProjectRisks(owner, repo);
      setStats(res.projectStats);
      setRisksList(res.risks);
    } catch { /* leave empty */ } finally { setLoading(false); }
  }, [activeRepo]);

  useEffect(() => { loadActiveRepoData(); }, [loadActiveRepoData]);

  // Auto-show combined panel when result arrives
  useEffect(() => { if (combinedWorkspace) setShowCombined(true); }, [combinedWorkspace]);

  const handleAddRepo = async () => {
    if (!repoUrl.trim()) { setStatusMessage({ text: "Enter a GitHub URL.", type: "error" }); return; }
    setActionLoading(true); setStatusMessage(null);
    const res = await addRepository(repoUrl.trim()); setActionLoading(false);
    if (res.success) { setStatusMessage({ text: `✅ Added ${res.repo?.fullName}`, type: "success" }); setRepoUrl(""); }
    else setStatusMessage({ text: `❌ ${res.error}`, type: "error" });
  };

  const selectedCount = selectedRepoIds.size;
  const readyRepos = repositories.filter((r) => r.status === "READY" && r.source !== "seeded");

  // Combined graph stats
  const combinedNodesByRepo = combinedWorkspace
    ? combinedWorkspace.nodes.reduce<Record<string, number>>((acc, n) => {
        if (n.repo) acc[n.repo] = (acc[n.repo] || 0) + 1;
        return acc;
      }, {})
    : {};

  return (
    <div className="space-y-10">
      {/* HEADER */}
      <section className="border-b border-white/10 pb-8">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <span className="text-[11px] font-medium tracking-[0.22em] text-cyan-400">SOFTWARE PROJECT INTELLIGENCE</span>
              <span className="rounded bg-white/10 px-2 py-0.5 text-[9px] font-semibold text-zinc-300">MULTI-REPOSITORY WORKSPACE</span>
            </div>
            <h1 className="text-5xl font-bold tracking-tight text-white lg:text-6xl">DEADLOCK</h1>
            <p className="mt-2 text-lg text-zinc-400">Deterministic Failure-Propagation Engine</p>
          </div>
          <div className="flex flex-col items-start gap-3 md:items-end">
            <div className="flex flex-wrap items-center gap-2">
              <input type="text" placeholder="https://github.com/owner/repo" value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleAddRepo(); }}
                className="w-64 rounded-lg border border-white/10 bg-[#09090b] px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-cyan-400 focus:outline-none" />
              <button onClick={handleAddRepo} disabled={actionLoading}
                className="flex items-center gap-1.5 rounded-lg border border-cyan-400/40 bg-cyan-400/10 px-3 py-1.5 text-xs font-medium text-cyan-300 transition hover:bg-cyan-400/20 disabled:opacity-50">
                {actionLoading ? <RefreshCw size={13} className="animate-spin" /> : <Plus size={13} />} Add Repository
              </button>
              <button onClick={loadDemoProject}
                className="flex items-center gap-1.5 rounded-lg border border-purple-500/30 bg-purple-500/10 px-3 py-1.5 text-xs font-medium text-purple-300 transition hover:bg-purple-500/20">
                <Sparkles size={13} /> Demo
              </button>
            </div>
            {statusMessage && (
              <p className={`text-xs ${statusMessage.type === "success" ? "text-emerald-400" : "text-red-400"}`}>{statusMessage.text}</p>
            )}
          </div>
        </div>
      </section>

      {/* MULTI-REPO WORKSPACE */}
      <section className="space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <FolderGit2 size={18} className="text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Project Workspace ({repositories.length})</h2>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs text-zinc-400">
              Total Risks: <strong className="text-white">{aggregatedStats.totalRisks}</strong>
              <span className="ml-3">Critical: <strong className="text-red-400">{aggregatedStats.criticalRisks}</strong></span>
            </span>
            {readyRepos.length > 0 && (
              <div className="flex items-center gap-2">
                <button onClick={selectAllRepos}
                  className="text-xs text-zinc-400 hover:text-white transition px-2 py-1 rounded border border-white/10 hover:bg-white/5">
                  Select All
                </button>
                {selectedCount > 0 && (
                  <button onClick={clearSelection}
                    className="text-xs text-zinc-500 hover:text-white transition px-2 py-1 rounded border border-white/10 hover:bg-white/5">
                    Clear ({selectedCount})
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {repositories.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-white/10 bg-[#111113]/50 p-8 text-center">
            <FolderGit2 size={32} className="text-zinc-600 mb-2" />
            <h3 className="text-sm font-semibold text-white">No Repositories in Workspace</h3>
            <p className="mt-1 text-xs text-zinc-500 max-w-sm">
              Add a GitHub repository URL above to begin analysis.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {repositories.map((repo) => {
              const isActive   = activeRepoId === repo.id;
              const isSelected = selectedRepoIds.has(repo.id);
              const canSelect  = repo.status === "READY" && repo.source !== "seeded";
              return (
                <div key={repo.id}
                  onClick={() => { if (!combinedWorkspace) setActiveRepoId(repo.id); }}
                  className={`group relative cursor-pointer rounded-xl border p-4 transition-all ${
                    isSelected
                      ? "border-cyan-400/80 bg-gradient-to-b from-cyan-950/30 to-[#111113] shadow-lg shadow-cyan-950/30"
                      : isActive
                      ? "border-cyan-400/40 bg-gradient-to-b from-cyan-950/10 to-[#111113]"
                      : "border-white/10 bg-[#111113] hover:border-white/20"
                  }`}>
                  {/* Checkbox */}
                  {canSelect && (
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleRepoSelection(repo.id); }}
                      className="absolute top-3 right-3 text-zinc-500 hover:text-cyan-400 transition z-10"
                      title={isSelected ? "Deselect" : "Select for combined analysis"}>
                      {isSelected ? <CheckSquare size={16} className="text-cyan-400" /> : <Square size={16} />}
                    </button>
                  )}

                  <div className="flex items-start justify-between gap-2 pr-6">
                    <div className="truncate">
                      <span className="font-semibold text-white truncate text-sm">{repo.fullName}</span>
                      <div className="mt-1 flex items-center gap-2 text-[10px] text-zinc-500">
                        <span>{repo.source === "seeded" ? "Demo" : "GitHub"}</span>
                        <span>•</span>
                        <span className="capitalize">{repo.status.toLowerCase()}</span>
                      </div>
                    </div>
                    <span className={`shrink-0 rounded px-2 py-0.5 text-[9px] font-bold tracking-wider ${
                      repo.status === "READY" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                      : repo.status === "ANALYZING" || repo.status === "SYNCING" ? "bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse"
                      : repo.status === "ERROR" ? "bg-red-500/10 text-red-400 border border-red-500/20"
                      : "bg-zinc-800 text-zinc-400"}`}>
                      {repo.status}
                    </span>
                  </div>

                  {repo.error ? (
                    <div className="mt-3 rounded-lg border border-red-500/20 bg-red-950/10 p-2 text-[11px] text-red-300">{repo.error}</div>
                  ) : (
                    <div className="mt-4 grid grid-cols-3 gap-2 border-t border-white/5 pt-3 text-center">
                      <div className="rounded bg-white/[0.02] p-1.5">
                        <div className="text-[9px] text-zinc-500 uppercase">Risks</div>
                        <div className="text-xs font-semibold text-white">{repo.riskCount ?? 0}</div>
                      </div>
                      <div className="rounded bg-white/[0.02] p-1.5">
                        <div className="text-[9px] text-zinc-500 uppercase">Critical</div>
                        <div className="text-xs font-semibold text-red-400">{repo.criticalRiskCount ?? 0}</div>
                      </div>
                      <div className="rounded bg-white/[0.02] p-1.5">
                        <div className="text-[9px] text-zinc-500 uppercase">Nodes</div>
                        <div className="text-xs font-semibold text-cyan-400">{repo.nodeCount ?? "—"}</div>
                      </div>
                    </div>
                  )}

                  <div className="mt-3 flex items-center justify-between border-t border-white/5 pt-2 text-[10px]">
                    <span className="text-zinc-500 flex items-center gap-1">
                      <Clock size={11} />
                      {repo.lastSynced ? new Date(repo.lastSynced).toLocaleTimeString() : "Never"}
                    </span>
                    <div className="flex items-center gap-2">
                      <button onClick={(e) => { e.stopPropagation(); syncRepository(repo.id); }}
                        disabled={repo.status === "SYNCING" || repo.status === "ANALYZING"}
                        className="text-zinc-400 hover:text-white transition" title="Re-sync">
                        <RefreshCw size={11} className={repo.status === "SYNCING" ? "animate-spin" : ""} />
                      </button>
                      <button onClick={(e) => { e.stopPropagation(); removeRepository(repo.id); }}
                        className="text-zinc-500 hover:text-red-400 transition" title="Remove">
                        <Trash2 size={11} />
                      </button>
                      <span className={`text-[10px] font-medium ${isActive ? "text-cyan-400" : "text-zinc-500 group-hover:text-zinc-300"}`}>
                        {isActive && !combinedWorkspace ? "● Active" : "Select →"}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ANALYZE SELECTED BUTTON */}
        {selectedCount >= 2 && (
          <div className="flex items-center gap-4 rounded-xl border border-cyan-500/30 bg-cyan-950/10 p-4">
            <div className="flex-1">
              <div className="text-sm font-semibold text-white">
                {selectedCount} repositories selected for combined analysis
              </div>
              <div className="mt-0.5 text-xs text-zinc-400">
                {Array.from(selectedRepoIds).join(" · ")}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {combinedWorkspace && (
                <button onClick={clearCombined}
                  className="px-3 py-1.5 text-xs text-zinc-400 border border-white/10 rounded-lg hover:bg-white/5 transition">
                  Clear
                </button>
              )}
              <button onClick={analyzeCombined} disabled={combinedLoading}
                className="flex items-center gap-2 rounded-lg border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-xs font-medium text-cyan-200 transition hover:bg-cyan-400/25 disabled:opacity-50">
                {combinedLoading ? <RefreshCw size={13} className="animate-spin" /> : <Network size={13} />}
                {combinedLoading ? "Analyzing…" : "Analyze Selected Repositories"}
              </button>
            </div>
          </div>
        )}
        {selectedCount === 1 && (
          <p className="text-xs text-zinc-500 pl-1">Select at least 2 repositories to run combined analysis.</p>
        )}
        {combinedError && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-950/10 p-3 text-xs text-red-300">
            <AlertCircle size={14} /> {combinedError}
          </div>
        )}
      </section>

      {/* COMBINED WORKSPACE RESULTS */}
      {combinedWorkspace && (
        <section className="space-y-4">
          <button onClick={() => setShowCombined((v) => !v)}
            className="flex w-full items-center justify-between rounded-xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/20 to-[#111113] p-4 text-left">
            <div className="flex items-center gap-3">
              <Network size={20} className="text-cyan-400" />
              <div>
                <div className="text-sm font-bold text-white">
                  Combined Workspace — {combinedWorkspace.repositories.length} Repositories
                </div>
                <div className="mt-0.5 text-xs text-zinc-400">
                  {combinedWorkspace.total_nodes} nodes · {combinedWorkspace.total_edges} edges ·{" "}
                  {combinedWorkspace.cross_repo_edge_count} cross-repo relationships ·{" "}
                  {combinedWorkspace.total_risks} risks
                </div>
              </div>
            </div>
            {showCombined ? <ChevronUp size={16} className="text-zinc-400" /> : <ChevronDown size={16} className="text-zinc-400" />}
          </button>

          {showCombined && (
            <div className="space-y-5">
              {/* Repo breakdown */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {combinedWorkspace.repositories.map((repo) => (
                  <div key={repo} className="rounded-xl border border-white/10 bg-[#111113] p-3 text-center">
                    <div className="text-xs font-semibold text-zinc-200 truncate">{repo}</div>
                    <div className="mt-1 text-[11px] text-zinc-500">{combinedNodesByRepo[repo] ?? 0} nodes</div>
                  </div>
                ))}
              </div>

              {/* Cross-repo edges */}
              <div className="rounded-xl border border-white/10 bg-[#111113] p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-white">
                    Cross-Repository Relationships ({combinedWorkspace.cross_repo_edge_count})
                  </h3>
                  {!combinedWorkspace.has_cross_repo_evidence && (
                    <span className="text-[10px] text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded">No verified evidence found</span>
                  )}
                </div>
                {combinedWorkspace.cross_repo_edges.length === 0 ? (
                  <p className="text-xs text-zinc-500 py-2">
                    No verified cross-repository dependency detected. The repositories may be independent, or their manifests do not reference each other directly.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {combinedWorkspace.cross_repo_edges.map((edge, i) => (
                      <div key={i} className="rounded-lg border border-cyan-500/20 bg-cyan-950/10 p-3 text-xs space-y-1">
                        <div className="flex items-center gap-2 font-mono text-[11px]">
                          <span className="text-cyan-300">{edge.source_repo}</span>
                          <ArrowRight size={11} className="text-zinc-500" />
                          <span className="text-purple-300">{edge.target_repo}</span>
                          <span className="ml-auto text-[9px] font-bold tracking-wider text-zinc-500 uppercase">{edge.relationship_type}</span>
                        </div>
                        <div className="text-zinc-400">{edge.evidence}</div>
                        <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                          <span>File: <code className="text-zinc-300">{edge.source_file}</code></span>
                          <span>Confidence: {Math.round(edge.confidence * 100)}%</span>
                          <span>{edge.inferred ? "INFERRED" : "DIRECT"}</span>
                          {edge.source_url && (
                            <a href={edge.source_url} target="_blank" rel="noreferrer"
                              className="flex items-center gap-1 text-cyan-500 hover:underline">
                              <ExternalLink size={10} /> View
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Combined risks */}
              {combinedWorkspace.risks.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-white">
                      Combined Risks ({combinedWorkspace.total_risks})
                    </h3>
                    <div className="flex items-center gap-2">
                      {["ALL", ...combinedWorkspace.repositories].map((r) => (
                        <button key={r} onClick={() => setCombinedRepoFilter(r)}
                          className={`text-[10px] px-2 py-0.5 rounded transition ${combinedRepoFilter === r ? "bg-white/15 text-white" : "text-zinc-500 hover:text-zinc-300"}`}>
                          {r === "ALL" ? "All" : r.split("/")[1]}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    {combinedWorkspace.risks
                      .filter((r) => combinedRepoFilter === "ALL" || r.repo === combinedRepoFilter)
                      .map((risk, i) => (
                        <div key={i} className="rounded-xl border border-white/10 bg-[#111113] p-4 space-y-2">
                          <div className="flex items-start justify-between gap-2">
                            <div className="text-xs font-semibold text-white">{risk.title}</div>
                            <span className={`shrink-0 rounded px-2 py-0.5 text-[9px] font-bold ${
                              risk.severity === "CRITICAL" ? "bg-red-500/15 text-red-400 border border-red-500/30"
                              : risk.severity === "HIGH" ? "bg-orange-500/15 text-orange-400 border border-orange-500/30"
                              : "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20"}`}>
                              {risk.severity}
                            </span>
                          </div>
                          <div className="text-[10px] text-zinc-400">{risk.impact}</div>
                          <div className="text-[10px] font-mono text-zinc-600">{risk.repo}</div>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {/* Navigate to combined graph */}
              <div className="flex items-center gap-3">
                <Link href="/graph"
                  className="flex items-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-xs font-medium text-cyan-300 hover:bg-cyan-400/20 transition">
                  <Network size={13} /> View Combined Graph
                </Link>
                <Link href="/what-if"
                  className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-zinc-300 hover:bg-white/10 transition">
                  <Play size={13} /> What-If on Combined
                </Link>
              </div>
            </div>
          )}
        </section>
      )}

      {/* ACTIVE REPO STATS (single repo mode) */}
      {!combinedWorkspace && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">
              Active Target: <span className="text-cyan-400">{activeRepo?.fullName || "None"}</span>
            </h2>
            <button onClick={loadActiveRepoData} disabled={loading}
              className="flex items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-zinc-300 transition hover:bg-white/10 disabled:opacity-50">
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-4">
            <StatCard title="Project Health" value={`${stats.health}%`} subtitle="Graph score" />
            <StatCard title="Critical Risks" value={stats.criticalRisks} subtitle="Direct blockers" />
            <StatCard title="Blocked Tasks" value={stats.blockedTasks} subtitle="Bottlenecks" />
            <StatCard title="Deadlines" value={stats.upcomingDeadlines} subtitle="Active milestones" />
          </div>
        </section>
      )}

      {/* QUICK ACTIONS */}
      <section className="rounded-xl border border-cyan-500/20 bg-gradient-to-r from-cyan-950/20 via-[#111113] to-purple-950/20 p-5">
        <div className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="text-xs font-semibold text-cyan-400">SIMULATE PROJECT CHAOS</div>
            <h3 className="mt-1 text-lg font-medium text-white">Hypothetical Failure &amp; Delay Reachability</h3>
            <p className="mt-1 text-xs text-zinc-400">
              {combinedWorkspace
                ? `Run What-If across all ${combinedWorkspace.repositories.length} combined repositories.`
                : `Run causal graph reachability for ${activeRepo?.fullName || "active repository"}.`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/what-if" className="flex items-center gap-2 rounded-lg border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-xs font-medium text-cyan-300 hover:bg-cyan-400/20">
              <Play size={13} /> Launch What-If
            </Link>
            <Link href="/graph" className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-zinc-300 hover:bg-white/10">
              Explore Graph <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      </section>

      {/* DETECTED FAILURE CHAINS (single repo) */}
      {!combinedWorkspace && (
        <section>
          <div className="mb-4 flex items-end justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">Detected Failure Chains ({risksList.length})</h2>
              <p className="mt-1 text-sm text-zinc-500">{activeRepo?.fullName || "active repository"}</p>
            </div>
            <Link href="/risks" className="flex items-center gap-1 text-sm text-zinc-400 hover:text-white">
              View all <ArrowRight size={14} />
            </Link>
          </div>
          {risksList.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-white/10 bg-[#111113] py-12 text-center">
              <ShieldCheck size={36} className="text-emerald-500 mb-2" />
              <h3 className="text-base font-semibold text-white">0 Critical Failure Chains</h3>
              <p className="mt-1 text-xs text-zinc-500 max-w-md">
                No blocking chains detected for {activeRepo?.fullName || "this repository"}.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {risksList.slice(0, 4).map((risk) => (<RiskCard key={risk.id} risk={risk} />))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
