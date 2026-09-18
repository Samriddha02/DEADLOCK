from app.models.risk_models import Risk


class InterventionAgent:
    """
    Generates the appropriate intervention
    based on risk severity.
    """

    def recommend(self, risk: Risk) -> Risk:

        if risk.severity == "CRITICAL":
            risk.recommendation = (
                f"IMMEDIATE ACTION: "
                f"{risk.recommendation}"
            )

        elif risk.severity == "HIGH":
            risk.recommendation = (
                f"PRIORITIZE TODAY: "
                f"{risk.recommendation}"
            )

        elif risk.severity == "MEDIUM":
            risk.recommendation = (
                f"PLAN ACTION: "
                f"{risk.recommendation}"
            )

        return risk