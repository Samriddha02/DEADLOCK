from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Body

from app.models.risk_models import SimulationRequest, SimulationResult
from app.simulation.what_if import simulate
from app.api.routes_risks import load_seeded_dataset
from app.database.repositories import (
    is_demo_repo,
    load_project,
    ProjectNotFoundError,
)


router = APIRouter(
    prefix="/api/simulate",
    tags=["simulation"],
)


def _execute_simulation(
    request: Optional[SimulationRequest] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
) -> SimulationResult:
    """
    Unified simulation execution.
    Defaults to node_id='pr_11' and delay_days=3 when body is omitted.
    Loads repo-specific data if owner/repo provided, or seeded data for demo.
    """
    if request is None:
        request = SimulationRequest(node_id="pr_11", delay_days=3)
    elif not request.node_id:
        request.node_id = "pr_11"

    # Legacy frontend compatibility: map old demo ID PR-47 to canonical pr_11
    if request.node_id in {"PR-47", "PR_47"}:
        request.node_id = "pr_11"

    project = None
    if owner and repo and owner.strip() and repo.strip():
        owner_clean = owner.strip()
        repo_clean = repo.strip()
        if is_demo_repo(owner_clean, repo_clean):
            project = load_seeded_dataset()
        else:
            try:
                project = load_project(owner_clean, repo_clean)
            except ProjectNotFoundError:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{owner_clean}/{repo_clean}' has not been synced yet.",
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load project '{owner_clean}/{repo_clean}': {exc}",
                ) from exc
    else:
        try:
            project = load_seeded_dataset()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load seeded project: {exc}",
            ) from exc

    try:
        return simulate(
            project,
            request,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Simulation failed: {exc}",
        ) from exc


@router.post("", response_model=SimulationResult)
@router.post("/", response_model=SimulationResult)
def run_simulation_direct(
    request: Optional[SimulationRequest] = Body(default=None),
) -> SimulationResult:
    """
    Direct simulation endpoint used by frontend and API clients.
    Supports empty body, default node_id=pr_11/delay_days=3, or custom parameters.
    """
    return _execute_simulation(request)


@router.post("/{owner}/{repo}", response_model=SimulationResult)
def run_simulation(
    owner: str,
    repo: str,
    request: Optional[SimulationRequest] = Body(default=None),
) -> SimulationResult:
    """
    Parameterized simulation endpoint for project-scoped simulation.
    """
    return _execute_simulation(request, owner=owner, repo=repo)