from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.risk_engine.detector import detect_risks
from app.agents.risk_agent import RiskAgent
from app.agents.verifier_agent import VerifierAgent
from app.agents.intervention_agent import InterventionAgent


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
    }


# ============================================================
# GET ALL RISKS
# ============================================================

@router.get("/{owner}/{repo}")
def get_risks(
    owner: str,
    repo: str,
):
    """
    Detect and verify project risks.

    DEADLOCK uses seeded_project.json as the
    deterministic production/demo risk-discovery input.

    IMPORTANT:
    This endpoint does NOT require:
      - GitHub
      - GITHUB_TOKEN
      - GitHub repository synchronization
      - SQLite project data

    owner/repo are retained in the URL so the existing
    frontend/API contract does not need to change.
    """

    # --------------------------------------------------------
    # Load deterministic demo dataset directly.
    # --------------------------------------------------------
    seeded_data = load_seeded_dataset()

    # --------------------------------------------------------
    # Run DEADLOCK risk detection.
    # --------------------------------------------------------
    detected_risks = detect_risks(
        seeded_data
    )

    final_risks = []

    # --------------------------------------------------------
    # Enrich each detected risk.
    #
    # Agent failures must not prevent deterministic
    # risk detection from being returned.
    # --------------------------------------------------------
    for risk in detected_risks:

        try:
            enriched = enrich_risk(
                risk
            )

        except Exception:
            enriched = risk

        final_risks.append(
            risk_to_dict(
                enriched
            )
        )

    return {
        "project": f"{owner}/{repo}",
        "source": "data/seeded_project.json",
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
    Return one verified risk from the seeded
    DEADLOCK project dataset.

    GitHub and SQLite are NOT required.
    """

    # --------------------------------------------------------
    # Load deterministic demo dataset directly.
    # --------------------------------------------------------
    seeded_data = load_seeded_dataset()

    # --------------------------------------------------------
    # Detect risks.
    # --------------------------------------------------------
    detected_risks = detect_risks(
        seeded_data
    )

    # --------------------------------------------------------
    # Find requested risk.
    # --------------------------------------------------------
    for risk in detected_risks:

        current_id = str(
            getattr(
                risk,
                "risk_id",
                "",
            )
        )

        # Also support dictionary-based risks.
        if isinstance(risk, dict):
            current_id = str(
                risk.get(
                    "risk_id",
                    "",
                )
            )

        if current_id == risk_id:

            try:
                risk = enrich_risk(
                    risk
                )

            except Exception:
                pass

            return risk_to_dict(
                risk
            )

    # --------------------------------------------------------
    # Risk was not found.
    # --------------------------------------------------------
    raise HTTPException(
        status_code=404,
        detail=(
            f"Risk '{risk_id}' not found"
        ),
    )