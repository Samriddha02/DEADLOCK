from fastapi import APIRouter, HTTPException

from app.database.repositories import load_project, store_project
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

        store_project(project)

        return {
            "message": "Project synced successfully",
            "owner": owner,
            "repo": repo,
            "project": project,
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
def get_project(owner: str, repo: str):
    """
    Return a previously synced project from the database.

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
    repo = repo.strip()

    try:
        data = load_project(
            owner,
            repo,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load project: {exc}",
        ) from exc

    if not data:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Project '{owner}/{repo}' has not been synced yet."
            ),
        )

    return data