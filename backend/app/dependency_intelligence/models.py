from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    DIRECT = "DIRECT"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class EvidenceModel(BaseModel):
    source_node: str
    target_node: str
    relationship_type: str = "IMPORTS"
    evidence: str
    inferred: bool = False
    inference_rule: str = "deterministic_static_analysis"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_type: str = "source_code"
    source_id: str | None = None
    source_url: str | None = None
    timestamp: str | None = None
    state: str = "ACTIVE"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectIntelligenceMetadata(BaseModel):
    project_intelligence_status: str = "complete"
    known_nodes: int = 0
    known_relationships: int = 0
    known_deadlines: int = 0
    unknown_areas: list[str] = Field(default_factory=list)
    discovered_dependencies: list[EvidenceModel] = Field(default_factory=list)
    manifest_packages: list[dict[str, str]] = Field(default_factory=list)
    api_endpoints: list[dict[str, str]] = Field(default_factory=list)
