from __future__ import annotations

import time
import uuid
from typing import Any

import networkx as nx

from app.graph.graph_builder import build_graph
from app.models.investigation_models import (
    AgentTrace,
    AdversarialVerdict,
    InvestigationResult,
    SuggestedIntervention,
)
from app.models.risk_models import Risk, SimulationResult


# ============================================================
# REQUEST-SCOPED INVESTIGATION CONTEXT
# ============================================================

class InvestigationContext:
    """
    Request-scoped analysis context.
    
    Guarantees:
    - Single project snapshot loaded per request.
    - Graph built ONCE per request.
    - Zero global mutable state or cross-project contamination.
    """

    def __init__(
        self,
        project: Any = None,
        owner: str = "Aritra-DSU",
        repo: str = "RF-SENTINEL",
        data: Any = None,
        raw_risks: list | None = None,
        verified_risks: list | None = None,
    ) -> None:
        self.request_id: str = str(uuid.uuid4())
        self.owner: str = owner.strip() if owner else "Aritra-DSU"
        self.repo: str = repo.strip() if repo else "RF-SENTINEL"
        self.project_label: str = f"{self.owner}/{self.repo}"

        # Use explicit data if provided, else fallback to project argument
        src = data if data is not None else project
        if hasattr(src, "model_dump"):
            self.data: dict[str, Any] = src.model_dump()
        elif isinstance(src, dict):
            self.data = dict(src)
        else:
            self.data = {}
        # Store provided risks for compatibility
        self.raw_risks = raw_risks or []
        self.verified_risks = verified_risks or []

        if isinstance(self.data.get("project_data"), dict):
            self.data = self.data["project_data"]

        # Build graph ONCE per context
        try:
            self.graph: nx.DiGraph = build_graph(self.data)
        except Exception:
            self.graph = nx.DiGraph()

        # Shared pipeline results
        self.traces: list[AgentTrace] = []
        self.dependency_findings: dict[str, Any] = {}
        self.bottleneck_findings: list[dict[str, Any]] = []
        self.candidate_risks: list[Risk] = []
        self.verified_risks: list[Risk] = []
        self.adversarial_verdicts: list[AdversarialVerdict] = []
        self.simulation_results: list[SimulationResult] = []
        self.explanations: list[dict[str, Any]] = []
        self.interventions: list[SuggestedIntervention] = []

    def add_trace(
        self,
        agent_name: str,
        order: int,
        status: str = "COMPLETED",
        input_summary: str = "",
        output_summary: str = "",
        duration_ms: float = 0.0,
        error_info: str | None = None,
    ) -> AgentTrace:
        trace = AgentTrace(
            agent_name=agent_name,
            execution_order=order,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=round(duration_ms, 2),
            error_info=error_info,
        )
        self.traces.append(trace)
        return trace


# ============================================================
# PIPELINE ORCHESTRATOR
# ============================================================

def run_investigation_pipeline(
    project: Any,
    owner: str = "Aritra-DSU",
    repo: str = "RF-SENTINEL",
) -> InvestigationResult:
    """
    Execute the five-agent risk investigation pipeline over a single request context.
    """
    context = InvestigationContext(project, owner, repo)

    # 1. Agent 1 — Dependency Discovery
    from app.agents.dependency_discovery_agent import DependencyDiscoveryAgent
    DependencyDiscoveryAgent().run(context)

    # 2. Agent 2 — Bottleneck Detection
    from app.agents.bottleneck_detection_agent import BottleneckDetectionAgent
    BottleneckDetectionAgent().run(context)

    # 3. Detect candidate risks using Phase 4 risk engine
    from app.risk_engine.detector import detect_risks
    try:
        context.candidate_risks = detect_risks(context.data)
    except Exception:
        context.candidate_risks = []

    # 4. Agent 3 — Adversarial Check
    from app.agents.adversarial_check_agent import AdversarialCheckAgent
    AdversarialCheckAgent().run(context)

    # 5. Agent 4 — Impact Simulation
    from app.agents.impact_simulation_agent import ImpactSimulationAgent
    ImpactSimulationAgent().run(context)

    # 6. Agent 5 — Explanation / Intervention
    from app.agents.explanation_intervention_agent import ExplanationInterventionAgent
    ExplanationInterventionAgent().run(context)

    return InvestigationResult(
        project=context.project_label,
        source="seeded" if "aritra-dsu" in context.owner.lower() else "synced",
        request_id=context.request_id,
        status="COMPLETED",
        risks=context.verified_risks,
        dependency_findings=context.dependency_findings,
        bottleneck_findings=context.bottleneck_findings,
        adversarial_verdicts=context.adversarial_verdicts,
        simulation_results=context.simulation_results,
        explanations=context.explanations,
        interventions=context.interventions,
        agent_trace=context.traces,
    )
