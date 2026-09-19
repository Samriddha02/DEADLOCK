"""
normalizer.py — GitHub → ProjectData

Fetches and normalises real GitHub data into DEADLOCK's canonical
ProjectData model.  Every entity produced here must be traceable to
an actual GitHub API response.  Nothing is invented.

Fetched endpoints:
  GET /repos/{owner}/{repo}/issues          (issues + PR stubs, state=all)
  GET /repos/{owner}/{repo}/pulls           (PR metadata, state=all)
  GET /repos/{owner}/{repo}/pulls/{n}/reviews  (per open PR, up to MAX_REVIEW_PRS)
  GET /repos/{owner}/{repo}/pulls/{n}/files    (per open PR, up to MAX_FILES_PRS)
  GET /repos/{owner}/{repo}/commits
  GET /repos/{owner}/{repo}/milestones
  GET /repos/{owner}/{repo}/contributors
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.models.project_models import (
    ProjectData,
    ProjectInfo,
    Developer,
    Issue,
    PullRequest,
    Commit,
    Milestone,
    Review,
)
from app.ingestion.github_parser import (
    parse_issue,
    parse_pull_request,
    parse_commit,
    parse_milestone,
)

logger = logging.getLogger(__name__)

# Maximum number of PRs for which we fetch per-PR reviews and files.
# Keeps the ingestion O(n) in the normal case while staying within
# GitHub rate limits for large repos.
MAX_REVIEW_PRS = 30
MAX_FILES_PRS  = 30


# ============================================================
# Helpers
# ============================================================

def _login(obj: Any) -> str | None:
    """Extract a GitHub login from a raw field value."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get("login") or None
    return str(obj) if obj else None


def _parse_review(raw: dict[str, Any], pr_number: int) -> dict[str, Any]:
    """Convert a raw GitHub review response to a normalised dict."""
    reviewer = _login(raw.get("user"))
    state = str(raw.get("state", "")).upper()
    # GitHub states: APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING
    # Map to our canonical statuses used by the risk engine
    status_map = {
        "APPROVED":           "approved",
        "CHANGES_REQUESTED":  "changes_requested",
        "COMMENTED":          "commented",
        "DISMISSED":          "dismissed",
        "PENDING":            "pending",
    }
    status = status_map.get(state, state.lower())
    return {
        "id":          str(raw.get("id", "")),
        "pr_id":       str(pr_number),
        "reviewer_id": reviewer,
        "status":      status,
        "state":       state,
        "comment":     raw.get("body") or "",
        "submitted_at": raw.get("submitted_at"),
    }


# ============================================================
# normalize_project  (pure, no I/O)
# ============================================================

