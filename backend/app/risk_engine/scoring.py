from __future__ import annotations

from typing import Any

from .rules import severity_from_score


RISK_WEIGHTS = {
    "DEADLINE_SLIPPAGE": 0.90,
    "DEVELOPER_BOTTLENECK": 0.85,
    "DEPENDENCY_BOTTLENECK": 0.80,
    "STALE_PULL_REQUEST": 0.60,
}

SEVERITY_MULTIPLIERS = {
    "LOW": 0.40,
    "MEDIUM": 0.60,
    "HIGH": 0.80,
    "CRITICAL": 1.00,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalise_severity(value: Any) -> str:
    return str(value or "LOW").upper()


# ============================================================
# PROBABILITY
# ============================================================

def probability_from_factors(
    downstream: int = 0,
    overdue: bool = False,
    **kwargs: Any,
) -> float:
    """
    Calculate normalized risk probability.

    downstream:
        Number of downstream dependencies.

    overdue:
        Whether the item is overdue.

    Additional keyword factors are accepted for
    compatibility with future risk rules.
    """

    score = 0.0

    # Downstream dependency pressure
    if isinstance(downstream, (int, float)):
        score += min(
            0.60,
            max(0.0, downstream) * 0.10,
        )

    # Deadline pressure
    if overdue:
        score += 0.40

    # Optional additional factors
    for value in kwargs.values():
        if isinstance(value, bool):
            if value:
                score += 0.10

        elif isinstance(value, (int, float)):
            score += min(
                0.10,
                max(0.0, float(value)),
            )

    return round(
        _clamp(score),
        4,
    )


# ============================================================
# RISK SCORE
# ============================================================

def calculate_risk_score(
    risk: dict[str, Any],
) -> float:

    risk_type = str(
        risk.get("risk_type", "")
    ).upper()

    severity = _normalise_severity(
        risk.get("severity")
    )

    base_weight = RISK_WEIGHTS.get(
        risk_type,
        0.50,
    )

    severity_multiplier = SEVERITY_MULTIPLIERS.get(
        severity,
        0.40,
    )

    score = (
        base_weight
        * severity_multiplier
    )

    # Developer bottleneck
    if risk_type == "DEVELOPER_BOTTLENECK":

        workload = risk.get("workload")
        average = risk.get("average_workload")

        if (
            isinstance(workload, (int, float))
            and isinstance(average, (int, float))
            and average > 0
        ):
            ratio = workload / average

            if ratio >= 3:
                score += 0.15
            elif ratio >= 2:
                score += 0.10

    # Dependency bottleneck
    elif risk_type == "DEPENDENCY_BOTTLENECK":

        count = risk.get("dependency_count")

        if isinstance(count, (int, float)):
            if count >= 8:
                score += 0.15
            elif count >= 5:
                score += 0.10
            elif count >= 3:
                score += 0.05

    # Stale PR
    elif risk_type == "STALE_PULL_REQUEST":

        stale_days = risk.get("stale_days")

        if isinstance(stale_days, (int, float)):
            if stale_days >= 30:
                score += 0.15
            elif stale_days >= 14:
                score += 0.10
            elif stale_days >= 7:
                score += 0.05

    return round(
        _clamp(score),
        4,
    )


# ============================================================
# SCORE ONE RISK
# ============================================================

def score_risk(
    risk: dict[str, Any],
) -> dict[str, Any]:

    result = dict(risk)

    score = calculate_risk_score(result)

    result["score"] = score

    result["severity"] = severity_from_score(
        score
    )

    return result


# ============================================================
# SCORE ALL RISKS
# ============================================================

def score_risks(
    risks: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    scored = [
        score_risk(risk)
        for risk in risks
        if isinstance(risk, dict)
    ]

    scored.sort(
        key=lambda item: item.get(
            "score",
            0.0,
        ),
        reverse=True,
    )

    return scored


# ============================================================
# PROJECT RISK
# ============================================================

def calculate_project_risk(
    risks: list[dict[str, Any]],
) -> dict[str, Any]:

    if not risks:
        return {
            "score": 0.0,
            "severity": "LOW",
            "risk_count": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
        }

    scored = score_risks(risks)

    scores = [
        float(
            risk.get("score", 0.0)
        )
        for risk in scored
    ]

    highest = max(scores)

    additional_pressure = min(
        0.25,
        max(0, len(scores) - 1) * 0.03,
    )

    project_score = _clamp(
        highest + additional_pressure
    )

    severities = [
        str(
            risk.get(
                "severity",
                "LOW",
            )
        ).upper()
        for risk in scored
    ]

    return {
        "score": round(
            project_score,
            4,
        ),
        "severity": severity_from_score(
            project_score
        ),
        "risk_count": len(scored),
        "critical_count": severities.count(
            "CRITICAL"
        ),
        "high_count": severities.count(
            "HIGH"
        ),
        "medium_count": severities.count(
            "MEDIUM"
        ),
        "low_count": severities.count(
            "LOW"
        ),
    }


# ============================================================
# COMPLETE RISK EVALUATION
# ============================================================

def evaluate_risks(
    risks: list[dict[str, Any]],
) -> dict[str, Any]:

    scored_risks = score_risks(risks)

    summary = calculate_project_risk(
        scored_risks
    )

    return {
        "risks": scored_risks,
        "summary": summary,
    }