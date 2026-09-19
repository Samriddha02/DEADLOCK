from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CanonicalBaseModel(BaseModel):
    """Base model that preserves extra fields, allows population by name, and auto-coerces models."""
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        from_attributes=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: Any) -> Any:
        if hasattr(data, "model_dump") and callable(data.model_dump):
            return data.model_dump()
        if hasattr(data, "dict") and callable(data.dict):
            return data.dict()
        return data


# ============================================================
# 1. Project Info
# ============================================================

class ProjectInfo(CanonicalBaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    repository: Optional[str] = None
    created_at: Optional[str] = None
    default_branch: Optional[str] = "main"


# ============================================================
# 2. Developer
# ============================================================

class Developer(CanonicalBaseModel):
    id: str
    name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    timezone: Optional[str] = None


# ============================================================
# 3. Milestone
# ============================================================

class Milestone(CanonicalBaseModel):
    id: str | int
    number: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = "open"
    state: Optional[str] = None
    created_at: Optional[str] = None
    target_date: Optional[str] = None
    due_on: Optional[str] = None
    due_date: Optional[str] = None
    open_issues: int = 0
    closed_issues: int = 0
    simulated_delay_days: Optional[int] = None
    simulated_overdue: Optional[bool] = None


# ============================================================
# 4. Deadline
# ============================================================

class Deadline(CanonicalBaseModel):
    id: str
    title: str
    milestone_id: Optional[str] = None
    due_date: Optional[str] = None
    due_at: Optional[str] = None
    due_on: Optional[str] = None
    description: Optional[str] = None
    deployment_id: Optional[str] = None
    issue_id: Optional[str] = None
    simulated_delay_days: Optional[int] = None
    simulated_overdue: Optional[bool] = None


# ============================================================
# 5. Issue
# ============================================================

class Issue(CanonicalBaseModel):
    id: str | int
    number: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = "open"
    state: Optional[str] = None
    priority: Optional[str] = None
    reporter_id: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee: Optional[str] = None
    developer_id: Optional[str] = None
    milestone_id: Optional[str] = None
    milestone: Optional[str] = None
    estimated_hours: Optional[float] = None
    estimate_hours: Optional[float] = None
    hours: Optional[float] = None
    labels: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    simulated_delay_days: Optional[int] = None
    simulated_overdue: Optional[bool] = None


# ============================================================
# 6. Pull Request
# ============================================================

class PullRequest(CanonicalBaseModel):
    id: str | int
    number: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = "open"
    state: Optional[str] = None
    author_id: Optional[str] = None
    author: Optional[str] = None
    user_id: Optional[str] = None
    user: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee: Optional[str] = None
    reviewers: list[str] = Field(default_factory=list)
    reviewer_ids: list[str] = Field(default_factory=list)
    linked_issues: list[str] = Field(default_factory=list)
    issue_ids: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    draft: bool = False
    labels: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    merged_at: Optional[str] = None
    closed_at: Optional[str] = None
    simulated_delay_days: Optional[int] = None
    simulated_overdue: Optional[bool] = None


# ============================================================
# 7. Commit
# ============================================================

class Commit(CanonicalBaseModel):
    id: Optional[str] = None
    hash: Optional[str] = None
    sha: Optional[str] = None
    message: str = ""
    author_id: Optional[str] = None
    author: Optional[str] = None
    pr_id: Optional[str] = None
    pull_request_id: Optional[str] = None
    timestamp: Optional[str] = None
    date: Optional[str] = None
    created_at: Optional[str] = None
    changes: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


# ============================================================
# 8. Review
# ============================================================

class Review(CanonicalBaseModel):
    id: str
    pr_id: Optional[str] = None
    pull_request_id: Optional[str] = None
    pull_request: Optional[str] = None
    reviewer_id: Optional[str] = None
    status: Optional[str] = "pending"
    state: Optional[str] = None
    comment: Optional[str] = None
    body: Optional[str] = None
    submitted_at: Optional[str] = None
    created_at: Optional[str] = None


# ============================================================
# 9. Dependency
# ============================================================

class Dependency(CanonicalBaseModel):
    id: Optional[str] = None
    source_id: Optional[str] = None
    source: Optional[str] = None
    target_id: Optional[str] = None
    target: Optional[str] = None
    type: Optional[str] = "depends_on"
    relation: Optional[str] = None
    status: Optional[str] = "active"
    description: Optional[str] = None


# ============================================================
# 10. Deployment
# ============================================================

class Deployment(CanonicalBaseModel):
    id: str
    title: Optional[str] = None
    name: Optional[str] = None
    target_environment: Optional[str] = "staging"
    environment: Optional[str] = None
    scheduled_at: Optional[str] = None
    executed_at: Optional[str] = None
    status: Optional[str] = "pending"
    state: Optional[str] = None
    related_issues: list[str] = Field(default_factory=list)
    issue_ids: list[str] = Field(default_factory=list)
    related_prs: list[str] = Field(default_factory=list)
    pull_request_ids: list[str] = Field(default_factory=list)
    pr_ids: list[str] = Field(default_factory=list)
    deadline_id: Optional[str] = None


# ============================================================
# Canonical ProjectData
# ============================================================

class ProjectData(CanonicalBaseModel):
    """
    Canonical DEADLOCK Project Data Model.
    Unifies GitHub ingestion, seeded datasets, database, graph, risk engine, and simulation.
    """
    owner: str = ""
    repo: str = ""
    project: Optional[ProjectInfo] = None

    developers: list[Developer] = Field(default_factory=list)
    milestones: list[Milestone] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    pull_requests: list[PullRequest] = Field(default_factory=list)
    commits: list[Commit] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    deployments: list[Deployment] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        """Derive owner and repo from project repository field if not explicitly set."""
        if not self.owner or not self.repo:
            if self.project and self.project.repository:
                repo_str = self.project.repository.replace("https://", "").replace("http://", "")
                parts = repo_str.split("/")
                if len(parts) >= 3 and "github.com" in parts[0]:
                    if not self.owner:
                        self.owner = parts[1]
                    if not self.repo:
                        self.repo = parts[2].replace(".git", "")
                elif len(parts) >= 2:
                    if not self.owner:
                        self.owner = parts[-2]
                    if not self.repo:
                        self.repo = parts[-1].replace(".git", "")
