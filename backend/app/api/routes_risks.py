from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models.github_models import ProjectData
from app.risk_engine.detector import detect_risks
from app.agents.risk_agent import RiskAgent
from app.agents.verifier_agent import VerifierAgent
from app.agents.intervention_agent import InterventionAgent
from app.database.repositories import load_project


router = APIRouter(
    prefix="/api/risks",
    tags=["risks"],
)

risk_agent = RiskAgent()
verifier = VerifierAgent()
intervention = InterventionAgent()


# DEADLOCK production/demo dataset.
# IMPORTANT:
# expected_results.json is NEVER loaded here.
BASE_DIR = Path(__file__).resolve().parents[2]
SEEDED_DATASET = BASE_DIR / "data" / "seeded_project.json"


def load_seeded_dataset() -> dict:
    """
    Load the production DEADLOCK risk-discovery dataset.

    expected_results.json is intentionally never used.
    """
    if not SEEDED_DATASET.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Seeded dataset not found: {SEEDED_DATASET}",
        )

    try:
        with SEEDED_DATASET.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid seeded_project.json: {exc}",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=500,
            detail="seeded_project.json must contain a JSON object.",
        )

    return data


def get_project_or_404(owner: str, repo: str) -> ProjectData:
    data = load_project(owner, repo)

    if not data:
        raise HTTPException(
            status_code=404,
            detail="Project not synced yet",
        )

    return ProjectData(**data)


def enrich_risk(risk):
    """
    Run the agent pipeline over one deterministic risk.
    """
    risk = risk_agent.explain(risk)
    risk = verifier.verify(risk)
    risk = intervention.recommend(risk)
    return risk


def risk_to_dict(risk):
    """
    Safely serialize either a Pydantic Risk model or a dict.
    """
    if hasattr(risk, "model_dump"):
        return risk.model_dump()

    if hasattr(risk, "dict"):
        return risk.dict()

    if isinstance(risk, dict):
        return risk

    return {
        "risk_id": getattr(risk, "risk_id", "RISK"),
        "title": getattr(
            risk,
            "title",
            "Detected project risk",
        ),
        "severity": getattr(
            risk,
            "severity",
            "UNKNOWN",
        ),
        "probability": getattr(
            risk,
            "probability",
            0,
        ),
        "impact": getattr(
            risk,
            "impact",
            "",
        ),
        "root_cause": getattr(
            risk,
            "root_cause",
            "",
        ),
        "evidence": getattr(
            risk,
            "evidence",
            [],
        ),
        "causal_chain": getattr(
            risk,
            "causal_chain",
            [],
        ),
        "recommendation": getattr(
            risk,
            "recommendation",
            "",
        ),
    }


@router.get("/{owner}/{repo}")
def get_risks(
    owner: str,
    repo: str,
):
    """
    Detect and verify project risks.

    DEADLOCK uses seeded_project.json as its production/demo
    risk-discovery input. GitHub-synced data may still be stored
    and displayed as project context.
    """

    # Keep the synced project requirement so the UI/API flow
    # remains consistent.
    get_project_or_404(owner, repo)

    # Production risk-discovery input.
    seeded_data = load_seeded_dataset()

    detected_risks = detect_risks(seeded_data)

    final_risks = []

    for risk in detected_risks:
        try:
            enriched = enrich_risk(risk)
        except Exception:
            # Keep deterministic detection usable even if an
            # optional agent layer has a problem.
            enriched = risk

        final_risks.append(
            risk_to_dict(enriched)
        )

    return {
        "project": f"{owner}/{repo}",
        "source": "data/seeded_project.json",
        "total_risks": len(final_risks),
        "risks": final_risks,
    }


@router.get("/{owner}/{repo}/{risk_id}")
def get_risk(
    owner: str,
    repo: str,
    risk_id: str,
):
    """
    Return one verified risk from the seeded project dataset.
    """

    get_project_or_404(owner, repo)

    seeded_data = load_seeded_dataset()

    detected_risks = detect_risks(seeded_data)

    for risk in detected_risks:
        current_id = str(
            getattr(
                risk,
                "risk_id",
                "",
            )
        )

        if current_id == risk_id:
            try:
                risk = enrich_risk(risk)
            except Exception:
                pass

            return risk_to_dict(risk)

    raise HTTPException(
        status_code=404,
        detail=f"Risk '{risk_id}' not found",
    )