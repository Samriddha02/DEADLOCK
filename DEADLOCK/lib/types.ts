export type RiskSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface Evidence {
  source: string;
  detail: string;
  status?: string;

  // New evidence fields
  sourceType?: string;
  sourceId?: string;
  sourceUrl?: string;
  title?: string;
  relationship?: string;
  inferred?: boolean;
  inferenceRule?: string | null;
  confidence?: number;

  // Relevant code information
  filePath?: string;
  startLine?: number;
  endLine?: number;
  code?: string;
}

export interface Risk {
  id: string;
  title: string;
  severity: RiskSeverity;

  // Kept for backward compatibility with existing mock data.
  // Backend integration can later use score instead.
  probability: number;

  score?: number;

  impact: string;
  rootCause: string;
  description: string;
  affected: string[];
  recommendation: string;
  evidence: Evidence[];

  // Backend-ready optional fields
  propagationPaths?: string[][];
  factors?: {
    name: string;
    contribution: number;
  }[];

  verified?: boolean;
}

export interface ProjectStats {
  health: number;
  criticalRisks: number;
  highRisks: number;
  blockedTasks: number;
  upcomingDeadlines: number;
}

export type RepoStatus = "NOT_ANALYZED" | "ANALYZING" | "READY" | "SYNCING" | "ERROR";

export interface WorkspaceRepo {
  id: string; // "owner/repo" or "demo"
  owner: string;
  repo: string;
  fullName: string;
  source: "github" | "seeded";
  status: RepoStatus;
  lastSynced?: string;
  error?: string;
  nodeCount?: number;
  edgeCount?: number;
  riskCount?: number;
  criticalRiskCount?: number;
  healthScore?: number;
}

export interface WorkspaceStats {
  totalRepos: number;
  readyRepos: number;
  errorRepos: number;
  totalRisks: number;
  criticalRisks: number;
}