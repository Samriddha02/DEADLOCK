"""
Phase 8 — Generic Failure Propagation & What-If Simulation Hardening Tests.

Verifies:
1. Multi-event failure propagation (PR_DELAY, TASK_DELAY, SERVICE_FAILURE, TIMEOUT,
   LATENCY, HTTP_500, HTTP_503, MALFORMED_RESPONSE, DEPLOYMENT_FAILURE, COMPONENT_UNAVAILABLE)
2. Partitioning into affected_nodes, unaffected_nodes, unknown_nodes
3. Before/after state transformations
4. Causal chains, propagation paths, and edge evidence collection
5. Cycle safety and depth truncation
6. Graph and database immutability
7. Request-scoped isolation and determinism
8. Edge type compatibility and strict NO EVIDENCE = NO PROPAGATION enforcement
9. API route integration and legacy compatibility
10. Benchmark isolation (expected_results.json never used at runtime)
"""
import copy
import json
import networkx as nx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.risk_models import SimulationRequest, SimulationResult
from app.simulation.propagation_policy import (
    PropagationPolicy,
    EVENT_PR_DELAY,
    EVENT_TASK_DELAY,
    EVENT_SERVICE_FAILURE,
    EVENT_TIMEOUT,
    EVENT_LATENCY,
    EVENT_HTTP_500,
    EVENT_HTTP_503,
    EVENT_MALFORMED_RESPONSE,
    EVENT_DEPLOYMENT_FAILURE,
    EVENT_COMPONENT_UNAVAILABLE,
)
from app.simulation.propagation_engine import PropagationEngine
from app.simulation.what_if import simulate
from app.graph.graph_builder import build_graph, _find_node
from app.agents.impact_simulation_agent import ImpactSimulationAgent
from app.api.routes_risks import load_seeded_dataset


client = TestClient(app)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def seeded_data():
    return load_seeded_dataset()


@pytest.fixture
def seeded_graph(seeded_data):
    return build_graph(seeded_data)


@pytest.fixture
def custom_graph():
    """Constructs a controlled test graph with diverse edge types and known structure."""
    g = nx.DiGraph()
    # Nodes
    g.add_node("auth_service", type="service", status="healthy", name="Auth Service")
    g.add_node("user_service", type="service", status="healthy", name="User Service")
    g.add_node("payment_service", type="service", status="healthy", name="Payment Service")
    g.add_node("notification_service", type="service", status="healthy", name="Notification Service")
    g.add_node("isolated_service", type="service", status="healthy", name="Isolated Service")
    g.add_node("analytics_db", type="database", status="healthy", name="Analytics DB")

    # Edges with evidence and types
    g.add_edge("auth_service", "user_service", type="api_call", confidence=1.0, evidence="REST API /verify")
    g.add_edge("user_service", "payment_service", type="service_dependency", confidence=0.9, evidence="gRPC client")
    g.add_edge("payment_service", "notification_service", type="service_dependency", confidence=0.8, evidence="Event queue")
    g.add_edge("analytics_db", "notification_service", type="database_query", confidence=0.7, evidence="SQL query")

    return g


# ============================================================
# Tests: Event Types Propagation
# ============================================================

def test_simulation_pr_delay_seeded_chain(seeded_data):
    """PR delay on pr_11 propagates through full causal chain to 12 affected nodes."""
    req = SimulationRequest(node_id="pr_11", event_type=EVENT_PR_DELAY, delay_days=3)
    result = simulate(seeded_data, req)

    assert isinstance(result, SimulationResult)
    assert "pull_request:pr_11" in result.affected_nodes or "pr_11" in result.affected_nodes
    assert len(result.affected_nodes) == 12
    assert len(result.unaffected_nodes) > 0
    assert len(result.unknown_nodes) == 0
    assert result.truncated is False
    assert len(result.propagation_paths) > 0
    assert len(result.evidence) > 0
    assert "risk_score" in result.after


def test_simulation_task_delay(seeded_data):
    """Task/milestone delay propagates along milestone and dependent deadline edges."""
    req = SimulationRequest(node_id="ms_02", event_type=EVENT_TASK_DELAY, delay_days=5)
    result = simulate(seeded_data, req)

    assert isinstance(result, SimulationResult)
    assert len(result.affected_nodes) >= 1
    target = _find_node(build_graph(seeded_data), "ms_02")
    assert target in result.affected_nodes
    assert target in result.after
    assert result.after[target]["status"] == "delayed"


