from __future__ import annotations

from typing import Any

from app.risk_engine.detector import detect_risks
from app.risk_engine.scoring import score_risks


class RiskAgent:
    def __init__(self) -> None:
        self.name = "risk_agent"

    def detect(
        self,
        project: Any,
        graph: Any = None,
    ) -> list[Any]:
        try:
            risks = detect_risks(project, graph)
        except TypeError:
            risks = detect_risks(project)

        if risks is None:
            return []

        return list(risks)

    def score(
        self,
        risks: list[Any],
    ) -> list[Any]:
        try:
            scored = score_risks(risks)
        except TypeError:
            scored = risks

        if scored is None:
            return []

        return list(scored)

    def explain(self, risk: Any) -> Any:
        """
        Explain a risk while preserving the original Risk object.

        The tests and the rest of the application expect Risk
        attributes such as:
            risk.impact
            risk.severity
            risk.probability
            risk.score

        Therefore, do NOT convert Risk objects into dictionaries.
        """

        # Risk model / dataclass
        if hasattr(risk, "impact"):
            return risk

        # Dictionary compatibility
        if isinstance(risk, dict):
            class ExplainedRisk:
                def __init__(self, data: dict[str, Any]) -> None:
                    self._data = data

                def __getattr__(self, name: str) -> Any:
                    if name in self._data:
                        return self._data[name]
                    raise AttributeError(name)

                def get(
                    self,
                    name: str,
                    default: Any = None,
                ) -> Any:
                    return self._data.get(name, default)

                def to_dict(self) -> dict[str, Any]:
                    return dict(self._data)

            return ExplainedRisk(risk)

        return risk

    def run(
        self,
        project: Any,
        graph: Any = None,
    ) -> dict[str, Any]:

        detected = self.detect(
            project,
            graph,
        )

        scored = self.score(
            detected,
        )

        explanations = [
            self.explain(risk)
            for risk in scored
        ]

        critical = [
            risk
            for risk in scored
            if str(
                getattr(
                    risk,
                    "severity",
                    risk.get("severity", "")
                    if isinstance(risk, dict)
                    else "",
                )
            ).upper() == "CRITICAL"
        ]

        high = [
            risk
            for risk in scored
            if str(
                getattr(
                    risk,
                    "severity",
                    risk.get("severity", "")
                    if isinstance(risk, dict)
                    else "",
                )
            ).upper() == "HIGH"
        ]

        return {
            "agent": self.name,
            "risks": scored,
            "explanations": explanations,
            "risk_count": len(scored),
            "critical_count": len(critical),
            "high_count": len(high),
            "status": (
                "HIGH_RISK"
                if critical or high
                else "STABLE"
            ),
        }

    def analyze(
        self,
        project: Any,
        graph: Any = None,
    ) -> dict[str, Any]:
        return self.run(
            project,
            graph,
        )


def run_risk_agent(
    project: Any,
    graph: Any = None,
) -> dict[str, Any]:

    return RiskAgent().run(
        project,
        graph,
    )