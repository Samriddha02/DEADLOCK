from app.models.graph_models import (
    ProjectGraph,
    GraphNode,
    GraphEdge,
)

import networkx as nx


def serialize_graph(graph: nx.DiGraph) -> ProjectGraph:
    """
    Convert the NetworkX graph into JSON-friendly
    Pydantic data for the frontend.
    """

    nodes = []

    for node_id, data in graph.nodes(data=True):
        nodes.append(
            GraphNode(
                id=node_id,
                type=data.get("type", "unknown"),
                label=data.get("label", node_id),
                data={
                    key: value
                    for key, value in data.items()
                    if key not in {"type", "label"}
                },
            )
        )

    edges = []

    for source, target, data in graph.edges(data=True):
        edges.append(
            GraphEdge(
                source=source,
                target=target,
                relation=data.get(
                    "relation",
                    "depends_on",
                ),
                data={
                    key: value
                    for key, value in data.items()
                    if key != "relation"
                },
            )
        )

    return ProjectGraph(
        nodes=nodes,
        edges=edges,
    )