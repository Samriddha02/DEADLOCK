"""
detector.py — DEADLOCK Real Risk Detection Engine

Detects verifiable failure-propagation risks from real GitHub project data.

ABSOLUTE RULE: Every risk returned MUST cite specific GitHub entities
(PR numbers, issue numbers, contributor logins, milestone titles) that
actually exist in the project data.  Nothing is fabricated.

Risk signals detected:
  RISK-01  Stale blocking PR — an open PR that has blocking review state
           and is not a draft, sorted by age (oldest = most critical).
  RISK-02  Contributor workload concentration — one contributor owns a
           disproportionate share of open PRs + assigned open issues.
  RISK-03  Overdue / near-due milestone with open issues still attached.
  RISK-04  High-churn PR — touches many files, no approvals, still open.
  RISK-05  Stale open issue — very old unresolved issue in an active repo.

For a repository with no open PRs and no open issues DEADLOCK correctly
returns 0 risks.  That is not a bug.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import networkx as nx

from app.models.risk_models import Risk
from app.graph.graph_builder import build_graph

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

# A PR older than this (days) with blocking reviews is HIGH/CRITICAL
STALE_PR_DAYS_HIGH     = 14
STALE_PR_DAYS_CRITICAL = 30

# Contributor owns this fraction of open PRs → bottleneck
BOTTLENECK_PR_SHARE  = 0.35   # 35 %
BOTTLENECK_MIN_PRS   = 3      # must have at least this many open PRs

# Milestone is "near-due" within this many days
MILESTONE_NEAR_DUE_DAYS = 14

# PR with >= this many changed files is "high-churn"
HIGH_CHURN_FILES = 10

# Issue older than this (days) is "stale"
STALE_ISSUE_DAYS = 90


# ============================================================
# Helpers
# ============================================================

def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def _items(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key, [])
    if not isinstance(value, list):
        return []
    return [_as_dict(item) for item in value if item is not None]


def _id(item: dict[str, Any]) -> str:
    for k in ("id", "number", "sha", "key"):
        v = item.get(k)
        if v is not None:
            return str(v)
    return ""


def _str(val: Any) -> str:
    return str(val).strip() if val is not None else ""


def _status(item: dict[str, Any]) -> str:
    return _str(item.get("status") or item.get("state") or "").lower()


def _is_open(item: dict[str, Any]) -> bool:
    s = _status(item)
    return s in {"open", "opened", "in_progress", "in progress", "pending", "blocked"}


def _login(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, dict):
        return _str(val.get("login") or val.get("id") or val.get("username")) or None
    return _str(val) or None


def _parse_dt(val: Any) -> datetime | None:
    if not val:
        return None
    try:
        s = str(val).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _days_ago(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    return (now - dt).days


def _days_until(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    return (dt - now).days


def _references(item: dict[str, Any], *fields: str) -> list[str]:
    result: list[str] = []
    for f in fields:
        v = item.get(f)
        if v is None:
            continue
        items = v if isinstance(v, list) else [v]
        for entry in items:
            if isinstance(entry, dict):
                ref = _str(entry.get("id") or entry.get("number") or entry.get("login"))
            else:
                ref = _str(entry)
            if ref:
                result.append(ref)
    return result


def _build_graph(data: dict[str, Any]) -> nx.DiGraph:
    try:
        return build_graph(data)
    except Exception:
        return nx.DiGraph()


def _sanitize(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bad = {
        "token", "access_token", "github_token", "secret",
        "password", "api_key", "private_key", "credentials",
    }
    return [
        {k: v for k, v in item.items() if k.lower() not in bad}
        for item in evidence
        if isinstance(item, dict)
    ]


def _pr_display(pr: dict[str, Any]) -> str:
    num = pr.get("number") or pr.get("id") or "?"
    title = _str(pr.get("title") or "").strip()
    if title:
        return f"PR #{num} — {title[:60]}"
    return f"PR #{num}"


def _issue_display(issue: dict[str, Any]) -> str:
    num = issue.get("number") or issue.get("id") or "?"
    title = _str(issue.get("title") or "").strip()
    if title:
        return f"Issue #{num} — {title[:60]}"
    return f"Issue #{num}"


# ============================================================
# Risk 1 — Stale Blocking PR
#
# Signal: open PR that has at least one "changes_requested" review
#         AND is not a draft AND has been open for >= 7 days.
#
# Worst offender (oldest PR) is reported.
# ============================================================

def _detect_stale_blocking_pr(
    data: dict[str, Any],
    graph: nx.DiGraph,
) -> Risk | None:
    prs      = _items(data, "pull_requests")
    reviews  = _items(data, "reviews")
    owner    = _str(data.get("owner"))
    repo     = _str(data.get("repo"))

    # Index reviews by pr_id → list of review dicts
    reviews_idx: dict[str, list[dict[str, Any]]] = {}
    for rv in reviews:
        pr_ref = _str(rv.get("pr_id") or rv.get("pull_request_id") or "")
        if pr_ref:
            reviews_idx.setdefault(pr_ref, []).append(rv)

    candidates: list[tuple[int, dict[str, Any], list[dict[str, Any]]]] = []

    for pr in prs:
        if not _is_open(pr):
            continue
        if pr.get("draft"):
            continue

        pr_num  = _str(pr.get("number") or pr.get("id") or "")
        pr_id   = _id(pr)

        # Look up reviews by number or id
        rv_list = reviews_idx.get(pr_num, []) or reviews_idx.get(pr_id, [])

        blocking = [
            rv for rv in rv_list
            if _str(rv.get("status") or rv.get("state") or "").lower()
               in {"changes_requested", "changes required"}
        ]

        if not blocking:
            continue

        opened_dt = _parse_dt(pr.get("created_at"))
        age_days  = _days_ago(opened_dt) or 0

        if age_days < 7:
            continue

        candidates.append((age_days, pr, blocking))

    if not candidates:
        return None

    # Pick worst offender (oldest)
    candidates.sort(key=lambda t: t[0], reverse=True)
    age_days, pr, blocking_reviews = candidates[0]

    pr_num   = pr.get("number") or pr.get("id")
    pr_title = _str(pr.get("title") or "")
    author   = _login(pr.get("author") or pr.get("author_id") or pr.get("user"))

    severity    = "CRITICAL" if age_days >= STALE_PR_DAYS_CRITICAL else "HIGH"
    probability = min(0.98, 0.60 + age_days * 0.012)

    # Downstream nodes in the graph
    pr_node = f"pull_request:{pr.get('id') or pr_num}"
    downstream: list[str] = []
    if graph.has_node(pr_node):
        try:
            downstream = [
                n for n in nx.descendants(graph, pr_node)
                if graph.nodes[n].get("type") in {"issue", "milestone", "deployment", "deadline"}
            ]
        except Exception:
            downstream = []

    causal: list[str] = [str(pr_num)]
    for n in downstream[:4]:
        causal.append(n.split(":", 1)[-1])

    reviewer_logins = list({
        _str(rv.get("reviewer_id") or rv.get("user") or "")
        for rv in blocking_reviews
        if rv.get("reviewer_id") or rv.get("user")
    })

    evidence = _sanitize([
        {
            "type":          "pull_request",
            "id":            str(pr_num),
            "number":        pr_num,
            "title":         pr_title,
            "status":        _status(pr),
            "author":        author,
            "age_days":      age_days,
            "url":           f"https://github.com/{owner}/{repo}/pull/{pr_num}" if owner and repo else None,
            "source":        "github_pull_request",
            "inferred":      False,
            "confidence":    1.0,
        },
        {
            "type":          "reviews",
            "count":         len(blocking_reviews),
            "reviewers":     reviewer_logins,
            "status":        "changes_requested",
            "detail":        f"{len(blocking_reviews)} reviewer(s) requested changes on {_pr_display(pr)}",
            "source":        "github_review",
            "inferred":      False,
            "confidence":    1.0,
        },
    ])
    if downstream:
        evidence.append({
            "type":       "causal_chain",
            "path":       causal,
            "detail":     f"Propagation path through {len(downstream)} downstream node(s)",
            "source":     "dependency_graph",
            "inferred":   True,
            "confidence": 0.85,
        })

    author_str = f" by {author}" if author else ""
    title_short = pr_title[:50] if pr_title else f"PR #{pr_num}"

    return Risk(
        risk_id="RISK-01-STALE-BLOCKING-PR",
        title=f"Stale blocking PR: {title_short}",
        severity=severity,
        probability=round(probability, 2),
        root_cause=str(pr_num),
        impact=(
            f"PR #{pr_num}{author_str} has been open {age_days} days with "
            f"{len(blocking_reviews)} blocking review(s) requesting changes. "
            "Until resolved it blocks any dependent work in its propagation path."
        ),
        evidence=evidence,
        causal_chain=causal,
        recommendation=(
            f"Address the review feedback on PR #{pr_num} or reassign it. "
            "If the PR is no longer needed, close it to unblock the dependency chain."
        ),
        verified=True,
        verification_confidence=min(1.0, 0.70 + len(blocking_reviews) * 0.10),
    )


# ============================================================
# Risk 2 — Contributor Workload Concentration (Bottleneck)
#
# Signal: one contributor is the author of >= 35 % of open PRs
#         AND has >= 3 open PRs.
# ============================================================

def _detect_contributor_bottleneck(
    data: dict[str, Any],
    graph: nx.DiGraph,
) -> Risk | None:
    prs        = _items(data, "pull_requests")
    issues     = _items(data, "issues")
    developers = _items(data, "developers")
    owner      = _str(data.get("owner"))
    repo       = _str(data.get("repo"))

    open_prs = [pr for pr in prs if _is_open(pr) and not pr.get("draft")]

    if len(open_prs) < BOTTLENECK_MIN_PRS + 1:
        # Not enough open PRs for a bottleneck to be meaningful
        return None

    # Count open PRs per author
    pr_by_author: dict[str, list[dict[str, Any]]] = {}
    for pr in open_prs:
        author = _login(pr.get("author") or pr.get("author_id") or pr.get("user"))
        if author:
            pr_by_author.setdefault(author, []).append(pr)

    if not pr_by_author:
        return None

    # Find the top contributor
    top_author, top_prs = max(pr_by_author.items(), key=lambda kv: len(kv[1]))
    share = len(top_prs) / len(open_prs)

    if share < BOTTLENECK_PR_SHARE or len(top_prs) < BOTTLENECK_MIN_PRS:
        return None

    # Assigned open issues for this author
    assigned_issues = [
        i for i in issues
        if _is_open(i) and _login(i.get("assignee") or i.get("assignee_id")) == top_author
    ]

    probability = min(0.95, 0.55 + share * 0.80)
    severity    = "CRITICAL" if share >= 0.50 else "HIGH"

    sample_pr_nums = [str(pr.get("number") or pr.get("id")) for pr in top_prs[:5]]
    causal = [top_author] + [f"pull_request:{pr.get('id') or pr.get('number')}" for pr in top_prs[:3]]

    profile_url = f"https://github.com/{top_author}" if top_author else None

    evidence = _sanitize([
        {
            "type":          "developer",
            "id":            top_author,
            "name":          top_author,
            "pr_count":      len(top_prs),
            "share":         round(share, 3),
            "open_issues":   len(assigned_issues),
            "url":           profile_url,
            "source":        "workload_distribution",
            "inferred":      False,
            "confidence":    1.0,
            "detail":        (
                f"{top_author} authored {len(top_prs)} of {len(open_prs)} "
                f"open PRs ({share*100:.0f}%) in {owner}/{repo}"
            ),
        },
        {
            "type":          "open_prs",
            "pr_numbers":    sample_pr_nums,
            "count":         len(top_prs),
            "source":        "github_pull_request",
            "inferred":      False,
            "confidence":    1.0,
            "detail":        f"Open PRs by {top_author}: {', '.join(f'#{n}' for n in sample_pr_nums)}",
        },
    ])

    if assigned_issues:
        evidence.append({
            "type":     "assigned_issues",
            "count":    len(assigned_issues),
            "titles":   [_str(i.get("title") or "")[:50] for i in assigned_issues[:3]],
            "source":   "github_issue",
            "inferred": False,
            "confidence": 1.0,
            "detail":   f"{top_author} also has {len(assigned_issues)} assigned open issue(s)",
        })

    return Risk(
        risk_id="RISK-02-CONTRIBUTOR-BOTTLENECK",
        title=f"Contributor bottleneck: {top_author}",
        severity=severity,
        probability=round(probability, 2),
        root_cause=top_author,
        impact=(
            f"{top_author} is the author of {len(top_prs)} out of {len(open_prs)} "
            f"open PRs ({share*100:.0f}%) in {owner}/{repo}. "
            "If this contributor is unavailable, a large fraction of in-flight "
            "work stalls simultaneously."
        ),
        evidence=evidence,
        causal_chain=causal,
        recommendation=(
            f"Distribute new work more evenly away from {top_author}. "
            "Ensure at least one other contributor is familiar with each "
            "active PR so reviews and merges can proceed independently."
        ),
        verified=True,
        verification_confidence=min(1.0, 0.65 + share * 0.40),
    )


# ============================================================
# Risk 3 — Overdue / Near-Due Milestone with Open Issues
#
# Signal: a milestone that has a due date AND is either past
#         due OR within MILESTONE_NEAR_DUE_DAYS days, AND still
#         has open_issues > 0.
# ============================================================

def _detect_milestone_pressure(
    data: dict[str, Any],
    graph: nx.DiGraph,
) -> Risk | None:
    milestones = _items(data, "milestones")
    issues     = _items(data, "issues")
    owner      = _str(data.get("owner"))
    repo       = _str(data.get("repo"))

    # Build issue index by milestone title (GitHub stores milestone title on issues)
    issues_by_milestone: dict[str, list[dict[str, Any]]] = {}
    for i in issues:
        if not _is_open(i):
            continue
        ms = _str(i.get("milestone") or i.get("milestone_id") or "")
        if ms:
            issues_by_milestone.setdefault(ms, []).append(i)

    candidates: list[tuple[int, dict[str, Any], list[dict[str, Any]]]] = []

    for ms in milestones:
        if not _is_open(ms):
            continue

        due_raw = ms.get("due_on") or ms.get("due_date") or ms.get("target_date")
        if not due_raw:
            continue

        due_dt    = _parse_dt(due_raw)
        days_left = _days_until(due_dt)
        if days_left is None:
            continue

        # Only report if overdue OR within near-due window
        if days_left > MILESTONE_NEAR_DUE_DAYS:
            continue

        ms_title = _str(ms.get("title") or "")

        # Gather open issues for this milestone
        open_issues_for_ms = (
            issues_by_milestone.get(ms_title, [])
            or issues_by_milestone.get(_id(ms), [])
        )

        # Also use the open_issues count stored on the milestone itself
        raw_open = int(ms.get("open_issues") or 0)
        if not open_issues_for_ms and raw_open == 0:
            continue

        total_open = max(raw_open, len(open_issues_for_ms))
        if total_open == 0:
            continue

        candidates.append((days_left, ms, open_issues_for_ms))

    if not candidates:
        return None

    # Most critical = most overdue (smallest / most negative days_left)
    candidates.sort(key=lambda t: t[0])
    days_left, ms, open_issues_for_ms = candidates[0]

    ms_title  = _str(ms.get("title") or _id(ms))
    ms_num    = ms.get("number") or ms.get("id")
    due_raw   = ms.get("due_on") or ms.get("due_date") or ms.get("target_date")
    raw_open  = max(int(ms.get("open_issues") or 0), len(open_issues_for_ms))

    overdue  = days_left < 0
    severity = "CRITICAL" if overdue else "HIGH"
    probability = min(0.97, 0.70 + abs(days_left) * 0.010) if overdue else min(0.85, 0.55 + (MILESTONE_NEAR_DUE_DAYS - days_left) * 0.015)

    ms_url = (
        f"https://github.com/{owner}/{repo}/milestone/{ms_num}"
        if owner and repo and ms_num else None
    )

    sample_issues = [_issue_display(i) for i in open_issues_for_ms[:5]]

    causal = [ms_title] + [str(i.get("number") or i.get("id")) for i in open_issues_for_ms[:4]]

    time_desc = (
        f"{abs(days_left)} day(s) overdue" if overdue
        else f"due in {days_left} day(s)"
    )

    evidence = _sanitize([
        {
            "type":       "milestone",
            "id":         str(ms_num or ms_title),
            "title":      ms_title,
            "due_date":   due_raw,
            "days_left":  days_left,
            "overdue":    overdue,
            "open_issues": raw_open,
            "url":        ms_url,
            "source":     "github_milestone",
            "inferred":   False,
            "confidence": 1.0,
            "detail":     f"Milestone '{ms_title}' is {time_desc} with {raw_open} open issue(s)",
        },
    ])
    if sample_issues:
        evidence.append({
            "type":     "open_issues",
            "count":    raw_open,
            "sample":   sample_issues,
            "source":   "github_issue",
            "inferred": False,
            "confidence": 1.0,
            "detail":   f"Open issues blocking milestone: {'; '.join(sample_issues[:3])}",
        })

    return Risk(
        risk_id="RISK-03-MILESTONE-PRESSURE",
        title=f"Milestone pressure: '{ms_title}' ({time_desc})",
        severity=severity,
        probability=round(probability, 2),
        root_cause=ms_title,
        impact=(
            f"Milestone '{ms_title}' is {time_desc} and still has "
            f"{raw_open} open issue(s) that must be resolved before it "
            "can be closed."
        ),
        evidence=evidence,
        causal_chain=causal,
        recommendation=(
            f"Review the {raw_open} open issue(s) attached to milestone "
            f"'{ms_title}'. Prioritise or de-scope items that cannot be "
            "resolved before the due date."
        ),
        verified=True,
        verification_confidence=0.95,
    )


# ============================================================
# Risk 4 — High-Churn PR (many files changed, no approval)
#
# Signal: open, non-draft PR that modifies >= HIGH_CHURN_FILES
#         files AND has no "approved" review.
# ============================================================

def _detect_high_churn_pr(
    data: dict[str, Any],
    graph: nx.DiGraph,
) -> Risk | None:
    prs      = _items(data, "pull_requests")
    reviews  = _items(data, "reviews")
    owner    = _str(data.get("owner"))
    repo     = _str(data.get("repo"))

    # Source-dependency edges carry file-change information stored by normalizer
    source_deps = data.get("source_dependencies") or []
    # Build index: pr_id → list of filenames changed
    files_by_pr_id: dict[str, list[str]] = {}
    for dep in (source_deps if isinstance(source_deps, list) else []):
        if not isinstance(dep, dict):
            continue
        src = _str(dep.get("source", ""))
        if src.startswith("pull_request:"):
            pr_ref = src.split(":", 1)[1]
            tgt = _str(dep.get("target", ""))
            if tgt.startswith("file:"):
                fname = tgt.split(":", 1)[1]
                files_by_pr_id.setdefault(pr_ref, []).append(fname)

    # Review index: pr_num → statuses
    approved_prs: set[str] = set()
    for rv in reviews:
        pr_ref = _str(rv.get("pr_id") or rv.get("pull_request_id") or "")
        if _str(rv.get("status") or rv.get("state") or "").lower() == "approved":
            approved_prs.add(pr_ref)

    candidates: list[tuple[int, dict[str, Any], list[str]]] = []

    for pr in prs:
        if not _is_open(pr):
            continue
        if pr.get("draft"):
            continue

        pr_id  = _id(pr)
        pr_num = _str(pr.get("number") or pr.get("id") or "")

        changed = files_by_pr_id.get(pr_id, []) or files_by_pr_id.get(pr_num, [])
        if len(changed) < HIGH_CHURN_FILES:
            continue

        # Skip if already approved
        if pr_id in approved_prs or pr_num in approved_prs:
            continue

        candidates.append((len(changed), pr, changed))

    if not candidates:
        return None

    # Worst = most files changed
    candidates.sort(key=lambda t: t[0], reverse=True)
    file_count, pr, changed_files = candidates[0]

    pr_num   = pr.get("number") or pr.get("id")
    pr_title = _str(pr.get("title") or "")
    author   = _login(pr.get("author") or pr.get("author_id") or pr.get("user"))
    age_days = _days_ago(_parse_dt(pr.get("created_at"))) or 0

    pr_url = (
        f"https://github.com/{owner}/{repo}/pull/{pr_num}"
        if owner and repo and pr_num else None
    )

    severity    = "HIGH"
    probability = min(0.90, 0.55 + file_count * 0.008)

    # Sample of changed file paths for evidence
    sample_files = changed_files[:8]

    causal = [str(pr_num)]
    evidence = _sanitize([
        {
            "type":        "pull_request",
            "id":          str(pr_num),
            "number":      pr_num,
            "title":       pr_title,
            "author":      author,
            "age_days":    age_days,
            "files_changed": file_count,
            "url":         pr_url,
            "source":      "github_pull_request",
            "inferred":    False,
            "confidence":  1.0,
            "detail":      f"PR #{pr_num} changes {file_count} files with no approvals",
        },
        {
            "type":      "changed_files",
            "count":     file_count,
            "sample":    sample_files,
            "source":    "github_pr_files",
            "inferred":  False,
            "confidence": 1.0,
            "detail":    f"Files changed include: {', '.join(sample_files[:4])}",
        },
    ])

    return Risk(
        risk_id="RISK-04-HIGH-CHURN-PR",
        title=f"High-churn PR without approval: {_pr_display(pr)}",
        severity=severity,
        probability=round(probability, 2),
        root_cause=str(pr_num),
        impact=(
            f"PR #{pr_num} modifies {file_count} files and has no approvals. "
            "Large unreviewed changesets increase the probability of regressions "
            "and make rollback harder."
        ),
        evidence=evidence,
        causal_chain=causal,
        recommendation=(
            f"Request reviews for PR #{pr_num} from contributors familiar with "
            "the changed files. Consider splitting the PR into smaller, "
            "independently reviewable units."
        ),
        verified=True,
        verification_confidence=0.85,
    )


# ============================================================
# Risk 5 — Long-Stale Open Issue
#
# Signal: an open issue that has not been updated in
#         >= STALE_ISSUE_DAYS days (default 90).
# ============================================================

def _detect_stale_issue(
    data: dict[str, Any],
    graph: nx.DiGraph,
) -> Risk | None:
    issues = _items(data, "issues")
    owner  = _str(data.get("owner"))
    repo   = _str(data.get("repo"))

    candidates: list[tuple[int, dict[str, Any]]] = []

    for issue in issues:
        if not _is_open(issue):
            continue

        updated_dt = _parse_dt(issue.get("updated_at") or issue.get("created_at"))
        staleness  = _days_ago(updated_dt)
        if staleness is None or staleness < STALE_ISSUE_DAYS:
            continue

        candidates.append((staleness, issue))

    if not candidates:
        return None

    candidates.sort(key=lambda t: t[0], reverse=True)
    staleness, issue = candidates[0]

    issue_num   = issue.get("number") or issue.get("id")
    issue_title = _str(issue.get("title") or "")
    assignee    = _login(issue.get("assignee") or issue.get("assignee_id"))
    labels      = issue.get("labels") or []
    ms_title    = _str(issue.get("milestone") or "")

    issue_url = (
        f"https://github.com/{owner}/{repo}/issues/{issue_num}"
        if owner and repo and issue_num else None
    )

    severity    = "HIGH" if staleness >= 180 else "MEDIUM"
    probability = min(0.85, 0.40 + staleness * 0.002)

    causal = [str(issue_num)]
    if ms_title:
        causal.append(ms_title)

    evidence = _sanitize([
        {
            "type":        "issue",
            "id":          str(issue_num),
            "number":      issue_num,
            "title":       issue_title,
            "assignee":    assignee,
            "labels":      labels,
            "milestone":   ms_title or None,
            "stale_days":  staleness,
            "updated_at":  issue.get("updated_at"),
            "url":         issue_url,
            "source":      "github_issue",
            "inferred":    False,
            "confidence":  1.0,
            "detail":      (
                f"Issue #{issue_num} has not been updated in {staleness} days"
                + (f" (assigned to {assignee})" if assignee else "")
            ),
        },
    ])

    total_stale = len(candidates)
    if total_stale > 1:
        evidence.append({
            "type":     "stale_issue_count",
            "count":    total_stale,
            "detail":   f"{total_stale} issues stale for >= {STALE_ISSUE_DAYS} days in this repo",
            "source":   "github_issue",
            "inferred": False,
            "confidence": 1.0,
        })

    return Risk(
        risk_id="RISK-05-STALE-ISSUE",
        title=f"Stale open issue: {issue_title[:55] or f'Issue #{issue_num}'}",
        severity=severity,
        probability=round(probability, 2),
        root_cause=str(issue_num),
        impact=(
            f"Issue #{issue_num} has been open without activity for "
            f"{staleness} days"
            + (f", assigned to {assignee}" if assignee else "")
            + f". There are {total_stale} stale issue(s) in this repository."
        ),
        evidence=evidence,
        causal_chain=causal,
        recommendation=(
            f"Triage Issue #{issue_num}: update its status, re-assign it, "
            "add it to a milestone, or close it if it is no longer relevant."
        ),
        verified=True,
        verification_confidence=0.90,
    )


# ============================================================
# validate_causal_path  (re-exported for tests / other modules)
# ============================================================

def validate_causal_path(
    graph: nx.DiGraph,
    path: list[str],
) -> bool:
    from app.graph.graph_builder import validate_causal_path as _vcp
    return _vcp(graph, path)


# ============================================================
# Main entry point
# ============================================================

def detect_risks(
    project: Any,
    graph: Any = None,
) -> list[Risk]:
    """
    Detect evidence-backed risks from real GitHub project data.

    Returns a list of Risk objects.  Each risk cites specific GitHub
    entities (PR numbers, contributor logins, milestone names) that
    exist in the provided project data.

    Returns [] when the project has no detectable risk signals.
    That is CORRECT behaviour — not a pipeline failure.
    """
    data = _as_dict(project)
    if not data:
        return []

    # Unwrap nested project_data wrapper if present
    if isinstance(data.get("project_data"), dict):
        data = data["project_data"]

    # Attach owner/repo from the project key if they exist at top level
    if not data.get("owner"):
        proj = data.get("project") or {}
        if isinstance(proj, dict):
            repo_str = _str(proj.get("repository") or "")
            if "/" in repo_str:
                parts = repo_str.replace("github.com/", "").split("/")
                if len(parts) >= 2:
                    data = dict(data)
                    data["owner"] = parts[-2]
                    data["repo"]  = parts[-1]

    built_graph = _build_graph(data) if graph is None else graph

    risks: list[Risk] = []

    detectors = [
        _detect_stale_blocking_pr,
        _detect_contributor_bottleneck,
        _detect_milestone_pressure,
        _detect_high_churn_pr,
        _detect_stale_issue,
    ]

    for detector in detectors:
        try:
            risk = detector(data, built_graph)
            if risk is not None:
                risks.append(risk)
        except Exception as exc:
            logger.warning("Detector %s raised: %s", detector.__name__, exc, exc_info=True)

    # Stable ordering: CRITICAL first, then HIGH, MEDIUM, LOW; within same
    # severity keep the detection order (most specific first)
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    risks.sort(key=lambda r: severity_order.get(r.severity, 9))

    return risks
