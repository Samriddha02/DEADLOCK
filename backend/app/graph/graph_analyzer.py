import networkx as nx


def downstream_nodes(
    graph: nx.DiGraph,
    node_id: str
) -> list[str]:
    """
    Find all nodes affected downstream from a given node.
    """

    if node_id not in graph:
        return []

    return list(
        nx.descendants(
            graph,
            node_id
        )
    )


def graph_metrics(
    graph: nx.DiGraph
) -> dict:
    """
    Calculate basic graph statistics.
    """

    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()

    density = (
        nx.density(graph)
        if node_count > 1
        else 0
    )

    return {
        "nodes": node_count,
        "edges": edge_count,
        "density": round(density, 4),
    }


def bottleneck_scores(
    graph: nx.DiGraph
) -> dict[str, float]:
    """
    Calculate a simple bottleneck score.

    A node with many downstream dependencies
    has a higher potential impact.
    """

    scores = {}

    for node in graph.nodes:

        downstream_count = len(
            nx.descendants(
                graph,
                node
            )
        )

        scores[node] = float(
            downstream_count
        )

    return scores