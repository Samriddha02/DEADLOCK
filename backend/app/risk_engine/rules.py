from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import networkx as nx


# ============================================================
# HELPERS
# ============================================================

def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def _extract_id(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, dict):
        value = (
            value.get("id")
            or value.get("number")
            or value.get("username")
        )

    if value is None:
        return None

    return str(value)


def _name(item: dict[str, Any]) -> str:
    return str(
        item.get("title")
        or item.get("name")
        or item.get("id")
        or item.get("number")
        or "Unknown"
    )


def _is_overdue(item: dict[str, Any]) -> bool:
    status = str(
        item.get("status")
        or item.get("state")
        or ""
    ).lower()

    if status in {
        "closed",
        "completed",
        "done",
        "merged",
    }:
        return False

    deadline = (
        item.get("deadline")
        or item.get("due_date")
        or item.get("due_at")
        or item.get("deadline_at")
    )

    parsed = _parse_datetime(deadline)

    if parsed is None:
        return False

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed < datetime.now(timezone.utc)


# ============================================================
# SEVERITY
# ============================================================

def severity_from_score(score: float) -> str:
    """
    Convert numeric risk score into the severity
    expected by the Risk Engine.
    """

    score = float(score)

    if score >= 0.85:
        return "CRITICAL"

    if score >= 0.65:
        return "HIGH"

    if score >= 0.40:
        return "MEDIUM"

    return "LOW"


# ============================================================
# DEADLINE SLIPPAGE
# ============================================================

def detect_deadline_slippage(
    dataset: dict[str, Any],
    graph: nx.DiGraph | None = None,
) -> list[dict[str, Any]]:

    risks: list[dict[str, Any]] = []

    for collection_name in (
        "issues",
        "milestones",
    ):

        items = dataset.get(
            collection_name,
            [],
        )

        if not isinstance(items, list):
            continue

        for item in items:

            if not isinstance(item, dict):
                continue

            if not _is_overdue(item):
                continue

            entity_id = str(
                item.get("id")
                or item.get("number")
            )

            risks.append(
                {
                    "rule": "deadline_slippage",
                    "risk_type": "DEADLINE_SLIPPAGE",
                    "entity_type": collection_name.rstrip("s"),
                    "entity_id": entity_id,
                    "title": _name(item),
                    "severity": "HIGH",
                    "reason": (
                        "Open work has passed "
                        "its deadline."
                    ),
                }
            )

    return risks


# ============================================================
# DEVELOPER BOTTLENECK
# ============================================================

def detect_developer_bottleneck(
    dataset: dict[str, Any],
    graph: nx.DiGraph | None = None,
) -> list[dict[str, Any]]:

    developers = dataset.get(
        "developers",
        [],
    )

    issues = dataset.get(
        "issues",
        [],
    )

    pull_requests = dataset.get(
        "pull_requests",
        [],
    )

    workload: dict[str, int] = {}

    # --------------------------------------------------------
    # Issues
    # --------------------------------------------------------

    for issue in issues:

        if not isinstance(issue, dict):
            continue

        status = str(
            issue.get("state")
            or issue.get("status")
            or ""
        ).lower()

        if status in {
            "closed",
            "completed",
            "done",
        }:
            continue

        developer = (
            issue.get("assignee_id")
            or issue.get("developer_id")
            or issue.get("assignee")
            or issue.get("developer")
        )

        developer = _extract_id(developer)

        if developer:
            workload[developer] = (
                workload.get(developer, 0) + 1
            )

    # --------------------------------------------------------
    # Pull Requests
    # --------------------------------------------------------

    for pr in pull_requests:

        if not isinstance(pr, dict):
            continue

        state = str(
            pr.get("state")
            or ""
        ).lower()

        if state in {
            "closed",
            "merged",
        }:
            continue

        developer = (
            pr.get("assignee_id")
            or pr.get("developer_id")
            or pr.get("assignee")
            or pr.get("author_id")
        )

        developer = _extract_id(developer)

        if developer:
            workload[developer] = (
                workload.get(developer, 0) + 1
            )

    if not workload:
        return []

    values = list(workload.values())

    average = sum(values) / len(values)

    threshold = max(
        3,
        average * 2,
    )

    developer_names: dict[str, str] = {}

    if isinstance(developers, list):

        for developer in developers:

            if not isinstance(developer, dict):
                continue

            developer_id = _extract_id(developer)

            if developer_id:
                developer_names[developer_id] = str(
                    developer.get(
                        "name",
                        developer.get(
                            "username",
                            developer_id,
                        ),
                    )
                )

    risks: list[dict[str, Any]] = []

    for developer_id, count in workload.items():

        if count < threshold:
            continue

        risks.append(
            {
                "rule": "developer_bottleneck",
                "risk_type": "DEVELOPER_BOTTLENECK",
                "entity_type": "developer",
                "entity_id": developer_id,
                "title": developer_names.get(
                    developer_id,
                    developer_id,
                ),
                "severity": (
                    "CRITICAL"
                    if count >= threshold * 1.5
                    else "HIGH"
                ),
                "workload": count,
                "average_workload": round(
                    average,
                    2,
                ),
                "reason": (
                    "A developer owns a "
                    "disproportionately large "
                    "amount of active work."
                ),
            }
        )

    return risks


