import { ProjectStats, Risk } from "./types";

export const projectStats: ProjectStats = {
  health: 82,
  criticalRisks: 2,
  highRisks: 4,
  blockedTasks: 5,
  upcomingDeadlines: 3,
};

export const risks: Risk[] = [
  {
    id: "RISK-001",
    title: "Deployment failure predicted",
    severity: "CRITICAL",
    probability: 87,
    impact: "HIGH",
    rootCause: "PR #47",
    description:
      "An unresolved authentication pull request is blocking integration testing, which is directly connected to the Friday deployment.",
    affected: [
      "Authentication",
      "Integration Testing",
      "Deployment",
      "Client Demo",
    ],
    recommendation:
      "Resolve PR #47 immediately or reassign the authentication task to another developer.",
    evidence: [
      {
        source: "PR #47",
        detail: "Authentication module implementation remains open.",
        status: "OPEN",
      },
      {
        source: "Integration Testing",
        detail: "Testing depends on authentication integration.",
      },
      {
        source: "Friday Deployment",
        detail: "Deployment depends on successful integration testing.",
      },
    ],
  },
  {
    id: "RISK-002",
    title: "Payment service bottleneck",
    severity: "HIGH",
    probability: 74,
    impact: "MEDIUM",
    rootCause: "Issue #31",
    description:
      "Multiple downstream tasks depend on an unresolved payment service issue.",
    affected: ["Payment API", "Checkout", "Order Service"],
    recommendation:
      "Prioritize Issue #31 before starting additional checkout work.",
    evidence: [
      {
        source: "Issue #31",
        detail: "Payment API timeout issue remains unresolved.",
        status: "OPEN",
      },
    ],
  },
];