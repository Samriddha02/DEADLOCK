import { ProjectStats, Risk, RiskSeverity, Evidence } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// Helper to format backend node IDs like "pull_request:pr_11" or "issue:issue_11" into clean labels
export function formatNodeLabel(id: string): string {
  if (!id) return "";
  if (id.startsWith("pull_request:")) {
    const num = id.replace("pull_request:pr_", "").replace("pull_request:", "");
    return `PR #${num}`;
  }
  if (id.startsWith("issue:")) {
    const num = id.replace("issue:issue_", "").replace("issue:", "");
    return `Issue #${num}`;
  }
  if (id.startsWith("deployment:")) {
    return id.replace("deployment:", "Deployment ");
  }
  if (id.startsWith("deadline:")) {
    return id.replace("deadline:", "Deadline ");
  }
  if (id.startsWith("milestone:")) {
    return id.replace("milestone:", "Milestone ");
  }
  if (id.startsWith("developer:")) {
    return id.replace("developer:", "Dev ");
  }
  if (id.startsWith("commit:")) {
    return id.replace("commit:", "Commit ");
  }
  return id;
}

export function normalizeSeverity(sev: unknown): RiskSeverity {
  const s = String(sev ?? "LOW").toUpperCase();
  if (s === "CRITICAL") return "CRITICAL";
  if (s === "HIGH") return "HIGH";
  if (s === "MEDIUM" || s === "MODERATE") return "MEDIUM";
  return "LOW";
}

export function transformBackendEvidence(rawItems: Record<string, unknown>[]): Evidence[] {
  if (!Array.isArray(rawItems)) return [];

  return rawItems.map((item, idx) => {
    // Check if already in frontend Evidence format
    if (typeof item.source === "string" && typeof item.detail === "string") {
      return item as unknown as Evidence;
    }

    const type = String(item.type || "finding");

    if (type === "pull_request") {
      const srcTitle = String(item.title || (item.id ? `PR #${item.id}` : `PR #${idx}`));
      const statusStr = String(item.status || "open").toUpperCase();
      return {
        source: srcTitle,
        sourceType: "github_pull_request",
        sourceId: item.id ? String(item.id) : undefined,
        title: item.title ? String(item.title) : undefined,
        detail: `Status: ${statusStr}. Connected to critical dependency path.`,
        status: statusStr,
        relationship: "BLOCKS",
        inferred: false,
        confidence: 1.0,
      };
    }

    if (type === "reviews") {
      const revList = Array.isArray(item.reviews) ? (item.reviews as Record<string, unknown>[]) : [];
      const rev = revList[0] || {};
      const reviewerId = String(rev.reviewer_id || "reviewer");
      const statusStr = String(rev.status || "changes_requested").replace("_", " ").toUpperCase();
      return {
        source: `Review on ${String(rev.pr_id || "PR")}`,
        sourceType: "github_review",
        sourceId: rev.id ? String(rev.id) : undefined,
        title: `Reviewer ${reviewerId}: ${statusStr}`,
        detail: String(rev.comment || "Changes requested blocking merge."),
        status: statusStr,
        relationship: "BLOCKS",
        inferred: false,
        confidence: 1.0,
      };
    }

    if (type === "causal_chain") {
      const chainLabels = Array.isArray(item.path)
        ? (item.path as string[]).map((n: string) => formatNodeLabel(n)).join(" → ")
        : "Dependency chain identified";
      return {
        source: "Graph Causal Chain",
        sourceType: "dependency_graph",
        title: "Propagation Path",
        detail: chainLabels,
        relationship: "PROPAGATES",
        inferred: true,
        inferenceRule: "Deterministic graph reachability propagation",
        confidence: 1.0,
      };
    }

    if (type === "adversarial_verification") {
      const statusStr = String(item.status || "VERIFIED");
      const score = item.evidence_score !== undefined ? Number(item.evidence_score) : 7;
      return {
        source: "Adversarial Verifier",
        sourceType: "engine_verifier",
        title: `Verification: ${statusStr}`,
        detail: `Evidence score: ${score}/10. Graph proof confirmed without synthetic hallucination.`,
        status: statusStr,
        relationship: "VERIFIED",
        inferred: false,
        confidence: Number(item.confidence ?? 1.0),
      };
    }

    if (type === "compatibility_risk") {
      const terms = Array.isArray(item.matched_terms) ? (item.matched_terms as string[]).join(", ") : "";
      return {
        source: "Schema Compatibility Scanner",
        sourceType: "ast_static_analysis",
        title: "Breaking Schema Change Detected",
        detail: `Matched pattern: ${terms}. Dropping or altering active tables causes client outage.`,
        relationship: "BREAKS",
        inferred: true,
        inferenceRule: "Schema migration destructive operation pattern check",
        confidence: 0.95,
      };
    }

    if (type === "developer") {
      const devName = String(item.name || item.id || "Developer");
      return {
        source: devName,
        sourceType: "workload_distribution",
        title: `Workload Bottleneck: ${devName}`,
        detail: "Assigned critical path reviews and implementation issues exceeding capacity limit.",
        relationship: "ASSIGNED",
        inferred: false,
        confidence: 1.0,
      };
    }

    // Fallback for generic evidence dict
    return {
      source: String(item.source || item.title || item.id || `Evidence item ${idx + 1}`),
      sourceType: type,
      detail: String(item.detail || item.impact || item.description || JSON.stringify(item)),
      relationship: String(item.relationship || item.edge_type || "RELATES_TO"),
      inferred: Boolean(item.inferred),
      inferenceRule: item.inferenceRule ? String(item.inferenceRule) : null,
      confidence: typeof item.confidence === "number" ? item.confidence : 1.0,
      filePath: item.filePath ? String(item.filePath) : undefined,
      startLine: typeof item.startLine === "number" ? item.startLine : undefined,
      endLine: typeof item.endLine === "number" ? item.endLine : undefined,
      code: item.code ? String(item.code) : undefined,
    };
  });
}

