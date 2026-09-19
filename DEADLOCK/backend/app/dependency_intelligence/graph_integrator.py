from __future__ import annotations

import networkx as nx
from app.dependency_intelligence.models import ProjectIntelligenceMetadata


def integrate_dependency_intelligence(
    graph: nx.DiGraph,
    intelligence: ProjectIntelligenceMetadata,
) -> nx.DiGraph:
    for edge in intelligence.discovered_dependencies:
        src = edge.source_node
        tgt = edge.target_node

        if not graph.has_node(src):
            src_type = src.split(":", 1)[0]
            graph.add_node(src, type=src_type, label=src.split(":", 1)[-1], data={"id": src})

        if not graph.has_node(tgt):
            tgt_type = tgt.split(":", 1)[0]
            graph.add_node(tgt, type=tgt_type, label=tgt.split(":", 1)[-1], data={"id": tgt})

        graph.add_edge(
            src,
            tgt,
            relation=edge.relationship_type.lower(),
            data={
                "relationship_type": edge.relationship_type,
                "evidence": edge.evidence,
                "inferred": edge.inferred,
                "inference_rule": edge.inference_rule,
                "confidence": edge.confidence,
                "source_type": edge.source_type,
                "source_id": edge.source_id,
                "state": edge.state,
                "metadata": edge.metadata,
            }
        )

    return graph
