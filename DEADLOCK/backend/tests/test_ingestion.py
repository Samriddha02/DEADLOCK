import pytest

from app.ingestion.github_parser import (
    parse_issue,
    parse_pull_request,
)


def test_parse_issue():
    raw = {
        "id": 101,
        "number": 1,
        "title": "Fix authentication",
        "state": "open",
        "assignee": {"login": "developer"},
        "labels": [{"name": "bug"}],
        "milestone": {"title": "v1"},
    }

    result = parse_issue(raw)

    assert result["number"] == 1
    assert result["title"] == "Fix authentication"
    assert result["labels"] == ["bug"]
    assert result["milestone"] == "v1"


def test_parse_pull_request():
    raw = {
        "id": 201,
        "number": 5,
        "title": "Fix #1",
        "state": "open",
        "user": {"login": "developer"},
        "draft": True,
        "labels": [],
    }

    result = parse_pull_request(raw)

    assert result["number"] == 5
    assert result["user"] == "developer"
    assert result["draft"] is True