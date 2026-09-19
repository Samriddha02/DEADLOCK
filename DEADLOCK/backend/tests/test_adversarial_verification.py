from __future__ import annotations

"""
Phase 6: Adversarial Verification, Evidence Integrity & False-Positive Hardening Tests.
Executed with Python 3.11.9 environment.
"""

import copy
import sys
import pytest
from fastapi.testclient import TestClient

from app.api.routes_risks import load_seeded_dataset
from app.agents.investigation_pipeline import (
    InvestigationContext,
    run_investigation_pipeline,
)
from app.agents.adversarial_check_agent import AdversarialCheckAgent
from app.agents.explanation_intervention_agent import ExplanationInterventionAgent
from app.agents.temporal_validator import (
    calculate_bounded_confidence,
    check_contradictory_evidence,
    classify_entity_state,
    deduplicate_evidence,
    validate_temporal_sequence,
)
from app.agents.verifier_agent import VerifierAgent
from app.graph.graph_builder import build_graph, validate_causal_path
from app.models.risk_models import Risk
from app.simulation.what_if import simulate, SimulationRequest
from app.main import app


def make_risk(
    risk_id: str = "RISK-01",
    title: str = "Test Risk",
    severity: str = "CRITICAL",
    probability: float = 0.95,
    root_cause: str = "pr_11",
    impact: str = "Test impact",
    recommendation: str = "Test recommendation",
    causal_chain: list[str] | None = None,
    evidence: list[dict] | None = None,
) -> Risk:
    return Risk(
        risk_id=risk_id,
        title=title,
        severity=severity,
        probability=probability,
        root_cause=root_cause,
        impact=impact,
        recommendation=recommendation,
        causal_chain=causal_chain or [],
        evidence=evidence or [],
    )


@pytest.fixture
def seeded_data():
    return load_seeded_dataset()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Stale PR False Positive Rejection (FP-01)
# ═══════════════════════════════════════════════════════════════════════════

def test_stale_pr_false_positive_rejection(seeded_data):
    agent = AdversarialCheckAgent()
    ctx = InvestigationContext(seeded_data)
    agent.run(ctx)

    fp01 = next((v for v in ctx.adversarial_verdicts if v.candidate_id == "FP-01-STALE-PR-BLOCKER"), None)
    assert fp01 is not None
    assert fp01.status == "REJECTED"
    assert fp01.is_false_positive is True
    assert fp01.confidence == 1.0
    assert "stale historical blocker" in fp01.reason.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 2. Active vs Historical PR Classification
# ═══════════════════════════════════════════════════════════════════════════

def test_active_vs_historical_pr():
    merged_pr = {"id": "pr_10", "status": "merged", "merged_at": "2026-09-01T10:00:00Z"}
    open_pr = {"id": "pr_11", "status": "open"}
    stale_pr = {"id": "pr_04", "status": "abandoned"}

    assert classify_entity_state(merged_pr, "pull_request") == "HISTORICAL"
    assert classify_entity_state(open_pr, "pull_request") == "ACTIVE"
    assert classify_entity_state(stale_pr, "pull_request") == "STALE"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Active vs Historical Issue Classification
# ═══════════════════════════════════════════════════════════════════════════

def test_active_vs_historical_issue():
    closed_issue = {"id": "issue_10", "status": "closed", "closed_at": "2026-09-02T10:00:00Z"}
    open_issue = {"id": "issue_11", "status": "open"}

    assert classify_entity_state(closed_issue, "issue") == "HISTORICAL"
    assert classify_entity_state(open_issue, "issue") == "ACTIVE"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Active vs Historical Deployment Classification
# ═══════════════════════════════════════════════════════════════════════════

def test_active_vs_historical_deployment():
    success_dep = {"id": "dep_00", "status": "success"}
    pending_dep = {"id": "dep_01", "status": "pending"}

    assert classify_entity_state(success_dep, "deployment") == "HISTORICAL"
    assert classify_entity_state(pending_dep, "deployment") == "ACTIVE"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Temporal Inconsistency: Closed Before Created
# ═══════════════════════════════════════════════════════════════════════════

def test_temporal_inconsistency_closed_before_created():
    events = [
        {"id": "pr_bad", "type": "pr", "created_at": "2026-09-10T12:00:00Z", "closed_at": "2026-09-05T12:00:00Z"}
    ]
    is_valid, issues = validate_temporal_sequence(events)
    assert is_valid is False
    assert len(issues) > 0
    assert "before created" in issues[0]


