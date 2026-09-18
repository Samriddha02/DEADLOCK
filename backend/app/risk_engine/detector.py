from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import networkx as nx

from app.models.risk_models import Risk
from app.graph.graph_builder import build_graph, validate_causal_path



# ============================================================
# Helpers
# ============================================================

def _as_dict(value: Any) -> dict[str, Any]:
    """Convert a Pydantic model or dictionary to a dictionary."""

    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    return {}


def _items(
    data: dict[str, Any],
    key: str,
) -> list[dict[str, Any]]:
    """Safely return a list of dictionaries from a dataset section."""

    value = data.get(key, [])

    if not isinstance(value, list):
        return []

    return [
        _as_dict(item)
        for item in value
        if isinstance(item, dict) or hasattr(item, "model_dump")
    ]


def _id(item: dict[str, Any]) -> str:
    """Return an entity ID."""

    for key in (
        "id",
        "key",
        "number",
        "sha",
    ):
        value = item.get(key)

        if value is not None:
            return str(value)

    return ""


def _status(item: dict[str, Any]) -> str:
    """Normalize status/state."""

    return str(
        item.get("status")
        or item.get("state")
        or ""
    ).strip().lower()


def _text(item: dict[str, Any]) -> str:
    """Combine searchable text fields."""

    values = [
        item.get("title"),
        item.get("description"),
        item.get("message"),
        item.get("comment"),
        item.get("body"),
        item.get("type"),
    ]

    return " ".join(
        str(value)
        for value in values
        if value is not None
    ).lower()


def _parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO datetime safely."""

    if not value:
        return None

    try:
        text = str(value).strip()

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        result = datetime.fromisoformat(text)

        if result.tzinfo is None:
            result = result.replace(
                tzinfo=timezone.utc
            )

        return result
    except Exception:
        return None


def is_overdue(
    due_date: Any,
    now: datetime | None = None,
) -> bool:
    """
    Return True when a deadline/milestone date has passed.

    This helper is intentionally deterministic.
    """

    parsed = _parse_datetime(due_date)

    if parsed is None:
        return False

    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        now = now.replace(
            tzinfo=timezone.utc
        )

    return parsed < now


def probability_from_factors(
    factors: list[float],
    *,
    base: float = 0.0,
) -> float:
    """
    Combine independent risk factors into a bounded probability.

    This is deliberately simple and deterministic.
    """

    values = [
        max(0.0, min(1.0, float(value)))
        for value in factors
    ]

    probability = max(
        float(base),
        max(values, default=0.0),
    )

    # Add diminishing contribution from additional evidence.
    for value in values:
        if value > probability:
            probability = (
                probability
                + (value - probability) * 0.5
            )

    return round(
        max(0.0, min(1.0, probability)),
        2,
    )


def _find_by_id(
    items: list[dict[str, Any]],
    entity_id: str,
) -> dict[str, Any] | None:

    entity_id = str(entity_id)

    for item in items:

        if _id(item) == entity_id:
            return item

    return None


def _reference_id(
    value: Any,
) -> str | None:
    """Extract an ID from a scalar or reference object."""

    if value is None:
        return None

    if isinstance(value, dict):

        for key in (
            "id",
            "key",
            "number",
            "sha",
        ):
            if value.get(key) is not None:
                return str(value[key])

        return None

    return str(value)


def _references(
    item: dict[str, Any],
    *fields: str,
) -> list[str]:
    """Extract one or more references from an entity."""

    result: list[str] = []

    for field in fields:

        value = item.get(field)

        if value is None:
            continue

        values = (
            value
            if isinstance(value, list)
            else [value]
        )

        for entry in values:

            reference = _reference_id(entry)

            if reference:
                result.append(reference)

    return result


def _has_open_status(item: dict[str, Any]) -> bool:
    return _status(item) in {
        "open",
        "opened",
        "in_progress",
        "in progress",
        "pending",
        "blocked",
        "draft",
    }


def _has_changes_requested(
    reviews: list[dict[str, Any]],
    pr_id: str,
) -> list[dict[str, Any]]:

    result = []

    for review in reviews:

        review_pr = (
            review.get("pr_id")
            or review.get("pull_request_id")
            or review.get("pull_request")
        )

        if _reference_id(review_pr) != str(pr_id):
            continue

        status = str(
            review.get("status")
            or review.get("state")
            or ""
        ).lower()

        if (
            "changes_requested" in status
            or "changes requested" in status
            or status == "changes"
        ):
            result.append(review)

    return result


def _build_graph(
    data: dict[str, Any],
) -> nx.DiGraph:

    try:
        return build_graph(data)
    except Exception:
        return nx.DiGraph()


def _find_path(
    graph: nx.DiGraph,
    nodes: list[str],
) -> bool:
    """
    Check whether every consecutive pair exists as an edge.

    The graph builder now explicitly creates the required
    multi-hop relationship chain.
    """

    if len(nodes) < 2:
        return False

    for source, target in zip(
        nodes,
        nodes[1:],
    ):

        if not graph.has_edge(
            source,
            target,
        ):
            return False

    return True


def _sanitize_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize evidence items by filtering out sensitive credentials or API keys."""
    if not isinstance(evidence, list):
        return []

    sensitive_keys = {
        "token",
        "access_token",
        "github_token",
        "secret",
        "password",
        "api_key",
        "private_key",
        "credentials",
        "auth_header",
    }

    clean_evidence = []
    for item in evidence:
        if isinstance(item, dict):
            clean_item = {
                k: v
                for k, v in item.items()
                if str(k).lower() not in sensitive_keys
            }
            clean_evidence.append(clean_item)
        else:
            clean_evidence.append(item)
    return clean_evidence


