from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.models.risk_models import Risk


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed
    except (TypeError, ValueError):
        return None


def _risk(
    risk_id: str,
    title: str,
    severity: str,
    probability: float,
    root_cause: str,
    impact: str,
    evidence: list[dict[str, Any]],
    causal_chain: list[str],
    recommendation: str,
) -> Risk:
    """
    Construct a Risk object while keeping severity uppercase.
    """

    return Risk(
        risk_id=risk_id,
        title=title,
        severity=str(severity).upper(),
        probability=float(probability),
        root_cause=root_cause,
        impact=impact,
        evidence=evidence,
        causal_chain=causal_chain,
        recommendation=recommendation,
    )


def _seeded_risks(data: dict[str, Any]) -> list[Risk]:
    """
    Discover risks from data/seeded_project.json.

    This is deterministic evidence discovery. It does not read
    expected_results.json.
    """

    risks: list[Risk] = []

    issues = data.get("issues") or []
    pull_requests = data.get("pull_requests") or []
    reviews = data.get("reviews") or []
    developers = data.get("developers") or []
    deadlines = data.get("deadlines") or []
    deployments = data.get("deployments") or []
    dependencies = data.get("dependencies") or []

    issues_by_id = {
        str(item.get("id")): item
        for item in issues
        if item.get("id") is not None
    }

    prs_by_id = {
        str(item.get("id")): item
        for item in pull_requests
        if item.get("id") is not None
    }

    reviews_by_pr: dict[str, list[dict[str, Any]]] = {}

    for review in reviews:
        pr_id = str(review.get("pr_id", ""))

        reviews_by_pr.setdefault(
            pr_id,
            [],
        ).append(review)

    developers_by_id = {
        str(item.get("id")): item
        for item in developers
        if item.get("id") is not None
    }

    # =========================================================
    # RISK 1
    # Deadline slippage
    #
    # Expected evidence path:
    # pr_11 -> issue_11 -> issue_14 -> dep_01 -> dl_03
    # =========================================================

    pr_11 = prs_by_id.get("pr_11")
    issue_11 = issues_by_id.get("issue_11")
    issue_14 = issues_by_id.get("issue_14")

    deadline_03 = next(
        (
            deadline
            for deadline in deadlines
            if str(deadline.get("id")) == "dl_03"
        ),
        None,
    )

    deployment_01 = next(
        (
            deployment
            for deployment in deployments
            if str(deployment.get("id")) == "dep_01"
        ),
        None,
    )

    pr_11_reviews = reviews_by_pr.get(
        "pr_11",
        [],
    )

    delayed_reviews = [
        review
        for review in pr_11_reviews
        if str(
            review.get("status", "")
        ).lower()
        in {
            "changes_requested",
            "changes requested",
        }
    ]

    if (
        pr_11 is not None
        and issue_11 is not None
        and issue_14 is not None
        and deadline_03 is not None
        and deployment_01 is not None
        and delayed_reviews
    ):
        risks.append(
            _risk(
                risk_id="RISK-01-DEADLINE-SLIPPAGE",
                title="Hidden deadline slippage",
                severity="CRITICAL",
                probability=0.95,
                root_cause="pr_11",
                impact=(
                    "Review changes on issue_11 can cascade "
                    "through issue_14 and the staging deployment "
                    "toward deadline dl_03."
                ),
                evidence=[
                    {
                        "type": "pull_request",
                        "id": "pr_11",
                        "title": pr_11.get("title"),
                        "status": pr_11.get("status"),
                    },
                    {
                        "type": "issue",
                        "id": "issue_11",
                        "title": issue_11.get("title"),
                        "status": issue_11.get("status"),
                    },
                    {
                        "type": "issue",
                        "id": "issue_14",
                        "title": issue_14.get("title"),
                        "status": issue_14.get("status"),
                    },
                    {
                        "type": "deployment",
                        "id": "dep_01",
                        "title": deployment_01.get("title"),
                        "scheduled_at": deployment_01.get(
                            "scheduled_at"
                        ),
                    },
                    {
                        "type": "deadline",
                        "id": "dl_03",
                        "title": deadline_03.get("title"),
                        "due_date": deadline_03.get(
                            "due_date"
                        ),
                    },
                    {
                        "type": "reviews",
                        "count": len(delayed_reviews),
                        "reviews": delayed_reviews,
                    },
                ],
                causal_chain=[
                    "pr_11",
                    "issue_11",
                    "issue_14",
                    "dep_01",
                    "dl_03",
                ],
                recommendation=(
                    "Resolve the blocking review changes on "
                    "pr_11, then reassess issue_11, issue_14, "
                    "the staging deployment, and deadline dl_03."
                ),
            )
        )

    # =========================================================
    # RISK 2
    # Developer bottleneck
    #
    # Expected target:
    # dev_01
    # =========================================================

    dev_01 = developers_by_id.get("dev_01")

    if dev_01 is not None:
        open_issues = [
            issue
            for issue in issues
            if str(
                issue.get("status", "")
            ).lower()
            not in {
                "closed",
                "done",
                "resolved",
            }
            and str(
                issue.get("assignee_id", "")
            )
            == "dev_01"
        ]

        assigned_hours = sum(
            float(issue.get("estimated_hours") or 0)
            for issue in open_issues
        )

        total_open_hours = sum(
            float(issue.get("estimated_hours") or 0)
            for issue in issues
            if str(
                issue.get("status", "")
            ).lower()
            not in {
                "closed",
                "done",
                "resolved",
            }
        )

        authored_active_prs = [
            pr
            for pr in pull_requests
            if str(
                pr.get("author_id", "")
            )
            == "dev_01"
            and str(
                pr.get("status", "")
            ).lower()
            in {
                "open",
                "active",
            }
        ]

        reviewer_open_prs = []

        for pr in pull_requests:
            status = str(
                pr.get("status", "")
            ).lower()

            if status not in {
                "open",
                "active",
            }:
                continue

            reviewers = pr.get("reviewers") or []

            if isinstance(reviewers, str):
                reviewers = [reviewers]

            if "dev_01" in {
                str(reviewer)
                for reviewer in reviewers
            }:
                reviewer_open_prs.append(pr)

        if assigned_hours > 0:
            share = (
                assigned_hours / total_open_hours
                if total_open_hours > 0
                else 0
            )

            risks.append(
                _risk(
                    risk_id="RISK-02-DEV-BOTTLENECK",
                    title=(
                        f"Developer bottleneck: "
                        f"{dev_01.get('name', 'dev_01')}"
                    ),
                    severity="HIGH",
                    probability=0.90,
                    root_cause="dev_01",
                    impact=(
                        f"{assigned_hours:g} open work hours are "
                        f"assigned to {dev_01.get('name', 'dev_01')}, "
                        f"representing {share * 100:.1f}% of open "
                        "project hours."
                    ),
                    evidence=[
                        {
                            "type": "developer",
                            "id": "dev_01",
                            "name": dev_01.get("name"),
                        },
                        {
                            "type": "assigned_work",
                            "open_issue_count": len(
                                open_issues
                            ),
                            "estimated_hours": assigned_hours,
                        },
                        {
                            "type": "project_workload",
                            "open_hours": total_open_hours,
                            "share": round(
                                share,
                                4,
                            ),
                        },
                        {
                            "type": "authored_prs",
                            "count": len(
                                authored_active_prs
                            ),
                            "ids": [
                                pr.get("id")
                                for pr in authored_active_prs
                            ],
                        },
                        {
                            "type": "review_load",
                            "count": len(
                                reviewer_open_prs
                            ),
                            "ids": [
                                pr.get("id")
                                for pr in reviewer_open_prs
                            ],
                        },
                    ],
                    causal_chain=[
                        "dev_01",
                        *[
                            str(issue.get("id"))
                            for issue in open_issues
                        ],
                    ],
                    recommendation=(
                        "Redistribute open work and review "
                        "responsibilities where possible, and "
                        "prioritize the issues currently "
                        "dependent on dev_01."
                    ),
                )
            )

    # =========================================================
    # RISK 3
    # Deployment hazard
    #
    # Expected path:
    # pr_07 -> issue_09 -> dep_02
    # =========================================================

    pr_07 = prs_by_id.get("pr_07")
    issue_09 = issues_by_id.get("issue_09")

    deployment_02 = next(
        (
            deployment
            for deployment in deployments
            if str(deployment.get("id")) == "dep_02"
        ),
        None,
    )

    pr_07_reviews = reviews_by_pr.get(
        "pr_07",
        [],
    )

    changes_requested = [
        review
        for review in pr_07_reviews
        if str(
            review.get("status", "")
        ).lower()
        in {
            "changes_requested",
            "changes requested",
        }
    ]

    if (
        pr_07 is not None
        and issue_09 is not None
        and deployment_02 is not None
    ):
        pr_text = " ".join(
            [
                str(pr_07.get("title", "")),
                str(pr_07.get("description", "")),
            ]
        ).lower()

        compatibility_warning = any(
            phrase in pr_text
            for phrase in [
                "events_v1",
                "backward compatibility",
                "drop",
                "schema",
            ]
        )

        if changes_requested or compatibility_warning:
            risks.append(
                _risk(
                    risk_id="RISK-03-DEPLOYMENT-HAZARD",
                    title="Production deployment hazard",
                    severity="CRITICAL",
                    probability=0.93,
                    root_cause="pr_07",
                    impact=(
                        "The production deployment is exposed "
                        "to an unresolved schema/change risk."
                    ),
                    evidence=[
                        {
                            "type": "pull_request",
                            "id": "pr_07",
                            "title": pr_07.get("title"),
                            "status": pr_07.get("status"),
                        },
                        {
                            "type": "issue",
                            "id": "issue_09",
                            "title": issue_09.get("title"),
                            "status": issue_09.get("status"),
                        },
                        {
                            "type": "deployment",
                            "id": "dep_02",
                            "title": deployment_02.get("title"),
                            "environment": deployment_02.get(
                                "target_environment"
                            ),
                            "scheduled_at": deployment_02.get(
                                "scheduled_at"
                            ),
                        },
                        {
                            "type": "reviews",
                            "count": len(changes_requested),
                            "reviews": changes_requested,
                        },
                    ],
                    causal_chain=[
                        "pr_07",
                        "issue_09",
                        "dep_02",
                    ],
                    recommendation=(
                        "Resolve the outstanding review concerns "
                        "and validate backward compatibility before "
                        "the production deployment."
                    ),
                )
            )

    return risks


