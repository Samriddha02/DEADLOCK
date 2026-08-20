from fastapi import APIRouter, HTTPException

from app.ingestion.github_client import GitHubClient
from app.ingestion.normalizer import fetch_project
from app.database.repositories import store_project, load_project


router = APIRouter(
    prefix="/api/projects",
    tags=["projects"]
)


@router.post("/{owner}/{repo}/sync")
async def sync_project(owner: str, repo: str):
    """
    Fetch project data from GitHub, normalize it,
    and store it in the DEADLOCK database.
    """
    try:
        client = GitHubClient()

        project = await fetch_project(
            client,
            owner,
            repo
        )

        store_project(project)

        return {
            "message": "Project synced successfully",
            "owner": owner,
            "repo": repo,
            "project": project
        }

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub sync failed: {exc}"
        ) from exc


@router.get("/{owner}/{repo}")
def get_project(owner: str, repo: str):
    """
    Return the previously synced project.
    """
    data = load_project(owner, repo)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="Project not synced yet"
        )

    return data