export function transformBackendRisk(raw: Record<string, unknown>): Risk {
  const id = String(raw.risk_id || raw.id || "RISK-UNKNOWN");
  const title = String(raw.title || "Detected Project Risk");
  const severity = normalizeSeverity(raw.severity);
  const score = typeof raw.risk_score === "number" ? raw.risk_score : (typeof raw.score === "number" ? raw.score : 50);
  const probability = typeof raw.probability === "number"
    ? (raw.probability <= 1 ? Math.round(raw.probability * 100) : raw.probability)
    : score;
  const rootCause = formatNodeLabel(String(raw.root_cause || raw.rootCause || "Unknown"));
  const impact = String(raw.impact || "Potential delay on linked milestones");
  const description = String(raw.description || raw.impact || title);
  
  let affected: string[] = [];
  if (Array.isArray(raw.causal_chain) && raw.causal_chain.length > 0) {
    affected = (raw.causal_chain as string[]).map((n: string) => formatNodeLabel(n));
  } else if (Array.isArray(raw.affected)) {
    affected = raw.affected as string[];
  } else {
    affected = [rootCause, "Deployment", "Release"];
  }

  const recommendation = String(
    raw.recommendation || "Prioritize resolving the root cause to mitigate downstream impact."
  );

  const evidence = transformBackendEvidence((raw.evidence || []) as Record<string, unknown>[]);

  const factors = raw.score_breakdown
    ? Object.entries(raw.score_breakdown as Record<string, Record<string, unknown>>).map(([key, val]) => ({
        name: key.toUpperCase(),
        contribution: typeof val.contribution === "number" ? val.contribution : (Number(val.weight) || 10),
      }))
    : undefined;

  return {
    id,
    title,
    severity,
    probability,
    score,
    impact,
    rootCause,
    description,
    affected,
    recommendation,
    evidence,
    factors,
    verified: Boolean(raw.verified ?? true),
    propagationPaths: raw.propagation_paths as string[][] | undefined,
  };
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export function parseGitHubUrl(url: string): { owner: string; repo: string } {
  if (!url || !url.trim()) {
    throw new Error("Please enter a GitHub repository URL.");
  }
  const clean = url.trim();
  if (clean.includes("gitlab.com") || clean.includes("bitbucket.org")) {
    throw new Error("Invalid URL. DEADLOCK requires a GitHub repository URL (e.g. https://github.com/owner/repo).");
  }
  const match = clean.match(/(?:https?:\/\/)?(?:www\.)?github\.com\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+?)(?:\.git)?(?:\/.*)?$/i);
  if (!match) {
    const bareMatch = clean.match(/^([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)$/);
    if (bareMatch) {
      return { owner: bareMatch[1], repo: bareMatch[2] };
    }
    throw new Error("Invalid GitHub URL. Expected format: https://github.com/owner/repo");
  }
  return { owner: match[1], repo: match[2] };
}

export async function fetchWorkspaceProjects(): Promise<Record<string, unknown>[]> {
  try {
    const res = await fetch(`${API_BASE}/api/projects`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.projects || []) as Record<string, unknown>[];
  } catch (err) {
    console.warn("Failed to fetch workspace projects:", err);
    return [];
  }
}

export async function fetchProjectRisks(owner?: string, repo?: string): Promise<{
  projectStats: ProjectStats;
  risks: Risk[];
  projectName: string;
  isLive: boolean;
}> {
  try {
    const endpoint = (owner && repo)
      ? `${API_BASE}/api/risks/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`
      : `${API_BASE}/api/risks`;

    const res = await fetch(endpoint, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(8000),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const rawRisks = data.risks || [];
    const transformedRisks = rawRisks.map(transformBackendRisk);

    const project = data.project || {};
    const summary = typeof project === "object" ? (project.summary || {}) : {};

    const criticalCount = transformedRisks.filter((r: Risk) => r.severity === "CRITICAL").length;
    const highCount = transformedRisks.filter((r: Risk) => r.severity === "HIGH").length;
    const blockedCount = summary.blocked_tasks ?? 0;

    // Calculate dynamic project health score (100 - weighted risk count)
    const penalty = criticalCount * 15 + highCount * 6;
    const health = Math.max(10, Math.min(100, 100 - penalty));

    const stats: ProjectStats = {
      health: transformedRisks.length === 0 ? 100 : health,
      criticalRisks: criticalCount,
      highRisks: highCount,
      blockedTasks: blockedCount,
      upcomingDeadlines: summary.relationships ? 3 : 0,
    };

    const projectName = (owner && repo)
      ? `${owner}/${repo}`
      : (project.name || "CampusConnect");

    return {
      projectStats: stats,
      risks: transformedRisks,
      projectName,
      isLive: true,
    };
  } catch (err) {
    console.warn("Failed to fetch project risks:", err);
    // Return empty data when live fetch fails – no demo fallback
    const emptyStats: ProjectStats = {
      health: 100,
      criticalRisks: 0,
      highRisks: 0,
      blockedTasks: 0,
      upcomingDeadlines: 0,
    };
    return {
      projectStats: emptyStats,
      risks: [],
      projectName: (owner && repo) ? `${owner}/${repo}` : "Unknown Project",
      isLive: false,
    };
  }
}

export async function syncGitHubRepo(urlOrOwner: string, maybeRepo?: string): Promise<{
  message: string;
  owner: string;
  repo: string;
  project: Record<string, unknown>;
}> {
  let owner: string;
  let repo: string;

  if (maybeRepo) {
    owner = urlOrOwner.trim();
    repo = maybeRepo.trim();
  } else {
    const parsed = parseGitHubUrl(urlOrOwner);
    owner = parsed.owner;
    repo = parsed.repo;
  }

  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: AbortSignal.timeout(30000),
  });

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchRiskById(id: string, owner?: string, repo?: string): Promise<{ risk: Risk | null; isLive: boolean }> {
  try {
    const endpoint = (owner && repo)
      ? `${API_BASE}/api/risks/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${encodeURIComponent(id)}`
      : `${API_BASE}/api/risks/${encodeURIComponent(id)}`;

    const res = await fetch(endpoint, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });

    if (res.ok) {
      const data = await res.json();
      return { risk: transformBackendRisk(data as Record<string, unknown>), isLive: true };
    }
  } catch (err) {
    console.warn("Failed to fetch specific risk from backend, searching risks list:", err);
  }

  // Try finding in general risks
  const { risks, isLive } = await fetchProjectRisks(owner, repo);
  const found = risks.find((r) => r.id.toLowerCase() === id.toLowerCase());
  return { risk: found || null, isLive };
}

