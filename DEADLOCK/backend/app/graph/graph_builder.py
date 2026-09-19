from __future__ import annotations

from typing import Any

import networkx as nx


# ============================================================
# Helpers
# ============================================================

def _get_id(item: dict[str, Any]) -> str | None:
    """
    Get the graph identifier.

    Priority:
    1. number
    2. id
    3. key
    4. sha
    """

    if "number" in item and item["number"] is not None:
        return str(item["number"])

    if "id" in item and item["id"] is not None:
        return str(item["id"])

    if "key" in item and item["key"] is not None:
        return str(item["key"])

    if "sha" in item and item["sha"] is not None:
        return str(item["sha"])

    return None


def _sanitize_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize entity metadata dictionary to exclude sensitive credentials
    and overly verbose nested dumps while preserving canonical fields.
    """
    if not isinstance(data, dict):
        return {}

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

    clean = {}
    for k, v in data.items():
        if str(k).lower() in sensitive_keys:
            continue
        if isinstance(v, (dict, list)) and len(str(v)) > 5000:
            continue
        clean[k] = v

    return clean


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
        "deadlines": "deadline",
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
            or item.get("description")
            or entity_id
        )

        graph.add_node(
            node_id,
            type=node_type,
            label=str(label),
            data=_sanitize_data(item),
        )


def _find_node(
    graph: nx.DiGraph,
    entity_id: Any,
    preferred_type: str | None = None,
) -> str | None:
    """
    Find a graph node using:
    - exact graph node ID
    - id
    - number
    - key
    - sha
    - title

    preferred_type is used when the reference is ambiguous.
    """

    if entity_id is None:
        return None

    entity_id = str(entity_id)

    # --------------------------------------------------------
    # Direct graph-node lookup
    # --------------------------------------------------------

    if ":" in entity_id and graph.has_node(entity_id):
        return entity_id

    # --------------------------------------------------------
    # Search graph data
    # --------------------------------------------------------

    for node, data in graph.nodes(data=True):

        if preferred_type:
            if data.get("type") != preferred_type:
                continue

        raw_data = data.get("data", {})

        if not isinstance(raw_data, dict):
            continue

        if str(raw_data.get("id", "")) == entity_id:
            return node

        if str(raw_data.get("number", "")) == entity_id:
            return node

        if str(raw_data.get("key", "")) == entity_id:
            return node

        if str(raw_data.get("sha", "")) == entity_id:
            return node

        if str(raw_data.get("title", "")) == entity_id:
            return node

    return None


def _extract_reference(
    reference: Any,
) -> Any:
    """
    Extract an ID from:
    - string
    - number
    - object
    """

    if isinstance(reference, dict):
        return (
            reference.get("id")
            or reference.get("number")
            or reference.get("key")
            or reference.get("sha")
            or reference.get("title")
        )

    return reference


def _add_reference_edge(
    graph: nx.DiGraph,
    source_node: str,
    reference: Any,
    relation: str,
    preferred_type: str | None = None,
) -> None:
    """Create an edge to a referenced entity."""

    reference = _extract_reference(reference)

    if reference is None:
        return

    target_node = _find_node(
        graph,
        reference,
        preferred_type=preferred_type,
    )

    if target_node is None:
        return

    graph.add_edge(
        source_node,
        target_node,
        relation=relation,
        data={"relation": relation, "direct": True},
    )


def validate_causal_path(
    graph: nx.DiGraph,
    path: list[str],
) -> bool:
    """
    Validate whether a proposed causal chain of node IDs forms a valid
    directed path in the graph. Supports bare IDs by resolving them.
    """

    if not path or not isinstance(path, list):
        return False

    resolved_path: list[str] = []
    for item in path:
        resolved = _find_node(graph, item)
        if resolved is None or not graph.has_node(resolved):
            return False
        resolved_path.append(resolved)

    for i in range(len(resolved_path) - 1):
        u = resolved_path[i]
        v = resolved_path[i + 1]
        if not graph.has_edge(u, v):
            return False

    return True



# ============================================================
# Main Graph Builder
# ============================================================

def build_graph(
    project: Any,
) -> nx.DiGraph:
    """
    Build the complete DEADLOCK project graph.

    Supports:
    - Pydantic ProjectData models
    - Raw seeded_project.json dictionaries
    - Wrapped project_data dictionaries

    Graph entities:
    - project
    - developers
    - issues
    - pull requests
    - commits
    - milestones
    - reviews
    - dependencies
    - deployments
    - deadlines

    The graph is intentionally relationship-rich so DEADLOCK
    can trace multi-hop project failure chains.
    """

    graph = nx.DiGraph()

    # ========================================================
    # Convert input to dictionary
    # ========================================================

    if hasattr(project, "model_dump"):
        data = project.model_dump()

    elif isinstance(project, dict):
        data = project

    else:
        raise TypeError(
            "project must be a dictionary or Pydantic model"
        )

    # ========================================================
    # Support wrapped datasets
    # ========================================================

    if isinstance(
        data.get("project_data"),
        dict,
    ):
        dataset = data["project_data"]

    else:
        dataset = data

    # ========================================================
    # Project node
    # ========================================================

    project_info = dataset.get("project")

    if isinstance(project_info, dict):

        project_id = (
            project_info.get("id")
            or project_info.get("key")
            or project_info.get("name")
        )

        if project_id:

            graph.add_node(
                f"project:{project_id}",
                type="project",
                label=str(
                    project_info.get(
                        "name",
                        project_id,
                    )
                ),
                data=project_info,
            )

    # ========================================================
    # Entity collections
    # ========================================================

    entity_types = [
        "developers",
        "issues",
        "pull_requests",
        "commits",
        "milestones",
        "reviews",
        "dependencies",
        "deployments",
        "deadlines",
    ]

    # ========================================================
    # Add entity nodes
    # ========================================================

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

    # ========================================================
    # Project → entities
    # ========================================================

    if isinstance(project_info, dict):

        project_id = (
            project_info.get("id")
            or project_info.get("key")
            or project_info.get("name")
        )

        if project_id:

            project_node = f"project:{project_id}"

            for entity_type in entity_types:

                items = dataset.get(
                    entity_type,
                    [],
                )

                if not isinstance(items, list):
                    continue

                for item in items:

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

    # ========================================================
    # Generic reference relationships
    # ========================================================

    reference_fields = {

        "assignee": (
            "assigned_to",
            "developer",
        ),

        "assignee_id": (
            "assigned_to",
            "developer",
        ),

        "developer_id": (
            "assigned_to",
            "developer",
        ),

        "developer": (
            "assigned_to",
            "developer",
        ),

        "author_id": (
            "authored_by",
            "developer",
        ),

        "author": (
            "authored_by",
            "developer",
        ),

        "user_id": (
            "created_by",
            "developer",
        ),

        "issue_id": (
            "references_issue",
            "issue",
        ),

        "pr_id": (
            "references_pr",
            "pull_request",
        ),

        "pull_request_id": (
            "references_pr",
            "pull_request",
        ),

        "milestone_id": (
            "belongs_to_milestone",
            "milestone",
        ),
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

            for field, config in reference_fields.items():

                if field not in item:
                    continue

                relation, preferred_type = config

                _add_reference_edge(
                    graph,
                    source_node,
                    item[field],
                    relation,
                    preferred_type=preferred_type,
                )

    # ========================================================
    # Issue → Milestone
    # ========================================================

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
                preferred_type="milestone",
            )

            if milestone_node:

                graph.add_edge(
                    issue_node,
                    milestone_node,
                    relation="belongs_to_milestone",
                )

    # ========================================================
    # Explicit dependencies
    # ========================================================

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
            _extract_reference(source),
        )

        target_node = _find_node(
            graph,
            _extract_reference(target),
        )

        if source_node and target_node:

            graph.add_edge(
                source_node,
                target_node,
                relation="depends_on",
            )

    # ========================================================
    # Pull Request → Issue
    # ========================================================

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
                preferred_type="issue",
            )

            if issue_node:

                graph.add_edge(
                    pr_node,
                    issue_node,
                    relation="resolves_issue",
                )

    # ========================================================
    # Commit → Pull Request
    # ========================================================

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
                preferred_type="pull_request",
            )

            if pr_node:

                graph.add_edge(
                    commit_node,
                    pr_node,
                    relation="contributes_to",
                )

    # ========================================================
    # Review → Pull Request
    # ========================================================

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
                preferred_type="pull_request",
            )

            if pr_node:

                graph.add_edge(
                    review_node,
                    pr_node,
                    relation="reviews",
                )

    # ========================================================
    # Deployment → Pull Request
    # ========================================================

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
                preferred_type="pull_request",
            )

            if pr_node:

                graph.add_edge(
                    deployment_node,
                    pr_node,
                    relation="deployed_from",
                )

    # ========================================================
    # Deployment → Deadline
    # ========================================================

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

        # Support several possible dataset field names.
        deadline_ref = (
            deployment.get("deadline_id")
            or deployment.get("deadline")
            or deployment.get("deadline_ref")
            or deployment.get("due_to")
            or deployment.get("target_deadline")
        )

        if deadline_ref is None:
            continue

        deadline_ref = _extract_reference(
            deadline_ref
        )

        deadline_node = _find_node(
            graph,
            deadline_ref,
            preferred_type="deadline",
        )

        if deadline_node:

            graph.add_edge(
                deployment_node,
                deadline_node,
                relation="targets_deadline",
            )

    # ========================================================
    # Deadline → Deployment / related entities
    #
    # Some seeded datasets define the relationship from the
    # deadline side instead of the deployment side.
    # ========================================================

    for deadline in dataset.get(
        "deadlines",
        [],
    ):

        if not isinstance(
            deadline,
            dict,
        ):
            continue

        deadline_id = _get_id(
            deadline
        )

        if deadline_id is None:
            continue

        deadline_node = (
            f"deadline:{deadline_id}"
        )

        if deadline_node not in graph:
            continue

        deployment_ref = (
            deadline.get("deployment_id")
            or deadline.get("deployment")
            or deadline.get("deployment_ref")
            or deadline.get("target_deployment")
        )

        if deployment_ref is None:
            continue

        deployment_ref = _extract_reference(
            deployment_ref
        )

        deployment_node = _find_node(
            graph,
            deployment_ref,
            preferred_type="deployment",
        )

        if deployment_node:

            graph.add_edge(
                deployment_node,
                deadline_node,
                relation="targets_deadline",
            )

    # ========================================================
    # Deadline → Milestone / Issue
    # ========================================================

    for deadline in dataset.get(
        "deadlines",
        [],
    ):

        if not isinstance(
            deadline,
            dict,
        ):
            continue

        deadline_id = _get_id(
            deadline
        )

        if deadline_id is None:
            continue

        deadline_node = (
            f"deadline:{deadline_id}"
        )

        if deadline_node not in graph:
            continue

        # Deadline may directly reference a milestone.
        milestone_ref = (
            deadline.get("milestone_id")
            or deadline.get("milestone")
        )

        if milestone_ref is not None:

            milestone_node = _find_node(
                graph,
                _extract_reference(
                    milestone_ref
                ),
                preferred_type="milestone",
            )

            if milestone_node:

                graph.add_edge(
                    milestone_node,
                    deadline_node,
                    relation="has_deadline",
                )

        # Deadline may directly reference an issue.
        issue_ref = (
            deadline.get("issue_id")
            or deadline.get("issue")
        )

        if issue_ref is not None:

            issue_node = _find_node(
                graph,
                _extract_reference(
                    issue_ref
                ),
                preferred_type="issue",
            )

            if issue_node:

                graph.add_edge(
                    issue_node,
                    deadline_node,
                    relation="has_deadline",
                )

    # ========================================================
    # Source code files and dependency intelligence
    # ========================================================

    files_data = dataset.get("files")
    if isinstance(files_data, dict):
        from app.dependency_intelligence.progressive_manager import DependencyIntelligenceManager
        from app.dependency_intelligence.graph_integrator import integrate_dependency_intelligence

        mgr = DependencyIntelligenceManager()
        intel = mgr.analyze_project_files(files_data)
        integrate_dependency_intelligence(graph, intel)

    elif isinstance(files_data, list):
        for f in files_data:
            if isinstance(f, str):
                node_id = f"file:{f}"
                if not graph.has_node(node_id):
                    graph.add_node(node_id, type="file", label=f, data={"id": f})
            elif isinstance(f, dict) and f.get("path"):
                f_path = str(f["path"])
                node_id = f"file:{f_path}"
                if not graph.has_node(node_id):
                    graph.add_node(node_id, type="file", label=f_path, data=f)

    # Direct source dependencies list
    source_deps = dataset.get("source_dependencies") or dataset.get("code_dependencies")
    if isinstance(source_deps, list):
        for dep in source_deps:
            if isinstance(dep, dict):
                src = str(dep.get("source", dep.get("from", "")))
                tgt = str(dep.get("target", dep.get("to", "")))
                rel = str(dep.get("relation", dep.get("relationship_type", "imports"))).lower()
                if src and tgt:
                    src_node = src if ":" in src else f"file:{src}"
                    tgt_node = tgt if ":" in tgt else f"file:{tgt}"
                    if not graph.has_node(src_node):
                        graph.add_node(src_node, type="file", label=src, data={"id": src})
                    if not graph.has_node(tgt_node):
                        graph.add_node(tgt_node, type="file", label=tgt, data={"id": tgt})
                    graph.add_edge(src_node, tgt_node, relation=rel, data=dep)

    return graph