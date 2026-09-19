"use client";

import React, { createContext, useContext, useEffect, useState, useMemo, useCallback } from "react";
import { WorkspaceRepo, WorkspaceStats, RepoStatus } from "./types";
import {
  fetchWorkspaceProjects,
  syncGitHubRepo,
  fetchProjectRisks,
  fetchGraphData,
  parseGitHubUrl,
  removeProjectFromBackend,
  fetchCombinedWorkspace,
  type CombinedWorkspace,
} from "./api";

interface WorkspaceContextType {
  repositories: WorkspaceRepo[];
  activeRepo: WorkspaceRepo | null;
  activeRepoId: string | null;
  setActiveRepoId: (id: string | null) => void;
  addRepository: (url: string) => Promise<{ success: boolean; error?: string; repo?: WorkspaceRepo }>;
  syncRepository: (repoId: string) => Promise<void>;
  loadDemoProject: () => void;
  removeRepository: (repoId: string) => Promise<void>;
  refreshWorkspace: () => Promise<void>;
  aggregatedStats: WorkspaceStats;
  isInitialLoading: boolean;
  // Combined workspace
  selectedRepoIds: Set<string>;
  toggleRepoSelection: (id: string) => void;
  selectAllRepos: () => void;
  clearSelection: () => void;
  combinedWorkspace: CombinedWorkspace | null;
  combinedLoading: boolean;
  combinedError: string | null;
  analyzeCombined: () => Promise<void>;
  clearCombined: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextType | null>(null);

const STORAGE_KEY_METRICS = "deadlock_repo_metrics_v4";  // bumped: clears stale v3 zero-risk cache
const STORAGE_KEY_ACTIVE  = "deadlock_active_repo_id_v3";

type RepoMetricsCache = Record<string, {
  nodeCount?: number; edgeCount?: number; riskCount?: number;
  criticalRiskCount?: number; healthScore?: number; lastSynced?: string;
}>;

function loadMetricsCache(): RepoMetricsCache {
  try { const r = localStorage.getItem(STORAGE_KEY_METRICS); return r ? JSON.parse(r) : {}; }
  catch { return {}; }
}
function saveMetricsCache(c: RepoMetricsCache) {
  try { localStorage.setItem(STORAGE_KEY_METRICS, JSON.stringify(c)); } catch { /**/ }
}

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [repositories, setRepositories]       = useState<WorkspaceRepo[]>([]);
  const [activeRepoId, setActiveRepoIdState]  = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  // Combined workspace state
  const [selectedRepoIds, setSelectedRepoIds]   = useState<Set<string>>(new Set());
  const [combinedWorkspace, setCombinedWorkspace] = useState<CombinedWorkspace | null>(null);
  const [combinedLoading, setCombinedLoading]   = useState(false);
  const [combinedError, setCombinedError]       = useState<string | null>(null);

  const setActiveRepoId = useCallback((id: string | null) => {
    setActiveRepoIdState(id);
    try { if (id) localStorage.setItem(STORAGE_KEY_ACTIVE, id); else localStorage.removeItem(STORAGE_KEY_ACTIVE); }
    catch { /**/ }
  }, []);

  const enrichRepoMetrics = useCallback(async (repo: WorkspaceRepo): Promise<WorkspaceRepo> => {
    try {
      const owner    = repo.source === "seeded" ? undefined : repo.owner;
      const repoName = repo.source === "seeded" ? undefined : repo.repo;
      const [risksData, graphData] = await Promise.all([
        fetchProjectRisks(owner, repoName),
        fetchGraphData(owner, repoName),
      ]);
      const enriched: WorkspaceRepo = {
        ...repo, status: "READY",
        riskCount: risksData.risks.length,
        criticalRiskCount: risksData.projectStats.criticalRisks,
        healthScore: risksData.projectStats.health,
        nodeCount: graphData.nodes.length,
        edgeCount: graphData.edges.length,
        lastSynced: new Date().toISOString(),
      };
      const cache = loadMetricsCache();
      cache[repo.id] = { nodeCount: enriched.nodeCount, edgeCount: enriched.edgeCount,
        riskCount: enriched.riskCount, criticalRiskCount: enriched.criticalRiskCount,
        healthScore: enriched.healthScore, lastSynced: enriched.lastSynced };
      saveMetricsCache(cache);
      return enriched;
    } catch { return repo; }
  }, []);

