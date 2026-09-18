"""Evidence-first API routes for demo and compatibility.

Uses the canonical DEADLOCK risk engine, graph builder, and seeded dataset.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import os
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.graph.graph_builder import build_graph
from app.risk_engine.detector import detect_risks
from app.api.routes_risks import load_seeded_dataset, enrich_risk, risk_to_dict
from app.database.repositories import load_project, ProjectNotFoundError
from app.models.risk_models import SimulationRequest
from app.simulation.what_if import simulate


router = APIRouter(tags=["deadlock-v1"])


class AnalyzeRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=100)
    repo: str = Field(min_length=1, max_length=100)


class DependencyFailureInput(BaseModel):
    dependency_id: str = Field(min_length=1)
    failure_type: Literal["timeout", "500", "503", "latency", "malformed_response"] = "timeout"
    latency_ms: int = Field(default=0, ge=0, le=120_000)


class WebhookEvent(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    source: str = Field(default="n8n", max_length=100)
    timestamp: datetime | None = None
    payload: dict = Field(default_factory=dict)


def is_demo_repo(owner: str, repo: str) -> bool:
    """Check if owner/repo refers to the canonical demo project."""
    owner_lower = owner.strip().lower()
    repo_lower = repo.strip().lower()
    demo_pairs = {
        ("aritra-dsu", "rf-sentinel"),
        ("nexus-org", "nexus-core"),
        ("campusconnect", "demo"),
        ("demo", "demo"),
        ("test", "demo"),
    }
    if (owner_lower, repo_lower) in demo_pairs:
        return True
    if repo_lower in {"rf-sentinel", "nexus-core", "demo", "seeded_project"}:
        return True
    return False


def get_canonical_demo_payload(
    owner: str = "Aritra-DSU",
    repo: str = "RF-SENTINEL",
) -> dict[str, Any]:
    """
    Generate demo payload using the canonical DEADLOCK engine and seeded dataset.
    """
    dataset = load_seeded_dataset()
    graph = build_graph(dataset)
    detected_risks = detect_risks(dataset)

    final_risks = []
    for r in detected_risks:
        try:
            enriched = enrich_risk(r)
        except Exception:
            enriched = r
        final_risks.append(risk_to_dict(enriched))

    nodes = [
        {"id": node_id, **data}
        for node_id, data in graph.nodes(data=True)
    ]
    edges = [
        {"source": source, "target": target, **data}
        for source, target, data in graph.edges(data=True)
    ]

    project_info = dataset.get("project", {})
    project_dict = {
        "id": project_info.get("id", "proj_nexus_01"),
        "name": project_info.get("name", "NEXUS Core Platform"),
        "owner": owner,
        "repo": repo,
        "mode": "demo",
        "source": "data/seeded_project.json",
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "nodes": len(nodes),
            "relationships": len(edges),
            "blocked_tasks": 1,
            "critical_risks": sum(1 for r in final_risks if str(r.get("severity", "")).upper() == "CRITICAL"),
        },
    }

    return {
        "project": project_dict,
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
        "risks": final_risks,
    }


@router.get("/api/projects/demo")
def demo_project() -> dict:
    """Return the canonical demo project payload."""
    return get_canonical_demo_payload()


@router.post("/api/projects/analyze")
async def analyze_project(request: AnalyzeRequest) -> dict:
    """
    Analyze a project.
    If demo repo, returns canonical seeded project analysis.
    If synced in SQLite, returns synced project analysis.
    If not found, returns HTTP 404.
    """
    owner = request.owner.strip()
    repo = request.repo.strip()

    if is_demo_repo(owner, repo):
        payload = get_canonical_demo_payload(owner, repo)
        payload["analysis_request"] = {"owner": owner, "repo": repo}
        return payload

    try:
        db_project = load_project(owner, repo)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{owner}/{repo}' has not been synced yet. Please sync the repository first via POST /api/projects/{owner}/{repo}/sync.",
        )

    if db_project:
        graph = build_graph(db_project)
        risks = detect_risks(db_project)
        final_risks = []
        for r in risks:
            try:
                enriched = enrich_risk(r)
            except Exception:
                enriched = r
            final_risks.append(risk_to_dict(enriched))

        nodes = [{"id": n, **d} for n, d in graph.nodes(data=True)]
        edges = [{"source": u, "target": v, **d} for u, v, d in graph.edges(data=True)]

        return {
            "project": {
                "owner": owner,
                "repo": repo,
                "mode": "synced",
                "source": "SQLite database",
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "nodes": len(nodes),
                    "relationships": len(edges),
                    "blocked_tasks": 0,
                    "critical_risks": sum(1 for r in final_risks if str(r.get("severity", "")).upper() == "CRITICAL"),
                },
            },
            "graph": {"nodes": nodes, "edges": edges},
            "risks": final_risks,
            "analysis_request": {"owner": owner, "repo": repo},
        }

    raise HTTPException(
        status_code=404,
        detail=f"Project '{owner}/{repo}' has not been synced yet. Please sync the repository first via POST /api/projects/{owner}/{repo}/sync.",
    )




@router.get("/api/projects/current")
def current_project() -> dict:
    """Return metadata for current demo project."""
    return get_canonical_demo_payload()["project"]


@router.get("/api/risks")
def risks() -> dict:
    """Return risks for canonical demo project."""
    payload = get_canonical_demo_payload()
    return {
        "project": payload["project"],
        "risks": payload["risks"],
    }


@router.get("/api/risks/{risk_id}")
def risk_detail(risk_id: str) -> dict:
    """Return risk details by risk ID."""
    for candidate in get_canonical_demo_payload()["risks"]:
        if candidate.get("risk_id") == risk_id or candidate.get("id") == risk_id:
            return candidate
    raise HTTPException(
        status_code=404,
        detail=f"Risk '{risk_id}' was not found.",
    )


@router.get("/api/graph")
def graph() -> dict:
    """Return canonical demo graph."""
    return get_canonical_demo_payload()["graph"]


@router.post("/api/dependencies/test-failure")
async def dependency_failure(request: DependencyFailureInput) -> dict:
    """
    Trigger an optional Beeceptor mock before calculating local impact.
    Propagates through DEADLOCK's canonical graph.
    """
    node_id = request.dependency_id
    if node_id in {"PR-47", "PR_47"}:
        node_id = "pr_11"

    dataset = load_seeded_dataset()
    sim_result = simulate(
        dataset,
        SimulationRequest(node_id=node_id, delay_days=3),
    )

    base_url = settings.beeceptor_base_url.strip().rstrip("/")
    delivery: dict[str, object] = {"configured": bool(base_url)}
    simulation_mode = "local"
    event_source = "CONTROLLED DEMO SIMULATION"

    if base_url:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    base_url,
                    json={
                        "dependency_id": request.dependency_id,
                        "failure_type": request.failure_type,
                        "latency_ms": request.latency_ms,
                        "source": "DEADLOCK controlled simulation",
                    },
                )
            delivery.update({
                "status_code": response.status_code,
                "delivered": response.is_success,
            })
            if response.is_success:
                simulation_mode = "beeceptor"
                event_source = "CONTROLLED BEECEPTOR SIMULATION"
            else:
                delivery["fallback_reason"] = "Beeceptor returned a non-success response."
        except httpx.RequestError as exc:
            delivery["fallback_reason"] = f"Beeceptor was unreachable: {exc.__class__.__name__}"

    return {
        "scenario": sim_result.scenario,
        "affected_nodes": sim_result.affected_nodes,
        "recommendation": sim_result.recommendation,
        "after": sim_result.after,
        "causal_chain": sim_result.causal_chain,
        "failure_type": request.failure_type,
        "event_source": event_source,
        "simulation_mode": simulation_mode,
        "beeceptor_delivery": delivery,
    }


@router.post("/api/webhooks/events")
async def webhook_event(
    event: WebhookEvent,
    x_deadlock_secret: str | None = Header(default=None),
) -> dict:
    """Handle incoming webhook events."""
    secret = os.getenv("N8N_WEBHOOK_SECRET", "")
    if secret and not hmac.compare_digest(secret, x_deadlock_secret or ""):
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    dependency_id = str(event.payload.get("dependency_id", "pr_11"))
    if event.event_type == "dependency_failure":
        return await dependency_failure(
            DependencyFailureInput(
                dependency_id=dependency_id,
                failure_type=str(event.payload.get("failure_type", "timeout")),
                latency_ms=int(event.payload.get("latency_ms", 0)),
            )
        )
    return {
        "accepted": True,
        "event_type": event.event_type,
        "source": event.source,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "note": "Event accepted; no dependency-impact rule applies to this event type.",
    }


@router.get("/api/evidence/{source_id}")
def evidence(source_id: str) -> dict:
    """Retrieve evidence entries by source_id from canonical risks."""
    for risk_item in get_canonical_demo_payload()["risks"]:
        if risk_item.get("root_cause") == source_id:
            return {"source_id": source_id, "evidence": risk_item.get("evidence", [])}
        evidence_list = risk_item.get("evidence", [])
        if isinstance(evidence_list, list):
            matches = [
                item
                for item in evidence_list
                if isinstance(item, dict) and str(item.get("id")) == source_id
            ]
            if matches:
                return {"source_id": source_id, "evidence": matches}
    raise HTTPException(
        status_code=404,
        detail=f"Evidence '{source_id}' was not found.",
    )
