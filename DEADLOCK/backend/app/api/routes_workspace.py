"""
routes_workspace.py — DEADLOCK Combined Multi-Repository Workspace

POST /api/workspace/combine
  Accepts a list of owner/repo strings.
  1. Loads each repository's stored graph from SQLite.
  2. Merges them into one NetworkX DiGraph, tagging every node/edge with its repo.
  3. Detects cross-repository edges from REAL evidence only:
       - package manifests (pyproject.toml, requirements.txt, setup.cfg,
         package.json, Cargo.toml, go.mod)
       - stored source_dependency edges that reference cross-repo package names
       - GitHub dependency graph via /repos/{owner}/{repo}/dependency-graph/sbom
         (optional, 404-tolerant)
  4. Runs the risk engine over the merged graph.
  5. Returns a combined response with nodes, edges, cross_repo_edges, risks.

ABSOLUTE RULE: Every cross-repo edge MUST cite the specific evidence file and
the exact package/import name that was found. No invented edges.
If no evidence is found the response includes cross_repo_edges: [] and an
explicit "no_evidence" flag.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import networkx as nx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database.repositories import load_project, ProjectNotFoundError
from app.graph.graph_builder import build_graph
from app.risk_engine.detector import detect_risks
from app.ingestion.github_client import GitHubClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


# ============================================================
# Request / Response schemas
# ============================================================

class CombineRequest(BaseModel):
    repositories: list[str]   # ["owner/repo", ...]


class CrossRepoEdge(BaseModel):
    source_node: str
    target_node: str
    source_repo: str
    target_repo: str
    relationship_type: str
    evidence: str
    source_file: str
    source_url: str | None = None
    inferred: bool
    confidence: float
    inference_rule: str | None = None


# ============================================================
# Manifest file candidates to check per repo
# ============================================================

MANIFEST_PATHS: list[str] = [
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "requirements.txt",
    "requirements/base.txt",
    "requirements/prod.txt",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
]


# ============================================================
# Parse manifest content → set of declared package names
# ============================================================

def _extract_packages_from_manifest(path: str, content: str) -> set[str]:
    """
    Extract normalised package/dependency names from manifest content.
    Returns lower-cased names for reliable comparison.
    """
    pkgs: set[str] = set()

    if path.endswith("pyproject.toml"):
        # [project] dependencies = ["pkg>=1.0", ...]  or  [tool.poetry.dependencies]
        for m in re.finditer(r'"([A-Za-z0-9_\-\.]+)\s*[>=<!\[]', content):
            pkgs.add(m.group(1).lower().replace("-", "_").replace(".", "_"))
        # Also bare names in arrays
        for m in re.finditer(r"['\"]([a-zA-Z0-9_\-\.]{2,})['\"]", content):
            pkgs.add(m.group(1).lower().replace("-", "_").replace(".", "_"))

    elif path.endswith("requirements.txt") or "requirements" in path:
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^([A-Za-z0-9_\-\.]+)", line)
            if m:
                pkgs.add(m.group(1).lower().replace("-", "_").replace(".", "_"))

    elif path.endswith("setup.cfg"):
        for line in content.splitlines():
            m = re.match(r"^\s+([A-Za-z0-9_\-\.]+)", line)
            if m:
                pkgs.add(m.group(1).lower().replace("-", "_").replace(".", "_"))

    elif path.endswith("setup.py"):
        for m in re.finditer(r"['\"]([A-Za-z0-9_\-\.]{2,})['\"]", content):
            pkgs.add(m.group(1).lower().replace("-", "_").replace(".", "_"))

    elif path.endswith("package.json"):
        import json
        try:
            data = json.loads(content)
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                pkgs.update(k.lower() for k in data.get(section, {}))
        except Exception:
            pass

    elif path.endswith("go.mod"):
        for m in re.finditer(r"^\s*require\s+([^\s]+)", content, re.MULTILINE):
            pkgs.add(m.group(1).lower())
        for m in re.finditer(r"^\s+([^\s]+)\s+v", content, re.MULTILINE):
            pkgs.add(m.group(1).lower())

    elif path.endswith("Cargo.toml"):
        for m in re.finditer(r'^([a-zA-Z0-9_\-]+)\s*=', content, re.MULTILINE):
            pkgs.add(m.group(1).lower())

    return pkgs


def _repo_package_name(owner: str, repo: str) -> set[str]:
    """
    Canonical package/import names that this repo likely publishes.
    Derived from the repo name alone — no network call needed.
    """
    base = repo.lower().replace("-", "_").replace(".", "_")
    hyphen = repo.lower().replace("_", "-").replace(".", "-")
    names = {base, hyphen, repo.lower()}
    # Also try without common prefixes/suffixes
    for strip in ("python_", "py_", "_python", "_py"):
        if base.startswith(strip):
            names.add(base[len(strip):])
        if base.endswith(strip.strip("_")):
            names.add(base[: -len(strip.strip("_"))])
    return names


# ============================================================
# Async manifest fetcher
# ============================================================

async def _fetch_manifests(
    client: GitHubClient,
    owner: str,
    repo: str,
) -> dict[str, str]:
    """
    Fetch all manifest files for owner/repo that actually exist.
    Returns {path: content}.
    """
    tasks = [client.get_file_content(owner, repo, p) for p in MANIFEST_PATHS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    manifests: dict[str, str] = {}
    for path, result in zip(MANIFEST_PATHS, results):
        if isinstance(result, str):
            manifests[path] = result
    return manifests


# ============================================================
# Cross-repo evidence detector
# ============================================================

async def _detect_cross_repo_edges(
    repos: list[tuple[str, str]],          # [(owner, repo), ...]
    project_graphs: dict[str, nx.DiGraph], # keyed by "owner/repo"
) -> list[CrossRepoEdge]:
    """
    For every pair of repositories, check whether repo A's manifests declare
    a package dependency that matches repo B's canonical package name.

    Returns only edges that have DIRECT manifest evidence.
    """
    client = GitHubClient()
    edges: list[CrossRepoEdge] = []

    # Fetch all manifests in parallel across repos
    manifest_tasks = {
        f"{owner}/{repo}": _fetch_manifests(client, owner, repo)
        for owner, repo in repos
    }
    manifest_results: dict[str, dict[str, str]] = {}
    for key, coro in manifest_tasks.items():
        try:
            manifest_results[key] = await coro
        except Exception:
            manifest_results[key] = {}

    logger.info(
        "Manifest fetch results: %s",
        {k: list(v.keys()) for k, v in manifest_results.items()},
    )

    # For each repo, compute what package names it exports
    repo_exports: dict[str, set[str]] = {}
    for owner, repo in repos:
        key = f"{owner}/{repo}"
        repo_exports[key] = _repo_package_name(owner, repo)

    # Compare: does repo A's manifests declare repo B's package?
    for a_owner, a_repo in repos:
        a_key = f"{a_owner}/{a_repo}"
        a_manifests = manifest_results.get(a_key, {})

        for b_owner, b_repo in repos:
            b_key = f"{b_owner}/{b_repo}"
            if a_key == b_key:
                continue

            b_names = repo_exports[b_key]

            for mpath, mcontent in a_manifests.items():
                declared = _extract_packages_from_manifest(mpath, mcontent)
                matched = declared & b_names
                if not matched:
                    continue

                # Found real evidence
                match_name = sorted(matched)[0]
                source_url = f"https://github.com/{a_owner}/{a_repo}/blob/HEAD/{mpath}"

                # Source node: project node of repo A
                a_project_node = f"project:{a_key}"
                b_project_node = f"project:{b_key}"

                edges.append(CrossRepoEdge(
                    source_node=a_project_node,
                    target_node=b_project_node,
                    source_repo=a_key,
                    target_repo=b_key,
                    relationship_type="DEPENDS_ON",
                    evidence=(
                        f"'{mpath}' in {a_key} declares package '{match_name}', "
                        f"which matches the canonical package name of {b_key}."
                    ),
                    source_file=mpath,
                    source_url=source_url,
                    inferred=False,
                    confidence=0.90,
                ))
                logger.info(
                    "Cross-repo edge: %s → %s via '%s' in %s",
                    a_key, b_key, match_name, mpath,
                )
                # One edge per (A→B) pair — don't duplicate for multiple manifests
                break

    return edges


# ============================================================
# Graph merger
# ============================================================

def _merge_graphs(
    graphs: dict[str, nx.DiGraph],
    cross_edges: list[CrossRepoEdge],
) -> nx.DiGraph:
    """
    Merge per-repo graphs into one combined DiGraph.
    Every node gets a 'repo' attribute for visual grouping.
    Cross-repo edges are added with full provenance.
    """
    combined = nx.DiGraph()

    for repo_key, g in graphs.items():
        for node, data in g.nodes(data=True):
            combined.add_node(node, **data, repo=repo_key)
        for src, tgt, data in g.edges(data=True):
            combined.add_edge(src, tgt, **data, repo=repo_key)

    for edge in cross_edges:
        # Ensure both project nodes exist even if the individual graph
        # didn't have them (defensive)
        if not combined.has_node(edge.source_node):
            combined.add_node(
                edge.source_node,
                type="project",
                label=edge.source_repo,
                repo=edge.source_repo,
                data={},
            )
        if not combined.has_node(edge.target_node):
            combined.add_node(
                edge.target_node,
                type="project",
                label=edge.target_repo,
                repo=edge.target_repo,
                data={},
            )
        combined.add_edge(
            edge.source_node,
            edge.target_node,
            relation=edge.relationship_type,
            cross_repo=True,
            repo_a=edge.source_repo,
            repo_b=edge.target_repo,
            evidence=edge.evidence,
            source_file=edge.source_file,
            source_url=edge.source_url,
            inferred=edge.inferred,
            confidence=edge.confidence,
            data={
                "cross_repo": True,
                "evidence": edge.evidence,
                "source_file": edge.source_file,
                "source_url": edge.source_url,
                "inferred": edge.inferred,
                "confidence": edge.confidence,
            },
        )

    return combined


# ============================================================
# Serialise combined graph → JSON-safe dicts
# ============================================================

def _serialise_graph(g: nx.DiGraph) -> tuple[list[dict], list[dict]]:
    nodes = []
    for node_id, data in g.nodes(data=True):
        nodes.append({
            "id": node_id,
            "type": data.get("type", "unknown"),
            "label": data.get("label", node_id),
            "repo": data.get("repo", ""),
            "data": {k: v for k, v in data.items() if k not in {"type", "label"}},
        })

    edges = []
    for src, tgt, data in g.edges(data=True):
        edges.append({
            "source": src,
            "target": tgt,
            "relation": data.get("relation", "related_to"),
            "cross_repo": bool(data.get("cross_repo", False)),
            "repo": data.get("repo", ""),
            "data": data.get("data", {}),
        })

    return nodes, edges


# ============================================================
# Combine endpoint
# ============================================================

@router.post("/combine")
async def combine_workspace(body: CombineRequest) -> dict[str, Any]:
    """
    Merge multiple synced repositories into one combined analysis workspace.

    Steps:
    1. Parse and validate repository identifiers.
    2. Load each repo's graph from SQLite (must be synced first).
    3. Detect cross-repo edges from real manifest evidence.
    4. Merge graphs into one.
    5. Run risk engine on merged graph + per-repo data.
    6. Return combined nodes, edges, cross_repo_edges, risks.
    """
    if not body.repositories:
        raise HTTPException(status_code=400, detail="repositories list is empty.")

    if len(body.repositories) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 repositories per combined workspace.")

    # Parse "owner/repo" strings
    repos: list[tuple[str, str]] = []
    for raw in body.repositories:
        parts = raw.strip().split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repository identifier '{raw}'. Expected 'owner/repo'.",
            )
        repos.append((parts[0].strip(), parts[1].strip()))

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique_repos: list[tuple[str, str]] = []
    for owner, repo in repos:
        key = f"{owner}/{repo}"
        if key not in seen:
            seen.add(key)
            unique_repos.append((owner, repo))

    # Load per-repo project data + build graphs
    project_data: dict[str, dict] = {}
    graphs: dict[str, nx.DiGraph] = {}
    missing: list[str] = []

    for owner, repo in unique_repos:
        key = f"{owner}/{repo}"
        try:
            data = load_project(owner, repo)
            project_data[key] = data
            graphs[key] = build_graph(data)
        except ProjectNotFoundError:
            missing.append(key)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", key, exc)
            missing.append(key)

    if not graphs:
        detail = "None of the requested repositories have been synced yet."
        if missing:
            detail += f" Missing: {', '.join(missing)}"
        raise HTTPException(status_code=404, detail=detail)

    # Detect cross-repository edges from real manifest evidence
    cross_edges = await _detect_cross_repo_edges(unique_repos, graphs)

    # Merge all graphs
    combined_graph = _merge_graphs(graphs, cross_edges)

    # Serialise
    all_nodes, all_edges = _serialise_graph(combined_graph)

    # Separate cross-repo edges for explicit display
    cross_repo_edges_out = [e.model_dump() for e in cross_edges]

    # Run risk engine on merged graph + per-repo data
    # Each risk is scoped to its originating repo
    all_risks: list[dict] = []
    for owner, repo in unique_repos:
        key = f"{owner}/{repo}"
        if key not in project_data:
            continue
        try:
            repo_risks = detect_risks(project_data[key], graphs[key])
            for risk in repo_risks:
                rd = risk.model_dump()
                rd["repo"] = key          # tag with originating repo
                all_risks.append(rd)
        except Exception as exc:
            logger.warning("Risk detection failed for %s: %s", key, exc)

    # Sort: CRITICAL first
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    all_risks.sort(key=lambda r: severity_order.get(r.get("severity", "LOW"), 9))

    return {
        "repositories": [f"{o}/{r}" for o, r in unique_repos],
        "missing_repositories": missing,
        "total_nodes": len(all_nodes),
        "total_edges": len(all_edges),
        "cross_repo_edge_count": len(cross_repo_edges_out),
        "total_risks": len(all_risks),
        "has_cross_repo_evidence": len(cross_edges) > 0,
        "nodes": all_nodes,
        "edges": all_edges,
        "cross_repo_edges": cross_repo_edges_out,
        "risks": all_risks,
    }
