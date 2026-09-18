import copy

import networkx as nx

from app.models.github_models import ProjectData
from app.models.risk_models import (
    Risk,
    SimulationRequest,
    SimulationResult,
)

from app.graph.graph_builder import build_graph
from app.risk_engine.detector import detect_risks


def simulate(
    project: ProjectData,
    request: SimulationRequest,
) -> SimulationResult:
    """
    Simulate a delay to a project node and determine
    which downstream nodes and risks could be affected.
    """

    # Build the current dependency graph
    graph = build_graph(project)

    affected_nodes: list[str] = []

    # --------------------------------------------------
    # Find downstream impact
    # --------------------------------------------------

    if request.node_id in graph:

        affected_nodes = list(
            nx.descendants(
                graph,
                request.node_id
            )
        )

        # Include the selected node itself
        affected_nodes.insert(
            0,
            request.node_id
        )

    # --------------------------------------------------
    # Create a copy so the original project
    # is never modified.
    # --------------------------------------------------

    scenario_project = copy.deepcopy(project)

    # --------------------------------------------------
    # Apply simulated delay
    # --------------------------------------------------

    for milestone in scenario_project.milestones:

        if request.node_id == (
            f"milestone:{milestone.number}"
        ):

            # Force milestone into an overdue state
            milestone.due_on = (
                "2000-01-01T00:00:00Z"
            )

    # --------------------------------------------------
    # Re-run risk detection
    # --------------------------------------------------

    new_risks: list[Risk] = detect_risks(
        scenario_project
    )

    # --------------------------------------------------
    # Generate recommendation
    # --------------------------------------------------

    if affected_nodes:

        recommendation = (
            "Prioritize the selected dependency "
            "and inspect the affected downstream "
            "nodes before the simulated delay "
            "propagates."
        )

    else:

        recommendation = (
            "No downstream graph impact was "
            "identified for the selected node."
        )

    return SimulationResult(
        scenario=(
            f"Simulate {request.delay_days}-day delay "
            f"for {request.node_id}"
        ),

        affected_nodes=affected_nodes,

        new_risks=new_risks,

        recommendation=recommendation,
    )