def test_simulation_service_failure(custom_graph):
    """SERVICE_FAILURE cascades through api_call and service_dependency edges."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_SERVICE_FAILURE)
    res = engine.propagate(custom_graph, req)

    assert res["affected_nodes"] == ["auth_service", "user_service", "payment_service", "notification_service"]
    assert "isolated_service" in res["unaffected_nodes"]
    assert "analytics_db" in res["unaffected_nodes"]
    assert res["after"]["auth_service"]["status"] == "failed"
    assert res["after"]["user_service"]["status"] == "degraded"
    assert res["after"]["payment_service"]["status"] == "degraded"


def test_simulation_timeout_propagation(custom_graph):
    """TIMEOUT failure event propagates through valid network dependency edges."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="user_service", event_type=EVENT_TIMEOUT)
    res = engine.propagate(custom_graph, req)

    assert res["affected_nodes"] == ["user_service", "payment_service", "notification_service"]
    assert "auth_service" in res["unaffected_nodes"]
    assert res["after"]["user_service"]["status"] == "delayed"


def test_simulation_latency_propagation(custom_graph):
    """LATENCY event impacts downstream callers with delay state."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_LATENCY, latency_ms=800)
    res = engine.propagate(custom_graph, req)

    assert "auth_service" in res["affected_nodes"]
    assert "user_service" in res["affected_nodes"]
    assert res["after"]["auth_service"]["status"] == "delayed"
    assert "800ms latency" in res["scenario"]


def test_simulation_http_500_propagation(custom_graph):
    """HTTP 500 causes downstream dependent services to degrade."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="user_service", event_type=EVENT_HTTP_500)
    res = engine.propagate(custom_graph, req)

    assert "payment_service" in res["affected_nodes"]
    assert res["after"]["user_service"]["status"] == "failed"
    assert res["after"]["payment_service"]["status"] == "degraded"


def test_simulation_http_503_propagation(custom_graph):
    """HTTP 503 unavailability cascades to consumers."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="payment_service", event_type=EVENT_HTTP_503)
    res = engine.propagate(custom_graph, req)

    assert res["affected_nodes"] == ["payment_service", "notification_service"]
    assert "auth_service" in res["unaffected_nodes"]


def test_simulation_malformed_response(custom_graph):
    """MALFORMED_RESPONSE marks affected downstream services with data contract violations."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_MALFORMED_RESPONSE)
    res = engine.propagate(custom_graph, req)

    assert "user_service" in res["affected_nodes"]
    assert res["after"]["user_service"]["status"] == "error"
    assert res["after"]["user_service"]["error_type"] == "data_contract_violation"


def test_simulation_deployment_failure():
    """DEPLOYMENT_FAILURE halts dependent components."""
    g = nx.DiGraph()
    g.add_node("deploy_staging", type="deployment", status="healthy")
    g.add_node("deploy_prod", type="deployment", status="healthy")
    g.add_node("qa_signoff", type="milestone", status="healthy")
    g.add_edge("deploy_staging", "deploy_prod", type="depends_on")
    g.add_edge("deploy_prod", "qa_signoff", type="blocks")

    engine = PropagationEngine()
    req = SimulationRequest(target_node="deploy_staging", event_type=EVENT_DEPLOYMENT_FAILURE)
    res = engine.propagate(g, req)

    assert res["affected_nodes"] == ["deploy_staging", "deploy_prod", "qa_signoff"]
    assert res["after"]["deploy_staging"]["status"] == "failed"
    assert res["after"]["deploy_prod"]["status"] == "degraded"


def test_simulation_component_unavailable():
    """COMPONENT_UNAVAILABLE propagates through component and service dependencies."""
    g = nx.DiGraph()
    g.add_node("redis_cache", type="component", status="healthy")
    g.add_node("session_service", type="service", status="healthy")
    g.add_node("web_app", type="service", status="healthy")
    g.add_edge("redis_cache", "session_service", type="component_dependency")
    g.add_edge("session_service", "web_app", type="service_dependency")

    engine = PropagationEngine()
    req = SimulationRequest(target_node="redis_cache", event_type=EVENT_COMPONENT_UNAVAILABLE)
    res = engine.propagate(g, req)

    assert res["affected_nodes"] == ["redis_cache", "session_service", "web_app"]
    assert res["after"]["redis_cache"]["status"] == "failed"


