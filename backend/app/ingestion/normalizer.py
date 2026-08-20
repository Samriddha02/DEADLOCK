from app.models.github_models import (
    ProjectData,
    GitHubIssue,
    GitHubPullRequest,
    GitHubCommit,
    GitHubMilestone,
)

from app.ingestion.github_parser import (
    parse_issue,
    parse_pull_request,
    parse_commit,
    parse_milestone,
)


def normalize_project(
    owner: str,
    repo: str,
    issues: list[dict],
    pull_requests: list[dict],
    commits: list[dict],
    milestones: list[dict],
) -> ProjectData:

    # GitHub's /issues endpoint also returns pull requests.
    # Remove those duplicates from the issue list.
    real_issues = [
        issue
        for issue in issues
        if "pull_request" not in issue
    ]

    return ProjectData(
        owner=owner,
        repo=repo,

        issues=[
            GitHubIssue(**parse_issue(issue))
            for issue in real_issues
        ],

        pull_requests=[
            GitHubPullRequest(**parse_pull_request(pr))
            for pr in pull_requests
        ],

        commits=[
            GitHubCommit(**parse_commit(commit))
            for commit in commits
        ],

        milestones=[
            GitHubMilestone(**parse_milestone(milestone))
            for milestone in milestones
        ],
    )


async def fetch_project(
    client,
    owner: str,
    repo: str,
) -> ProjectData:

    # Fetch raw data from GitHub
    issues = await client.get_issues(
        owner,
        repo
    )

    pull_requests = await client.get_pull_requests(
        owner,
        repo
    )

    commits = await client.get_commits(
        owner,
        repo
    )

    milestones = await client.get_milestones(
        owner,
        repo
    )

    # Convert raw GitHub data into our models
    return normalize_project(
        owner=owner,
        repo=repo,
        issues=issues,
        pull_requests=pull_requests,
        commits=commits,
        milestones=milestones,
    )