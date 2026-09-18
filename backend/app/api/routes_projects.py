from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.database.repositories import (
    ProjectCorruptError,
    ProjectNotFoundError,
    is_demo_repo,
    load_project,
    store_project,
)
from app.ingestion.dataset_loader import load_canonical_project
from app.ingestion.github_client import GitHubClient
from app.ingestion.normalizer import fetch_project


router = APIRouter(
    prefix="/api/projects",
    tags=["projects"],
)


# ============================================================
# SYNC PROJECT
# ============================================================

@router.post("/{owner}/{repo}/sync")
async def sync_project(owner: str, repo: str):
    """
    Fetch a GitHub repository, normalize its project data,
    store it in the DEADLOCK database, and return the result.

    Endpoint:
        POST /api/projects/{owner}/{repo}/sync
    """

    if not owner.strip():
        raise HTTPException(
            status_code=400,
            detail="GitHub owner is required.",
        )

    if not repo.strip():
        raise HTTPException(
            status_code=400,
            detail="GitHub repository is required.",
        )

    owner = owner.strip()
    repo = repo.strip()

    # Demo repos use the seeded dataset — never attempt a live sync.
    if is_demo_repo(owner, repo):
        project = load_canonical_project()
        store_project(project, source="seeded")
        return {
            "message": "Demo project synced from seeded dataset",
            "owner": owner,
            "repo": repo,
            "project": project.model_dump(),
        }

    try:
        client = GitHubClient()

        project = await fetch_project(
            client,
            owner,
            repo,
        )

        if not project:
            raise HTTPException(
                status_code=404,
                detail="GitHub repository returned no project data.",
            )

        store_project(project, source="github")

        return {
            "message": "Project synced successfully",
            "owner": owner,
            "repo": repo,
            "project": project.model_dump(),
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub sync failed: {exc}",
        ) from exc


# ============================================================
# GET PROJECT
# ============================================================

@router.get("/{owner}/{repo}")
def get_project_endpoint(owner: str, repo: str):
    """
    Return a previously synced project from the database.

    For the canonical demo repo (Aritra-DSU/RF-SENTINEL) a
    seeded-data fallback is used when no live record exists.

    LIVE projects are never silently substituted with demo data:
    if a live project has not been synced yet the caller
    receives a 404 so they know to trigger a sync.

    Endpoint:
        GET /api/projects/{owner}/{repo}
    """

    if not owner.strip():
        raise HTTPException(
            status_code=400,
            detail="GitHub owner is required.",
        )

    if not repo.strip():
        raise HTTPException(
            status_code=400,
            detail="GitHub repository is required.",
        )

    owner = owner.strip()
    repo  = repo.strip()

    try:
        data = load_project(owner, repo)
        return data

    except ProjectNotFoundError:
        # For the demo repo, fall back to seeded data so the UI
        # always works offline without requiring a DB row.
        if is_demo_repo(owner, repo):
            project = load_canonical_project()
            result = project.model_dump()
            result["_meta"] = {
                "source": "seeded",
                "created_at": None,
                "updated_at": None,
                "last_synced_at": None,
            }
            return result

        # For live repos, do NOT substitute demo data — return 404.
        raise HTTPException(
            status_code=404,
            detail=f"Project '{owner}/{repo}' has not been synced yet.",
        )

    except ProjectCorruptError as exc:
        # The row exists but is unreadable.  Do NOT auto-delete;
        # return a 500 so the caller knows the DB needs attention.
        raise HTTPException(
            status_code=500,
            detail=f"Stored project data for '{owner}/{repo}' is corrupt: {exc}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load project: {exc}",
        ) from exc