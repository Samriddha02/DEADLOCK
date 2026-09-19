from __future__ import annotations

"""
Phase 3 Graph Engine Tests — 23 Test Cases.
"""

import pytest
import networkx as nx
from fastapi.testclient import TestClient

from app.api.routes_risks import load_seeded_dataset
from app.graph.graph_builder import (
    build_graph,
    _find_node,
    validate_causal_path,
)
from app.graph.graph_analyzer import (
    downstream_nodes,
    upstream_nodes,
    find_shortest_causal_path,
    graph_metrics,
    bottleneck_scores,
)
from app.main import app


# ─── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def seeded_data():
    return load_seeded_dataset()


@pytest.fixture
def seeded_graph(seeded_data):
    return build_graph(seeded_data)


# ═══════════════════════════════════════════════════════════════════════════
# 1. All required node types present in seeded graph
# ═══════════════════════════════════════════════════════════════════════════

def test_all_required_node_types(seeded_graph):
    node_types = {
        data.get("type")
        for _, data in seeded_graph.nodes(data=True)
    }
    required_types = {
        "project",
        "developer",
        "milestone",
        "deadline",
        "issue",
        "pull_request",
        "commit",
        "review",
        "dependency",
        "deployment",
    }
    missing = required_types - node_types
    assert not missing, f"Missing required node types: {missing}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Stable node IDs format (type:id)
# ═══════════════════════════════════════════════════════════════════════════

def test_stable_node_ids(seeded_graph):
    for node_id in seeded_graph.nodes:
        assert ":" in node_id, f"Node ID '{node_id}' does not use typed format 'type:id'"
        prefix, raw_id = node_id.split(":", 1)
        assert len(prefix) > 0 and len(raw_id) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 3. Required seeded chain exists
# ═══════════════════════════════════════════════════════════════════════════

def test_required_seeded_chain(seeded_graph):
    chain = ["pr_11", "issue_11", "issue_14", "dep_01", "dl_03"]
    resolved = [_find_node(seeded_graph, item) for item in chain]

    for item, res in zip(chain, resolved):
        assert res is not None and seeded_graph.has_node(res), f"Node '{item}' not found in graph"

    for u, v in zip(resolved[:-1], resolved[1:]):
        assert seeded_graph.has_edge(u, v), f"Missing edge between {u} and {v}"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Required edge relations present on edges
# ═══════════════════════════════════════════════════════════════════════════

def test_required_edge_relations(seeded_graph):
    for u, v, data in seeded_graph.edges(data=True):
        assert "relation" in data and data["relation"], f"Edge ({u}, {v}) missing relation"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Developer relationships (authored_by / assigned_to)
# ═══════════════════════════════════════════════════════════════════════════

def test_developer_relationships(seeded_graph):
    dev_relations = {
        data.get("relation")
        for _, _, data in seeded_graph.edges(data=True)
        if data.get("relation") in {"authored_by", "assigned_to", "created_by"}
    }
    assert len(dev_relations) > 0, "Developer relationships missing"


# ═══════════════════════════════════════════════════════════════════════════
# 6. PR/issue relationships (resolves_issue)
# ═══════════════════════════════════════════════════════════════════════════

def test_pr_issue_relationships(seeded_graph):
    pr_node = _find_node(seeded_graph, "pr_11")
    issue_node = _find_node(seeded_graph, "issue_11")
    assert seeded_graph.has_edge(pr_node, issue_node)
    edge_data = seeded_graph.edges[pr_node, issue_node]
    assert edge_data.get("relation") in {"resolves_issue", "implements", "references_issue", "depends_on"}


# ═══════════════════════════════════════════════════════════════════════════
# 7. Commit/PR relationships
# ═══════════════════════════════════════════════════════════════════════════

def test_commit_pr_relationships(seeded_graph):
    commit_edges = [
        (u, v, data)
        for u, v, data in seeded_graph.edges(data=True)
        if u.startswith("commit:") and v.startswith("pull_request:")
    ]
    assert len(commit_edges) > 0, "Commit to PR relationships missing"


# ═══════════════════════════════════════════════════════════════════════════
# 8. Review/PR relationships
# ═══════════════════════════════════════════════════════════════════════════

def test_review_pr_relationships(seeded_graph):
    review_edges = [
        (u, v, data)
        for u, v, data in seeded_graph.edges(data=True)
        if u.startswith("review:") and v.startswith("pull_request:")
    ]
    assert len(review_edges) > 0, "Review to PR relationships missing"


