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

from app.simulation.propagation_engine import (
    PropagationEngine,
)


# ============================================================
# Verifier & Propagation Engine
# ============================================================

verifier = VerifierAgent()
engine = PropagationEngine()


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
        request.effective_target_node
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
    # Execute generic failure propagation
    # ========================================================

    prop = engine.propagate(
        graph,
        request,
    )

    # ========================================================
    # BASELINE: detect risks on the UNMODIFIED real project
    # ========================================================

    baseline_risks = detect_risks(project_data)
    baseline_risk_count    = len(baseline_risks)
    baseline_critical      = sum(1 for r in baseline_risks if r.severity == "CRITICAL")
    baseline_high          = sum(1 for r in baseline_risks if r.severity == "HIGH")
    # Weighted baseline score: each CRITICAL=20pts, HIGH=10pts, MEDIUM=5pts, capped at 100
    baseline_score = min(100, baseline_critical * 20 + baseline_high * 10 +
                         sum(1 for r in baseline_risks if r.severity == "MEDIUM") * 5)

    # ========================================================
    # SCENARIO: apply delay/event to a copy, detect new risks
    # ========================================================

    scenario_project = copy.deepcopy(project_data)
    _apply_delay(scenario_project, request)
    detected_risks = detect_risks(scenario_project)

    final_risks: list[Risk] = []
    for risk in detected_risks:
        if isinstance(risk, dict):
            risk = Risk(**risk)
        elif not isinstance(risk, Risk):
            if hasattr(risk, "model_dump"):
                risk = Risk(**risk.model_dump())
            else:
                continue
        try:
            risk = verifier.verify(risk)
        except Exception:
            pass
        final_risks.append(risk)

    # ========================================================
    # SIMULATED SCORE: baseline + downstream propagation impact
    # Downstream affected nodes (excluding root) add to score.
    # Different scenarios produce different counts → different scores.
    # ========================================================

    affected = prop.get("affected_nodes", [])
    root_node = prop.get("target_node", request.effective_target_node)
    downstream_count = len([n for n in affected if n != root_node])

    scenario_critical = sum(1 for r in final_risks if r.severity == "CRITICAL")
    scenario_high     = sum(1 for r in final_risks if r.severity == "HIGH")
    scenario_medium   = sum(1 for r in final_risks if r.severity == "MEDIUM")

    # Score = risk-severity contribution + downstream propagation (2 pts per downstream node, max 20)
    risk_score = min(100,
        scenario_critical * 20 +
        scenario_high     * 10 +
        scenario_medium   *  5 +
        min(20, downstream_count * 2)
    )

    # ========================================================
    # Build before/after dicts with real risk scores
    # ========================================================

    before_dict = dict(prop.get("before", {}))
    before_dict["risk_score"]    = baseline_score
    before_dict["risk_count"]    = baseline_risk_count
    before_dict["critical_count"] = baseline_critical

    after_dict = dict(prop.get("after", {}))
    after_dict["risk_score"]     = risk_score
    after_dict["risk_count"]     = len(final_risks)
    after_dict["critical_count"] = scenario_critical

    # ========================================================
    # Final result
    # ========================================================

    return SimulationResult(
        scenario=prop.get("scenario", f"Simulate failure for {request.effective_target_node}"),
        affected_nodes=prop.get("affected_nodes", []),
        unaffected_nodes=prop.get("unaffected_nodes", []),
        unknown_nodes=prop.get("unknown_nodes", []),
        new_risks=final_risks,
        recommendation=prop.get("recommendation", ""),
        before=before_dict,
        after=after_dict,
        causal_chain=prop.get("causal_chain", []),
        propagation_paths=prop.get("propagation_paths", []),
        evidence=prop.get("evidence", []),
        truncated=prop.get("truncated", False),
        warnings=prop.get("warnings", []),
    )
