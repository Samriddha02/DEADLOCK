from app.models.project_models import (
    ProjectData,
    ProjectInfo,
    Developer,
    Issue,
    PullRequest,
    Commit,
    Milestone,
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
        if isinstance(issue, dict) and "pull_request" not in issue
    ]

    parsed_issues = [
        parse_issue(issue)
        for issue in real_issues
        if isinstance(issue, dict) and "id" in issue
    ]

    parsed_prs = [
        parse_pull_request(pr)
        for pr in pull_requests
        if isinstance(pr, dict) and "id" in pr
    ]

    parsed_commits = [
        parse_commit(commit)
        for commit in commits
        if isinstance(commit, dict)
    ]

    parsed_milestones = [
        parse_milestone(milestone)
        for milestone in milestones
        if isinstance(milestone, dict) and "id" in milestone
    ]

    # Extract unique developers across issues, PRs, and commits
    developer_logins: set[str] = set()
    for item in parsed_issues:
        if item.get("assignee"):
            developer_logins.add(str(item["assignee"]))
    for item in parsed_prs:
        if item.get("user"):
            developer_logins.add(str(item["user"]))
        if item.get("assignee"):
            developer_logins.add(str(item["assignee"]))
    for item in parsed_commits:
        if item.get("author"):
            developer_logins.add(str(item["author"]))

    developers = [
        Developer(
            id=login,
            username=login,
            name=login,
        )
        for login in sorted(developer_logins)
    ]

    canonical_issues = [
        Issue(
            id=str(item.get("id", "")),
            number=item.get("number"),
            title=str(item.get("title", "")),
            status=str(item.get("state", "open")),
            assignee_id=item.get("assignee"),
            assignee=item.get("assignee"),
            milestone=item.get("milestone"),
            labels=item.get("labels", []),
            created_at=item.get("created_at"),
            updated_at=item.get("updated_at"),
        )
        for item in parsed_issues
    ]

    canonical_prs = [
        PullRequest(
            id=str(item.get("id", "")),
            number=item.get("number"),
            title=str(item.get("title", "")),
            status=str(item.get("state", "open")),
            author_id=item.get("user"),
            author=item.get("user"),
            assignee_id=item.get("assignee"),
            assignee=item.get("assignee"),
            labels=item.get("labels", []),
            draft=bool(item.get("draft", False)),
            created_at=item.get("created_at"),
            updated_at=item.get("updated_at"),
            merged_at=item.get("merged_at"),
        )
        for item in parsed_prs
    ]

    canonical_commits = [
        Commit(
            id=str(item.get("sha", "")),
            hash=str(item.get("sha", "")),
            sha=str(item.get("sha", "")),
            message=str(item.get("message", "")),
            author_id=item.get("author"),
            author=item.get("author"),
            timestamp=item.get("date"),
            date=item.get("date"),
        )
        for item in parsed_commits
    ]

    canonical_milestones = [
        Milestone(
            id=str(item.get("id", "")),
            number=item.get("number"),
            title=str(item.get("title", "")),
            status=str(item.get("state", "open")),
            due_on=item.get("due_on"),
            open_issues=item.get("open_issues", 0),
            closed_issues=item.get("closed_issues", 0),
        )
        for item in parsed_milestones
    ]

    return ProjectData(
        owner=owner,
        repo=repo,
        project=ProjectInfo(
            id=f"{owner}/{repo}",
            name=repo,
            repository=f"github.com/{owner}/{repo}",
        ),
        developers=developers,
        issues=canonical_issues,
        pull_requests=canonical_prs,
        commits=canonical_commits,
        milestones=canonical_milestones,
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