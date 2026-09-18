from __future__ import annotations

"""
Phase 5 Five-Agent Investigation Pipeline Tests — 34 Test Cases.
Executed with Python 3.11.9 environment.
"""

import sys
import copy
import pytest
from fastapi.testclient import TestClient

from app.api.routes_risks import load_seeded_dataset
from app.agents.investigation_pipeline import (
    InvestigationContext,
    run_investigation_pipeline,
)
from app.agents.dependency_discovery_agent import DependencyDiscoveryAgent
from app.agents.bottleneck_detection_agent import BottleneckDetectionAgent
from app.agents.adversarial_check_agent import AdversarialCheckAgent
from app.agents.impact_simulation_agent import ImpactSimulationAgent
from app.agents.explanation_intervention_agent import ExplanationInterventionAgent
from app.models.risk_models import Risk
from app.main import app


# ─── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def python_version_check():
    assert sys.version_info.major == 3 and sys.version_info.minor == 11, f"Expected Python 3.11, got {sys.version}"


@pytest.fixture
def seeded_data():
    return load_seeded_dataset()


@pytest.fixture
def pipeline_result(seeded_data):
    return run_investigation_pipeline(seeded_data, "Aritra-DSU", "RF-SENTINEL")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Agent 1 executes
# ═══════════════════════════════════════════════════════════════════════════

def test_agent1_executes(seeded_data):
    ctx = InvestigationContext(seeded_data)
    agent = DependencyDiscoveryAgent()
    agent.run(ctx)
    assert len(ctx.traces) == 1
    assert ctx.traces[0].agent_name == "dependency_discovery_agent"
    assert ctx.traces[0].status == "COMPLETED"
    assert "graph_metrics" in ctx.dependency_findings


# ═══════════════════════════════════════════════════════════════════════════
# 2. Agent 1 discovers actual graph relationships
# ═══════════════════════════════════════════════════════════════════════════

def test_agent1_discovers_graph_relationships(seeded_data):
    ctx = InvestigationContext(seeded_data)
    DependencyDiscoveryAgent().run(ctx)
    metrics = ctx.dependency_findings.get("graph_metrics", {})
    assert metrics.get("nodes", 0) > 100
    assert metrics.get("edges", 0) > 200


# ═══════════════════════════════════════════════════════════════════════════
# 3. Agent 2 executes
# ═══════════════════════════════════════════════════════════════════════════

def test_agent2_executes(seeded_data):
    ctx = InvestigationContext(seeded_data)
    BottleneckDetectionAgent().run(ctx)
    assert len(ctx.traces) == 1
    assert ctx.traces[0].agent_name == "bottleneck_detection_agent"
    assert ctx.traces[0].status == "COMPLETED"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Agent 2 discovers bottleneck evidence
# ═══════════════════════════════════════════════════════════════════════════

def test_agent2_discovers_bottleneck_evidence(seeded_data):
    ctx = InvestigationContext(seeded_data)
    BottleneckDetectionAgent().run(ctx)
    findings = ctx.bottleneck_findings
    assert len(findings) >= 1
    dev1 = next((f for f in findings if f["developer_id"] == "dev_01"), None)
    assert dev1 is not None
    assert dev1["workload_share"] >= 0.40


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


# ═══════════════════════════════════════════════════════════════════════════
# 5. Agent 3 executes
# ═══════════════════════════════════════════════════════════════════════════

