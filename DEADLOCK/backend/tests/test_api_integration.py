import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "deadlock-backend"


def test_simulate_direct_empty_body():
    response = client.post("/api/simulate", json={})
    assert response.status_code == 200
    data = response.json()
    assert "Simulate 3-day delay for pr_11" in data["scenario"]
    assert isinstance(data["affected_nodes"], list)
    assert len(data["affected_nodes"]) > 0
    assert "pull_request:pr_11" in data["affected_nodes"]


def test_simulate_direct_explicit_payload():
    payload = {"node_id": "pr_11", "delay_days": 3}
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "pr_11" in data["scenario"]
    assert "pull_request:pr_11" in data["affected_nodes"]


def test_simulate_parameterized():
    payload = {"node_id": "pr_11", "delay_days": 3}
    response = client.post("/api/simulate/Aritra-DSU/RF-SENTINEL", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "pr_11" in data["scenario"]
    assert "pull_request:pr_11" in data["affected_nodes"]


def test_simulate_consistency():
    payload = {"node_id": "pr_11", "delay_days": 3}
    res_direct = client.post("/api/simulate", json=payload).json()
    res_param = client.post("/api/simulate/Aritra-DSU/RF-SENTINEL", json=payload).json()

    assert res_direct["scenario"] == res_param["scenario"]
    assert res_direct["affected_nodes"] == res_param["affected_nodes"]
    assert res_direct["recommendation"] == res_param["recommendation"]


def test_simulate_frontend_legacy_compat():
    payload = {
        "node_id": "PR-47",
        "event_type": "delay",
        "delay_days": 3,
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Mapped to canonical pr_11 and evaluated against seeded graph
    assert "pull_request:pr_11" in data["affected_nodes"]
    assert "AUTH-API" not in str(data)


def test_projects_analyze_demo_repo():
    payload = {"owner": "Aritra-DSU", "repo": "RF-SENTINEL"}
    response = client.post("/api/projects/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Must be canonical seeded project, not CampusConnect
    assert data["project"]["name"] == "NEXUS Core Platform"
    assert "CampusConnect" not in str(data)

    risk_ids = [r["risk_id"] for r in data["risks"]]
    assert "RISK-01-DEADLINE-SLIPPAGE" in risk_ids
    assert "RISK-02-DEV-BOTTLENECK" in risk_ids
    assert "RISK-03-DEPLOYMENT-HAZARD" in risk_ids


def test_projects_analyze_fake_repo():
    payload = {"owner": "fake-owner-nonexistent", "repo": "fake-repo-nonexistent"}
    response = client.post("/api/projects/analyze", json=payload)
    assert response.status_code == 404
    # Must NOT silently return CampusConnect
    assert "CampusConnect" not in response.text


def test_projects_demo():
    response = client.get("/api/projects/demo")
    assert response.status_code == 200
    data = response.json()
    assert data["project"]["name"] == "NEXUS Core Platform"
    assert len(data["risks"]) >= 3
    risk_ids = [r["risk_id"] for r in data["risks"]]
    assert "RISK-01-DEADLINE-SLIPPAGE" in risk_ids


def test_risks_endpoint():
    response = client.get("/api/risks/Aritra-DSU/RF-SENTINEL")
    assert response.status_code == 200
    data = response.json()
    assert data["total_risks"] >= 3
    risk_ids = [r["risk_id"] for r in data["risks"]]
    assert "RISK-01-DEADLINE-SLIPPAGE" in risk_ids
    assert "RISK-02-DEV-BOTTLENECK" in risk_ids
    assert "RISK-03-DEPLOYMENT-HAZARD" in risk_ids


def test_graph_endpoint():
    response = client.get("/api/graph/Aritra-DSU/RF-SENTINEL")
    assert response.status_code == 200
    data = response.json()
    assert data["total_nodes"] > 50
    assert data["total_edges"] > 50
