from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.database.repositories import (
    ProjectCorruptError,
    ProjectNotFoundError,
    load_project,
)
from app.graph.graph_builder import build_graph


router = APIRouter(
    prefix="/api/graph",
    tags=["graph"],
)


@router.get("/{owner}/{repo}")
def get_graph(
    owner: str,
    repo: str,
):
    """
    Return the complete DEADLOCK project graph.

    Supports demo project fallback and synced SQLite projects.
    """

    if not owner.strip() or not repo.strip():
        raise HTTPException(
            status_code=400,
            detail="Owner and repo are required.",
        )

    owner = owner.strip()
    repo = repo.strip()

    dataset = None
    source = "SQLite database"

    # is_demo_repo only applies when the request comes from an explicit demo endpoint.
    # In the standard graph endpoint we always load from SQLite so live and demo repos
    # are treated identically — if the data isn't synced the caller gets a 404.
    try:
        dataset = load_project(owner, repo)
        source = "SQLite database"
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{owner}/{repo}' has not been synced yet.",
        )
    except ProjectCorruptError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Stored project data for '{owner}/{repo}' is corrupt: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load project: {exc}",
        ) from exc

    try:
        graph = build_graph(dataset)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build project graph: {exc}",
        ) from exc

    nodes = []

    for node_id, node_data in graph.nodes(data=True):
        nodes.append(
            {
                "id": node_id,
                "type": node_data.get(
                    "type",
                    "unknown",
                ),
                "label": node_data.get(
                    "label",
                    node_id,
                ),
                "data": node_data.get(
                    "data",
                    {},
                ),
            }
        )

    edges = []

    for src_node, tgt_node, edge_data in graph.edges(data=True):
        edges.append(
            {
                "source": src_node,
                "target": tgt_node,
                "relation": edge_data.get(
                    "relation",
                    "related_to",
                ),
                "data": edge_data.get(
                    "data",
                    {},
                ),
            }
        )

    return {
        "project": f"{owner}/{repo}",
        "source": source,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