# ═══════════════════════════════════════════════════════════════════════════
# 6. Temporal Inconsistency: Review Submitted Before PR Created
# ═══════════════════════════════════════════════════════════════════════════

def test_temporal_inconsistency_review_before_pr():
    events = [
        {
            "id": "pr_bad_rev",
            "type": "pull_request",
            "created_at": "2026-09-10T12:00:00Z",
            "reviews": [{"id": "rev_01", "submitted_at": "2026-09-01T12:00:00Z"}]
        }
    ]
    is_valid, issues = validate_temporal_sequence(events)
    assert is_valid is False
    assert any("before PR was created" in iss for iss in issues)


# ═══════════════════════════════════════════════════════════════════════════
# 7. Contradictory Evidence: Resolved by Another Entity
# ═══════════════════════════════════════════════════════════════════════════

def test_contradictory_evidence_resolved_by_another():
    root_pr = {"id": "pr_04", "status": "open"}
    related = [{"id": "issue_10", "type": "issue", "status": "closed", "resolved_by": "pr_10"}]

    has_contra, reason = check_contradictory_evidence(root_pr, related)
    assert has_contra is True
    assert "resolved by pr_10" in reason


# ═══════════════════════════════════════════════════════════════════════════
# 8. Contradictory Evidence: Blocking Review Superseded by Approval
# ═══════════════════════════════════════════════════════════════════════════

def test_contradictory_evidence_blocking_superseded_by_approval():
    root_pr = {
        "id": "pr_11",
        "status": "open",
        "reviews": [
            {"id": "rev_1", "state": "CHANGES_REQUESTED", "submitted_at": "2026-09-01T10:00:00Z"},
            {"id": "rev_2", "state": "APPROVED", "submitted_at": "2026-09-02T10:00:00Z"},
        ]
    }
    has_contra, reason = check_contradictory_evidence(root_pr, [])
    assert has_contra is True
    assert "superseded by newer approval" in reason


# ═══════════════════════════════════════════════════════════════════════════
# 9. Invalid Causal Path: Missing Node -> INSUFFICIENT_EVIDENCE
# ═══════════════════════════════════════════════════════════════════════════