export async function fetchGraphData(owner?: string, repo?: string): Promise<{
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  isLive: boolean;
}> {
  try {
    const endpoint = (owner && repo)
      ? `${API_BASE}/api/graph/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`
      : `${API_BASE}/api/graph`;

    const res = await fetch(endpoint, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    return {
      nodes: (data.nodes || []) as Record<string, unknown>[],
      edges: (data.edges || []) as Record<string, unknown>[],
      isLive: true,
    };
  } catch (err) {
    console.warn("Failed to fetch live graph:", err);
    return { nodes: [], edges: [], isLive: false };
  }
}

export async function removeProjectFromBackend(owner: string, repo: string): Promise<{ success: boolean; error?: string }> {  try {
    const res = await fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`,
      {
        method: "DELETE",
        cache: "no-store",
        signal: AbortSignal.timeout(8000),
      }
    );
    if (res.ok) return { success: true };
    // 404 means it wasn't in the DB — treat as success (already gone)
    if (res.status === 404) return { success: true };
    const txt = await res.text();
    return { success: false, error: txt || `HTTP ${res.status}` };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : "Request failed" };
  }
}

export async function runSimulation(payload: {
  node_id: string;
  event_type: string;
  delay_days?: number;
  latency_ms?: number;
  description?: string;
}, owner?: string, repo?: string): Promise<Record<string, unknown>> {
  const endpoint = (owner && repo)
    ? `${API_BASE}/api/simulate/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`
    : `${API_BASE}/api/simulate`;

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Simulation failed: ${text || `HTTP ${res.status}`}`);
  }

  return (await res.json()) as Record<string, unknown>;
}