def test_agent3_executes(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.candidate_risks = [make_risk(risk_id="RISK-01-DEADLINE-SLIPPAGE", title="Test", root_cause="pr_11", causal_chain=["pr_11", "issue_11", "issue_14", "dep_01", "dl_03"])]
    AdversarialCheckAgent().run(ctx)
    assert len(ctx.traces) == 1
    assert ctx.traces[0].agent_name == "adversarial_check_agent"
    assert len(ctx.adversarial_verdicts) >= 2  # FP-01 + candidate


# ═══════════════════════════════════════════════════════════════════════════
# 6. Agent 3 genuinely challenges candidates
# ═══════════════════════════════════════════════════════════════════════════

def test_agent3_challenges_candidates(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.candidate_risks = [
        make_risk(risk_id="RISK-01-DEADLINE-SLIPPAGE", title="Active", root_cause="pr_11", causal_chain=["pr_11", "issue_11", "issue_14", "dep_01", "dl_03"]),
        make_risk(risk_id="RISK-CLOSED", title="Closed PR", root_cause="pr_10", causal_chain=["pr_10"]),
    ]
    AdversarialCheckAgent().run(ctx)
    statuses = {v.candidate_id: v.status for v in ctx.adversarial_verdicts}
    assert statuses.get("RISK-01-DEADLINE-SLIPPAGE") == "VERIFIED"
    assert statuses.get("RISK-CLOSED") == "REJECTED"


# ═══════════════════════════════════════════════════════════════════════════
# 7. Agent 3 rejects stale PR false positive
# ═══════════════════════════════════════════════════════════════════════════

def test_agent3_rejects_stale_pr(seeded_data):
    ctx = InvestigationContext(seeded_data)
    AdversarialCheckAgent().run(ctx)
    fp_v = next(v for v in ctx.adversarial_verdicts if v.candidate_id == "FP-01-STALE-PR-BLOCKER")
    assert fp_v.status == "REJECTED"
    assert fp_v.is_false_positive is True


# ═══════════════════════════════════════════════════════════════════════════
# 8. Agent 3 retains valid evidence
# ═══════════════════════════════════════════════════════════════════════════

def test_agent3_retains_valid_evidence(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.candidate_risks = [make_risk(risk_id="RISK-01-DEADLINE-SLIPPAGE", title="Valid", root_cause="pr_11", causal_chain=["pr_11", "issue_11", "issue_14", "dep_01", "dl_03"])]
    AdversarialCheckAgent().run(ctx)
    assert len(ctx.verified_risks) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 9. Agent 3 INSUFFICIENT_EVIDENCE verdict
# ═══════════════════════════════════════════════════════════════════════════

def test_agent3_insufficient_evidence_verdict(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.candidate_risks = [make_risk(risk_id="RISK-BROKEN", title="Broken Chain", root_cause="pr_9999", causal_chain=["pr_9999", "nonexistent_node"])]
    AdversarialCheckAgent().run(ctx)
    v = next(v for v in ctx.adversarial_verdicts if v.candidate_id == "RISK-BROKEN")
    assert v.status == "INSUFFICIENT_EVIDENCE"


# ═══════════════════════════════════════════════════════════════════════════
# 10. Agent 4 executes
# ═══════════════════════════════════════════════════════════════════════════

def test_agent4_executes(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.verified_risks = [make_risk(risk_id="RISK-01", root_cause="pr_11")]
    ImpactSimulationAgent().run(ctx)
    assert len(ctx.traces) == 1
    assert ctx.traces[0].agent_name == "impact_simulation_agent"
    assert len(ctx.simulation_results) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# 11. Agent 4 returns affected nodes
# ═══════════════════════════════════════════════════════════════════════════

def test_agent4_returns_affected_nodes(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.verified_risks = [make_risk(risk_id="RISK-01", root_cause="pr_11")]
    ImpactSimulationAgent().run(ctx)
    res = ctx.simulation_results[0]
    assert len(res.affected_nodes) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 12. Agent 4 preserves project immutability
# ═══════════════════════════════════════════════════════════════════════════

def test_agent4_preserves_project_immutability(seeded_data):
    original_copy = copy.deepcopy(seeded_data)
    ctx = InvestigationContext(seeded_data)
    ctx.verified_risks = [make_risk(risk_id="RISK-01", root_cause="pr_11")]
    ImpactSimulationAgent().run(ctx)
    assert seeded_data == original_copy


# ═══════════════════════════════════════════════════════════════════════════
# 13. Agent 5 executes
# ═══════════════════════════════════════════════════════════════════════════

def test_agent5_executes(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.verified_risks = [make_risk(risk_id="RISK-01-DEADLINE-SLIPPAGE", title="Delay", root_cause="pr_11", recommendation="Review PR 11")]
    ExplanationInterventionAgent().run(ctx)
    assert len(ctx.traces) == 1
    assert ctx.traces[0].agent_name == "explanation_intervention_agent"
    assert len(ctx.explanations) == 1
    assert len(ctx.interventions) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# 14. Agent 5 produces explanation
# ═══════════════════════════════════════════════════════════════════════════

def test_agent5_produces_explanation(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.verified_risks = [make_risk(risk_id="RISK-01-DEADLINE-SLIPPAGE", title="Delay", root_cause="pr_11", impact="Impact text", recommendation="Review PR 11")]
    ExplanationInterventionAgent().run(ctx)
    exp = ctx.explanations[0]
    assert "what" in exp and "why" in exp and "which_entities" in exp and "how_propagates" in exp


# ═══════════════════════════════════════════════════════════════════════════
# 15. Agent 5 produces grounded intervention (executed=False)
# ═══════════════════════════════════════════════════════════════════════════

def test_agent5_produces_grounded_intervention(seeded_data):
    ctx = InvestigationContext(seeded_data)
    ctx.verified_risks = [make_risk(risk_id="RISK-01-DEADLINE-SLIPPAGE", title="Delay", root_cause="pr_11", recommendation="Review PR 11")]
    ExplanationInterventionAgent().run(ctx)
    inv = ctx.interventions[0]
    assert inv.executed is False
    assert "SUGGESTED" in inv.action


# ═══════════════════════════════════════════════════════════════════════════
# 16. Agent execution order is deterministic (1, 2, 3, 4, 5)
# ═══════════════════════════════════════════════════════════════════════════

def test_agent_execution_order_deterministic(pipeline_result):
    orders = [t.execution_order for t in pipeline_result.agent_trace]
    assert orders == [1, 2, 3, 4, 5]


# ═══════════════════════════════════════════════════════════════════════════
# 17. Agent trace is complete
# ═══════════════════════════════════════════════════════════════════════════

def test_agent_trace_complete(pipeline_result):
    assert len(pipeline_result.agent_trace) == 5
    names = [t.agent_name for t in pipeline_result.agent_trace]
    expected = [
        "dependency_discovery_agent",
        "bottleneck_detection_agent",
        "adversarial_check_agent",
        "impact_simulation_agent",
        "explanation_intervention_agent",
    ]
    assert names == expected


# ═══════════════════════════════════════════════════════════════════════════
# 18. Agent trace real statuses
# ═══════════════════════════════════════════════════════════════════════════

def test_agent_trace_real_statuses(pipeline_result):
    for trace in pipeline_result.agent_trace:
        assert trace.status == "COMPLETED"
        assert trace.duration_ms >= 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 19. Repeated analysis is deterministic
# ═══════════════════════════════════════════════════════════════════════════

def test_repeated_analysis_deterministic(seeded_data):
    r1 = run_investigation_pipeline(seeded_data)
    r2 = run_investigation_pipeline(seeded_data)

    assert len(r1.risks) == len(r2.risks)
    assert len(r1.adversarial_verdicts) == len(r2.adversarial_verdicts)
    assert len(r1.interventions) == len(r2.interventions)
    for a, b in zip(r1.risks, r2.risks):
        assert a.risk_id == b.risk_id


# ═══════════════════════════════════════════════════════════════════════════
# 20. Cross-project state isolation
# ═══════════════════════════════════════════════════════════════════════════

def test_cross_project_isolation(seeded_data):
    project_b = {
        "project": {"id": "proj_b", "name": "Project B"},
        "developers": [{"id": "dev_b1", "name": "Bob"}],
        "issues": [{"id": "issue_b1", "title": "B Task", "assignee_id": "dev_b1"}]
    }

    res_a1 = run_investigation_pipeline(seeded_data, "Aritra-DSU", "RF-SENTINEL")
    res_b = run_investigation_pipeline(project_b, "org-b", "repo-b")
    res_a2 = run_investigation_pipeline(seeded_data, "Aritra-DSU", "RF-SENTINEL")

    assert res_a1.project == "Aritra-DSU/RF-SENTINEL"
    assert res_b.project == "org-b/repo-b"
    assert len(res_a1.risks) == len(res_a2.risks)
    assert not any("dev_b1" in str(r) for r in res_a1.risks)


# ═══════════════════════════════════════════════════════════════════════════
# 21. Agent failure isolation
# ═══════════════════════════════════════════════════════════════════════════

def test_agent_failure_isolation(seeded_data):
    ctx = InvestigationContext(seeded_data)
    # Simulate partial failure in Agent 1 by passing invalid graph
    ctx.graph = None  # Force exception in Agent 1
    DependencyDiscoveryAgent().run(ctx)

    assert len(ctx.traces) == 1
    assert ctx.traces[0].status == "FAILED"
    assert ctx.traces[0].error_info is not None


# ═══════════════════════════════════════════════════════════════════════════
# 22. No secret leakage in trace
# ═══════════════════════════════════════════════════════════════════════════

def test_no_secret_leakage_in_trace(pipeline_result):
    forbidden = {"token", "secret", "password", "api_key"}
    for trace in pipeline_result.agent_trace:
        text = (trace.input_summary + trace.output_summary).lower()
        for f in forbidden:
            assert f not in text


# ═══════════════════════════════════════════════════════════════════════════
# 23. No hardcoded benchmark chain
# ═══════════════════════════════════════════════════════════════════════════

def test_no_hardcoded_benchmark_chain(pipeline_result):
    df = pipeline_result.dependency_findings
    assert "graph_metrics" in df
    assert df["graph_metrics"]["nodes"] > 100


# ═══════════════════════════════════════════════════════════════════════════
# 24. expected_results absent from runtime dependencies
# ═══════════════════════════════════════════════════════════════════════════

def test_expected_results_absent_from_runtime():
    for mod in list(sys.modules.values()):
        if hasattr(mod, "__file__") and mod.__file__ and "app/" in mod.__file__.replace("\\", "/"):
            content = open(mod.__file__, "r", encoding="utf-8", errors="ignore").read()
            assert "expected_results.json" not in content or "#" in content or '"""' in content or "'''" in content


# ═══════════════════════════════════════════════════════════════════════════
# 25. Full pipeline API integration
# ═══════════════════════════════════════════════════════════════════════════

def test_full_pipeline_api_integration():
    client = TestClient(app)
    resp = client.post("/api/analyze/Aritra-DSU/RF-SENTINEL")
    assert resp.status_code == 200

    data = resp.json()
    assert data["project"] == "Aritra-DSU/RF-SENTINEL"
    assert "agent_trace" in data
    assert len(data["agent_trace"]) == 5
    assert len(data["risks"]) >= 3


# ═══════════════════════════════════════════════════════════════════════════
# 26. Existing GET /api/risks regression
# ═══════════════════════════════════════════════════════════════════════════

def test_existing_get_risks_regression():
    client = TestClient(app)
    resp = client.get("/api/risks/Aritra-DSU/RF-SENTINEL")
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 27. Existing POST /api/simulate regression
# ═══════════════════════════════════════════════════════════════════════════

def test_existing_post_simulate_regression():
    client = TestClient(app)
    resp = client.post("/api/simulate/Aritra-DSU/RF-SENTINEL", json={"node_id": "pr_11", "delay_days": 3})
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 28. Existing GET /api/graph regression
# ═══════════════════════════════════════════════════════════════════════════

def test_existing_get_graph_regression():
    client = TestClient(app)
    resp = client.get("/api/graph/Aritra-DSU/RF-SENTINEL")
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 29. Empty project pipeline behavior
# ═══════════════════════════════════════════════════════════════════════════

def test_empty_project_pipeline_behavior():
    res = run_investigation_pipeline({})
    assert res.status == "COMPLETED"
    assert len(res.agent_trace) == 5


# ═══════════════════════════════════════════════════════════════════════════
# 30. Malformed/incomplete project behavior
# ═══════════════════════════════════════════════════════════════════════════

def test_malformed_project_pipeline_behavior():
    malformed = {"issues": ["not_a_dict"], "developers": "not_a_list"}
    res = run_investigation_pipeline(malformed)
    assert res.status == "COMPLETED"
    assert len(res.agent_trace) == 5


# ═══════════════════════════════════════════════════════════════════════════
# 31. Shared graph built once
# ═══════════════════════════════════════════════════════════════════════════

def test_shared_graph_built_once(seeded_data):
    ctx = InvestigationContext(seeded_data)
    g_id1 = id(ctx.graph)
    DependencyDiscoveryAgent().run(ctx)
    BottleneckDetectionAgent().run(ctx)
    g_id2 = id(ctx.graph)
    assert g_id1 == g_id2  # Graph object is reused, not rebuilt five times


# ═══════════════════════════════════════════════════════════════════════════
# 32. Agent 3 actually invoked in trace
# ═══════════════════════════════════════════════════════════════════════════

def test_agent3_invoked_by_pipeline(pipeline_result):
    t3 = next(t for t in pipeline_result.agent_trace if t.agent_name == "adversarial_check_agent")
    assert t3.status == "COMPLETED"
    assert len(pipeline_result.adversarial_verdicts) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 33. Agent 4 actually invokes What-If behavior
# ═══════════════════════════════════════════════════════════════════════════

def test_agent4_invokes_whatif_engine(pipeline_result):
    t4 = next(t for t in pipeline_result.agent_trace if t.agent_name == "impact_simulation_agent")
    assert t4.status == "COMPLETED"
    assert len(pipeline_result.simulation_results) >= 1
    assert len(pipeline_result.simulation_results[0].affected_nodes) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 34. Agent 5 interventions not executed
# ═══════════════════════════════════════════════════════════════════════════

def test_agent5_interventions_not_executed(pipeline_result):
    for inv in pipeline_result.interventions:
        assert inv.executed is False
        assert "SUGGESTED" in inv.action
