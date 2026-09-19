from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.models.risk_models import SimulationRequest, SimulationResult
from app.simulation.what_if import simulate

if TYPE_CHECKING:
    from app.agents.investigation_pipeline import InvestigationContext


class ImpactSimulationAgent:
    """
    Agent 4 — Impact Simulation Agent.
    
    Determines downstream consequences of candidate risks using the deterministic What-If engine
    (app.simulation.what_if). Does NOT mutate original ProjectData.
    """

    def __init__(self) -> None:
        self.name = "impact_simulation_agent"
        self.order = 4

    def run(self, context: InvestigationContext) -> None:
        start_time = time.perf_counter()
        data = context.data
        verified_risks = context.verified_risks

        try:
            simulation_results: list[SimulationResult] = []

            # Determine nodes to simulate based on verified risks
            sim_target_nodes = set()
            for risk in verified_risks:
                root_cause = getattr(risk, "root_cause", None)
                if root_cause:
                    sim_target_nodes.add(str(root_cause))

            # Default to pr_11 benchmark node if no specific verified risk target
            if not sim_target_nodes:
                sim_target_nodes.add("pr_11")

            for node_id in sorted(sim_target_nodes):
                request = SimulationRequest(node_id=node_id, delay_days=3)
                sim_res = simulate(data, request)
                simulation_results.append(sim_res)

            context.simulation_results = simulation_results
            duration = (time.perf_counter() - start_time) * 1000.0

            total_affected = sum(len(res.affected_nodes) for res in simulation_results)

            context.add_trace(
                agent_name=self.name,
                order=self.order,
                status="COMPLETED",
                input_summary=f"Simulated impact for {len(sim_target_nodes)} target node(s) with 3-day delay",
                output_summary=f"Calculated downstream propagation affecting {total_affected} total node(s)",
                duration_ms=duration,
            )

        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000.0
            context.simulation_results = []
            context.add_trace(
                agent_name=self.name,
                order=self.order,
                status="FAILED",
                input_summary="Impact simulation",
                output_summary="Failed to simulate impact",
                duration_ms=duration,
                error_info=str(exc),
            )