# ═══════════════════════════════════════════════════════════════════════════
# 9. Dependency relationships
# ═══════════════════════════════════════════════════════════════════════════

def test_dependency_relationships(seeded_graph):
    dep_edges = [
        (u, v, data)
        for u, v, data in seeded_graph.edges(data=True)
        if data.get("relation") in {"depends_on", "blocks", "implements"}
    ]
    assert len(dep_edges) > 0, "Explicit dependency relationships missing"


# ═══════════════════════════════════════════════════════════════════════════
# 10. Deployment relationships
# ═══════════════════════════════════════════════════════════════════════════

def test_deployment_relationships(seeded_graph):
    dep_node = _find_node(seeded_graph, "dep_01")
    assert dep_node is not None
    neighbors = list(seeded_graph.predecessors(dep_node)) + list(seeded_graph.successors(dep_node))
    assert len(neighbors) > 0, "Deployment dep_01 has no connected relationships"


# ═══════════════════════════════════════════════════════════════════════════
# 11. Deadline relationships
# ═══════════════════════════════════════════════════════════════════════════

def test_deadline_relationships(seeded_graph):
    dl_node = _find_node(seeded_graph, "dl_03")
    assert dl_node is not None
    in_edges = list(seeded_graph.predecessors(dl_node))
    assert len(in_edges) > 0, "Deadline dl_03 has no incoming relationships"


# ═══════════════════════════════════════════════════════════════════════════
# 12. Milestone relationships
# ═══════════════════════════════════════════════════════════════════════════

def test_milestone_relationships(seeded_graph):
    ms_edges = [
        (u, v, data)
        for u, v, data in seeded_graph.edges(data=True)
        if data.get("relation") in {"belongs_to_milestone", "has_deadline", "contains"}
        or v.startswith("milestone:")
    ]
    assert len(ms_edges) > 0, "Milestone relationships missing"


# ═══════════════════════════════════════════════════════════════════════════
# 13. Missing references do NOT create fake nodes
# ═══════════════════════════════════════════════════════════════════════════

def test_missing_references_no_fake_nodes():
    partial_project = {
        "project": {"id": "p1", "name": "Partial"},
        "issues": [
            {"id": "iss_1", "title": "Issue 1", "milestone_id": "nonexistent_ms"}
        ]
    }
    g = build_graph(partial_project)
    assert g.has_node("issue:iss_1")
    assert not g.has_node("milestone:nonexistent_ms")
    assert not any("nonexistent" in n for n in g.nodes)


# ═══════════════════════════════════════════════════════════════════════════
# 14. Duplicate relationships handling
# ═══════════════════════════════════════════════════════════════════════════

def test_duplicate_relationships_handling():
    project_data = {
        "project": {"id": "p1", "name": "Test"},
        "issues": [{"id": "iss_1", "title": "1"}, {"id": "iss_2", "title": "2"}],
        "dependencies": [
            {"source_id": "iss_1", "target_id": "iss_2", "type": "blocks"},
            {"source_id": "iss_1", "target_id": "iss_2", "type": "blocks"},
        ]
    }
    g = build_graph(project_data)
    # NetworkX DiGraph automatically deduplicates directed edges between same nodes
    assert g.has_edge("issue:iss_1", "issue:iss_2")
    assert g.number_of_edges() >= 1


# ═══════════════════════════════════════════════════════════════════════════
# 15. Duplicate entities handling
# ═══════════════════════════════════════════════════════════════════════════

def test_duplicate_entities_handling():
    project_data = {
        "project": {"id": "p1", "name": "Test"},
        "issues": [
            {"id": "iss_1", "title": "First Version"},
            {"id": "iss_1", "title": "Updated Version"},
        ]
    }
    g = build_graph(project_data)

    issue_nodes = [n for n in g.nodes if n == "issue:iss_1"]
    assert len(issue_nodes) == 1
    assert g.nodes["issue:iss_1"]["label"] == "Updated Version"


# ═══════════════════════════════════════════════════════════════════════════
# 16. Empty project input
# ═══════════════════════════════════════════════════════════════════════════

def test_empty_project():
    g = build_graph({})
    assert isinstance(g, nx.DiGraph)
    assert g.number_of_nodes() == 0
    assert g.number_of_edges() == 0


# ═══════════════════════════════════════════════════════════════════════════
# 17. Partial project input
# ═══════════════════════════════════════════════════════════════════════════

