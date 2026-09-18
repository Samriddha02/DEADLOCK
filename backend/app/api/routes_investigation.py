from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.routes_risks import load_seeded_dataset
from app.database.repositories import (
    ProjectCorruptError,
    ProjectNotFoundError,
    is_demo_repo,
    load_project,
)
from app.models.investigation_models import InvestigationResult
from app.agents.investigation_pipeline import run_investigation_pipeline


router = APIRouter(
    prefix="/api/analyze",
    tags=["investigation"],
)


@router.post("", response_model=InvestigationResult)
@router.post("/", response_model=InvestigationResult)
def run_default_investigation() -> InvestigationResult:
    """
    Run full five-agent risk investigation pipeline on default demo dataset.
    """
    dataset = load_seeded_dataset()
    return run_investigation_pipeline(dataset, "Aritra-DSU", "RF-SENTINEL")


@router.post("/{owner}/{repo}", response_model=InvestigationResult)
def run_investigation(
    owner: str,
    repo: str,
) -> InvestigationResult:
    """
    Run full five-agent risk investigation pipeline for a specific repository.
    Supports offline seeded fallback for demo repositories.
    """
    if not owner.strip() or not repo.strip():
        raise HTTPException(
            status_code=400,
            detail="Owner and repo are required.",
        )

    owner_str = owner.strip()
    repo_str = repo.strip()

    if is_demo_repo(owner_str, repo_str):
        dataset = load_seeded_dataset()
    else:
        try:
            dataset = load_project(owner_str, repo_str)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{owner_str}/{repo_str}' has not been synced yet.",
            )
        except ProjectCorruptError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Stored project data for '{owner_str}/{repo_str}' is corrupt: {exc}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load project: {exc}",
            ) from exc

    return run_investigation_pipeline(dataset, owner_str, repo_str)
