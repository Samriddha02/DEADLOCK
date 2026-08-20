from fastapi import APIRouter, HTTPException

from app.models.github_models import ProjectData
from app.risk_engine.detector import detect_risks
from app.agents.risk_agent import RiskAgent
from app.agents.verifier_agent import VerifierAgent
from app.agents.intervention_agent import InterventionAgent
from app.database.repositories import load_project


router = APIRouter(
    prefix="/api/risks",
    tags=["risks"]
)


# Initialize the agents once.
risk_agent = RiskAgent()
verifier = VerifierAgent()
intervention = InterventionAgent()


def get_project_or_404(owner: str, repo: str) -> ProjectData:
    """
    Load a previously synced project.
    """
    data = load_project(owner, repo)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="Project not synced yet"
        )

    return ProjectData(**data)


@router.get("/{owner}/{repo}")
def get_risks(owner: str, repo: str):
    """
    Detect and verify all risks for a project.
    """
    project = get_project_or_404(owner, repo)

    # Step 1: deterministic risk detection
    detected_risks = detect_risks(project)

    final_risks = []

    for risk in detected_risks:

        # Step 2: AI/explanation layer
        risk = risk_agent.explain(risk)

        # Step 3: verify the evidence
        risk = verifier.verify(risk)

        # Step 4: generate intervention
        risk = intervention.recommend(risk)

        final_risks.append(risk)

    return {
        "project": f"{owner}/{repo}",
        "total_risks": len(final_risks),
        "risks": final_risks
    }


@router.get("/{owner}/{repo}/{risk_id}")
def get_risk(
    owner: str,
    repo: str,
    risk_id: str
):
    """
    Get detailed information about one specific risk.
    """
    project = get_project_or_404(owner, repo)

    detected_risks = detect_risks(project)

    for risk in detected_risks:

        if risk.risk_id == risk_id:

            risk = risk_agent.explain(risk)
            risk = verifier.verify(risk)
            risk = intervention.recommend(risk)

            return risk

    raise HTTPException(
        status_code=404,
        detail=f"Risk '{risk_id}' not found"
    )