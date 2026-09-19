"""Deterministic risk scoring engine for DEADLOCK.

This module calculates a numeric risk_score (0‑100) for a verified Risk
object based solely on deterministic, evidence‑driven factors.  No
randomness, external services, or wall‑clock time are used, ensuring that
identical input always yields the same output.

The scoring pipeline consists of:
1. **Factor extraction** – raw values are derived from the Risk object's
   existing fields and evidence list.
2. **Normalization** – raw values are mapped to a 0‑1 range using
   deterministic thresholds.
3. **Weighted contribution** – each normalized value is multiplied by an
   explicit weight (the weights sum to 100).
4. **Aggregation** – contributions are summed, rounded, and clamped to the
   0‑100 interval.
5. **Band assignment** – the final integer score is mapped to a risk
   band (LOW, MODERATE, HIGH, CRITICAL).

The engine also produces a detailed ``score_breakdown`` dictionary that
contains raw, normalized, weight, contribution, status and a short reason
for each factor.  Missing evidence is represented with ``status:\n"UNKNOWN"`` and a contribution of 0.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.models.risk_models import Risk

# ---------------------------------------------------------------------------
# Explicit, inspectable weights – they sum to 100.
# ---------------------------------------------------------------------------
WEIGHTS: Dict[str, int] = {
    "evidence": 30,      # verification confidence
    "impact": 25,        # size of causal chain
    "propagation": 20,   # number of evidence entries
    "bottleneck": 15,    # presence of bottleneck evidence
    "deadline": 10,      # deadline pressure evidence
}

# Normalization helpers ------------------------------------------------------
def _norm_confidence(conf: float) -> float:
    """Clamp verification confidence (0‑1) to [0,1]."""
    return max(0.0, min(1.0, conf))

def _norm_count(value: int, max_expected: int) -> float:
    """Normalize a count to [0,1] given a deterministic maximum.
    ``max_expected`` is the threshold at which the factor is considered
    fully saturated.
    """
    if max_expected <= 0:
        return 0.0
    return max(0.0, min(1.0, value / float(max_expected)))

def _norm_deadline(days_remaining: int) -> float:
    """Convert days remaining into a pressure score.
    Positive *days_remaining* means the deadline is in the future → low
    pressure (0).  Zero or negative values indicate deadline passed → high
    pressure.  The pressure is capped at 30 days past deadline.
    """
    if days_remaining >= 0:
        return 0.0
    pressure = min(abs(days_remaining), 30) / 30.0
    return pressure

# ---------------------------------------------------------------------------
# Core scoring function
# ---------------------------------------------------------------------------
def compute_score(risk: Risk) -> tuple[int, Dict[str, Any], str]:
    """Compute a deterministic risk score for a *verified* ``Risk``.
    Returns ``(score, breakdown, band)`` where:
    * ``score`` – integer in ``0‥100``.
    * ``breakdown`` – dictionary keyed by factor name containing raw value,
      normalized value, weight, contribution, status and a short reason.
    * ``band`` – one of ``LOW``, ``MODERATE``, ``HIGH`` or ``CRITICAL``.
    """
    breakdown: Dict[str, Dict[str, Any]] = {}
    total_contribution = 0.0

    # Evidence factor – verification confidence (0‑1).
    raw_evidence = getattr(risk, "verification_confidence", 0.0)
    norm_evidence = _norm_confidence(raw_evidence)
    weight = WEIGHTS["evidence"]
    contribution = weight * norm_evidence
    breakdown["evidence"] = {
        "raw_value": raw_evidence,
        "normalized_value": norm_evidence,
        "weight": weight,
        "contribution": round(contribution, 2),
        "status": "KNOWN" if raw_evidence is not None else "UNKNOWN",
        "reason": "Verification confidence",
    }
    total_contribution += contribution

    # Impact factor – size of causal chain.
    chain = getattr(risk, "causal_chain", []) or []
    raw_impact = len(chain)
    norm_impact = _norm_count(raw_impact, 10)  # saturates at 10 nodes
    weight = WEIGHTS["impact"]
    contribution = weight * norm_impact
    breakdown["impact"] = {
        "raw_value": raw_impact,
        "normalized_value": norm_impact,
        "weight": weight,
        "contribution": round(contribution, 2),
        "status": "KNOWN" if raw_impact > 0 else "UNKNOWN",
        "reason": f"{raw_impact} nodes in causal chain",
    }
    total_contribution += contribution

    # Propagation factor – total evidence entries.
    evidence_list: List[Dict[str, Any]] = getattr(risk, "evidence", []) or []
    raw_propagation = len(evidence_list)
    norm_propagation = _norm_count(raw_propagation, 20)
    weight = WEIGHTS["propagation"]
    contribution = weight * norm_propagation
    breakdown["propagation"] = {
        "raw_value": raw_propagation,
        "normalized_value": norm_propagation,
        "weight": weight,
        "contribution": round(contribution, 2),
        "status": "KNOWN" if raw_propagation > 0 else "UNKNOWN",
        "reason": f"{raw_propagation} evidence items",
    }
    total_contribution += contribution

    # Bottleneck factor – evidence items of type "bottleneck".
    bottleneck_items = [e for e in evidence_list if e.get("type") == "bottleneck"]
    raw_bottleneck = len(bottleneck_items)
    norm_bottleneck = _norm_count(raw_bottleneck, 5)
    weight = WEIGHTS["bottleneck"]
    contribution = weight * norm_bottleneck
    breakdown["bottleneck"] = {
        "raw_value": raw_bottleneck,
        "normalized_value": norm_bottleneck,
        "weight": weight,
        "contribution": round(contribution, 2),
        "status": "KNOWN" if raw_bottleneck > 0 else "UNKNOWN",
        "reason": f"{raw_bottleneck} bottleneck evidence entries",
    }
    total_contribution += contribution

    # Deadline pressure factor.
    deadline_items = [e for e in evidence_list if e.get("type") == "deadline"]
    if deadline_items:
        days_remaining = min(int(e.get("days_remaining", 0)) for e in deadline_items)
        raw_deadline = days_remaining
        norm_deadline = _norm_deadline(days_remaining)
        status = "KNOWN"
        reason = f"deadline {days_remaining} days from now"
    else:
        raw_deadline = None
        norm_deadline = 0.0
        status = "UNKNOWN"
        reason = "no deadline evidence"
    weight = WEIGHTS["deadline"]
    contribution = weight * norm_deadline
    breakdown["deadline"] = {
        "raw_value": raw_deadline,
        "normalized_value": norm_deadline,
        "weight": weight,
        "contribution": round(contribution, 2),
        "status": status,
        "reason": reason,
    }
    total_contribution += contribution

    # Final score – deterministic rounding and clamping.
    score = int(round(total_contribution))
    score = max(0, min(100, score))

    # Band assignment.
    if score <= 24:
        band = "LOW"
    elif score <= 49:
        band = "MODERATE"
    elif score <= 74:
        band = "HIGH"
    else:
        band = "CRITICAL"

    return score, breakdown, band

# ---------------------------------------------------------------------------
# Compatibility helpers used by older modules and tests
# ---------------------------------------------------------------------------

def score_risks(risks: list[Risk]) -> list[Risk]:
    """Score a list of `Risk` objects.

    For each risk that is verified, compute a deterministic risk score using
    :func:`compute_score` and populate the ``risk_score``, ``score_breakdown``
    and ``score_band`` fields. Non‑verified risks are returned unchanged.
    """
    scored: list[Risk] = []
    for r in risks:
        if getattr(r, "verified", False):
            score, breakdown, band = compute_score(r)
            r.risk_score = score
            r.score_breakdown = breakdown
            r.score_band = band
        scored.append(r)
    return scored

def probability_from_factors(downstream: int = 0, overdue: bool = False) -> float:
    """Deterministic probability estimate used by legacy tests.

    The function combines a simple downstream count with an overdue flag.
    It is intentionally straightforward and deterministic:

    * ``downstream`` is normalized against a maximum of 10.
    * ``overdue`` adds a fixed 0.2 weight when true.
    * The result is clamped to the ``[0, 1]`` interval.
    """
    norm_down = max(0.0, min(1.0, downstream / 10.0))
    extra = 0.2 if overdue else 0.0
    prob = norm_down + extra
    return max(0.0, min(1.0, prob))