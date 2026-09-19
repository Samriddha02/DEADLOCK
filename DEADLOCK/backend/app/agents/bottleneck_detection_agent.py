from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.graph.graph_analyzer import downstream_nodes, bottleneck_scores
from app.graph.graph_builder import _find_node

if TYPE_CHECKING:
    from app.agents.investigation_pipeline import InvestigationContext


class BottleneckDetectionAgent:
    """
    Agent 2 — Bottleneck Detection Agent.
    
    Identifies concentrated project ownership, developer work imbalances,
    and structural bottlenecks across the NetworkX graph and dataset.
    """

    def __init__(self) -> None:
        self.name = "bottleneck_detection_agent"
        self.order = 2

    def run(self, context: InvestigationContext) -> None:
        start_time = time.perf_counter()
        data = context.data
        graph = context.graph

        try:
            developers = data.get("developers", [])
            issues = [i for i in data.get("issues", []) if isinstance(i, dict)]
            prs = [p for p in data.get("pull_requests", []) if isinstance(p, dict)]

            open_issues = [
                i for i in issues
                if str(i.get("status", i.get("state", ""))).lower() in {"open", "opened", "in_progress", "pending"}
            ]

            total_open_hours = 0.0
            for issue in open_issues:
                try:
                    total_open_hours += float(issue.get("estimated_hours", issue.get("estimate_hours", 0)) or 0)
                except (TypeError, ValueError):
                    pass

            findings = []
            scores = bottleneck_scores(graph)

            if developers and isinstance(developers, list) and total_open_hours > 0:
                for dev in developers:
                    if not isinstance(dev, dict):
                        continue

                    dev_id = str(dev.get("id", dev.get("username", "")))
                    if not dev_id:
                        continue

                    assigned = [
                        i for i in open_issues
                        if str(i.get("assignee_id", i.get("assignee", i.get("developer_id", "")))) == dev_id
                    ]

                    assigned_hours = sum(
                        float(i.get("estimated_hours", i.get("estimate_hours", 0)) or 0) for i in assigned
                    )

                    share = assigned_hours / total_open_hours if total_open_hours > 0 else 0.0

                    dev_node = _find_node(graph, dev_id, preferred_type="developer")
                    downstream_reach = len(downstream_nodes(graph, dev_node)) if dev_node else 0

                    if share >= 0.30 or assigned_hours >= 150:
                        dev_name = dev.get("name", dev.get("username", dev_id))
                        findings.append({
                            "developer_id": dev_id,
                            "developer_name": dev_name,
                            "assigned_issue_count": len(assigned),
                            "assigned_hours": assigned_hours,
                            "total_open_hours": total_open_hours,
                            "workload_share": round(share, 4),
                            "graph_reachability": downstream_reach,
                            "bottleneck_score": scores.get(dev_node, 0.0) if dev_node else 0.0,
                            "is_primary_bottleneck": share >= 0.40 and assigned_hours >= 200,
                        })

            context.bottleneck_findings = findings
            duration = (time.perf_counter() - start_time) * 1000.0

            summary_text = (
                f"Identified {len(findings)} developer bottleneck(s)"
                if findings else "No developer workload concentration detected"
            )

            context.add_trace(
                agent_name=self.name,
                order=self.order,
                status="COMPLETED",
                input_summary=f"Analyzed {len(developers)} developers and {len(open_issues)} open issues",
                output_summary=summary_text,
                duration_ms=duration,
            )

        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000.0
            context.bottleneck_findings = []
            context.add_trace(
                agent_name=self.name,
                order=self.order,
                status="FAILED",
                input_summary="Workload analysis",
                output_summary="Failed to analyze bottleneck findings",
                duration_ms=duration,
                error_info=str(exc),
            )