# ============================================================
# DEPENDENCY RISK
# ============================================================

def detect_dependency_risk(
    dataset: dict[str, Any],
    graph: nx.DiGraph | None = None,
) -> list[dict[str, Any]]:

    if graph is None:
        return []

    risks: list[dict[str, Any]] = []

    for node in graph.nodes:

        dependency_count = 0

        for target in graph.successors(node):

            relation = graph.edges[
                node,
                target,
            ].get("relation")

            if relation == "depends_on":
                dependency_count += 1

        if dependency_count < 3:
            continue

        node_data = graph.nodes[node]

        risks.append(
            {
                "rule": "dependency_risk",
                "risk_type": "DEPENDENCY_BOTTLENECK",
                "entity_type": node_data.get(
                    "type",
                    "unknown",
                ),
                "entity_id": str(node),
                "title": node_data.get(
                    "label",
                    str(node),
                ),
                "severity": (
                    "CRITICAL"
                    if dependency_count >= 5
                    else "HIGH"
                ),
                "dependency_count": dependency_count,
                "reason": (
                    "This entity has multiple "
                    "downstream dependencies."
                ),
            }
        )

    return risks


# ============================================================
# STALE PULL REQUEST
# ============================================================

def detect_stale_pull_requests(
    dataset: dict[str, Any],
    graph: nx.DiGraph | None = None,
) -> list[dict[str, Any]]:

    risks: list[dict[str, Any]] = []

    pull_requests = dataset.get(
        "pull_requests",
        [],
    )

    if not isinstance(pull_requests, list):
        return risks

    for pr in pull_requests:

        if not isinstance(pr, dict):
            continue

        state = str(
            pr.get("state")
            or ""
        ).lower()

        if state in {
            "closed",
            "merged",
        }:
            continue

        updated_at = (
            pr.get("updated_at")
            or pr.get("last_updated_at")
        )

        updated = _parse_datetime(updated_at)

        if updated is None:
            continue

        if updated.tzinfo is None:
            updated = updated.replace(
                tzinfo=timezone.utc
            )

        age_days = (
            datetime.now(timezone.utc)
            - updated
        ).days

        if age_days < 7:
            continue

        risks.append(
            {
                "rule": "stale_pull_request",
                "risk_type": "STALE_PULL_REQUEST",
                "entity_type": "pull_request",
                "entity_id": str(
                    pr.get("id")
                    or pr.get("number")
                ),
                "title": _name(pr),
                "severity": (
                    "MEDIUM"
                    if age_days < 14
                    else "HIGH"
                ),
                "stale_days": age_days,
                "reason": (
                    "An open pull request has "
                    "had no recent update."
                ),
            }
        )

    return risks


# ============================================================
# RULE REGISTRY
# ============================================================

RULES = [
    detect_deadline_slippage,
    detect_developer_bottleneck,
    detect_dependency_risk,
    detect_stale_pull_requests,
]


# ============================================================
# RUN ALL RULES
# ============================================================

def run_all_rules(
    dataset: dict[str, Any],
    graph: nx.DiGraph | None = None,
) -> list[dict[str, Any]]:

    results: list[dict[str, Any]] = []

    for rule in RULES:

        try:
            detected = rule(
                dataset,
                graph,
            )

            if detected:
                results.extend(detected)

        except Exception:
            # One failing rule must not stop
            # the complete risk pipeline.
            continue

    return results

def is_overdue(due_date, current_date=None):
    from datetime import datetime, date
    if due_date is None:
        return False
    try:
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        if current_date is None:
            current_date = datetime.now()
        elif isinstance(current_date, str):
            current_date = datetime.fromisoformat(current_date.replace('Z', '+00:00'))
        if isinstance(due_date, date) and not isinstance(due_date, datetime):
            if isinstance(current_date, datetime):
                current_date = current_date.date()
        return due_date < current_date
    except (ValueError, TypeError):
        return False