  const refreshWorkspace = useCallback(async () => {
    try {
      const backendProjects = await fetchWorkspaceProjects();
      const metricsCache = loadMetricsCache();
      const repos: WorkspaceRepo[] = backendProjects.map((bp) => {
        const owner = String(bp.owner || ""); const repo = String(bp.repo || "");
        const id = `${owner}/${repo}`; const cached = metricsCache[id] || {};
        return { id, owner, repo, fullName: String(bp.full_name || id),
          source: bp.source === "seeded" ? "seeded" : "github",
          status: "READY" as RepoStatus,
          lastSynced: cached.lastSynced || (bp.last_synced_at ? String(bp.last_synced_at) : undefined),
          nodeCount: cached.nodeCount, edgeCount: cached.edgeCount,
          riskCount: cached.riskCount, criticalRiskCount: cached.criticalRiskCount,
          healthScore: cached.healthScore };
      });
      setRepositories(repos);
      const savedActive = (() => { try { return localStorage.getItem(STORAGE_KEY_ACTIVE); } catch { return null; } })();
      if (savedActive && repos.some((r) => r.id === savedActive)) setActiveRepoIdState(savedActive);
      else if (repos.length > 0) setActiveRepoIdState(repos[0].id);
      else setActiveRepoIdState(null);
      // Always re-fetch risk/graph counts for every READY live repo on load
      // so repository cards show current backend data, not stale cache.
      repos.forEach(async (repo) => {
        if (repo.status === "READY" && repo.source !== "seeded") {
          const enriched = await enrichRepoMetrics(repo);
          setRepositories((prev) => prev.map((r) => (r.id === repo.id ? enriched : r)));
        }
      });
    } finally { setIsInitialLoading(false); }
  }, [enrichRepoMetrics]);

  useEffect(() => { refreshWorkspace(); }, [refreshWorkspace]);

  const addRepository = async (url: string): Promise<{ success: boolean; error?: string; repo?: WorkspaceRepo }> => {
    let owner: string; let repo: string;
    try { const p = parseGitHubUrl(url); owner = p.owner; repo = p.repo; }
    catch (err: unknown) { return { success: false, error: err instanceof Error ? err.message : "Invalid URL." }; }
    const repoId = `${owner}/${repo}`;
    const analyzingRepo: WorkspaceRepo = { id: repoId, owner, repo, fullName: repoId, source: "github", status: "ANALYZING" };
    setRepositories((prev) => [analyzingRepo, ...prev.filter((r) => r.id !== repoId)]);
    setActiveRepoId(repoId);
    try {
      await syncGitHubRepo(owner, repo);
      const enriched = await enrichRepoMetrics({ ...analyzingRepo, status: "READY", lastSynced: new Date().toISOString() });
      setRepositories((prev) => prev.map((r) => (r.id === repoId ? enriched : r)));
      return { success: true, repo: enriched };
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed.";
      const errorRepo: WorkspaceRepo = { ...analyzingRepo, status: "ERROR", error: errorMsg };
      setRepositories((prev) => prev.map((r) => (r.id === repoId ? errorRepo : r)));
      return { success: false, error: errorMsg, repo: errorRepo };
    }
  };

