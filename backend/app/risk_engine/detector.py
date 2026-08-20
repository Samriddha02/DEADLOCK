import re

from app.models.github_models import ProjectData
from app.models.risk_models import Risk

from app.graph.graph_builder import build_graph
from app.graph.graph_analyzer import downstream_nodes

from app.risk_engine.rules import (
    severity_from_score,
    is_overdue,
)

from app.risk_engine.scoring import (
    probability_from_factors,
)


def detect_risks(project: ProjectData) -> list[Risk]:
    """
    Detect potential project risks using deterministic rules.
    """

    graph = build_graph(project)

    risks: list[Risk] = []
    counter = 1

    # --------------------------------------------------
    # RULE 1: Open PR affecting downstream work
    # --------------------------------------------------

    for pr in project.pull_requests:

        if pr.state != "open":
            continue

        referenced_issues = re.findall(
            r"#(\d+)",
            pr.title
        )

        for number_text in referenced_issues:

            issue_number = int(number_text)
            issue_id = f"issue:{issue_number}"

            if issue_id not in graph:
                continue

            affected_nodes = downstream_nodes(
                graph,
                issue_id
            )

            if not affected_nodes:
                continue

            probability = probability_from_factors(
                downstream=len(affected_nodes),
                inactive=pr.draft,
            )

            severity = severity_from_score(
                probability
            )

            risks.append(
                Risk(
                    risk_id=f"RISK-{counter:03d}",

                    title=(
                        f"Open PR #{pr.number} "
                        "may block downstream work"
                    ),

                    severity=severity,

                    probability=probability,

                    root_cause=f"pr:{pr.number}",

                    impact=(
                        f"{len(affected_nodes)} "
                        "downstream node(s) may be affected."
                    ),

                    evidence=[
                        {
                            "type": "pull_request",
                            "id": f"PR #{pr.number}",
                            "title": pr.title,
                            "state": pr.state,
                        },
                        {
                            "type": "graph",
                            "id": issue_id,
                            "downstream_count": len(
                                affected_nodes
                            ),
                        },
                    ],

                    causal_chain=[
                        f"pr:{pr.number}",
                        issue_id,
                        *affected_nodes,
                    ],

                    recommendation=(
                        f"Review and resolve PR #{pr.number} "
                        "before downstream work proceeds."
                    ),
                )
            )

            counter += 1

    # --------------------------------------------------
    # RULE 2: Overdue milestone
    # --------------------------------------------------

    for milestone in project.milestones:

        if (
            milestone.state == "open"
            and milestone.open_issues > 0
            and is_overdue(milestone.due_on)
        ):

            probability = probability_from_factors(
                blocked=1,
                downstream=milestone.open_issues,
                overdue=True,
            )

            severity = severity_from_score(
                probability
            )

            risks.append(
                Risk(
                    risk_id=f"RISK-{counter:03d}",

                    title=(
                        f"Overdue milestone: "
                        f"{milestone.title}"
                    ),

                    severity=severity,

                    probability=probability,

                    root_cause=(
                        f"milestone:{milestone.number}"
                    ),

                    impact=(
                        f"{milestone.open_issues} open "
                        "issue(s) remain after the deadline."
                    ),

                    evidence=[
                        {
                            "type": "milestone",
                            "id": (
                                f"Milestone #{milestone.number}"
                            ),
                            "title": milestone.title,
                            "due_on": milestone.due_on,
                            "open_issues": (
                                milestone.open_issues
                            ),
                        }
                    ],

                    causal_chain=[
                        f"milestone:{milestone.number}"
                    ],

                    recommendation=(
                        f"Re-plan milestone "
                        f"'{milestone.title}' and "
                        "prioritize remaining issues."
                    ),
                )
            )

            counter += 1

    # --------------------------------------------------
    # RULE 3: Open draft PR
    # --------------------------------------------------

    for pr in project.pull_requests:

        if pr.state == "open" and pr.draft:

            probability = probability_from_factors(
                inactive=True
            )

            severity = severity_from_score(
                probability
            )

            risks.append(
                Risk(
                    risk_id=f"RISK-{counter:03d}",

                    title=(
                        f"Draft PR #{pr.number} "
                        "is still open"
                    ),

                    severity=severity,

                    probability=probability,

                    root_cause=f"pr:{pr.number}",

                    impact=(
                        "A draft change may remain "
                        "unavailable to downstream integration."
                    ),

                    evidence=[
                        {
                            "type": "pull_request",
                            "id": f"PR #{pr.number}",
                            "title": pr.title,
                            "draft": True,
                        }
                    ],

                    causal_chain=[
                        f"pr:{pr.number}"
                    ],

                    recommendation=(
                        f"Review PR #{pr.number}; "
                        "mark it ready for review or "
                        "close it if obsolete."
                    ),
                )
            )

            counter += 1

    # Highest probability risks first
    risks.sort(
        key=lambda risk: risk.probability,
        reverse=True
    )

    return risks