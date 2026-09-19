from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.models.project_models import (
    ProjectData,
    ProjectInfo,
    Developer,
    Milestone,
    Deadline,
    Issue,
    PullRequest,
    Commit,
    Review,
    Dependency,
    Deployment,
)
from app.ingestion.dataset_loader import load_canonical_project, load_seeded_project
from app.ingestion.normalizer import normalize_project
from app.graph.graph_builder import build_graph
from app.risk_engine.detector import detect_risks
from app.agents.verifier_agent import VerifierAgent
from app.simulation.what_if import simulate
from app.models.risk_models import SimulationRequest
from app.database.repositories import store_project, load_project


@pytest.fixture
def seeded_raw() -> dict:
    return load_seeded_project()


@pytest.fixture
def canonical_project() -> ProjectData:
    return load_canonical_project()


# ============================================================
# 1. Seeded JSON -> Canonical ProjectData
# ============================================================

def test_seeded_json_to_canonical(seeded_raw):
    project = ProjectData(**seeded_raw)
    assert project.project is not None
    assert project.project.name == "NEXUS Core Platform"
    assert len(project.developers) == 6
    assert len(project.milestones) == 3
    assert len(project.deadlines) == 4
    assert len(project.issues) == 20
    assert len(project.pull_requests) == 15
    assert len(project.commits) == 40
    assert len(project.reviews) == 18
    assert len(project.dependencies) == 22
    assert len(project.deployments) == 4


# ============================================================
# 2. Canonical ProjectData -> Serialization
# ============================================================

def test_canonical_serialization(canonical_project):
    dumped = canonical_project.model_dump()
    assert isinstance(dumped, dict)
    assert dumped["project"]["name"] == "NEXUS Core Platform"
    assert len(dumped["issues"]) == 20

    # Ensure JSON serializable
    json_str = json.dumps(dumped)
    assert isinstance(json_str, str)
    assert "NEXUS Core Platform" in json_str

    # Roundtrip back to ProjectData
    restored = ProjectData(**json.loads(json_str))
    assert restored.project.name == "NEXUS Core Platform"
    assert len(restored.pull_requests) == 15


# ============================================================
# 3. Missing optional collections
# ============================================================

def test_missing_optional_collections():
    minimal = {
        "project": {
            "name": "Minimal Project",
        },
        "issues": [
            {"id": "issue_1", "title": "First Issue"}
        ],
    }
    project = ProjectData(**minimal)
    assert project.project.name == "Minimal Project"
    assert len(project.issues) == 1
    assert project.developers == []
    assert project.milestones == []
    assert project.deadlines == []
    assert project.pull_requests == []
    assert project.commits == []
    assert project.reviews == []
    assert project.dependencies == []
    assert project.deployments == []


# ============================================================
# 4. Null optional values
# ============================================================

def test_null_optional_values():
    issue = Issue(
        id="iss_1",
        title="Issue with nulls",
        description=None,
        assignee=None,
        milestone=None,
        estimated_hours=None,
        closed_at=None,
    )
    assert issue.id == "iss_1"
    assert issue.description is None
    assert issue.labels == []


# ============================================================
# 5. Malformed optional entity handling
# ============================================================

def test_extra_fields_preserved():
    extra_data = {
        "id": "dev_99",
        "name": "Custom Dev",
        "custom_metric": 42,
        "tags": ["core", "infra"],
    }
    developer = Developer(**extra_data)
    assert developer.id == "dev_99"
    assert developer.custom_metric == 42
    assert developer.tags == ["core", "infra"]


# ============================================================
# 6. Unknown relationship reference
# ============================================================

def test_unknown_relationship_reference():
    project = ProjectData(
        project=ProjectInfo(name="Test"),
        issues=[Issue(id="issue_1", title="Issue 1", milestone_id="nonexistent_ms")],
    )
    graph = build_graph(project)
    assert "issue:issue_1" in graph.nodes
    # Unknown milestone is not in graph and does not crash builder
    assert "milestone:nonexistent_ms" not in graph.nodes