def normalize_project(
    owner: str,
    repo: str,
    issues: list[dict],
    pull_requests: list[dict],
    commits: list[dict],
    milestones: list[dict],
    reviews_by_pr: dict[int, list[dict]] | None = None,
    files_by_pr: dict[int, list[dict]] | None = None,
    contributors: list[dict] | None = None,
) -> ProjectData:
    """
    Convert raw GitHub API payloads into a canonical ProjectData.

    Parameters
    ----------
    reviews_by_pr  : {pr_number: [raw_review, ...]}
    files_by_pr    : {pr_number: [{"filename": str, ...}, ...]}
    contributors   : [{"login": str, "contributions": int}, ...]
    """
    reviews_by_pr = reviews_by_pr or {}
    files_by_pr   = files_by_pr   or {}
    contributors  = contributors  or []

    # GitHub's /issues endpoint also returns pull requests — strip them.
    real_issues = [
        i for i in issues
        if isinstance(i, dict) and "pull_request" not in i
    ]

    parsed_issues = [
        parse_issue(i)
        for i in real_issues
        if isinstance(i, dict) and "id" in i
    ]

    parsed_prs = [
        parse_pull_request(pr)
        for pr in pull_requests
        if isinstance(pr, dict) and "id" in pr
    ]

    parsed_commits = [
        parse_commit(c)
        for c in commits
        if isinstance(c, dict)
    ]

    parsed_milestones = [
        parse_milestone(m)
        for m in milestones
        if isinstance(m, dict) and "id" in m
    ]

    # --------------------------------------------------------
    # Developers — combine from contributors, assignees,
    # PR authors and commit authors.
    # Contributor list is authoritative for login/commit count.
    # --------------------------------------------------------
    dev_map: dict[str, dict[str, Any]] = {}

    # Seed from contributor list (most reliable)
    for c in contributors:
        login = _login(c)
        if login:
            dev_map[login] = {
                "id":           login,
                "username":     login,
                "name":         login,
                "contributions": int(c.get("contributions", 0)),
            }

    def _ensure_dev(login: str | None) -> None:
        if login and login not in dev_map:
            dev_map[login] = {"id": login, "username": login, "name": login}

    for item in parsed_issues:
        _ensure_dev(item.get("assignee"))
    for item in parsed_prs:
        _ensure_dev(item.get("user"))
        _ensure_dev(item.get("assignee"))
        for reviewer_login in (item.get("requested_reviewers") or []):
            _ensure_dev(reviewer_login)
    for item in parsed_commits:
        _ensure_dev(item.get("author"))
    for reviews in reviews_by_pr.values():
        for rv in reviews:
            reviewer = _login(rv.get("user"))
            _ensure_dev(reviewer)

    developers = [
        Developer(
            id=info["id"],
            username=info.get("username", info["id"]),
            name=info.get("name", info["id"]),
        )
        for info in sorted(dev_map.values(), key=lambda x: x["id"])
    ]

    # --------------------------------------------------------
    # Issues
    # --------------------------------------------------------
    canonical_issues = [
        Issue(
            id=str(item.get("id", "")),
            number=item.get("number"),
            title=str(item.get("title", "")),
            status=str(item.get("state", "open")),
            state=str(item.get("state", "open")),
            assignee_id=item.get("assignee"),
            assignee=item.get("assignee"),
            milestone=item.get("milestone"),
            labels=item.get("labels", []),
            created_at=item.get("created_at"),
            updated_at=item.get("updated_at"),
            closed_at=item.get("closed_at"),
        )
        for item in parsed_issues
    ]

    # --------------------------------------------------------
    # Pull Requests  (include reviewer logins + linked issues
    # extracted from the PR body / title heuristic)
    # --------------------------------------------------------
    canonical_prs: list[PullRequest] = []
    for item in parsed_prs:
        pr_number = item.get("number")

        # Reviewer logins from requested_reviewers
        reviewer_logins: list[str] = item.get("requested_reviewers") or []

        # Files changed for this PR
        changed_files: list[str] = []
        if pr_number and pr_number in files_by_pr:
            changed_files = [
                f.get("filename", "")
                for f in files_by_pr[pr_number]
                if f.get("filename")
            ]

        canonical_prs.append(
            PullRequest(
                id=str(item.get("id", "")),
                number=pr_number,
                title=str(item.get("title", "")),
                status=str(item.get("state", "open")),
                state=str(item.get("state", "open")),
                author_id=item.get("user"),
                author=item.get("user"),
                assignee_id=item.get("assignee"),
                assignee=item.get("assignee"),
                reviewers=reviewer_logins,
                labels=item.get("labels", []),
                draft=bool(item.get("draft", False)),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                merged_at=item.get("merged_at"),
                closed_at=item.get("closed_at"),
            )
        )

    # --------------------------------------------------------
    # Commits
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Milestones — include due_on as due_date too
    # --------------------------------------------------------
    canonical_milestones = [
        Milestone(
            id=str(item.get("id", "")),
            number=item.get("number"),
            title=str(item.get("title", "")),
            status=str(item.get("state", "open")),
            state=str(item.get("state", "open")),
            due_on=item.get("due_on"),
            due_date=item.get("due_on"),  # expose as due_date too
            open_issues=item.get("open_issues", 0),
            closed_issues=item.get("closed_issues", 0),
        )
        for item in parsed_milestones
    ]

    # --------------------------------------------------------
    # Reviews — flatten reviews_by_pr dict into Review objects
    # --------------------------------------------------------
    canonical_reviews: list[Review] = []
    for pr_number, raw_reviews in reviews_by_pr.items():
        for rv in raw_reviews:
            reviewer = _login(rv.get("user"))
            state = str(rv.get("state", "")).upper()
            status_map = {
                "APPROVED":          "approved",
                "CHANGES_REQUESTED": "changes_requested",
                "COMMENTED":         "commented",
                "DISMISSED":         "dismissed",
                "PENDING":           "pending",
            }
            canonical_reviews.append(
                Review(
                    id=str(rv.get("id", f"rev_{pr_number}_{len(canonical_reviews)}")),
                    pr_id=str(pr_number),
                    reviewer_id=reviewer,
                    status=status_map.get(state, state.lower()),
                    state=state,
                    comment=rv.get("body") or "",
                    submitted_at=rv.get("submitted_at"),
                )
            )

    # --------------------------------------------------------
    # Store changed files per PR on the project dict as
    # source_dependencies so graph builder can use them
    # --------------------------------------------------------
    source_deps: list[dict[str, Any]] = []
    for pr in canonical_prs:
        pr_number = pr.number
        if pr_number and pr_number in files_by_pr:
            for f in files_by_pr[pr_number]:
                fname = f.get("filename", "")
                if fname:
                    source_deps.append({
                        "source": f"pull_request:{pr.id}",
                        "target": f"file:{fname}",
                        "relation": "modifies",
                        "pr_number": pr_number,
                        "filename": fname,
                        "status": f.get("status", "modified"),
                        "additions": f.get("additions", 0),
                        "deletions": f.get("deletions", 0),
                        "inferred": False,
                        "confidence": 1.0,
                    })

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
        reviews=canonical_reviews,
        # Store file-change edges for the graph builder
        # (model has extra="allow" so this passes through to SQLite JSON)
        source_dependencies=source_deps,
    )