def test_partial_project():
    data = {
        "developers": [{"id": "dev_01", "name": "Alice"}],
        "issues": [{"id": "iss_01", "title": "Bug", "assignee_id": "dev_01"}]
    }
    g = build_graph(data)
    assert g.has_node("developer:dev_01")
    assert g.has_node("issue:iss_01")
    assert g.has_edge("issue:iss_01", "developer:dev_01")


# ═══════════════════════════════════════════════════════════════════════════
# 18. Cyclic graph traversal terminates cleanly
# ═══════════════════════════════════════════════════════════════════════════

def test_cyclic_graph_traversal():
    g = nx.DiGraph()
    g.add_node("issue:a", type="issue", label="A")
    g.add_node("issue:b", type="issue", label="B")
    g.add_node("issue:c", type="issue", label="C")
    g.add_edge("issue:a", "issue:b")
    g.add_edge("issue:b", "issue:c")
    g.add_edge("issue:c", "issue:a")  # Cycle A -> B -> C -> A

    ds = downstream_nodes(g, "issue:a")
    assert set(ds) == {"issue:b", "issue:c"}  # Terminated without infinite loop

    us = upstream_nodes(g, "issue:a")
    assert set(us) == {"issue:b", "issue:c"}  # Terminated without infinite loop

    metrics = bottleneck_scores(g)
    assert metrics["issue:a"] == 2.0


# ═══════════════════════════════════════════════════════════════════════════
# 19. Disconnected graph handling
# ═══════════════════════════════════════════════════════════════════════════

def test_disconnected_graph():
    g = nx.DiGraph()
    g.add_edge("issue:a", "issue:b")
    g.add_edge("issue:x", "issue:y")

    ds = downstream_nodes(g, "issue:a")
    assert ds == ["issue:b"]
    assert "issue:y" not in ds


# ═══════════════════════════════════════════════════════════════════════════
# 20. Deterministic graph output
# ═══════════════════════════════════════════════════════════════════════════

def test_deterministic_graph_output(seeded_data):
    g1 = build_graph(seeded_data)
    g2 = build_graph(seeded_data)

    assert list(g1.nodes) == list(g2.nodes)
    assert list(g1.edges) == list(g2.edges)


# ═══════════════════════════════════════════════════════════════════════════
# 21. Causal path validation
# ═══════════════════════════════════════════════════════════════════════════

def test_causal_path_validation(seeded_graph):
    valid_path = ["pr_11", "issue_11", "issue_14", "dep_01", "dl_03"]
    assert validate_causal_path(seeded_graph, valid_path) is True

    fake_path = ["pr_11", "issue_14", "dl_03"]
    assert validate_causal_path(seeded_graph, fake_path) is False

    invalid_node_path = ["pr_11", "nonexistent_node"]
    assert validate_causal_path(seeded_graph, invalid_node_path) is False


# ═══════════════════════════════════════════════════════════════════════════
# 22. Bounded traversal (max_depth)
# ═══════════════════════════════════════════════════════════════════════════

def test_bounded_traversal(seeded_graph):
    pr11 = _find_node(seeded_graph, "pr_11")
    ds_depth1 = downstream_nodes(seeded_graph, pr11, max_depth=1)
    ds_all = downstream_nodes(seeded_graph, pr11, max_depth=None)

    assert len(ds_depth1) <= len(ds_all)
    assert "issue:issue_11" in ds_depth1
    # dl_03 is 4 hops away, so it shouldn't be in depth 1
    dl03 = _find_node(seeded_graph, "dl_03")
    assert dl03 not in ds_depth1


# ═══════════════════════════════════════════════════════════════════════════
# 23. API graph serialization
# ═══════════════════════════════════════════════════════════════════════════

def test_api_graph_serialization():
    client = TestClient(app)
    resp = client.get("/api/graph/Aritra-DSU/RF-SENTINEL")
    assert resp.status_code == 200

    data = resp.json()
    assert data["project"] == "Aritra-DSU/RF-SENTINEL"
    assert "total_nodes" in data
    assert "total_edges" in data
    assert len(data["nodes"]) == data["total_nodes"]
    assert len(data["edges"]) == data["total_edges"]

    first_node = data["nodes"][0]
    assert "id" in first_node and "type" in first_node and "label" in first_node and "data" in first_node

    first_edge = data["edges"][0]
    assert "source" in first_edge and "target" in first_edge and "relation" in first_edge and "data" in first_edge
