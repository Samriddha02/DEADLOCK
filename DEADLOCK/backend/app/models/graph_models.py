from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    type: str
    label: str

    data: dict[str, Any] = Field(
        default_factory=dict
    )


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str

    data: dict[str, Any] = Field(
        default_factory=dict
    )


class ProjectGraph(BaseModel):
    nodes: list[GraphNode] = Field(
        default_factory=list
    )

    edges: list[GraphEdge] = Field(
        default_factory=list
    )