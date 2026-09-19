from app.models.risk_models import Risk

from app.agents.risk_agent import RiskAgent
from app.agents.verifier_agent import VerifierAgent
from app.agents.intervention_agent import (
    InterventionAgent,
)


def make_risk():

    return Risk(
        risk_id="RISK-001",
        title="Test risk",
        severity="HIGH",
        probability=0.80,
        root_cause="issue:1",
        impact="Test impact",
        evidence=[
            {
                "type": "issue",
                "id": "issue:1",
            }
        ],
        causal_chain=[
            "issue:1",
            "milestone:1",
        ],
        recommendation="Review the issue.",
    )


def test_risk_agent():

    risk = make_risk()

    result = RiskAgent().explain(risk)

    assert result.impact
    assert len(result.evidence) > 0


def test_verifier_agent():

    risk = make_risk()

    result = VerifierAgent().verify(risk)

    assert result.verified is True
    assert result.verification_confidence > 0


def test_intervention_agent():

    risk = make_risk()

    result = InterventionAgent().recommend(risk)

    assert "PRIORITIZE" in result.recommendation