# ============================================================
# Tests: Strict Evidence & Boundary Rules
# ============================================================

def test_no_evidence_no_propagation(custom_graph):
    """An isolated node with no outgoing edges does not propagate to any other node."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="isolated_service", event_type=EVENT_SERVICE_FAILURE)
    res = engine.propagate(custom_graph, req)

    assert res["affected_nodes"] == ["isolated_service"]
    assert len(res["unaffected_nodes"]) == len(custom_graph.nodes) - 1
    assert "isolated_service" not in res["unaffected_nodes"]
    assert len(res["propagation_paths"]) == 0
    assert len(res["evidence"]) == 0


def test_unaffected_nodes_partitioning(custom_graph):
    """Verify that affected_nodes and unaffected_nodes form an exact partition of all graph nodes."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="payment_service", event_type=EVENT_SERVICE_FAILURE)
    res = engine.propagate(custom_graph, req)

    all_nodes = set(custom_graph.nodes)
    affected_set = set(res["affected_nodes"])
    unaffected_set = set(res["unaffected_nodes"])

    # Disjoint union equals all nodes
    assert affected_set.isdisjoint(unaffected_set)
    assert (affected_set | unaffected_set) == all_nodes


def test_unknown_target_node(custom_graph):
    """Requesting simulation for a non-existent node records it in unknown_nodes."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="non_existent_node_xyz", event_type=EVENT_SERVICE_FAILURE)
    res = engine.propagate(custom_graph, req)

    assert res["affected_nodes"] == []
    assert res["unknown_nodes"] == ["non_existent_node_xyz"]
    assert len(res["unaffected_nodes"]) == len(custom_graph.nodes)
    assert len(res["warnings"]) > 0
    assert "not found" in res["warnings"][0].lower()


def test_before_after_state_accuracy(custom_graph):
    """Before states accurately capture pre-simulation state; after states record changes."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_SERVICE_FAILURE)
    res = engine.propagate(custom_graph, req)

    assert res["before"]["auth_service"]["status"] == "healthy"
    assert res["before"]["user_service"]["status"] == "healthy"
    assert res["after"]["auth_service"]["status"] == "failed"
    assert res["after"]["user_service"]["status"] == "degraded"
    assert res["after"]["isolated_service"]["status"] == "healthy"


# ============================================================
# Tests: Cycle Safety & Depth Bounding
# ============================================================

def test_cycle_safety():
    """Graph with circular dependencies terminates safely without infinite loops or duplicates."""
    g = nx.DiGraph()
    g.add_node("svc_a", type="service", status="healthy")
    g.add_node("svc_b", type="service", status="healthy")
    g.add_node("svc_c", type="service", status="healthy")
    g.add_edge("svc_a", "svc_b", type="service_dependency")
    g.add_edge("svc_b", "svc_c", type="service_dependency")
    g.add_edge("svc_c", "svc_a", type="service_dependency")  # Cycle back to A

    engine = PropagationEngine()
    req = SimulationRequest(target_node="svc_a", event_type=EVENT_SERVICE_FAILURE)
    res = engine.propagate(g, req)

    assert len(res["affected_nodes"]) == 3
    assert set(res["affected_nodes"]) == {"svc_a", "svc_b", "svc_c"}
    assert res["truncated"] is False


def test_max_depth_truncation():
    """Long chain is truncated when max_depth limit is reached."""
    g = nx.DiGraph()
    nodes = [f"node_{i}" for i in range(10)]
    for n in nodes:
        g.add_node(n, type="service", status="healthy")
    for i in range(len(nodes) - 1):
        g.add_edge(nodes[i], nodes[i+1], type="service_dependency")

    engine = PropagationEngine()
    req = SimulationRequest(target_node="node_0", event_type=EVENT_SERVICE_FAILURE, max_depth=3)
    res = engine.propagate(g, req)

    # Reaches depth 0, 1, 2, 3 -> node_0, node_1, node_2, node_3
    assert len(res["affected_nodes"]) == 4
    assert res["truncated"] is True
    assert any("truncated" in w.lower() for w in res["warnings"])
    assert "node_4" in res["unaffected_nodes"]


