from typing import Optional

from pydantic import BaseModel, Field


class Developer(BaseModel):
    login: str


class GitHubIssue(BaseModel):
    id: int
    number: int
    title: str
    state: str

    assignee: Optional[str] = None

    labels: list[str] = Field(
        default_factory=list
    )

    milestone: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GitHubPullRequest(BaseModel):
    id: int
    number: int
    title: str
    state: str

    user: Optional[str] = None
    assignee: Optional[str] = None

    labels: list[str] = Field(
        default_factory=list
    )

    draft: bool = False

    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    merged_at: Optional[str] = None


class GitHubCommit(BaseModel):
    sha: str
    message: str

    author: Optional[str] = None
    date: Optional[str] = None


class GitHubMilestone(BaseModel):
    id: int
    number: int
    title: str
    state: str

    due_on: Optional[str] = None

    open_issues: int = 0
    closed_issues: int = 0


class ProjectData(BaseModel):
    owner: str
    repo: str

    issues: list[GitHubIssue] = Field(
        default_factory=list
    )

    pull_requests: list[GitHubPullRequest] = Field(
        default_factory=list
    )

    commits: list[GitHubCommit] = Field(
        default_factory=list
    )

    milestones: list[GitHubMilestone] = Field(
        default_factory=list
    )