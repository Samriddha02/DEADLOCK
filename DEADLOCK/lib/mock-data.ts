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
    sourceType: "github_pull_request",
    sourceId: "47",
    title: "Authentication implementation",
    detail:
      "PR #47 modifies the authentication module and remains open.",
    status: "OPEN",
    relationship: "IMPLEMENTS",
    inferred: false,
    inferenceRule: null,
    confidence: 1,
    filePath: "backend/auth.py",
    startLine: 18,
    endLine: 27,
    code: `@router.post("/api/login")
def login(credentials: LoginRequest):
    user = authenticate_user(credentials)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    token = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer"
    }`,
  },

  {
    source: "Integration Testing",
    sourceType: "repository_test",
    sourceId: "test_auth.py",
    title: "Authentication integration test",
    detail:
      "The integration test calls the authentication endpoint and therefore requires the authentication service.",
    relationship: "REQUIRED_FOR",
    inferred: true,
    inferenceRule:
      "Integration test workflow requires authentication service",
    confidence: 0.92,
    filePath: "tests/test_auth.py",
    startLine: 12,
    endLine: 22,
    code: `def test_login():
    response = client.post(
        "/api/login",
        json={
            "username": "demo",
            "password": "demo"
        }
    )

    assert response.status_code == 200`,
  },

  {
    source: "Deployment Pipeline",
    sourceType: "github_workflow",
    sourceId: "deploy.yml",
    title: "Deployment requires successful tests",
    detail:
      "The deployment workflow depends on the test stage completing successfully.",
    relationship: "BLOCKS",
    inferred: false,
    inferenceRule: null,
    confidence: 1,
    filePath: ".github/workflows/deploy.yml",
    startLine: 18,
    endLine: 28,
    code: `jobs:
  deploy:
    needs: test

    steps:
      - uses: actions/checkout@v4

      - name: Deploy
        run: ./scripts/deploy.sh`,
  },
],
  },
];