from typing import Any, Literal, Optional
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
    # Target node: supports target_node or node_id interchangeably
    node_id: str = "pr_11"
    target_node: Optional[str] = None
    
    # Generic Failure Event Types
    # e.g., PR_DELAY, TASK_DELAY, SERVICE_FAILURE, TIMEOUT, LATENCY,
    # HTTP_500, HTTP_503, MALFORMED_RESPONSE, DEPLOYMENT_FAILURE, COMPONENT_UNAVAILABLE
    event_type: str = "PR_DELAY"
    
    # Event parameters
    delay_days: Optional[int] = 3
    delay_hours: Optional[int] = None
    latency_ms: Optional[int] = None
    http_status: Optional[int] = None
    duration: Optional[str] = None
    severity: Optional[str] = "high"
    max_depth: Optional[int] = 10
    description: Optional[str] = None

    @property
    def effective_target_node(self) -> str:
        return self.target_node or self.node_id


class SimulationResult(BaseModel):
    scenario: str

    affected_nodes: list[str] = Field(
        default_factory=list
    )

    unaffected_nodes: list[str] = Field(
        default_factory=list
    )

    unknown_nodes: list[str] = Field(
        default_factory=list
    )

    new_risks: list[Risk] = Field(
        default_factory=list
    )

    recommendation: str

    before: dict[str, Any] = Field(
        default_factory=dict
    )

    after: dict[str, Any] = Field(
        default_factory=dict
    )

    causal_chain: list[str] = Field(
        default_factory=list
    )

    propagation_paths: list[Any] = Field(
        default_factory=list
    )

    evidence: list[dict[str, Any]] = Field(
        default_factory=list
    )

    truncated: bool = False

    warnings: list[str] = Field(
        default_factory=list
    )