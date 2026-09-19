from __future__ import annotations

from collections import deque

import networkx as nx

from app.graph.graph_builder import _find_node


# ============================================================
# DOWNSTREAM NODES
# ============================================================

def downstream_nodes(
    graph: nx.DiGraph,
    node_id: str,
    max_depth: int | None = None,
) -> list[str]:
    """
    Find all nodes affected downstream from a given node.

    Supports bare IDs (e.g., 'pr_11') and typed IDs ('pull_request:pr_11').
    Uses BFS with a visited set so cyclic graphs never cause infinite loops.
    Optional max_depth bounds the search depth.
    """

    if not graph or graph.number_of_nodes() == 0:
        return []

    resolved = _find_node(graph, node_id)
    if resolved is None or resolved not in graph:
        return []

    if max_depth is not None and max_depth <= 0:
        return []

    visited: set[str] = {resolved}
    queue: deque[tuple[str, int]] = deque([(resolved, 0)])
    result: list[str] = []

    while queue:
        curr, depth = queue.popleft()

        if max_depth is not None and depth >= max_depth:
            continue

        for nbr in graph.successors(curr):
            if nbr not in visited:
                visited.add(nbr)
                result.append(nbr)
                queue.append((nbr, depth + 1))

    return result


# ============================================================
# UPSTREAM NODES
# ============================================================

def upstream_nodes(
    graph: nx.DiGraph,
    node_id: str,
    max_depth: int | None = None,
) -> list[str]:
    """
    Find all nodes upstream (predecessors) from a given node.

    Supports bare IDs and typed IDs. Cycle-safe BFS traversal.
    """

    if not graph or graph.number_of_nodes() == 0:
        return []

    resolved = _find_node(graph, node_id)
    if resolved is None or resolved not in graph:
        return []

    if max_depth is not None and max_depth <= 0:
        return []

    visited: set[str] = {resolved}
    queue: deque[tuple[str, int]] = deque([(resolved, 0)])
    result: list[str] = []

    while queue:
        curr, depth = queue.popleft()

        if max_depth is not None and depth >= max_depth:
            continue

        for nbr in graph.predecessors(curr):
            if nbr not in visited:
                visited.add(nbr)
                result.append(nbr)
                queue.append((nbr, depth + 1))

    return result


# ============================================================
# SHORTEST CAUSAL PATH
# ============================================================

def find_shortest_causal_path(
    graph: nx.DiGraph,
    source_id: str,
    target_id: str,
) -> list[str] | None:
    """
    Find the shortest directed path from source_id to target_id.
    Returns None if no path exists or either node is not in graph.
    """

    if not graph or graph.number_of_nodes() == 0:
        return None

    src = _find_node(graph, source_id)
    tgt = _find_node(graph, target_id)

    if src is None or tgt is None or src not in graph or tgt not in graph:
        return None

    try:
        return list(nx.shortest_path(graph, src, tgt))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


# ============================================================
# GRAPH METRICS
# ============================================================

def graph_metrics(
    graph: nx.DiGraph,
) -> dict:
    """
    Calculate basic graph statistics safely.
    """

    if not graph or graph.number_of_nodes() == 0:
        return {
            "nodes": 0,
            "edges": 0,
            "density": 0.0,
        }

    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()

    density = nx.density(graph) if node_count > 1 else 0.0

    return {
        "nodes": node_count,
        "edges": edge_count,
        "density": round(float(density), 4),
    }


# ============================================================
# BOTTLENECK SCORES
# ============================================================

def bottleneck_scores(
    graph: nx.DiGraph,
) -> dict[str, float]:
    """
    Calculate a bottleneck score for each node based on its downstream reach.
    A node with many downstream dependencies has higher potential impact.
    """

    if not graph or graph.number_of_nodes() == 0:
        return {}

    scores: dict[str, float] = {}

    for node in graph.nodes:
        # Use downstream_nodes to remain cycle-safe and handles any graph structure
        reachable = len(downstream_nodes(graph, node))
        scores[node] = float(reachable)

    return scores