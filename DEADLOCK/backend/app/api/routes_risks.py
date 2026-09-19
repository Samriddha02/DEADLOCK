from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.risk_engine.detector import detect_risks
from app.agents.risk_agent import RiskAgent
from app.agents.verifier_agent import VerifierAgent
from app.agents.intervention_agent import InterventionAgent
from app.database.repositories import (
    is_demo_repo,
    load_project,
    ProjectNotFoundError,
    ProjectCorruptError,
)


router = APIRouter(
    prefix="/api/risks",
    tags=["risks"],
)


risk_agent = RiskAgent()
verifier = VerifierAgent()
intervention = InterventionAgent()


# ============================================================
# SEEDED DEADLOCK DEMO DATASET
# ============================================================
#
# Actual location:
#
# DEADLOCK/
# └── backend/
#     ├── app/
#     │   └── api/
#     │       └── routes_risks.py
#     └── data/
#         └── seeded_project.json
#
# parents[2] resolves to:
# DEADLOCK/backend
#
BASE_DIR = Path(__file__).resolve().parents[2]

SEEDED_DATASET = (
    BASE_DIR
    / "data"
    / "seeded_project.json"
)


def load_seeded_dataset() -> dict:
    """
    Load the deterministic DEADLOCK demo dataset.

    This is the primary risk-discovery input for the
    hackathon/demo environment.

    GitHub is NOT required.
    SQLite is NOT required.
    expected_results.json is NEVER loaded here.
    """

    if not SEEDED_DATASET.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Seeded dataset not found: "
                f"{SEEDED_DATASET}"
            ),
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
            detail=(
                "Invalid seeded_project.json: "
                f"{exc}"
            ),
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=500,
            detail=(
                "seeded_project.json must contain "
                "a JSON object."
            ),
        )

    return data


def enrich_risk(risk):
    """
    Run the optional DEADLOCK agent pipeline over
    one deterministic risk.

    Detection remains usable even if an optional
    agent layer fails.
    """

    risk = risk_agent.explain(risk)
    risk = verifier.verify(risk)
    risk = intervention.recommend(risk)

    return risk


def risk_to_dict(risk):
    """
    Safely serialize either:
      - Pydantic model
      - dictionary
      - regular Python object
    """

    if hasattr(risk, "model_dump"):
        return risk.model_dump()

    if hasattr(risk, "dict"):
        return risk.dict()

    if isinstance(risk, dict):
        return risk

    return {
        "risk_id": getattr(
            risk,
            "risk_id",
            "RISK",
        ),
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
        # Optional deterministic scoring fields – may be None for unverified risks
        "risk_score": getattr(
            risk,
            "risk_score",
            None,
        ),
        "score_breakdown": getattr(
            risk,
            "score_breakdown",
            None,
        ),
        "score_band": getattr(
            risk,
            "score_band",
            None,
        ),
    }


def _get_risks_dataset(owner: str, repo: str) -> tuple[dict, str]:
    if not owner.strip() or not repo.strip():
        raise HTTPException(
            status_code=400,
            detail="Owner and repo are required.",
        )

    owner = owner.strip()
    repo = repo.strip()

    if is_demo_repo(owner, repo):
        return load_seeded_dataset(), "data/seeded_project.json"

    try:
        data = load_project(owner, repo)
        return data, "SQLite database"
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{owner}/{repo}' has not been synced yet.",
        )
    except ProjectCorruptError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Stored project data for '{owner}/{repo}' is corrupt: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load project: {exc}",
        ) from exc


# ============================================================
# GET ALL RISKS
# ============================================================

@router.get("/{owner}/{repo}")
def get_risks(
    owner: str,
    repo: str,
):
    """
    Detect and verify project risks for the specified repository.
    Loads from SQLite database for synced projects, or seeded data for demo.
    """
    dataset, source = _get_risks_dataset(owner, repo)

    # Run DEADLOCK risk detection on real dataset.
    detected_risks = detect_risks(dataset)

    final_risks = []
    for risk in detected_risks:
        try:
            enriched = enrich_risk(risk)
        except Exception:
            enriched = risk

        final_risks.append(risk_to_dict(enriched))

    return {
        "project": f"{owner.strip()}/{repo.strip()}",
        "source": source,
        "total_risks": len(final_risks),
        "risks": final_risks,
    }


# ============================================================
# GET ONE RISK
# ============================================================

@router.get("/{owner}/{repo}/{risk_id}")
def get_risk(
    owner: str,
    repo: str,
    risk_id: str,
):
    """
    Return one verified risk from the specified project dataset.
    """
    dataset, _ = _get_risks_dataset(owner, repo)

    detected_risks = detect_risks(dataset)

    for risk in detected_risks:
        current_id = str(getattr(risk, "risk_id", ""))
        if isinstance(risk, dict):
            current_id = str(risk.get("risk_id", ""))

        if current_id == risk_id:
            try:
                risk = enrich_risk(risk)
            except Exception:
                pass

            return risk_to_dict(risk)

    raise HTTPException(
        status_code=404,
        detail=f"Risk '{risk_id}' not found in project '{owner}/{repo}'.",
    )