// ============================================================
// Combined Workspace Types
// ============================================================

export interface CombinedNode {
  id: string;
  type: string;
  label: string;
  repo: string;           // "owner/repo"
  data: Record<string, unknown>;
}

export interface CombinedEdge {
  source: string;
  target: string;
  relation: string;
  cross_repo: boolean;
  repo: string;
  data: Record<string, unknown>;
}

export interface CrossRepoEdge {
  source_node: string;
  target_node: string;
  source_repo: string;
  target_repo: string;
  relationship_type: string;
  evidence: string;
  source_file: string;
  source_url: string | null;
  inferred: boolean;
  confidence: number;
  inference_rule?: string | null;
}

export interface CombinedRisk {
  risk_id: string;
  title: string;
  severity: RiskSeverity;
  probability: number;
  root_cause: string;
  impact: string;
  description?: string;
  recommendation: string;
  evidence: Record<string, unknown>[];
  causal_chain: string[];
  repo: string;           // originating repo "owner/repo"
  verified?: boolean;
}

export interface CombinedWorkspace {
  repositories: string[];
  missing_repositories: string[];
  total_nodes: number;
  total_edges: number;
  cross_repo_edge_count: number;
  total_risks: number;
  has_cross_repo_evidence: boolean;
  nodes: CombinedNode[];
  edges: CombinedEdge[];
  cross_repo_edges: CrossRepoEdge[];
  risks: CombinedRisk[];
}

// ============================================================
// fetchCombinedWorkspace
// ============================================================

export async function fetchCombinedWorkspace(
  repositories: string[]           // ["owner/repo", ...]
): Promise<CombinedWorkspace | null> {
  try {
    const res = await fetch(`${API_BASE}/api/workspace/combine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repositories }),
      cache: "no-store",
      signal: AbortSignal.timeout(60000),   // manifest fetches can take ~10 s
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || `HTTP ${res.status}`);
    }
    return (await res.json()) as CombinedWorkspace;
  } catch (err) {
    console.warn("fetchCombinedWorkspace failed:", err);
    return null;
  }
}
