from typing import Any


def labels_from(item: dict[str, Any]) -> list[str]:
    """
    Extract label names from a GitHub issue or PR.
    """
    return [
        str(label.get("name", ""))
        for label in item.get("labels", [])
        if label.get("name")
    ]


def parse_issue(item: dict[str, Any]) -> dict[str, Any]:
    """
    Convert raw GitHub issue data into our normalized format.
    """
    return {
        "id": item["id"],
        "number": item["number"],
        "title": item.get("title", ""),
        "state": item.get("state", ""),
        "assignee": (
            item.get("assignee") or {}
        ).get("login"),
        "labels": labels_from(item),
        "milestone": (
            item.get("milestone") or {}
        ).get("title"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def parse_pull_request(
    item: dict[str, Any]
) -> dict[str, Any]:
    """
    Convert raw GitHub PR data into our normalized format.
    """
    return {
        "id": item["id"],
        "number": item["number"],
        "title": item.get("title", ""),
        "state": item.get("state", ""),
        "user": (
            item.get("user") or {}
        ).get("login"),
        "assignee": (
            item.get("assignee") or {}
        ).get("login"),
        "labels": labels_from(item),
        "draft": bool(item.get("draft", False)),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "merged_at": item.get("merged_at"),
    }


def parse_commit(
    item: dict[str, Any]
) -> dict[str, Any]:
    """
    Convert raw GitHub commit data.
    """
    commit = item.get("commit", {})

    author = (
        item.get("author") or {}
    ).get("login")

    commit_author = (
        commit.get("author") or {}
    )

    return {
        "sha": item.get("sha", ""),
        "message": (
            commit.get("message") or ""
        ).splitlines()[0],
        "author": author,
        "date": commit_author.get("date"),
    }


def parse_milestone(
    item: dict[str, Any]
) -> dict[str, Any]:
    """
    Convert raw GitHub milestone data.
    """
    return {
        "id": item["id"],
        "number": item["number"],
        "title": item.get("title", ""),
        "state": item.get("state", ""),
        "due_on": item.get("due_on"),
        "open_issues": item.get("open_issues", 0),
        "closed_issues": item.get("closed_issues", 0),
    }