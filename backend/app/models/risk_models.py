from typing import Any, Literal

from pydantic import BaseModel, Field


RiskSeverity = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
]


class Risk(BaseModel):
    risk_id: str

    title: str

    severity: RiskSeverity

    probability: float = Field(
        ge=0,
        le=1
    )

    root_cause: str

    impact: str

    evidence: list[dict[str, Any]] = Field(
        default_factory=list
    )

    causal_chain: list[str] = Field(
        default_factory=list
    )

    recommendation: str

    verified: bool = False

    verification_confidence: float = Field(
        default=0.0,
        ge=0,
        le=1
    )


class RiskList(BaseModel):
    risks: list[Risk] = Field(
        default_factory=list
    )


class SimulationRequest(BaseModel):
    node_id: str = "pr_11"

    delay_days: int = Field(
        default=3,
        ge=0,
        le=365
    )

    event_type: str = "delay"
    latency_ms: int = 0


class SimulationResult(BaseModel):
    scenario: str

    affected_nodes: list[str] = Field(
        default_factory=list
    )

    new_risks: list[Risk] = Field(
        default_factory=list
    )

    recommendation: str

    after: dict[str, Any] = Field(
        default_factory=dict
    )

    causal_chain: list[str] = Field(
        default_factory=list
    )