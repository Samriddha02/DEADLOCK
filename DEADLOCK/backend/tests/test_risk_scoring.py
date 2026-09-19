import pytest
from app.models.risk_models import Risk
from app.risk_engine.scoring import compute_score

@pytest.fixture
def verified_risk():
    """A verified risk with full evidence for deterministic score testing."""
    return Risk(
        risk_id="RISK-TEST-01",
        title="Test Risk",
        severity="MEDIUM",
        probability=0.5,
        root_cause="component_x",
        impact="some impact",
        causal_chain=["c1", "c2", "c3"],
        evidence=[
            {"type": "simulation", "detail": "..."},
            {"type": "bottleneck", "detail": "..."},
            {"type": "deadline", "days_remaining": -5},
        ],
        recommendation="fix it",
        verified=True,
        verification_confidence=0.9,
    )

def test_compute_score_deterministic(verified_risk):
    score, breakdown, band = compute_score(verified_risk)
    # Expected contributions based on WEIGHTS
    # evidence (conf 0.9) -> 30 * 0.9 = 27.0
    # impact (3 nodes) -> 25 * (3/10) = 7.5
    # propagation (3 evidences) -> 20 * (3/20) = 3.0
    # bottleneck (1) -> 15 * (1/5) = 3.0
    # deadline (days_remaining -5) -> pressure 5/30 = 0.1667 -> 10 * 0.1667 ≈ 1.6667
    expected_total = round(27.0 + 7.5 + 3.0 + 3.0 + 1.6667)
    assert score == expected_total
    # Band mapping check
    if score <= 24:
        expected_band = "LOW"
    elif score <= 49:
        expected_band = "MODERATE"
    elif score <= 74:
        expected_band = "HIGH"
    else:
        expected_band = "CRITICAL"
    assert band == expected_band
    # Verify breakdown contains all factors with required keys
    for factor in ["evidence", "impact", "propagation", "bottleneck", "deadline"]:
        assert factor in breakdown
        for key in ["raw_value", "normalized_value", "weight", "contribution", "status", "reason"]:
            assert key in breakdown[factor]

def test_missing_data_handling():
    """Risk with minimal evidence – missing factors should be UNKNOWN."""
    risk = Risk(
        risk_id="RISK-TEST-02",
        title="Minimal Risk",
        severity="LOW",
        probability=0.1,
        root_cause="component_y",
        impact="",
        causal_chain=[],
        evidence=[],
        recommendation="",
        verified=True,
        verification_confidence=0.2,
    )
    score, breakdown, band = compute_score(risk)
    # Only evidence factor contributes (0.2 * 30 = 6)
    assert score == round(30 * 0.2)
    # Missing factors should be UNKNOWN
    for factor in ["impact", "propagation", "bottleneck", "deadline"]:
        assert breakdown[factor]["status"] == "UNKNOWN"
