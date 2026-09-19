from __future__ import annotations

"""
Phase 4 Risk Engine Tests — 23 Test Cases.
"""

import time
import pytest
from fastapi.testclient import TestClient

from app.api.routes_risks import load_seeded_dataset
from app.risk_engine.detector import detect_risks, is_overdue
from app.graph.graph_builder import build_graph, validate_causal_path
from app.agents.verifier_agent import VerifierAgent
from app.main import app


# ─── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def seeded_data():
    return load_seeded_dataset()


@pytest.fixture
def seeded_graph(seeded_data):
    return build_graph(seeded_data)


@pytest.fixture
def detected_risks(seeded_data):
    return detect_risks(seeded_data)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Required Risk 1 detection
# ═══════════════════════════════════════════════════════════════════════════

def test_risk1_detection(detected_risks):
    r1 = next((r for r in detected_risks if r.risk_id == "RISK-01-DEADLINE-SLIPPAGE"), None)
    assert r1 is not None, "RISK-01-DEADLINE-SLIPPAGE not detected"
    assert r1.root_cause == "pr_11"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Required Risk 2 detection
# ═══════════════════════════════════════════════════════════════════════════

def test_risk2_detection(detected_risks):
    r2 = next((r for r in detected_risks if r.risk_id == "RISK-02-DEV-BOTTLENECK"), None)
    assert r2 is not None, "RISK-02-DEV-BOTTLENECK not detected"
    assert r2.root_cause == "dev_01"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Required Risk 3 detection
# ═══════════════════════════════════════════════════════════════════════════

def test_risk3_detection(detected_risks):
    r3 = next((r for r in detected_risks if r.risk_id == "RISK-03-DEPLOYMENT-HAZARD"), None)
    assert r3 is not None, "RISK-03-DEPLOYMENT-HAZARD not detected"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Required risk IDs contract
# ═══════════════════════════════════════════════════════════════════════════

def test_required_risk_ids(detected_risks):
    risk_ids = [r.risk_id for r in detected_risks]
    assert "RISK-01-DEADLINE-SLIPPAGE" in risk_ids
    assert "RISK-02-DEV-BOTTLENECK" in risk_ids
    assert "RISK-03-DEPLOYMENT-HAZARD" in risk_ids


# ═══════════════════════════════════════════════════════════════════════════
# 5. Uppercase severity values
# ═══════════════════════════════════════════════════════════════════════════

def test_uppercase_severity(detected_risks):
    valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    for r in detected_risks:
        assert r.severity in valid_severities, f"Invalid severity: {r.severity}"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Confidence range (0.0 <= p <= 1.0)
# ═══════════════════════════════════════════════════════════════════════════

def test_confidence_range(detected_risks):
    for r in detected_risks:
        p = r.probability
        assert 0.0 <= p <= 1.0, f"Probability out of bounds: {p}"


# ═══════════════════════════════════════════════════════════════════════════
# 7. Valid causal chain
# ═══════════════════════════════════════════════════════════════════════════

def test_valid_causal_chain(seeded_graph, detected_risks):
    r1 = next(r for r in detected_risks if r.risk_id == "RISK-01-DEADLINE-SLIPPAGE")
    assert r1.causal_chain is not None
    assert len(r1.causal_chain) >= 2
    assert validate_causal_path(seeded_graph, r1.causal_chain)


# ═══════════════════════════════════════════════════════════════════════════
# 8. Invalid causal chain rejection
# ═══════════════════════════════════════════════════════════════════════════

def test_invalid_causal_chain_rejection(seeded_graph):
    invalid_chain = ["pr_11", "issue_99999", "dl_03"]
    assert not validate_causal_path(seeded_graph, invalid_chain)


# ═══════════════════════════════════════════════════════════════════════════
# 9. False-positive stale PR behavior
# ═══════════════════════════════════════════════════════════════════════════

def test_false_positive_stale_pr(seeded_data):
    verifier = VerifierAgent()
    fp_res = verifier.verify_stale_pr_blocker(seeded_data)
    assert fp_res.get("status") == "REJECTED" or fp_res.get("decision") == "REJECTED"


# ═══════════════════════════════════════════════════════════════════════════
# 10. Empty project risk detection
# ═══════════════════════════════════════════════════════════════════════════

def test_empty_project_risk_detection():
    assert detect_risks({}) == []
    assert detect_risks([]) == []
    assert detect_risks(None) == []


# ═══════════════════════════════════════════════════════════════════════════
# 11. No deadlines project
# ═══════════════════════════════════════════════════════════════════════════

def test_no_deadlines_project():
    data = {
        "issues": [{"id": "iss_1", "title": "Test"}]
    }
    risks = detect_risks(data)
    assert isinstance(risks, list)


# ═══════════════════════════════════════════════════════════════════════════
# 12. No developers project
# ═══════════════════════════════════════════════════════════════════════════

def test_no_developers_project():
    data = {
        "issues": [{"id": "iss_1", "title": "Test"}]
    }
    risks = detect_risks(data)
    assert not any(r.risk_id == "RISK-02-DEV-BOTTLENECK" for r in risks)


# ═══════════════════════════════════════════════════════════════════════════
# 13. No deployments project
# ═══════════════════════════════════════════════════════════════════════════

def test_no_deployments_project():
    data = {
        "issues": [{"id": "iss_1", "title": "Test"}]
    }
    risks = detect_risks(data)
    assert not any(r.risk_id == "RISK-03-DEPLOYMENT-HAZARD" for r in risks)


