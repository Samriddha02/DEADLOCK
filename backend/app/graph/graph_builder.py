from __future__ import annotations

from typing import Any

import networkx as nx


# ============================================================
# Helpers
# ============================================================

def _get_id(item: dict[str, Any]) -> str | None:
    """
    Get the graph identifier.

    GitHub milestones use their public number as the
    graph identifier. Other entities normally use id.
    """

    if "number" in item:
        return str(item["number"])

    if "id" in item:
        return str(item["id"])

    return None


def _node_type(entity_type: str) -> str:
    """Convert collection names into graph node types."""

    mapping = {
        "developers": "developer",
        "issues": "issue",
        "pull_requests": "pull_request",
        "commits": "commit",
        "milestones": "milestone",
        "reviews": "review",
        "dependencies": "dependency",
        "deployments": "deployment",
    }

    return mapping.get(
        entity_type,
        entity_type.rstrip("s"),
    )


def _add_entities(
    graph: nx.DiGraph,
    entity_type: str,
    items: list[dict[str, Any]],
) -> None:
    """Add dataset entities as graph nodes."""

    node_type = _node_type(entity_type)

    for item in items:

        if not isinstance(item, dict):
            continue

        entity_id = _get_id(item)

        if entity_id is None:
            continue

        node_id = f"{node_type}:{entity_id}"

        label = (
            item.get("title")
            or item.get("name")
            or item.get("message")
            or entity_id
        )

        graph.add_node(
            node_id,
            type=node_type,
            label=str(label),
            data=item,
        )


def _find_node(
    graph: nx.DiGraph,
    entity_id: Any,
) -> str | None:
    """
    Find a graph node using:
    - id
    - number
    - title
    """

    if entity_id is None:
        return None

    entity_id = str(entity_id)

    for node, data in graph.nodes(data=True):

        raw_data = data.get("data", {})

        if str(raw_data.get("id", "")) == entity_id:
            return node

        if str(raw_data.get("number", "")) == entity_id:
            return node

        if str(raw_data.get("title", "")) == entity_id:
            return node

    return None


def _extract_reference(
    reference: Any,
) -> Any:
    """Extract an ID from a string, number, or object."""

    if isinstance(reference, dict):
        return (
            reference.get("id")
            or reference.get("number")
            or reference.get("title")
        )

    return reference


def _add_reference_edge(
    graph: nx.DiGraph,
    source_node: str,
    reference: Any,
    relation: str,
) -> None:
    """Create an edge to a referenced entity."""

    reference = _extract_reference(reference)

    if reference is None:
        return

    target_node = _find_node(
        graph,
        reference,
    )

    if target_node is None:
        return

    graph.add_edge(
        source_node,
        target_node,
        relation=relation,
    )


# ============================================================
# Main Graph Builder
# ============================================================