def test_max_depth_untruncated(custom_graph):
    """Graph whose diameter is smaller than max_depth does not trigger truncation flag."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_SERVICE_FAILURE, max_depth=10)
    res = engine.propagate(custom_graph, req)

    assert res["truncated"] is False
    assert len(res["warnings"]) == 0


# ============================================================
# Tests: Immutability & Determinism
# ============================================================

def test_graph_immutability(custom_graph):
    """Engine must not mutate input NetworkX graph nodes or edge attributes."""
    nodes_before = copy.deepcopy(dict(custom_graph.nodes(data=True)))
    edges_before = copy.deepcopy(list(custom_graph.edges(data=True)))

    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_SERVICE_FAILURE)
    engine.propagate(custom_graph, req)

    nodes_after = dict(custom_graph.nodes(data=True))
    edges_after = list(custom_graph.edges(data=True))

    assert nodes_before == nodes_after
    assert edges_before == edges_after


def test_project_data_immutability(seeded_data):
    """Simulate must not mutate the original project dictionary."""
    data_copy = copy.deepcopy(seeded_data)
    req = SimulationRequest(node_id="pr_11", event_type=EVENT_PR_DELAY, delay_days=7)
    simulate(seeded_data, req)

    assert seeded_data == data_copy


def test_request_scoped_isolation(seeded_data):
    """Consecutive simulations with varying inputs must execute in complete isolation."""
    req1 = SimulationRequest(node_id="pr_11", delay_days=3)
    req2 = SimulationRequest(node_id="pr_11", delay_days=14)

    res1 = simulate(seeded_data, req1)
    res2 = simulate(seeded_data, req2)

    assert "3-day delay" in res1.scenario
    assert "14-day delay" in res2.scenario


def test_deterministic_propagation(custom_graph):
    """Identical simulation runs produce identical results byte-for-byte."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_SERVICE_FAILURE)

    res1 = engine.propagate(custom_graph, req)
    res2 = engine.propagate(custom_graph, req)

    assert res1 == res2


# ============================================================
# Tests: Paths, Evidence & Edge Compatibility
# ============================================================

