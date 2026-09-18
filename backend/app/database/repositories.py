from __future__ import annotations

from app.database.database import (
    ProjectCorruptError,
    ProjectNotFoundError,
    get_project,
    save_project,
)

# Re-export so callers can import exceptions from here.
__all__ = [
    "store_project",
    "load_project",
    "is_demo_repo",
    "ProjectNotFoundError",
    "ProjectCorruptError",
]

# ============================================================
# DEMO-REPO DETECTION
# ============================================================

# The canonical demo / seed repository.  For this owner/repo
# pair the system always falls back to seeded data offline and
# never silently substitutes a live project with demo data.
_DEMO_REPOS: frozenset[tuple[str, str]] = frozenset(
    {
        ("aritra-dsu", "rf-sentinel"),
    }
)


def is_demo_repo(owner: str, repo: str) -> bool:
    """
    Return True if owner/repo refers to the canonical demo dataset.

    Comparison is case-insensitive.
    """

    return (owner.lower(), repo.lower()) in _DEMO_REPOS


# ============================================================
# STORE PROJECT
# ============================================================

def store_project(project, *, source: str = "github") -> None:
    """
    Persist a ProjectData object in SQLite.

    Parameters
    ----------
    project : ProjectData
        Must expose ``.owner``, ``.repo``, and ``.model_dump()``.
    source  : str
        Provenance tag stored alongside the data.
    """

    save_project(
        owner=project.owner,
        repo=project.repo,
        data=project.model_dump(),
        source=source,
    )


# ============================================================
# LOAD PROJECT
# ============================================================

def load_project(
    owner: str,
    repo: str,
) -> dict:
    """
    Load a project from SQLite.

    Returns
    -------
    dict
        The project data dict (includes ``_meta`` cache metadata).

    Raises
    ------
    ProjectNotFoundError
        No row for (owner, repo) exists.
    ProjectCorruptError
        A row exists but the stored JSON is invalid.
        The row is NOT automatically deleted.
    """

    return get_project(owner=owner, repo=repo)