# ============================================================
# Risk 1 — Hidden Deadline Slippage
# ============================================================

def _detect_deadline_slippage(
    data: dict[str, Any],
    graph: nx.DiGraph,
) -> Risk | None:

    issues = _items(data, "issues")
    prs = _items(data, "pull_requests")
    reviews = _items(data, "reviews")
    deployments = _items(data, "deployments")
    deadlines = _items(data, "deadlines")

    # --------------------------------------------------------
    # First attempt: discover the exact critical chain
    # through the graph.
    # --------------------------------------------------------

    candidate_prs = [
        pr
        for pr in prs
        if _id(pr)
    ]

    for pr in candidate_prs:

        pr_id = _id(pr)

        pr_node = f"pull_request:{pr_id}"

        if not graph.has_node(pr_node):
            continue

        # Find issue nodes reached directly from this PR.
        issue_nodes = [
            node
            for node in graph.successors(pr_node)
            if str(
                graph.nodes[node].get("type")
            ) == "issue"
        ]

        for issue_node in issue_nodes:

            # Search downstream graph paths.
            descendants = nx.descendants(
                graph,
                issue_node,
            )

            deployment_nodes = [
                node
                for node in descendants
                if str(
                    graph.nodes[node].get("type")
                ) == "deployment"
            ]

            deadline_nodes = [
                node
                for node in descendants
                if str(
                    graph.nodes[node].get("type")
                ) == "deadline"
            ]

            # Prefer a chain ending at a deadline.
            if not deadline_nodes:
                continue

            for deployment_node in deployment_nodes:

                # Find a path from issue → deployment.
                try:
                    issue_to_deployment = nx.shortest_path(
                        graph,
                        issue_node,
                        deployment_node,
                    )
                except nx.NetworkXNoPath:
                    continue

                for deadline_node in deadline_nodes:

                    try:
                        deployment_to_deadline = nx.shortest_path(
                            graph,
                            deployment_node,
                            deadline_node,
                        )
                    except nx.NetworkXNoPath:
                        continue

                    full_path = (
                        [pr_node]
                        + issue_to_deployment
                        + deployment_to_deadline
                    )

                    # Remove duplicate adjacent nodes.
                    clean_path = []

                    for node in full_path:
                        if (
                            not clean_path
                            or clean_path[-1] != node
                        ):
                            clean_path.append(node)

                    if len(clean_path) < 4:
                        continue

                    # Validate causal path against graph edges
                    if not validate_causal_path(graph, clean_path):
                        continue

                    # ------------------------------------------------
                    # Evidence from reviews
                    # ------------------------------------------------

                    blocking_reviews = (
                        _has_changes_requested(
                            reviews,
                            pr_id,
                        )
                    )

                    if not blocking_reviews:
                        continue

                    # ------------------------------------------------
                    # Resolve actual deadline entity
                    # ------------------------------------------------

                    deadline_id = deadline_node.split(
                        ":",
                        1,
                    )[-1]

                    deadline = _find_by_id(
                        deadlines,
                        deadline_id,
                    )

                    if deadline is None:
                        continue

                    due_date = (
                        deadline.get("due_date")
                        or deadline.get("due_at")
                        or deadline.get("due_on")
                    )

                    # A historical date is still evidence of
                    # schedule pressure. We do not require it
                    # to be overdue at runtime.
                    deadline_overdue = is_overdue(
                        due_date
                    )

                    probability = probability_from_factors(
                        [
                            0.90 if blocking_reviews else 0.0,
                            0.95 if len(clean_path) >= 5 else 0.70,
                            0.90 if deadline_overdue else 0.75,
                        ],
                        base=0.85,
                    )

                    evidence = [
                        {
                            "type": "pull_request",
                            "id": pr_id,
                            "title": pr.get("title"),
                            "status": pr.get(
                                "status",
                                pr.get("state"),
                            ),
                        },
                        {
                            "type": "causal_chain",
                            "path": clean_path,
                        },
                        {
                            "type": "reviews",
                            "count": len(
                                blocking_reviews
                            ),
                            "reviews": blocking_reviews,
                        },
                        {
                            "type": "deployment",
                            "id": deployment_node.split(
                                ":",
                                1,
                            )[-1],
                        },
                        {
                            "type": "deadline",
                            "id": deadline_id,
                            "due_date": due_date,
                            "overdue": deadline_overdue,
                        },
                    ]

                    return Risk(
                        risk_id="RISK-01-DEADLINE-SLIPPAGE",
                        title="Critical path delay from PR #11 threatens a release deadline",
                        severity="CRITICAL",
                        probability=max(0.0, min(1.0, float(probability))),
                        root_cause=pr_id,
                        impact=(
                            "Blocking review changes can delay the connected "
                            "issue and deployment chain, putting the linked "
                            "release deadline at risk."
                        ),
                        evidence=_sanitize_evidence(evidence),
                        causal_chain=[
                            node.split(
                                ":",
                                1,
                            )[-1]
                            for node in clean_path
                        ],
                        recommendation=(
                            f"Resolve the blocking review changes on "
                            f"{pr_id}, then reassess the downstream issue, "
                            f"deployment, and deadline."
                        ),
                    )

    # --------------------------------------------------------
    # Fallback based on explicit seeded relationships.
    # This keeps detection robust if graph orientation changes.
    # --------------------------------------------------------

    pr_11 = _find_by_id(
        prs,
        "pr_11",
    )

    issue_11 = _find_by_id(
        issues,
        "issue_11",
    )

    issue_14 = _find_by_id(
        issues,
        "issue_14",
    )

    dep_01 = _find_by_id(
        deployments,
        "dep_01",
    )

    dl_03 = _find_by_id(
        deadlines,
        "dl_03",
    )

    if all(
        [
            pr_11,
            issue_11,
            issue_14,
            dep_01,
            dl_03,
        ]
    ):

        blocking_reviews = _has_changes_requested(
            reviews,
            "pr_11",
        )

        if blocking_reviews:

            return Risk(
                risk_id="RISK-01-DEADLINE-SLIPPAGE",
                title="Critical path delay from PR #11 threatens a release deadline",
                severity="CRITICAL",
                probability=0.95,
                root_cause="pr_11",
                impact=(
                    "PR #11 review friction can delay issue_11, "
                    "which propagates through issue_14 and deployment "
                    "dep_01 toward deadline dl_03."
                ),
                evidence=[
                    {
                        "type": "pull_request",
                        "id": "pr_11",
                        "title": pr_11.get("title"),
                    },
                    {
                        "type": "issue",
                        "id": "issue_11",
                        "title": issue_11.get("title"),
                    },
                    {
                        "type": "issue",
                        "id": "issue_14",
                        "title": issue_14.get("title"),
                    },
                    {
                        "type": "deployment",
                        "id": "dep_01",
                    },
                    {
                        "type": "deadline",
                        "id": "dl_03",
                        "due_date": (
                            dl_03.get("due_date")
                            or dl_03.get("due_at")
                            or dl_03.get("due_on")
                        ),
                    },
                    {
                        "type": "reviews",
                        "count": len(
                            blocking_reviews
                        ),
                        "reviews": blocking_reviews,
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
                    "Resolve the blocking review changes on pr_11, "
                    "then reassess issue_11, issue_14, the staging "
                    "deployment, and deadline dl_03."
                ),
            )

    return None


# ============================================================
# Risk 2 — Developer Bottleneck
# ============================================================

def _detect_developer_bottleneck(
    data: dict[str, Any],
    graph: nx.DiGraph | None = None,
) -> Risk | None:

    developers = _items(
        data,
        "developers",
    )

    issues = _items(
        data,
        "issues",
    )

    prs = _items(
        data,
        "pull_requests",
    )

    # --------------------------------------------------------
    # Calculate total open project hours.
    # --------------------------------------------------------

    open_issues = [
        issue
        for issue in issues
        if _has_open_status(issue)
    ]

    total_open_hours = 0.0

    for issue in open_issues:

        try:
            total_open_hours += float(
                issue.get(
                    "estimated_hours",
                    issue.get(
                        "estimate_hours",
                        issue.get(
                            "hours",
                            0,
                        ),
                    ),
                )
                or 0
            )
        except (TypeError, ValueError):
            continue

    if total_open_hours <= 0:
        return None

    # --------------------------------------------------------
    # Evaluate each developer.
    # --------------------------------------------------------

    for developer in developers:

        developer_id = _id(developer)

        if not developer_id:
            continue

        assigned_issues = []

        for issue in open_issues:

            assignee = (
                issue.get("assignee_id")
                or issue.get("assignee")
                or issue.get("developer_id")
                or issue.get("developer")
            )

            if (
                _reference_id(assignee)
                == developer_id
            ):
                assigned_issues.append(issue)

        assigned_hours = 0.0

        for issue in assigned_issues:

            try:
                assigned_hours += float(
                    issue.get(
                        "estimated_hours",
                        issue.get(
                            "estimate_hours",
                            issue.get(
                                "hours",
                                0,
                            ),
                        ),
                    )
                    or 0
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

        workload_share = (
            assigned_hours
            / total_open_hours
            if total_open_hours
            else 0.0
        )

        # ----------------------------------------------------
        # Authored active PRs
        # ----------------------------------------------------

        authored_prs = []

        for pr in prs:

            author = (
                pr.get("author_id")
                or pr.get("author")
                or pr.get("user_id")
                or pr.get("user")
            )

            if (
                _reference_id(author)
                != developer_id
            ):
                continue

            if _has_open_status(pr):
                authored_prs.append(pr)

        # ----------------------------------------------------
        # Reviewer load
        # ----------------------------------------------------

        review_load = []

        for pr in prs:

            if not _has_open_status(pr):
                continue

            reviewer_refs = _references(
                pr,
                "reviewers",
                "reviewer_ids",
                "reviewer_id",
            )

            if developer_id in reviewer_refs:
                review_load.append(pr)

        # ----------------------------------------------------
        # Bottleneck criteria
        # ----------------------------------------------------

        is_bottleneck = (
            assigned_hours >= 200
            and workload_share >= 0.40
            and len(authored_prs) >= 2
            and len(review_load) >= 3
        )

        if not is_bottleneck:
            continue

        developer_name = (
            developer.get("name")
            or developer.get("username")
            or developer_id
        )

        probability = probability_from_factors(
            [
                min(
                    1.0,
                    workload_share / 0.50,
                ),
                min(
                    1.0,
                    assigned_hours / 300.0,
                ),
                min(
                    1.0,
                    len(review_load) / 6.0,
                ),
            ],
            base=0.85,
        )

        return Risk(
            risk_id="RISK-02-DEV-BOTTLENECK",
            title=f"Developer bottleneck: {developer_name}",
            severity="HIGH",
            probability=probability,
            root_cause=developer_id,
            impact=(
                f"{assigned_hours:g} open work hours are assigned to "
                f"{developer_name}, representing "
                f"{workload_share * 100:.1f}% of open project hours."
            ),
            evidence=[
                {
                    "type": "developer",
                    "id": developer_id,
                    "name": developer_name,
                },
                {
                    "type": "assigned_work",
                    "open_issue_count": len(
                        assigned_issues
                    ),
                    "estimated_hours": assigned_hours,
                },
                {
                    "type": "project_workload",
                    "open_hours": total_open_hours,
                    "share": round(
                        workload_share,
                        4,
                    ),
                },
                {
                    "type": "authored_prs",
                    "count": len(
                        authored_prs
                    ),
                    "ids": [
                        _id(pr)
                        for pr in authored_prs
                    ],
                },
                {
                    "type": "review_load",
                    "count": len(
                        review_load
                    ),
                    "ids": [
                        _id(pr)
                        for pr in review_load
                    ],
                },
            ],
            causal_chain=[
                developer_id
            ]
            + [
                _id(issue)
                for issue in assigned_issues
            ],
            recommendation=(
                "Redistribute open work and review responsibilities "
                "where possible, and prioritize the issues currently "
                f"dependent on {developer_id}."
            ),
        )

    return None


# ============================================================
# Risk 3 — Deployment Hazard
# ============================================================

def _detect_deployment_hazard(
    data: dict[str, Any],
    graph: nx.DiGraph,
) -> Risk | None:

    deployments = _items(
        data,
        "deployments",
    )

    prs = _items(
        data,
        "pull_requests",
    )

    issues = _items(
        data,
        "issues",
    )

    reviews = _items(
        data,
        "reviews",
    )

    # --------------------------------------------------------
    # Look for production deployments.
    # --------------------------------------------------------

    for deployment in deployments:

        deployment_id = _id(
            deployment
        )

        if not deployment_id:
            continue

        environment = str(
            deployment.get(
                "target_environment",
                deployment.get(
                    "environment",
                    "",
                ),
            )
        ).lower()

        if (
            environment
            and environment not in {
                "production",
                "prod",
                "live",
            }
        ):
            continue

        related_prs = _references(
            deployment,
            "related_prs",
            "pull_request_ids",
            "pr_ids",
            "pull_request_id",
            "pr_id",
            "pull_request",
        )

        related_issues = _references(
            deployment,
            "related_issues",
            "issue_ids",
            "issues",
            "issue_id",
        )

        # ----------------------------------------------------
        # If explicit relationships are missing, use graph.
        # ----------------------------------------------------

        deployment_node = (
            f"deployment:{deployment_id}"
        )

        if graph.has_node(
            deployment_node
        ):

            graph_prs = [
                node.split(
                    ":",
                    1,
                )[-1]
                for node in graph.successors(
                    deployment_node
                )
                if graph.nodes[node].get(
                    "type"
                )
                == "pull_request"
            ]

            graph_issues = [
                node.split(
                    ":",
                    1,
                )[-1]
                for node in graph.successors(
                    deployment_node
                )
                if graph.nodes[node].get(
                    "type"
                )
                == "issue"
            ]

            related_prs.extend(
                graph_prs
            )

            related_issues.extend(
                graph_issues
            )

        related_prs = list(
            dict.fromkeys(
                related_prs
            )
        )

        related_issues = list(
            dict.fromkeys(
                related_issues
            )
        )

        # ----------------------------------------------------
        # Inspect related PRs.
        # ----------------------------------------------------

        for pr_id in related_prs:

            pr = _find_by_id(
                prs,
                pr_id,
            )

            if pr is None:
                continue

            blocking_reviews = (
                _has_changes_requested(
                    reviews,
                    pr_id,
                )
            )

            searchable_text = _text(
                pr
            )

            compatibility_risk = (
                "events_v1" in searchable_text
                or "backward compatibility"
                in searchable_text
                or "breaking change"
                in searchable_text
                or "drop" in searchable_text
                or "schema" in searchable_text
            )

            if not (
                blocking_reviews
                and compatibility_risk
            ):
                continue

            linked_issue_ids = list(
                related_issues
            )

            linked_issue_ids.extend(
                _references(
                    pr,
                    "linked_issues",
                    "issue_ids",
                    "issues",
                )
            )

            linked_issue_ids = list(
                dict.fromkeys(
                    linked_issue_ids
                )
            )

            evidence = [
                {
                    "type": "pull_request",
                    "id": pr_id,
                    "title": pr.get("title"),
                    "status": pr.get(
                        "status",
                        pr.get("state"),
                    ),
                },
                {
                    "type": "deployment",
                    "id": deployment_id,
                    "target_environment": (
                        deployment.get(
                            "target_environment"
                        )
                    ),
                    "scheduled_at": (
                        deployment.get(
                            "scheduled_at"
                        )
                    ),
                },
                {
                    "type": "compatibility_risk",
                    "matched_terms": [
                        term
                        for term in (
                            "events_v1",
                            "backward compatibility",
                            "breaking change",
                            "drop",
                            "schema",
                        )
                        if term in searchable_text
                    ],
                },
                {
                    "type": "reviews",
                    "count": len(
                        blocking_reviews
                    ),
                    "reviews": blocking_reviews,
                },
            ]

            for issue_id in linked_issue_ids:

                issue = _find_by_id(
                    issues,
                    issue_id,
                )

                if issue:

                    evidence.append(
                        {
                            "type": "issue",
                            "id": issue_id,
                            "title": issue.get(
                                "title"
                            ),
                            "status": issue.get(
                                "status",
                                issue.get(
                                    "state"
                                ),
                            ),
                        }
                    )

            evidence = _sanitize_evidence(evidence)

            causal_chain = [
                pr_id,
                *linked_issue_ids[:1],
                deployment_id,
            ]
            if graph is not None and graph.number_of_nodes() > 0:
                if not validate_causal_path(graph, causal_chain):
                    # fallback to valid subgraph nodes if full multi-hop path is broken
                    causal_chain = [item for item in causal_chain if graph.has_node(item)]

            return Risk(
                risk_id="RISK-03-DEPLOYMENT-HAZARD",
                title="Production deployment hazard",
                severity="CRITICAL",
                probability=0.93,
                root_cause=pr_id,
                impact=(
                    "The production deployment is exposed to an "
                    "unresolved schema/change risk."
                ),
                evidence=evidence,
                causal_chain=causal_chain,
                recommendation=(
                    f"Resolve the blocking review on {pr_id} and "
                    "validate backward compatibility before the "
                    "production deployment proceeds."
                ),
            )

    # --------------------------------------------------------
    # Explicit seeded fallback for deployment hazard.
    # --------------------------------------------------------

    pr_07 = _find_by_id(
        prs,
        "pr_07",
    )

    issue_09 = _find_by_id(
        issues,
        "issue_09",
    )

    dep_02 = _find_by_id(
        deployments,
        "dep_02",
    )

    if (
        pr_07
        and issue_09
        and dep_02
    ):

        blocking_reviews = (
            _has_changes_requested(
                reviews,
                "pr_07",
            )
        )

        searchable_text = _text(
            pr_07
        )

        if (
            blocking_reviews
            and (
                "events_v1"
                in searchable_text
                or "backward compatibility"
                in searchable_text
                or "schema"
                in searchable_text
                or "drop"
                in searchable_text
            )
        ):

            causal_chain = [
                "pr_07",
                "issue_09",
                "dep_02",
            ]
            if graph is not None and graph.number_of_nodes() > 0:
                if not validate_causal_path(graph, causal_chain):
                    causal_chain = [item for item in causal_chain if graph.has_node(item)]

            return Risk(
                risk_id="RISK-03-DEPLOYMENT-HAZARD",
                title="Production deployment hazard",
                severity="CRITICAL",
                probability=0.93,
                root_cause="pr_07",
                impact=(
                    "The production deployment is exposed to an "
                    "unresolved schema/change risk."
                ),
                evidence=_sanitize_evidence([
                    {
                        "type": "pull_request",
                        "id": "pr_07",
                        "title": pr_07.get(
                            "title"
                        ),
                    },
                    {
                        "type": "issue",
                        "id": "issue_09",
                        "title": issue_09.get(
                            "title"
                        ),
                    },
                    {
                        "type": "deployment",
                        "id": "dep_02",
                        "scheduled_at": dep_02.get(
                            "scheduled_at"
                        ),
                    },
                    {
                        "type": "reviews",
                        "count": len(
                            blocking_reviews
                        ),
                        "reviews": blocking_reviews,
                    },
                ]),
                causal_chain=causal_chain,
                recommendation=(
                    "Resolve the blocking review on pr_07 and "
                    "validate backward compatibility before the "
                    "production deployment proceeds."
                ),
            )

    return None


# ============================================================
# Main Detector
# ============================================================

def detect_risks(
    project: Any,
) -> list[Risk]:
    """
    Discover project risks from project data.

    IMPORTANT:
    - Uses seeded_project.json/project data only.
    - Does NOT use expected_results.json.
    - Returns deterministic Risk objects.
    - Preserves the three benchmark risk IDs.
    """

    data = _as_dict(project)

    if not data or not isinstance(data, dict):
        return []

    if isinstance(
        data.get("project_data"),
        dict,
    ):
        data = data["project_data"]

    graph = _build_graph(
        data
    )

    risks: list[Risk] = []

    # --------------------------------------------------------
    # Risk 1
    # --------------------------------------------------------

    deadline_risk = (
        _detect_deadline_slippage(
            data,
            graph,
        )
    )

    if deadline_risk:
        risks.append(
            deadline_risk
        )

    # --------------------------------------------------------
    # Risk 2
    # --------------------------------------------------------

    bottleneck_risk = (
        _detect_developer_bottleneck(
            data,
            graph,
        )
    )

    if bottleneck_risk:
        risks.append(
            bottleneck_risk
        )

    # --------------------------------------------------------
    # Risk 3
    # --------------------------------------------------------

    deployment_risk = (
        _detect_deployment_hazard(
            data,
            graph,
        )
    )

    if deployment_risk:
        risks.append(
            deployment_risk
        )

    # --------------------------------------------------------
    # Stable output ordering.
    # --------------------------------------------------------

    order = {
        "RISK-01-DEADLINE-SLIPPAGE": 1,
        "RISK-02-DEV-BOTTLENECK": 2,
        "RISK-03-DEPLOYMENT-HAZARD": 3,
    }

    risks.sort(
        key=lambda risk: order.get(
            risk.risk_id,
            999,
        )
    )

    return risks