from app.models.github_models import (
    ProjectData,
    GitHubIssue,
    GitHubMilestone,
)

from app.graph.graph_builder import build_graph


def test_graph_building():

    project = ProjectData(
        owner="test",
        repo="demo",

        issues=[
            GitHubIssue(
                id=1,
                number=1,
                title="Authentication",
                state="open",
                milestone="v1",
            )
        ],

        milestones=[
            GitHubMilestone(
                id=10,
                number=1,
                title="v1",
                state="open",
            )
        ],
    )

    graph = build_graph(project)

    assert "issue:1" in graph.nodes
    assert "milestone:1" in graph.nodes

    assert graph.has_edge(
        "issue:1",
        "milestone:1"
    )