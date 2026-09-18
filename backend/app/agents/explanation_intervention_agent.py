from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.models.investigation_models import SuggestedIntervention

if TYPE_CHECKING:
    from app.agents.investigation_pipeline import InvestigationContext


class ExplanationInterventionAgent:
    """
    Agent 5 — Explanation / Intervention Agent.
    
    Converts verified findings into structured evidence-backed explanations
    and generates SUGGESTED interventions (executed=False).
    """

    def __init__(self) -> None:
        self.name = "explanation_intervention_agent"
        self.order = 5

    def run(self, context: InvestigationContext) -> None:
        start_time = time.perf_counter()
        verified_risks = context.verified_risks
        bottlenecks = context.bottleneck_findings

        try:
            explanations: list[dict[str, str]] = []
            interventions: list[SuggestedIntervention] = []

            for idx, risk in enumerate(verified_risks, start=1):
                risk_id = str(getattr(risk, "risk_id", f"RISK-{idx}"))
                title = str(getattr(risk, "title", "Project Risk"))
                impact = str(getattr(risk, "impact", "Potential project delay"))
                root_cause = str(getattr(risk, "root_cause", "Unknown"))
                recommendation = str(getattr(risk, "recommendation", "Review and mitigate risk."))
                causal_chain = getattr(risk, "causal_chain", []) or []

                exp = {
                    "risk_id": risk_id,
                    "what": title,
                    "why": impact,
                    "which_entities": f"Root cause: {root_cause}; Chain: {' -> '.join(causal_chain)}",
                    "how_propagates": f"Propagates along validated graph path: {' -> '.join(causal_chain)}",
                    "evidence_summary": f"{len(getattr(risk, 'evidence', []))} evidence item(s) confirmed",
                    "suggested_action": recommendation,
                }
                explanations.append(exp)

                if "DEADLINE" in risk_id:
                    interventions.append(SuggestedIntervention(
                        id=f"int_{idx}_deadline",
                        target_entity=root_cause,
                        category="schedule_mitigation",
                        action=f"SUGGESTED: Prioritize review & merge of {root_cause} to unblock critical path",
                        rationale="Prevent downstream release deadline slippage",
                        expected_impact="Unblocks downstream issues and safeguards release target",
                        executed=False,
                    ))
                elif "BOTTLENECK" in risk_id:
                    interventions.append(SuggestedIntervention(
                        id=f"int_{idx}_bottleneck",
                        target_entity=root_cause,
                        category="workload_rebalancing",
                        action=f"SUGGESTED: Redistribute open issue assignments and review load away from {root_cause}",
                        rationale="Developer owns disproportionate share of open project hours",
                        expected_impact="Reduces single-point-of-failure risk and balances team velocity",
                        executed=False,
                    ))
                elif "DEPLOYMENT" in risk_id:
                    interventions.append(SuggestedIntervention(
                        id=f"int_{idx}_deployment",
                        target_entity=root_cause,
                        category="deployment_safety",
                        action=f"SUGGESTED: Perform backward compatibility audit on {root_cause} before deployment",
                        rationale="Deployment is exposed to breaking schema change risk",
                        expected_impact="Prevents runtime breaking failures in production",
                        executed=False,
                    ))

            # Additional interventions for bottleneck findings if not already covered
            for b in bottlenecks:
                dev_id = b.get("developer_id")
                if dev_id and not any(i.target_entity == dev_id for i in interventions):
                    interventions.append(SuggestedIntervention(
                        id=f"int_b_{dev_id}",
                        target_entity=dev_id,
                        category="workload_rebalancing",
                        action=f"SUGGESTED: Rebalance workload for developer {b.get('developer_name', dev_id)}",
                        rationale=f"Developer owns {b.get('workload_share', 0)*100:.1f}% of open project hours",
                        expected_impact="Mitigates workload concentration",
                        executed=False,
                    ))

            context.explanations = explanations
            context.interventions = interventions
            duration = (time.perf_counter() - start_time) * 1000.0

            context.add_trace(
                agent_name=self.name,
                order=self.order,
                status="COMPLETED",
                input_summary=f"Generated explanations and interventions for {len(verified_risks)} verified risk(s)",
                output_summary=f"Emitted {len(explanations)} explanations and {len(interventions)} suggested interventions (all executed=False)",
                duration_ms=duration,
            )

        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000.0
            context.explanations = []
            context.interventions = []
            context.add_trace(
                agent_name=self.name,
                order=self.order,
                status="FAILED",
                input_summary="Explanation and intervention generation",
                output_summary="Failed to generate explanations and interventions",
                duration_ms=duration,
                error_info=str(exc),
            )
