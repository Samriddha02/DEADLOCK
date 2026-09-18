from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

from app.models.risk_models import Risk, SimulationResult


# ============================================================
# AGENT TRACE
# ============================================================

class AgentTrace(BaseModel):
    agent_name: str
    execution_order: int
    status: Literal["RUNNING", "COMPLETED", "FAILED", "PARTIAL", "SKIPPED"] = "COMPLETED"
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: float = 0.0
    error_info: str | None = None


# ============================================================
# ADVERSARIAL VERDICT
# ============================================================

class AdversarialVerdict(BaseModel):
    candidate_id: str
    status: Literal["VERIFIED", "REJECTED", "INSUFFICIENT_EVIDENCE"]
    is_false_positive: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    state: str | None = None
    temporal_validity: bool | None = None
    contradictions: list[str] = Field(default_factory=list)


# ============================================================
# SUGGESTED INTERVENTION
# ============================================================

class SuggestedIntervention(BaseModel):
    id: str
    target_entity: str
    category: str = "general"
    action: str
    rationale: str
    expected_impact: str = ""
    executed: bool = False  # Always False as interventions are SUGGESTED only


# ============================================================
# INVESTIGATION RESULT
# ============================================================

class InvestigationResult(BaseModel):
    project: str
    source: str = "seeded"
    request_id: str = ""
    status: str = "COMPLETED"
    risks: list[Risk] = Field(default_factory=list)
    dependency_findings: dict[str, Any] = Field(default_factory=dict)
    bottleneck_findings: list[dict[str, Any]] = Field(default_factory=list)
    adversarial_verdicts: list[AdversarialVerdict] = Field(default_factory=list)
    simulation_results: list[SimulationResult] = Field(default_factory=list)
    explanations: list[dict[str, Any]] = Field(default_factory=list)
    interventions: list[SuggestedIntervention] = Field(default_factory=list)
    agent_trace: list[AgentTrace] = Field(default_factory=list)