  const syncRepository = async (repoId: string) => {
    const target = repositories.find((r) => r.id === repoId); if (!target) return;
    setRepositories((prev) => prev.map((r) => (r.id === repoId ? { ...r, status: "SYNCING" as RepoStatus } : r)));
    try {
      if (target.source !== "seeded") await syncGitHubRepo(target.owner, target.repo);
      const enriched = await enrichRepoMetrics({ ...target, status: "READY", lastSynced: new Date().toISOString(), error: undefined });
      setRepositories((prev) => prev.map((r) => (r.id === repoId ? enriched : r)));
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Sync failed.";
      setRepositories((prev) => prev.map((r) => r.id === repoId ? { ...r, status: "ERROR" as RepoStatus, error: errorMsg } : r));
    }
  };

  const loadDemoProject = () => {
    const id = "demo/campusconnect";
    const demo: WorkspaceRepo = { id, owner: "CampusConnect", repo: "Demo", fullName: "CampusConnect (Demo)",
      source: "seeded", status: "READY", lastSynced: new Date().toISOString(),
      healthScore: 82, criticalRiskCount: 2, riskCount: 3, nodeCount: 12, edgeCount: 14 };
    setRepositories((prev) => [demo, ...prev.filter((r) => r.id !== id)]);
    setActiveRepoId(id);
  };

  const removeRepository = async (repoId: string) => {
    setRepositories((prev) => {
      const updated = prev.filter((r) => r.id !== repoId);
      if (activeRepoId === repoId) setActiveRepoIdState(updated.length > 0 ? updated[0].id : null);
      return updated;
    });
    setSelectedRepoIds((prev) => { const next = new Set(prev); next.delete(repoId); return next; });
    const cache = loadMetricsCache(); delete cache[repoId]; saveMetricsCache(cache);
    const parts = repoId.split("/");
    if (parts.length === 2 && !repoId.startsWith("demo/")) await removeProjectFromBackend(parts[0], parts[1]);
  };

  // ---- Combined workspace actions ----
  const toggleRepoSelection = useCallback((id: string) => {
    setSelectedRepoIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const selectAllRepos = useCallback(() => {
    setSelectedRepoIds(new Set(repositories.filter((r) => r.status === "READY" && r.source !== "seeded").map((r) => r.id)));
  }, [repositories]);

  const clearSelection = useCallback(() => setSelectedRepoIds(new Set()), []);

  const analyzeCombined = useCallback(async () => {
    const repoList = Array.from(selectedRepoIds);
    if (repoList.length === 0) return;
    setCombinedLoading(true);
    setCombinedError(null);
    try {
      const result = await fetchCombinedWorkspace(repoList);
      if (!result) throw new Error("Backend returned no data.");
      setCombinedWorkspace(result);
    } catch (err: unknown) {
      setCombinedError(err instanceof Error ? err.message : "Combined analysis failed.");
      setCombinedWorkspace(null);
    } finally {
      setCombinedLoading(false);
    }
  }, [selectedRepoIds]);

  const clearCombined = useCallback(() => {
    setCombinedWorkspace(null);
    setCombinedError(null);
  }, []);

  const activeRepo = useMemo(() => {
    if (!activeRepoId) return repositories[0] || null;
    return repositories.find((r) => r.id === activeRepoId) || repositories[0] || null;
  }, [repositories, activeRepoId]);

  const aggregatedStats = useMemo<WorkspaceStats>(() => ({
    totalRepos: repositories.length,
    readyRepos: repositories.filter((r) => r.status === "READY").length,
    errorRepos: repositories.filter((r) => r.status === "ERROR").length,
    totalRisks: repositories.reduce((sum, r) => sum + (r.riskCount || 0), 0),
    criticalRisks: repositories.reduce((sum, r) => sum + (r.criticalRiskCount || 0), 0),
  }), [repositories]);

  return (
    <WorkspaceContext.Provider value={{
      repositories, activeRepo, activeRepoId, setActiveRepoId,
      addRepository, syncRepository, loadDemoProject, removeRepository,
      refreshWorkspace, aggregatedStats, isInitialLoading,
      selectedRepoIds, toggleRepoSelection, selectAllRepos, clearSelection,
      combinedWorkspace, combinedLoading, combinedError, analyzeCombined, clearCombined,
    }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within a WorkspaceProvider");
  return ctx;
}
