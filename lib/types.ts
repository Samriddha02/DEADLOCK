export type RiskSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface Evidence {
  source: string;
  detail: string;
  status?: string;
}

export interface Risk {
  id: string;
  title: string;
  severity: RiskSeverity;
  probability: number;
  impact: string;
  rootCause: string;
  description: string;
  affected: string[];
  recommendation: string;
  evidence: Evidence[];
}

export interface ProjectStats {
  health: number;
  criticalRisks: number;
  highRisks: number;
  blockedTasks: number;
  upcomingDeadlines: number;
}