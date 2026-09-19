from __future__ import annotations

from typing import Any

from app.dependency_intelligence.api_analyzer import ApiDependencyAnalyzer
from app.dependency_intelligence.js_ts_analyzer import JsTsDependencyAnalyzer
from app.dependency_intelligence.manifest_analyzer import ManifestDependencyAnalyzer
from app.dependency_intelligence.models import EvidenceModel, ProjectIntelligenceMetadata
from app.dependency_intelligence.python_analyzer import PythonDependencyAnalyzer
from app.dependency_intelligence.schema_config_analyzer import SchemaConfigAnalyzer
from app.dependency_intelligence.test_analyzer import TestDependencyAnalyzer


class DependencyIntelligenceManager:
    def __init__(self) -> None:
        self.py_analyzer = PythonDependencyAnalyzer()
        self.js_analyzer = JsTsDependencyAnalyzer()
        self.api_analyzer = ApiDependencyAnalyzer()
        self.manifest_analyzer = ManifestDependencyAnalyzer()
        self.schema_analyzer = SchemaConfigAnalyzer()
        self.test_analyzer = TestDependencyAnalyzer()

    def analyze_project_files(
        self,
        files: dict[str, str],
        extra_metadata: dict[str, Any] | None = None,
    ) -> ProjectIntelligenceMetadata:
        all_filepaths = {f.replace("\\", "/") for f in files.keys()}
        discovered: list[EvidenceModel] = []
        unknown_areas: list[str] = []
        all_routes: list[dict[str, str]] = []
        all_calls: list[dict[str, str]] = []
        all_manifest_packages: list[dict[str, str]] = []

        all_schemas: dict[str, str] = {}
        for path, content in files.items():
            norm_p = path.replace("\\", "/")
            if norm_p.endswith((".py", ".ts", ".tsx")):
                for line in content.splitlines():
                    if "class " in line and "(BaseModel)" in line:
                        cls_name = line.split("class ")[1].split("(")[0].strip()
                        all_schemas[cls_name] = norm_p
                    elif "interface " in line:
                        iface_name = line.split("interface ")[1].split("{")[0].strip()
                        all_schemas[iface_name] = norm_p

        for path, content in files.items():
            norm_p = path.replace("\\", "/")
            if norm_p.endswith(".py"):
                py_ev, py_unk = self.py_analyzer.analyze_source(norm_p, content, all_filepaths)
                discovered.extend(py_ev)
                unknown_areas.extend(py_unk)

                cfg_ev = self.schema_analyzer.analyze_configuration_references(norm_p, content, all_filepaths)
                discovered.extend(cfg_ev)

                sch_ev = self.schema_analyzer.analyze_schema_contracts(norm_p, content, all_schemas)
                discovered.extend(sch_ev)

                tst_ev = self.test_analyzer.analyze_test_dependencies(norm_p, content, all_filepaths)
                discovered.extend(tst_ev)

                routes = self.api_analyzer.extract_api_routes(norm_p, content)
                all_routes.extend(routes)

            elif norm_p.endswith((".js", ".jsx", ".ts", ".tsx")):
                js_ev, js_unk = self.js_analyzer.analyze_source(norm_p, content, all_filepaths)
                discovered.extend(js_ev)
                unknown_areas.extend(js_unk)

                calls = self.api_analyzer.extract_api_calls(norm_p, content)
                all_calls.extend(calls)

                routes = self.api_analyzer.extract_api_routes(norm_p, content)
                all_routes.extend(routes)

            elif norm_p.endswith("package.json"):
                pkg_ev = self.manifest_analyzer.parse_package_json(norm_p, content)
                discovered.extend(pkg_ev)
                for e in pkg_ev:
                    all_manifest_packages.append(e.metadata)

            elif norm_p.endswith("requirements.txt"):
                req_ev = self.manifest_analyzer.parse_requirements_txt(norm_p, content)
                discovered.extend(req_ev)
                for e in req_ev:
                    all_manifest_packages.append(e.metadata)

        api_ev = self.api_analyzer.match_api_dependencies(all_routes, all_calls)
        discovered.extend(api_ev)

        seen_pairs: dict[tuple[str, str], EvidenceModel] = {}
        for d in discovered:
            pair = (d.source_node, d.target_node)
            if pair not in seen_pairs:
                seen_pairs[pair] = d
            elif seen_pairs[pair].relationship_type == "CONFIG_DEPENDENCY" and d.relationship_type in {"IMPORTS", "API_PROVIDER_DEPENDENCY"}:
                seen_pairs[pair] = d

        unique_dependencies = list(seen_pairs.values())

        has_manifests = any(p.endswith(("package.json", "requirements.txt", "pyproject.toml")) for p in all_filepaths)
        status = "complete"
        if len(files) <= 3 or not has_manifests or unknown_areas:
            status = "partial"

        unique_nodes = set()
        for d in unique_dependencies:
            unique_nodes.add(d.source_node)
            unique_nodes.add(d.target_node)
        for p in all_filepaths:
            unique_nodes.add(f"file:{p}")

        return ProjectIntelligenceMetadata(
            project_intelligence_status=status,
            known_nodes=len(unique_nodes),
            known_relationships=len(unique_dependencies),
            known_deadlines=0,
            unknown_areas=unknown_areas[:15],
            discovered_dependencies=unique_dependencies,
            manifest_packages=all_manifest_packages,
            api_endpoints=all_routes,
        )