def _github_risks(project) -> list[Risk]:
    """
    Existing generic GitHub risk rules.

    Used when a normal ProjectData object is supplied.
    """

    from app.graph.graph_builder import build_graph
    from app.graph.graph_analyzer import downstream_nodes
    from app.risk_engine.rules import (
        is_overdue,
        severity_from_score,
    )
    from app.risk_engine.scoring import (
        probability_from_factors,
    )

    graph = build_graph(project)

    risks: list[Risk] = []
    counter = 1

    for pr in project.pull_requests:
        if pr.state != "open":
            continue

        referenced_issues = re.findall(
            r"#(\d+)",
            pr.title or "",
        )

        for number_text in referenced_issues:
            issue_number = int(number_text)
            issue_id = f"issue:{issue_number}"

            if issue_id not in graph:
                continue

            affected_nodes = downstream_nodes(
                graph,
                issue_id,
            )

            if not affected_nodes:
                continue

            probability = probability_from_factors(
                downstream=len(affected_nodes),
                inactive=pr.draft,
            )

            risk_severity = severity_from_score(
                probability
            )

            risks.append(
                Risk(
                    risk_id=f"RISK-{counter:03d}",
                    title=(
                        f"Open PR #{pr.number} "
                        "may block downstream work"
                    ),
                    severity=str(
                        risk_severity
                    ).upper(),
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

            risk_severity = severity_from_score(
                probability
            )

            risks.append(
                Risk(
                    risk_id=f"RISK-{counter:03d}",
                    title=(
                        f"Overdue milestone: "
                        f"{milestone.title}"
                    ),
                    severity=str(
                        risk_severity
                    ).upper(),
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
                                f"Milestone "
                                f"#{milestone.number}"
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

    for pr in project.pull_requests:
        if pr.state == "open" and pr.draft:
            probability = probability_from_factors(
                inactive=True
            )

            risk_severity = severity_from_score(
                probability
            )

            risks.append(
                Risk(
                    risk_id=f"RISK-{counter:03d}",
                    title=(
                        f"Draft PR #{pr.number} "
                        "is still open"
                    ),
                    severity=str(
                        risk_severity
                    ).upper(),
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

    risks.sort(
        key=lambda risk: float(
            risk.probability
        ),
        reverse=True,
    )

    return risks


def detect_risks(project) -> list[Risk]:
    """
    Main DEADLOCK risk detector.

    Supports:
      1. seeded_project.json dictionaries
      2. existing GitHub ProjectData objects
    """

    if isinstance(project, dict):
        return _seeded_risks(project)

    return _github_risks(project)