def build_graph(
    project: Any,
) -> nx.DiGraph:
    """
    Build the DEADLOCK project graph.

    Supports:
    - Existing Pydantic ProjectData models
    - Raw seeded_project.json dictionaries

    Runtime input:
        data/seeded_project.json

    The graph represents relationships between:
    developers, issues, pull requests, commits,
    milestones, reviews, dependencies and deployments.
    """

    graph = nx.DiGraph()

    # --------------------------------------------------------
    # Convert Pydantic model to dictionary
    # --------------------------------------------------------

    if hasattr(project, "model_dump"):
        data = project.model_dump()

    elif isinstance(project, dict):
        data = project

    else:
        raise TypeError(
            "project must be a dictionary or Pydantic model"
        )

    # --------------------------------------------------------
    # Support wrapped datasets
    # --------------------------------------------------------

    if isinstance(
        data.get("project_data"),
        dict,
    ):
        dataset = data["project_data"]

    else:
        dataset = data

    # --------------------------------------------------------
    # Add project node
    # --------------------------------------------------------

    project_info = dataset.get("project")

    if isinstance(project_info, dict):

        project_id = project_info.get("id")

        if project_id:

            graph.add_node(
                f"project:{project_id}",
                type="project",
                label=project_info.get(
                    "name",
                    str(project_id),
                ),
                data=project_info,
            )

    # --------------------------------------------------------
    # Entity collections
    # --------------------------------------------------------

    entity_types = [
        "developers",
        "issues",
        "pull_requests",
        "commits",
        "milestones",
        "reviews",
        "dependencies",
        "deployments",
    ]

    # --------------------------------------------------------
    # Add nodes
    # --------------------------------------------------------

    for entity_type in entity_types:

        items = dataset.get(
            entity_type,
            [],
        )

        if isinstance(items, list):

            _add_entities(
                graph,
                entity_type,
                items,
            )

    # --------------------------------------------------------
    # Project → entities
    # --------------------------------------------------------

    if isinstance(project_info, dict):

        project_id = project_info.get("id")

        if project_id:

            project_node = f"project:{project_id}"

            for entity_type in entity_types:

                for item in dataset.get(
                    entity_type,
                    [],
                ):

                    if not isinstance(item, dict):
                        continue

                    entity_id = _get_id(item)

                    if entity_id is None:
                        continue

                    node_type = _node_type(
                        entity_type
                    )

                    node_id = (
                        f"{node_type}:{entity_id}"
                    )

                    if node_id in graph:

                        graph.add_edge(
                            project_node,
                            node_id,
                            relation="contains",
                        )

    # --------------------------------------------------------
    # Generic reference relationships
    # --------------------------------------------------------

    reference_fields = {

        "assignee": "assigned_to",

        "assignee_id": "assigned_to",

        "developer_id": "assigned_to",

        "developer": "assigned_to",

        "author_id": "authored_by",

        "author": "authored_by",

        "user_id": "created_by",

        "issue_id": "references_issue",

        "pr_id": "references_pr",

        "pull_request_id": "references_pr",

        "milestone_id": "belongs_to_milestone",
    }

    for entity_type in entity_types:

        items = dataset.get(
            entity_type,
            [],
        )

        if not isinstance(items, list):
            continue

        node_type = _node_type(
            entity_type
        )

        for item in items:

            if not isinstance(item, dict):
                continue

            entity_id = _get_id(item)

            if entity_id is None:
                continue

            source_node = (
                f"{node_type}:{entity_id}"
            )

            if source_node not in graph:
                continue

            for field, relation in reference_fields.items():

                if field not in item:
                    continue

                _add_reference_edge(
                    graph,
                    source_node,
                    item[field],
                    relation,
                )

    # --------------------------------------------------------
    # Issue → Milestone
    # --------------------------------------------------------

    for issue in dataset.get(
        "issues",
        [],
    ):

        if not isinstance(issue, dict):
            continue

        issue_id = _get_id(issue)

        if issue_id is None:
            continue

        issue_node = f"issue:{issue_id}"

        if issue_node not in graph:
            continue

        milestone = issue.get(
            "milestone"
        )

        if milestone is not None:

            milestone_ref = _extract_reference(
                milestone
            )

            milestone_node = _find_node(
                graph,
                milestone_ref,
            )

            if milestone_node:

                graph.add_edge(
                    issue_node,
                    milestone_node,
                    relation="belongs_to_milestone",
                )

    # --------------------------------------------------------
    # Explicit dependencies
    # --------------------------------------------------------

    for dependency in dataset.get(
        "dependencies",
        [],
    ):

        if not isinstance(
            dependency,
            dict,
        ):
            continue

        source = (
            dependency.get("source")
            or dependency.get("source_id")
            or dependency.get("from")
            or dependency.get("from_id")
        )

        target = (
            dependency.get("target")
            or dependency.get("target_id")
            or dependency.get("to")
            or dependency.get("to_id")
        )

        if source is None or target is None:
            continue

        source_node = _find_node(
            graph,
            source,
        )

        target_node = _find_node(
            graph,
            target,
        )

        if source_node and target_node:

            graph.add_edge(
                source_node,
                target_node,
                relation="depends_on",
            )

    # --------------------------------------------------------
    # Pull Request → Issue
    # --------------------------------------------------------

    for pr in dataset.get(
        "pull_requests",
        [],
    ):

        if not isinstance(pr, dict):
            continue

        pr_id = _get_id(pr)

        if pr_id is None:
            continue

        pr_node = f"pull_request:{pr_id}"

        if pr_node not in graph:
            continue

        issue_refs = (
            pr.get("issue_ids")
            or pr.get("issues")
            or pr.get("linked_issues")
            or []
        )

        if not isinstance(
            issue_refs,
            list,
        ):
            issue_refs = [issue_refs]

        for issue_ref in issue_refs:

            issue_ref = _extract_reference(
                issue_ref
            )

            issue_node = _find_node(
                graph,
                issue_ref,
            )

            if issue_node:

                graph.add_edge(
                    pr_node,
                    issue_node,
                    relation="resolves_issue",
                )

    # --------------------------------------------------------
    # Commit → Pull Request
    # --------------------------------------------------------

    for commit in dataset.get(
        "commits",
        [],
    ):

        if not isinstance(commit, dict):
            continue

        commit_id = _get_id(commit)

        if commit_id is None:
            continue

        commit_node = f"commit:{commit_id}"

        if commit_node not in graph:
            continue

        pr_ref = (
            commit.get("pull_request_id")
            or commit.get("pr_id")
            or commit.get("pull_request")
        )

        if pr_ref is not None:

            pr_ref = _extract_reference(
                pr_ref
            )

            pr_node = _find_node(
                graph,
                pr_ref,
            )

            if pr_node:

                graph.add_edge(
                    commit_node,
                    pr_node,
                    relation="contributes_to",
                )

    # --------------------------------------------------------
    # Review → Pull Request
    # --------------------------------------------------------

    for review in dataset.get(
        "reviews",
        [],
    ):

        if not isinstance(review, dict):
            continue

        review_id = _get_id(review)

        if review_id is None:
            continue

        review_node = f"review:{review_id}"

        if review_node not in graph:
            continue

        pr_ref = (
            review.get("pull_request_id")
            or review.get("pr_id")
            or review.get("pull_request")
        )

        if pr_ref is not None:

            pr_ref = _extract_reference(
                pr_ref
            )

            pr_node = _find_node(
                graph,
                pr_ref,
            )

            if pr_node:

                graph.add_edge(
                    review_node,
                    pr_node,
                    relation="reviews",
                )

    # --------------------------------------------------------
    # Deployment → Pull Request
    # --------------------------------------------------------

    for deployment in dataset.get(
        "deployments",
        [],
    ):

        if not isinstance(
            deployment,
            dict,
        ):
            continue

        deployment_id = _get_id(
            deployment
        )

        if deployment_id is None:
            continue

        deployment_node = (
            f"deployment:{deployment_id}"
        )

        if deployment_node not in graph:
            continue

        pr_ref = (
            deployment.get(
                "pull_request_id"
            )
            or deployment.get("pr_id")
            or deployment.get(
                "pull_request"
            )
        )

        if pr_ref is not None:

            pr_ref = _extract_reference(
                pr_ref
            )

            pr_node = _find_node(
                graph,
                pr_ref,
            )

            if pr_node:

                graph.add_edge(
                    deployment_node,
                    pr_node,
                    relation="deployed_from",
                )

    return graph