from __future__ import annotations

import copy
from typing import Any

import networkx as nx

from app.models.risk_models import (
    Risk,
    SimulationRequest,
    SimulationResult,
)

from app.graph.graph_builder import (
    build_graph,
    _find_node,
)

from app.risk_engine.detector import (
    detect_risks,
)

from app.agents.verifier_agent import (
    VerifierAgent,
)


# ============================================================
# Verifier
# ============================================================

verifier = VerifierAgent()


# ============================================================
# Helpers
# ============================================================

def _to_dataset(
    project: Any,
) -> dict[str, Any]:

    if hasattr(
        project,
        "model_dump",
    ):
        return project.model_dump()

    if isinstance(
        project,
        dict,
    ):
        return project

    raise TypeError(
        "project must be a dictionary or Pydantic model"
    )


def _apply_delay(
    project: dict[str, Any],
    request: SimulationRequest,
) -> None:

    node_id = str(
        request.node_id
    )

    if ":" in node_id:
        node_type, raw_id = node_id.split(":", 1)
    else:
        node_type = ""
        raw_id = node_id

    node_type = node_type.lower()
    raw_id = str(raw_id)

    # ========================================================
    # Milestone delay
    # ========================================================

    if node_type in {"", "milestone"}:
        for milestone in project.get("milestones", []):
            if not isinstance(milestone, dict):
                continue
            m_id = str(milestone.get("id", ""))
            m_num = str(milestone.get("number", ""))
            if raw_id in {m_id, m_num} or (not node_type and raw_id == m_id):
                milestone["due_on"] = "2000-01-01T00:00:00Z"
                milestone["simulated_delay_days"] = request.delay_days
                milestone["simulated_overdue"] = True

    # ========================================================
    # Deadline delay
    # ========================================================

    if node_type in {"", "deadline"}:
        for deadline in project.get("deadlines", []):
            if not isinstance(deadline, dict):
                continue
            d_id = str(deadline.get("id", ""))
            if d_id == raw_id or (not node_type and raw_id == d_id):
                deadline["simulated_delay_days"] = request.delay_days
                deadline["simulated_overdue"] = True
                for field in ("due_date", "due_at", "due_on"):
                    if field in deadline:
                        deadline[field] = "2000-01-01T00:00:00Z"
                if "due_date" not in deadline and "due_at" not in deadline and "due_on" not in deadline:
                    deadline["due_date"] = "2000-01-01T00:00:00Z"

    # ========================================================
    # PR / Issue delay
    # ========================================================

    if node_type in {"", "pull_request", "issue", "pr"}:
        for coll in ("pull_requests", "issues"):
            for item in project.get(coll, []):
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id", item.get("number", "")))
                if item_id == raw_id or (not node_type and item_id == raw_id):
                    item["simulated_delay_days"] = request.delay_days
                    item["simulated_overdue"] = True


# ============================================================
# Simulation
# ============================================================

def simulate(
    project: Any,
    request: SimulationRequest,
) -> SimulationResult:

    # ========================================================
    # Convert to unified dataset
    # ========================================================

    project_data = _to_dataset(
        project
    )

    # ========================================================
    # Build graph from same project representation
    # ========================================================

    graph = build_graph(
        project_data
    )

    # ========================================================
    # Determine affected nodes
    # ========================================================

    target_node = _find_node(graph, request.node_id) or request.node_id
    affected_nodes = []

    if graph.has_node(target_node):
        affected_nodes = list(
            nx.descendants(
                graph,
                target_node,
            )
        )
        affected_nodes.insert(
            0,
            target_node,
        )

    # ========================================================
    # Create isolated simulation copy
    # ========================================================

    scenario_project = copy.deepcopy(
        project_data
    )

    # ========================================================
    # Apply hypothetical delay
    # ========================================================

    _apply_delay(
        scenario_project,
        request,
    )

    # ========================================================
    # Detect risks using same detector
    # ========================================================

    detected_risks = detect_risks(
        scenario_project
    )

    # ========================================================
    # Verify detected risks
    # ========================================================

    final_risks: list[Risk] = []

    for risk in detected_risks:

        if isinstance(
            risk,
            dict,
        ):

            risk = Risk(
                **risk
            )

        elif not isinstance(
            risk,
            Risk,
        ):

            if hasattr(
                risk,
                "model_dump",
            ):

                risk = Risk(
                    **risk.model_dump()
                )

            else:
                continue

        # ----------------------------------------------
        # Agent 3 verification
        # ----------------------------------------------

        try:

            risk = verifier.verify(
                risk
            )

        except Exception:

            # Simulation should remain usable even
            # if verification encounters an issue.
            pass

        final_risks.append(
            risk
        )

    # ========================================================
    # Recommendation
    # ========================================================

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

    # ========================================================
    # Risk Score & Causal Chain calculation
    # ========================================================

    risk_score = 85
    if final_risks:
        risk_score = int(max([r.probability * 100 for r in final_risks]))

    # ========================================================
    # Final result
    # ========================================================

    return SimulationResult(
        scenario=(
            f"Simulate "
            f"{request.delay_days}-day delay "
            f"for {request.node_id}"
        ),
        affected_nodes=affected_nodes,
        new_risks=final_risks,
        recommendation=recommendation,
        after={"risk_score": risk_score},
        causal_chain=affected_nodes,
    )