# ============================================================
# 7. GitHub normalized sample -> canonical ProjectData
# ============================================================

def test_github_normalized_to_canonical():
    issues = [
        {
            "id": 100,
            "number": 1,
            "title": "Fix bug",
            "state": "open",
            "assignee": {"login": "octocat"},
            "labels": [{"name": "bug"}],
            "milestone": {"title": "v1.0"},
            "created_at": "2026-08-01T00:00:00Z",
        }
    ]
    pulls = [
        {
            "id": 200,
            "number": 10,
            "title": "Fix #1",
            "state": "open",
            "user": {"login": "developer"},
            "assignee": {"login": "octocat"},
            "draft": False,
            "labels": [],
            "created_at": "2026-08-02T00:00:00Z",
        }
    ]
    commits = [
        {
            "sha": "abc1234",
            "commit": {"message": "commit msg", "author": {"date": "2026-08-02T01:00:00Z"}},
            "author": {"login": "developer"},
        }
    ]
    milestones = [
        {
            "id": 300,
            "number": 1,
            "title": "v1.0",
            "state": "open",
            "due_on": "2026-09-01T00:00:00Z",
            "open_issues": 1,
            "closed_issues": 0,
        }
    ]

    canonical = normalize_project(
        owner="test-org",
        repo="test-repo",
        issues=issues,
        pull_requests=pulls,
        commits=commits,
        milestones=milestones,
    )

    assert isinstance(canonical, ProjectData)
    assert canonical.owner == "test-org"
    assert canonical.repo == "test-repo"
    assert len(canonical.developers) == 2  # octocat, developer
    assert len(canonical.issues) == 1
    assert len(canonical.pull_requests) == 1
    assert len(canonical.commits) == 1
    assert len(canonical.milestones) == 1


# ============================================================
# 8. Canonical ProjectData -> Graph
# ============================================================

def test_canonical_to_graph(canonical_project):
    graph = build_graph(canonical_project)
    assert graph.number_of_nodes() > 50
    assert graph.number_of_edges() > 50
    assert "pull_request:pr_11" in graph.nodes
    assert "issue:issue_11" in graph.nodes
    assert "deadline:dl_03" in graph.nodes
    assert graph.has_edge("pull_request:pr_11", "issue:issue_11")


# ============================================================
# 9. Canonical ProjectData -> Risk Engine (Benchmark Risks)
# ============================================================

def test_canonical_to_risk_detector(canonical_project):
    risks = detect_risks(canonical_project)
    risk_ids = [r.risk_id for r in risks]

    assert "RISK-01-DEADLINE-SLIPPAGE" in risk_ids
    assert "RISK-02-DEV-BOTTLENECK" in risk_ids
    assert "RISK-03-DEPLOYMENT-HAZARD" in risk_ids


# ============================================================
# 10. Canonical ProjectData -> Simulation
# ============================================================

def test_canonical_to_simulation(canonical_project):
    req = SimulationRequest(node_id="pr_11", delay_days=3)
    res = simulate(canonical_project, req)
    assert "pr_11" in res.scenario
    assert "pull_request:pr_11" in res.affected_nodes
    assert len(res.new_risks) >= 3


# ============================================================
# 11. False Positive Verifier
# ============================================================

def test_false_positive_verifier(canonical_project):
    verifier = VerifierAgent()
    fp_result = verifier.verify_stale_pr_blocker(canonical_project.model_dump())
    assert fp_result["candidate_id"] == "FP-01-STALE-PR-BLOCKER"
    assert fp_result["status"] == "REJECTED"
    assert fp_result["is_false_positive"] is True


# ============================================================
# 12. Database Save / Load Compatibility
# ============================================================

def test_database_compatibility(canonical_project):
    store_project(canonical_project)
    loaded = load_project(canonical_project.owner, canonical_project.repo)
    assert loaded is not None
    restored = ProjectData(**loaded)
    assert restored.project.name == "NEXUS Core Platform"
    assert len(restored.issues) == 20