# ============================================================
# fetch_project  (async, calls GitHub API)
# ============================================================

async def fetch_project(
    client,
    owner: str,
    repo: str,
) -> ProjectData:
    """
    Fetch real GitHub data and normalise it into a ProjectData.

    Strategy:
    1. Fetch issues, PRs, commits, milestones, contributors in parallel.
    2. For the most recently updated open/draft PRs (up to MAX_REVIEW_PRS),
       fetch reviews and changed files in parallel.
    3. Normalise everything into the canonical model.
    """

    # --------------------------------------------------------
    # Phase 1: bulk fetches in parallel
    # --------------------------------------------------------
    logger.info("Fetching GitHub data for %s/%s", owner, repo)

    issues_task      = client.get_issues(owner, repo)
    prs_task         = client.get_pull_requests(owner, repo)
    commits_task     = client.get_commits(owner, repo)
    milestones_task  = client.get_milestones(owner, repo)
    contribs_task    = client.get_contributors(owner, repo)

    (
        issues,
        pull_requests,
        commits,
        milestones,
        contributors,
    ) = await asyncio.gather(
        issues_task,
        prs_task,
        commits_task,
        milestones_task,
        contribs_task,
        return_exceptions=False,
    )

    # --------------------------------------------------------
    # Phase 2: per-PR reviews + files (for open/draft PRs)
    # --------------------------------------------------------
    # Prioritise open PRs, then recently updated closed ones.
    open_prs = [
        pr for pr in pull_requests
        if isinstance(pr, dict) and pr.get("state") == "open"
    ]
    recently_closed = [
        pr for pr in pull_requests
        if isinstance(pr, dict) and pr.get("state") != "open"
    ]
    # Use up to MAX_REVIEW_PRS total, open PRs first
    prs_for_detail = (open_prs + recently_closed)[:MAX_REVIEW_PRS]

    reviews_by_pr: dict[int, list[dict]] = {}
    files_by_pr:   dict[int, list[dict]] = {}

    if prs_for_detail:
        pr_numbers = [
            int(pr["number"])
            for pr in prs_for_detail
            if pr.get("number") is not None
        ]

        review_tasks = [
            client.get_pr_reviews(owner, repo, n) for n in pr_numbers[:MAX_REVIEW_PRS]
        ]
        files_tasks = [
            client.get_pr_files(owner, repo, n) for n in pr_numbers[:MAX_FILES_PRS]
        ]

        review_results = await asyncio.gather(*review_tasks, return_exceptions=True)
        files_results  = await asyncio.gather(*files_tasks,  return_exceptions=True)

        for n, result in zip(pr_numbers[:MAX_REVIEW_PRS], review_results):
            if isinstance(result, list):
                reviews_by_pr[n] = result
            else:
                reviews_by_pr[n] = []

        for n, result in zip(pr_numbers[:MAX_FILES_PRS], files_results):
            if isinstance(result, list):
                files_by_pr[n] = result
            else:
                files_by_pr[n] = []

    logger.info(
        "%s/%s: %d issues, %d PRs, %d commits, %d milestones, "
        "%d contributors, %d reviews across %d PRs",
        owner, repo,
        len([i for i in issues if "pull_request" not in i]),
        len(pull_requests),
        len(commits),
        len(milestones),
        len(contributors),
        sum(len(v) for v in reviews_by_pr.values()),
        len(reviews_by_pr),
    )

    return normalize_project(
        owner=owner,
        repo=repo,
        issues=issues,
        pull_requests=pull_requests,
        commits=commits,
        milestones=milestones,
        reviews_by_pr=reviews_by_pr,
        files_by_pr=files_by_pr,
        contributors=contributors,
    )