def test_invalid_causal_path_missing_node(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.candidate_risks = [
        make_risk(risk_id="RISK-MISSING-NODE", root_cause="pr_11", causal_chain=["pr_11", "nonexistent_node_xyz"])
    ]
    AdversarialCheckAgent().run(ctx)
    v = next(v for v in ctx.adversarial_verdicts if v.candidate_id == "RISK-MISSING-NODE")
    assert v.status == "INSUFFICIENT_EVIDENCE"
    assert "cannot be verified" in v.reason


# ═══════════════════════════════════════════════════════════════════════════
# 10. Invalid Causal Path: Broken Edge -> INSUFFICIENT_EVIDENCE
# ═══════════════════════════════════════════════════════════════════════════

def test_invalid_causal_path_missing_edge(seeded_data):
    ctx = InvestigationContext(seeded_data)
    # pr_11 and dep_01 exist, but there is no direct edge from pr_11 directly to dep_01 without issues
    ctx.candidate_risks = [
        make_risk(risk_id="RISK-BROKEN-EDGE", root_cause="pr_11", causal_chain=["pr_11", "dep_01"])
    ]
    AdversarialCheckAgent().run(ctx)
    v = next(v for v in ctx.adversarial_verdicts if v.candidate_id == "RISK-BROKEN-EDGE")
    assert v.status == "INSUFFICIENT_EVIDENCE"


# ═══════════════════════════════════════════════════════════════════════════
# 11. No Invented Graph Edges
# ═══════════════════════════════════════════════════════════════════════════

def test_no_invented_graph_edges(seeded_data):
    g = build_graph(seeded_data)
    # Validate that arbitrary pairs do not have fabricated edges
    assert validate_causal_path(g, ["pr_01", "dl_03"]) is False
    assert validate_causal_path(g, ["dev_01", "nonexistent_x", "dl_01"]) is False


# ═══════════════════════════════════════════════════════════════════════════
# 12. Confidence Bounds and Deduplication
# ═══════════════════════════════════════════════════════════════════════════

def test_confidence_bounds_and_deduplication():
    duplicate_evidence = [
        {"type": "pull_request", "id": "pr_11", "detail": "Test PR"},
        {"type": "pull_request", "id": "pr_11", "detail": "Test PR"},
        {"type": "pull_request", "id": "pr_11", "detail": "Test PR"},
    ]
    deduped = deduplicate_evidence(duplicate_evidence)
    assert len(deduped) == 1

    conf1 = calculate_bounded_confidence(0.90, duplicate_evidence)
    conf2 = calculate_bounded_confidence(0.90, deduped)
    assert conf1 == conf2
    assert 0.0 <= conf1 <= 1.0

    # With contradiction, confidence becomes 0.0
    conf_contra = calculate_bounded_confidence(0.90, deduped, contradictions=["Contradiction found"])
    assert conf_contra == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 13. Cross-Project State Isolation
# ═══════════════════════════════════════════════════════════════════════════

def test_cross_project_isolation(seeded_data):
    project_synth = {
        "project": {"id": "synth_proj", "name": "Synthetic Project"},
        "developers": [{"id": "synth_dev_99", "name": "Alice Synthetic"}],
        "issues": [{"id": "synth_issue_99", "title": "Synth Issue", "assignee_id": "synth_dev_99"}]
    }

    res_a = run_investigation_pipeline(seeded_data, "Aritra-DSU", "RF-SENTINEL")
    res_b = run_investigation_pipeline(project_synth, "synth-owner", "synth-repo")

    assert res_a.project == "Aritra-DSU/RF-SENTINEL"
    assert res_b.project == "synth-owner/synth-repo"
    assert not any("synth_dev_99" in str(r) for r in res_a.risks)
    assert not any("pr_11" in str(r) for r in res_b.risks)


# ═══════════════════════════════════════════════════════════════════════════
# 14. Deterministic Repeated Analysis
# ═══════════════════════════════════════════════════════════════════════════

def test_deterministic_repeated_analysis(seeded_data):
    results = [run_investigation_pipeline(seeded_data) for _ in range(3)]

    for r in results[1:]:
        assert len(r.risks) == len(results[0].risks)
        assert len(r.adversarial_verdicts) == len(results[0].adversarial_verdicts)
        assert len(r.explanations) == len(results[0].explanations)
        assert [v.status for v in r.adversarial_verdicts] == [v.status for v in results[0].adversarial_verdicts]


# ═══════════════════════════════════════════════════════════════════════════
# 15. Graph Cycle Safety
# ═══════════════════════════════════════════════════════════════════════════

def test_graph_cycle_safety():
    cyclic_project = {
        "issues": [
            {"id": "issue_a", "title": "A"},
            {"id": "issue_b", "title": "B"},
            {"id": "issue_c", "title": "C"},
        ],
        "dependencies": [
            {"source": "issue_a", "target": "issue_b"},
            {"source": "issue_b", "target": "issue_c"},
            {"source": "issue_c", "target": "issue_a"},
        ],
    }
    g = build_graph(cyclic_project)
    assert g.number_of_nodes() == 3
    # validate that causal path or simulation handles cycles without recursion error
    assert validate_causal_path(g, ["issue_a", "issue_b", "issue_c", "issue_a"]) is True
    res = simulate(cyclic_project, SimulationRequest(node_id="issue_a", delay_days=3))
    assert len(res.affected_nodes) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 16. Empty Project Safety
# ═══════════════════════════════════════════════════════════════════════════

def test_empty_project_safety():
    res = run_investigation_pipeline({})
    assert res.status == "COMPLETED"
    assert len(res.agent_trace) == 5
    assert len(res.risks) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 17. Malformed Project Safety
# ═══════════════════════════════════════════════════════════════════════════

def test_malformed_project_safety():
    malformed = {
        "pull_requests": "not_a_list",
        "issues": [{"id": None, "invalid_field": 123}],
        "deadlines": 9999,
    }
    res = run_investigation_pipeline(malformed)
    assert res.status == "COMPLETED"
    assert len(res.agent_trace) == 5


# ═══════════════════════════════════════════════════════════════════════════
# 18. Rejected Risk Not in Verified Risks
# ═══════════════════════════════════════════════════════════════════════════

def test_rejected_risk_not_in_verified_risks(seeded_data):
    ctx = InvestigationContext(seeded_data)
    # Candidate with closed root PR
    ctx.candidate_risks = [
        make_risk(risk_id="RISK-CLOSED", root_cause="pr_10", causal_chain=["pr_10"])
    ]
    AdversarialCheckAgent().run(ctx)
    assert len(ctx.verified_risks) == 0
    assert any(v.candidate_id == "RISK-CLOSED" and v.status == "REJECTED" for v in ctx.adversarial_verdicts)


# ═══════════════════════════════════════════════════════════════════════════
# 19. Explanation Truthfulness for Rejected Risks
# ═══════════════════════════════════════════════════════════════════════════

def test_explanation_truthfulness_rejected_risk(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.candidate_risks = [
        make_risk(risk_id="RISK-CLOSED", root_cause="pr_10", causal_chain=["pr_10"])
    ]
    AdversarialCheckAgent().run(ctx)
    ExplanationInterventionAgent().run(ctx)

    exp = next((e for e in ctx.explanations if e.get("risk_id") == "RISK-CLOSED"), None)
    assert exp is not None
    assert exp["verification_status"] == "REJECTED"
    assert "rejected" in exp["what"].lower()
    assert "no propagation" in exp["how_propagates"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# 20. Explanation Truthfulness for Insufficient Evidence
# ═══════════════════════════════════════════════════════════════════════════

def test_explanation_truthfulness_insufficient_evidence(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.candidate_risks = [
        make_risk(risk_id="RISK-BROKEN", root_cause="pr_9999", causal_chain=["pr_9999", "nonexistent"])
    ]
    AdversarialCheckAgent().run(ctx)
    ExplanationInterventionAgent().run(ctx)

    exp = next((e for e in ctx.explanations if e.get("risk_id") == "RISK-BROKEN"), None)
    assert exp is not None
    assert exp["verification_status"] == "INSUFFICIENT_EVIDENCE"
    assert "insufficient_evidence" in exp["what"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# 21. Suggested Interventions Never Executed
# ═══════════════════════════════════════════════════════════════════════════

def test_suggested_interventions_never_executed(seeded_data):
    res = run_investigation_pipeline(seeded_data)
    assert len(res.interventions) > 0
    for inv in res.interventions:
        assert inv.executed is False
        assert "SUGGESTED" in inv.action


# ═══════════════════════════════════════════════════════════════════════════
# 22. What-If Engine Immutability
# ═══════════════════════════════════════════════════════════════════════════

def test_whatif_engine_immutability(seeded_data):
    original_copy = copy.deepcopy(seeded_data)
    res = simulate(seeded_data, SimulationRequest(node_id="pr_11", delay_days=5))
    assert "pr_11" in res.scenario
    assert len(res.affected_nodes) > 0
    assert seeded_data == original_copy


# ═══════════════════════════════════════════════════════════════════════════
# 23. Benchmark Independence at Runtime
# ═══════════════════════════════════════════════════════════════════════════

def test_benchmark_independence_runtime():
    for mod_name, mod in list(sys.modules.items()):
        if hasattr(mod, "__file__") and mod.__file__ and "app" in mod.__file__.replace("\\", "/"):
            with open(mod.__file__, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            # Assert expected_results.json is never loaded via open() or json.load()
            assert 'open("expected_results.json' not in content
            assert "open('expected_results.json" not in content
            assert 'expected_results = json.load' not in content


# ═══════════════════════════════════════════════════════════════════════════
# 24. Security Audit: No eval/exec/subprocess/os.system
# ═══════════════════════════════════════════════════════════════════════════

def test_security_audit_no_eval_exec():
    forbidden = ["eval(", "exec(", "os.system(", "subprocess.Popen(", "subprocess.run("]
    for mod_name, mod in list(sys.modules.items()):
        if hasattr(mod, "__file__") and mod.__file__ and "/app/" in mod.__file__.replace("\\", "/"):
            with open(mod.__file__, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for pattern in forbidden:
                assert pattern not in content, f"Forbidden pattern {pattern} found in {mod.__file__}"


# ═══════════════════════════════════════════════════════════════════════════
# 25. API Endpoints Compatibility
# ═══════════════════════════════════════════════════════════════════════════

def test_api_endpoints_compatibility():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/risks/Aritra-DSU/RF-SENTINEL").status_code == 200
    assert client.get("/api/graph/Aritra-DSU/RF-SENTINEL").status_code == 200
    assert client.post("/api/simulate/Aritra-DSU/RF-SENTINEL", json={"node_id": "pr_11", "delay_days": 3}).status_code == 200
    assert client.post("/api/analyze/Aritra-DSU/RF-SENTINEL").status_code == 200
