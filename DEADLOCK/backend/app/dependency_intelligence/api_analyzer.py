from __future__ import annotations

import re
from app.dependency_intelligence.models import EvidenceModel

FASTAPI_ROUTE_PATTERN = re.compile(
    r'''@(app|router)\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]'''
)
EXPRESS_ROUTE_PATTERN = re.compile(
    r'''(?<!@)\b(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]'''
)
FETCH_PATTERN = re.compile(
    r'''(?:fetch|axios\.(?:get|post|put|delete|patch))\s*\(\s*['"]([^'"]+)['"]'''
)


class ApiDependencyAnalyzer:
    def extract_api_routes(self, filepath: str, content: str) -> list[dict[str, str]]:
        routes = []
        normalized_file = filepath.replace("\\", "/")

        for match in FASTAPI_ROUTE_PATTERN.finditer(content):
            routes.append({
                "file": normalized_file,
                "method": match.group(2).upper(),
                "path": match.group(3),
                "framework": "fastapi",
            })

        for match in EXPRESS_ROUTE_PATTERN.finditer(content):
            routes.append({
                "file": normalized_file,
                "method": match.group(1).upper(),
                "path": match.group(2),
                "framework": "express",
            })

        return routes

    def extract_api_calls(self, filepath: str, content: str) -> list[dict[str, str]]:
        calls = []
        normalized_file = filepath.replace("\\", "/")

        for match in FETCH_PATTERN.finditer(content):
            url_str = match.group(1)
            endpoint = re.sub(r"^https?://[^/]+", "", url_str)
            if not endpoint.startswith("/"):
                endpoint = f"/{endpoint}"
            calls.append({
                "file": normalized_file,
                "endpoint": endpoint,
                "raw_url": url_str,
            })

        return calls

    def match_api_dependencies(
        self,
        routes: list[dict[str, str]],
        calls: list[dict[str, str]],
    ) -> list[EvidenceModel]:
        evidence_list: list[EvidenceModel] = []
        route_index: dict[str, dict[str, str]] = {}
        for r in routes:
            route_index[r["path"].rstrip("/")] = r

        for c in calls:
            call_file = c["file"]
            raw_endpoint = c["endpoint"].rstrip("/")
            
            matched_route = route_index.get(raw_endpoint)
            if not matched_route:
                for r_path, r_info in route_index.items():
                    pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", r_path) + "$"
                    if re.match(pattern, raw_endpoint):
                        matched_route = r_info
                        break

            if matched_route:
                evidence_list.append(EvidenceModel(
                    source_node=f"file:{call_file}",
                    target_node=f"endpoint:{matched_route['method']} {matched_route['path']}",
                    relationship_type="API_CALL",
                    evidence=f"Frontend file '{call_file}' calls endpoint '{matched_route['method']} {matched_route['path']}' implemented in '{matched_route['file']}'",
                    inferred=False,
                    inference_rule="static_endpoint_matching",
                    confidence=1.0,
                    source_type="api_consumer",
                    source_id=call_file,
                    metadata={"target_file": matched_route["file"], "endpoint": matched_route["path"]},
                ))
                evidence_list.append(EvidenceModel(
                    source_node=f"file:{call_file}",
                    target_node=f"file:{matched_route['file']}",
                    relationship_type="API_PROVIDER_DEPENDENCY",
                    evidence=f"'{call_file}' depends on backend API provider '{matched_route['file']}' via route '{matched_route['path']}'",
                    inferred=True,
                    inference_rule="api_route_call_linkage",
                    confidence=0.95,
                    source_type="api_linkage",
                ))

        seen = set()
        deduped = []
        for e in evidence_list:
            key = (e.source_node, e.target_node, e.relationship_type)
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        return deduped