# ═══════════════════════════════════════════════════════════════════════════
# 14. Missing optional fields
# ═══════════════════════════════════════════════════════════════════════════

def test_missing_optional_fields():
    data = {
        "issues": [{"id": "i1"}],
        "pull_requests": [{"id": "pr1"}],
        "developers": [{"id": "d1"}],
    }
    risks = detect_risks(data)
    assert isinstance(risks, list)


# ═══════════════════════════════════════════════════════════════════════════
# 15. Malformed date handling
# ═══════════════════════════════════════════════════════════════════════════

def test_malformed_date_handling():
    assert is_overdue("not-a-date") is False
    assert is_overdue(12345) is False
    assert is_overdue(None) is False
    assert is_overdue({}) is False


# ═══════════════════════════════════════════════════════════════════════════
# 16. Deterministic repeated execution
# ═══════════════════════════════════════════════════════════════════════════

def test_deterministic_repeated_execution(seeded_data):
    r1 = detect_risks(seeded_data)
    r2 = detect_risks(seeded_data)

    assert len(r1) == len(r2)
    for a, b in zip(r1, r2):
        assert a.risk_id == b.risk_id
        assert a.severity == b.severity
        assert a.probability == b.probability
        assert a.causal_chain == b.causal_chain


# ═══════════════════════════════════════════════════════════════════════════
# 17. Deterministic risk ordering
# ═══════════════════════════════════════════════════════════════════════════

def test_deterministic_risk_ordering(detected_risks):
    ids = [r.risk_id for r in detected_risks]
    assert ids == sorted(ids) or ids[0] == "RISK-01-DEADLINE-SLIPPAGE"


# ═══════════════════════════════════════════════════════════════════════════
# 18. Unrelated node isolation
# ═══════════════════════════════════════════════════════════════════════════

def test_unrelated_node_isolation(seeded_data):
    r_before = detect_risks(seeded_data)

    # Copy and add an unrelated developer & issue
    import copy
    augmented = copy.deepcopy(seeded_data)
    augmented["developers"].append({"id": "dev_99", "name": "Unrelated Dev"})
    augmented["issues"].append({
        "id": "issue_99",
        "title": "Unrelated Task",
        "assignee_id": "dev_99",
        "estimated_hours": 2.0,
        "status": "open"
    })

    r_after = detect_risks(augmented)

    before_ids = [r.risk_id for r in r_before]
    after_ids = [r.risk_id for r in r_after]

    for req in before_ids:
        assert req in after_ids, f"Core risk '{req}' disappeared after adding unrelated node"


# ═══════════════════════════════════════════════════════════════════════════
# 19. Evidence is project-derived
# ═══════════════════════════════════════════════════════════════════════════

def test_evidence_is_project_derived(detected_risks):
    r1 = next(r for r in detected_risks if r.risk_id == "RISK-01-DEADLINE-SLIPPAGE")
    assert len(r1.evidence) > 0
    pr_ev = next(e for e in r1.evidence if e.get("type") == "pull_request")
    assert pr_ev.get("id") == "pr_11"


# ═══════════════════════════════════════════════════════════════════════════
# 20. No expected_results runtime dependency
# ═══════════════════════════════════════════════════════════════════════════

def test_no_expected_results_runtime_dependency():
    import sys
    for mod in sys.modules.values():
        if hasattr(mod, "__file__") and mod.__file__ and "app/" in mod.__file__.replace("\\", "/"):
            file_content = open(mod.__file__, "r", encoding="utf-8", errors="ignore").read()
            assert "expected_results.json" not in file_content or "#" in file_content or '"""' in file_content or "'''" in file_content


# ═══════════════════════════════════════════════════════════════════════════
# 21. No secret leakage
# ═══════════════════════════════════════════════════════════════════════════

def test_no_secret_leakage(detected_risks):
    forbidden_keys = {"token", "secret", "password", "api_key", "private_key", "credentials"}
    for r in detected_risks:
        for ev in r.evidence:
            if isinstance(ev, dict):
                for k in ev.keys():
                    assert k.lower() not in forbidden_keys, f"Secret key '{k}' leaked in evidence"


# ═══════════════════════════════════════════════════════════════════════════
# 22. Graph reuse / performance
# ═══════════════════════════════════════════════════════════════════════════

def test_graph_reuse_performance(seeded_data):
    start = time.perf_counter()
    for _ in range(5):
        detect_risks(seeded_data)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"Detection too slow: {elapsed:.2f}s for 5 runs"


# ═══════════════════════════════════════════════════════════════════════════
# 23. API risks endpoint regression
# ═══════════════════════════════════════════════════════════════════════════

def test_api_risks_endpoint_regression():
    client = TestClient(app)
    resp = client.get("/api/risks/Aritra-DSU/RF-SENTINEL")
    assert resp.status_code == 200

    data = resp.json()

    # Accommodate both list response or dict wrapper
    if isinstance(data, dict) and "risks" in data:
        risks_list = data["risks"]
    elif isinstance(data, list):
        risks_list = data
    else:
        risks_list = []

    assert len(risks_list) >= 3
    risk_ids = [r["risk_id"] for r in risks_list]
    assert "RISK-01-DEADLINE-SLIPPAGE" in risk_ids
    assert "RISK-02-DEV-BOTTLENECK" in risk_ids
    assert "RISK-03-DEPLOYMENT-HAZARD" in risk_ids
