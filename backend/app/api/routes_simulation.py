from fastapi import APIRouter, HTTPException

from app.models.github_models import ProjectData
from app.models.risk_models import SimulationRequest
from app.database.repositories import load_project
from app.simulation.what_if import simulate


router = APIRouter(
    prefix="/api/simulate",
    tags=["simulation"]
)


@router.post("/{owner}/{repo}")
def run_simulation(
    owner: str,
    repo: str,
    request: SimulationRequest
):
    """
    Run a What-If simulation on a synced project.
    """

    # Load project from database
    data = load_project(owner, repo)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="Project not synced yet"
        )

    # Convert stored data back into our project model
    project = ProjectData(**data)

    # Run simulation
    result = simulate(
        project,
        request
    )

    return result