from app.risk_engine.scoring import (
    probability_from_factors,
)

from app.risk_engine.rules import (
    severity_from_score,
)


def test_risk_probability():

    score = probability_from_factors(
        downstream=5,
        overdue=True,
    )

    assert 0 <= score <= 1


def test_risk_severity():

    assert severity_from_score(
        0.90
    ) == "CRITICAL"

    assert severity_from_score(
        0.70
    ) == "HIGH"

    assert severity_from_score(
        0.50
    ) == "MEDIUM"

    assert severity_from_score(
        0.20
    ) == "LOW"