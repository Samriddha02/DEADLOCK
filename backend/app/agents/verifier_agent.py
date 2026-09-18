from app.models.risk_models import Risk


class VerifierAgent:
    """
    Verifies whether a detected risk has
    sufficient evidence and a causal chain.
    """

    def verify(self, risk: Risk) -> Risk:

        has_evidence = bool(risk.evidence)
        has_causal_chain = bool(risk.causal_chain)

        is_valid = (
            has_evidence
            and has_causal_chain
        )

        risk.verified = is_valid

        if is_valid:
            risk.verification_confidence = 0.90
        else:
            risk.verification_confidence = 0.10

        return risk