def test_propagation_paths_structure(custom_graph):
    """Propagation paths contain valid ordered step lists from root to leaf."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_SERVICE_FAILURE)
    res = engine.propagate(custom_graph, req)

    paths = res["propagation_paths"]
    assert len(paths) >= 3
    assert ["auth_service", "user_service"] in paths
    assert ["auth_service", "user_service", "payment_service"] in paths


def test_evidence_records_collected(custom_graph):
    """Traversed edges generate evidence dictionaries with edge types and confidence."""
    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_SERVICE_FAILURE)
    res = engine.propagate(custom_graph, req)

    ev_list = res["evidence"]
    assert len(ev_list) >= 3
    sources = [e["source"] for e in ev_list]
    assert "auth_service" in sources
    assert all("edge_type" in e and "confidence" in e for e in ev_list)


def test_edge_incompatibility_blocks_propagation():
    """Edges incompatible with the event type block failure traversal."""
    g = nx.DiGraph()
    g.add_node("auth_service", type="service", status="healthy")
    g.add_node("developer_bob", type="developer", status="healthy")
    # Developer review edge should NOT propagate a SERVICE_FAILURE
    g.add_edge("auth_service", "developer_bob", type="reviewed_by")

    engine = PropagationEngine()
    req = SimulationRequest(target_node="auth_service", event_type=EVENT_SERVICE_FAILURE)
    res = engine.propagate(g, req)

    assert res["affected_nodes"] == ["auth_service"]
    assert "developer_bob" in res["unaffected_nodes"]


def test_custom_delay_hours_and_latency_ms():
    """Scenario strings properly format hours or milliseconds when specified."""
    req_hours = SimulationRequest(target_node="task_1", event_type=EVENT_TASK_DELAY, delay_hours=12, delay_days=None)
    req_ms = SimulationRequest(target_node="api_1", event_type=EVENT_LATENCY, latency_ms=450, delay_days=None)

    g = nx.DiGraph()
    g.add_node("task_1", type="task", status="healthy")
    g.add_node("api_1", type="service", status="healthy")

    engine = PropagationEngine()
    res_hours = engine.propagate(g, req_hours)
    res_ms = engine.propagate(g, req_ms)

    assert "12-hour delay" in res_hours["scenario"]
    assert "450ms latency" in res_ms["scenario"]


# ============================================================
# Tests: HTTP API Integration
# ============================================================

def test_api_simulation_endpoint_service_failure():
    """POST /api/simulate with SERVICE_FAILURE payload returns 200 with complete results."""
    payload = {
        "target_node": "pr_11",
        "event_type": "SERVICE_FAILURE",
        "severity": "CRITICAL"
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "affected_nodes" in data
    assert "unaffected_nodes" in data
    assert "unknown_nodes" in data
    assert "before" in data
    assert "after" in data
    assert "propagation_paths" in data
    assert "evidence" in data
    assert "truncated" in data
    assert "warnings" in data


def test_api_simulation_endpoint_timeout():
    """POST /api/simulate with TIMEOUT payload returns 200."""
    payload = {
        "node_id": "pr_11",
        "event_type": "TIMEOUT",
        "latency_ms": 5000
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "affected_nodes" in data


def test_api_simulation_endpoint_http_500():
    """POST /api/simulate with HTTP_500 payload returns 200."""
    payload = {
        "node_id": "pr_11",
        "event_type": "HTTP_500",
        "http_status": 500
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "affected_nodes" in data


def test_api_simulation_endpoint_unknown_node():
    """POST /api/simulate with unknown node records it in unknown_nodes."""
    payload = {
        "target_node": "nonexistent_service_12345",
        "event_type": "SERVICE_FAILURE"
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "nonexistent_service_12345" in data["unknown_nodes"]
    assert len(data["affected_nodes"]) == 0


def test_api_simulation_endpoint_max_depth():
    """POST /api/simulate respects max_depth parameter over HTTP."""
    payload = {
        "node_id": "pr_11",
        "event_type": "PR_DELAY",
        "max_depth": 1
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["truncated"] is True
    assert len(data["affected_nodes"]) < 12


def test_api_simulation_route_consistency():
    """Both /api/simulate and /api/simulate/{owner}/{repo} yield consistent results."""
    payload = {
        "node_id": "pr_11",
        "event_type": "PR_DELAY",
        "delay_days": 3
    }
    res1 = client.post("/api/simulate", json=payload).json()
    res2 = client.post("/api/simulate/Aritra-DSU/RF-SENTINEL", json=payload).json()

    assert res1["affected_nodes"] == res2["affected_nodes"]
    assert res1["recommendation"] == res2["recommendation"]


# ============================================================
# Tests: Benchmark & Pipeline Integration
# ============================================================

def test_benchmark_isolation():
    """Strict verification: expected_results.json is never imported in simulation modules."""
    import sys
    import app.simulation.what_if as w
    import app.simulation.propagation_engine as pe
    import app.simulation.propagation_policy as pp

    for mod in (w, pe, pp):
        mod_src = open(mod.__file__, "r", encoding="utf-8").read()
        assert "expected_results.json" not in mod_src
        assert "expected_results" not in mod_src


def test_agent4_impact_simulation_compatibility(seeded_data):
    """ImpactSimulationAgent integrates seamlessly with hardened Phase 8 engine."""
    from app.agents.investigation_pipeline import InvestigationContext
    agent = ImpactSimulationAgent()
    context = InvestigationContext(data=seeded_data, raw_risks=[], verified_risks=[])
    agent.run(context)

    assert len(context.simulation_results) > 0
    sim_res = context.simulation_results[0]
    assert "pull_request:pr_11" in sim_res.affected_nodes or "pr_11" in sim_res.affected_nodes
    assert len(sim_res.affected_nodes) == 12
    assert len(sim_res.causal_chain) == 12


def test_backward_compat_delay_days_default():
    """SimulationRequest defaults node_id to pr_11 and delay_days to 3."""
    req = SimulationRequest()
    assert req.node_id == "pr_11"
    assert req.delay_days == 3
    assert req.event_type == "PR_DELAY"
    assert req.effective_target_node == "pr_11"
