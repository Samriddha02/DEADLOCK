from __future__ import annotations

"""
Phase 7: Real Dependency Intelligence & Evidence-Backed Graph Tests.
Executed with Python 3.11.9 environment.
"""

import sys
import copy
import pytest
from fastapi.testclient import TestClient

from app.dependency_intelligence.models import (
    EvidenceModel,
    ProjectIntelligenceMetadata,
    RelationshipType,
)
from app.dependency_intelligence.python_analyzer import PythonDependencyAnalyzer
from app.dependency_intelligence.js_ts_analyzer import JsTsDependencyAnalyzer
from app.dependency_intelligence.api_analyzer import ApiDependencyAnalyzer
from app.dependency_intelligence.manifest_analyzer import ManifestDependencyAnalyzer
from app.dependency_intelligence.schema_config_analyzer import SchemaConfigAnalyzer
from app.dependency_intelligence.test_analyzer import TestDependencyAnalyzer
from app.dependency_intelligence.progressive_manager import DependencyIntelligenceManager
from app.dependency_intelligence.graph_integrator import integrate_dependency_intelligence
from app.graph.graph_builder import build_graph, validate_causal_path
from app.simulation.what_if import simulate, SimulationRequest
from app.agents.investigation_pipeline import run_investigation_pipeline
from app.api.routes_risks import load_seeded_dataset
from app.main import app


# ═══════════════════════════════════════════════════════════════════════════
# 1. Python Direct Import
# ═══════════════════════════════════════════════════════════════════════════

def test_python_direct_import():
    analyzer = PythonDependencyAnalyzer()
    files = {"app.py", "config.py"}
    content = "import config\nprint(config.PORT)"
    
    evidence, unknowns = analyzer.analyze_source("app.py", content, files)
    assert len(evidence) == 1
    assert evidence[0].source_node == "file:app.py"
    assert evidence[0].target_node == "file:config.py"
    assert evidence[0].relationship_type == "IMPORTS"
    assert evidence[0].inferred is False
    assert evidence[0].confidence == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Python From-Import
# ═══════════════════════════════════════════════════════════════════════════

def test_python_from_import():
    analyzer = PythonDependencyAnalyzer()
    files = {"backend/main.py", "backend/config.py"}
    content = "from backend.config import DATABASE_URL, TIMEOUT"
    
    evidence, unknowns = analyzer.analyze_source("backend/main.py", content, files)
    assert len(evidence) == 1
    assert evidence[0].target_node == "file:backend/config.py"
    assert "DATABASE_URL" in evidence[0].evidence


# ═══════════════════════════════════════════════════════════════════════════
# 3. Python Nested / Local Module Resolution
# ═══════════════════════════════════════════════════════════════════════════

def test_python_nested_module_resolution():
    analyzer = PythonDependencyAnalyzer()
    files = {"app.py", "services/auth/service.py"}
    content = "from services.auth.service import AuthService"
    
    evidence, unknowns = analyzer.analyze_source("app.py", content, files)
    assert len(evidence) == 1
    assert evidence[0].target_node == "file:services/auth/service.py"


# ═══════════════════════════════════════════════════════════════════════════
# 4. JS Direct Relative Import
# ═══════════════════════════════════════════════════════════════════════════

def test_js_direct_relative_import():
    analyzer = JsTsDependencyAnalyzer()
    files = {"src/app.js", "src/utils.js"}
    content = 'import { formatDate } from "./utils";'
    
    evidence, unknowns = analyzer.analyze_source("src/app.js", content, files)
    assert len(evidence) == 1
    assert evidence[0].source_node == "file:src/app.js"
    assert evidence[0].target_node == "file:src/utils.js"
    assert evidence[0].confidence == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 5. TS/TSX Relative Import
# ═══════════════════════════════════════════════════════════════════════════

def test_ts_tsx_relative_import():
    analyzer = JsTsDependencyAnalyzer()
    files = {"app/dashboard/page.tsx", "components/RiskCard.tsx"}
    content = 'import { RiskCard } from "../../components/RiskCard";'
    
    evidence, unknowns = analyzer.analyze_source("app/dashboard/page.tsx", content, files)
    assert len(evidence) == 1
    assert evidence[0].target_node == "file:components/RiskCard.tsx"


# ═══════════════════════════════════════════════════════════════════════════
# 6. API Route Discovery
# ═══════════════════════════════════════════════════════════════════════════

def test_api_route_discovery():
    analyzer = ApiDependencyAnalyzer()
    content = '''
@app.get("/api/risks")
def get_risks():
    return []

@router.post("/api/analyze/{owner}/{repo}")
def analyze_repo():
    pass
'''
    routes = analyzer.extract_api_routes("backend/routes.py", content)
    assert len(routes) == 2
    paths = {r["path"] for r in routes}
    assert "/api/risks" in paths
    assert "/api/analyze/{owner}/{repo}" in paths


# ═══════════════════════════════════════════════════════════════════════════
# 7. Frontend API Call Discovery
# ═══════════════════════════════════════════════════════════════════════════

def test_frontend_api_call_discovery():
    analyzer = ApiDependencyAnalyzer()
    content = '''
const res = await fetch("http://127.0.0.1:8000/api/risks");
const data = await axios.post("/api/simulate/Aritra-DSU/RF-SENTINEL");
'''
    calls = analyzer.extract_api_calls("frontend/dashboard.tsx", content)
    assert len(calls) == 2
    endpoints = {c["endpoint"] for c in calls}
    assert "/api/risks" in endpoints
    assert "/api/simulate/Aritra-DSU/RF-SENTINEL" in endpoints


# ═══════════════════════════════════════════════════════════════════════════
# 8. API Route + Call Static Matching with Evidence
# ═══════════════════════════════════════════════════════════════════════════

def test_api_route_call_matching():
    analyzer = ApiDependencyAnalyzer()
    routes = [{"file": "backend/api.py", "method": "GET", "path": "/api/risks", "framework": "fastapi"}]
    calls = [{"file": "frontend/page.tsx", "endpoint": "/api/risks", "raw_url": "/api/risks"}]
    
    evidence = analyzer.match_api_dependencies(routes, calls)
    assert len(evidence) >= 1
    api_call_ev = next(e for e in evidence if e.relationship_type == "API_CALL")
    assert api_call_ev.source_node == "file:frontend/page.tsx"
    assert api_call_ev.target_node == "endpoint:GET /api/risks"
    assert "backend/api.py" in api_call_ev.evidence


# ═══════════════════════════════════════════════════════════════════════════
# 9. Pydantic / Shared Schema Evidence
# ═══════════════════════════════════════════════════════════════════════════

def test_shared_schema_evidence():
    analyzer = SchemaConfigAnalyzer()
    all_schemas = {"RiskModel": "backend/models.py"}
    content = "from backend.models import RiskModel\ndef process(r: RiskModel): pass"
    
    evidence = analyzer.analyze_schema_contracts("backend/service.py", content, all_schemas)
    assert len(evidence) == 1
    assert evidence[0].relationship_type == "SCHEMA_CONTRACT_DEPENDENCY"
    assert evidence[0].target_node == "file:backend/models.py"


# ═══════════════════════════════════════════════════════════════════════════
# 10. Configuration Dependency & Secret Sanitization
# ═══════════════════════════════════════════════════════════════════════════

def test_config_dependency_and_secret_sanitization():
    analyzer = SchemaConfigAnalyzer()
    files = {"app.py", "config.py"}
    content = "import config\nSECRET_KEY = 'super_secret_jwt_token_xyz'\nDATABASE_URL = config.DB"
    
    evidence = analyzer.analyze_configuration_references("app.py", content, files)
    assert len(evidence) == 1
    assert evidence[0].relationship_type == "CONFIG_DEPENDENCY"
    assert "super_secret_jwt_token_xyz" not in evidence[0].evidence


# ═══════════════════════════════════════════════════════════════════════════
# 11. package.json Dependency
# ═══════════════════════════════════════════════════════════════════════════

def test_package_json_dependency():
    analyzer = ManifestDependencyAnalyzer()
    content = '''{
        "name": "frontend",
        "dependencies": {
            "next": "^14.0.0",
            "react": "^18.2.0"
        }
    }'''
    evidence = analyzer.parse_package_json("package.json", content)
    assert len(evidence) == 2
    targets = {e.target_node for e in evidence}
    assert "package:next" in targets
    assert "package:react" in targets


# ═══════════════════════════════════════════════════════════════════════════
# 12. requirements.txt Dependency
# ═══════════════════════════════════════════════════════════════════════════

def test_requirements_txt_dependency():
    analyzer = ManifestDependencyAnalyzer()
    content = "fastapi>=0.100.0\npydantic==2.5.0\n# comment line\nnetworkx"
    evidence = analyzer.parse_requirements_txt("requirements.txt", content)
    assert len(evidence) == 3
    targets = {e.target_node for e in evidence}
    assert "package:fastapi" in targets
    assert "package:pydantic" in targets
    assert "package:networkx" in targets


# ═══════════════════════════════════════════════════════════════════════════
# 13. Test -> Implementation Dependency
# ═══════════════════════════════════════════════════════════════════════════

def test_test_to_implementation_dependency():
    analyzer = TestDependencyAnalyzer()
    files = {"tests/test_detector.py", "app/detector.py", "app/unrelated.py"}
    content = "import app.detector\ndef test_foo(): app.detector.detect()"
    
    evidence = analyzer.analyze_test_dependencies("tests/test_detector.py", content, files)
    assert len(evidence) == 1
    assert evidence[0].source_node == "file:tests/test_detector.py"
    assert evidence[0].target_node == "file:app/detector.py"
    assert evidence[0].relationship_type == "TEST_OF"


# ═══════════════════════════════════════════════════════════════════════════
# 14. GitHub PR -> Issue Relationship
# ═══════════════════════════════════════════════════════════════════════════

def test_github_pr_to_issue_relationship():
    project = {
        "pull_requests": [{"id": "pr_11", "issue_id": "issue_11"}],
        "issues": [{"id": "issue_11", "title": "Core Task"}],
    }
    g = build_graph(project)
    assert g.has_edge("pull_request:pr_11", "issue:issue_11")


# ═══════════════════════════════════════════════════════════════════════════
# 15. GitHub Issue -> Milestone
# ═══════════════════════════════════════════════════════════════════════════

def test_github_issue_to_milestone_relationship():
    project = {
        "issues": [{"id": "issue_11", "milestone": "ms_03"}],
        "milestones": [{"id": "ms_03", "title": "Beta Release"}],
    }
    g = build_graph(project)
    assert g.has_edge("issue:issue_11", "milestone:ms_03")


# ═══════════════════════════════════════════════════════════════════════════
# 16. PR -> File Relationship
# ═══════════════════════════════════════════════════════════════════════════

def test_pr_to_file_relationship():
    project = {
        "pull_requests": [{"id": "pr_07", "changed_files": ["backend/main.py"]}],
        "files": ["backend/main.py"],
    }
    g = build_graph(project)
    assert g.has_node("pull_request:pr_07")
    assert g.has_node("file:backend/main.py")


# ═══════════════════════════════════════════════════════════════════════════
# 17. DIRECT Evidence Classification
# ═══════════════════════════════════════════════════════════════════════════

def test_direct_evidence_classification():
    manager = DependencyIntelligenceManager()
    files = {
        "main.py": "import config",
        "config.py": "PORT = 8000"
    }
    intel = manager.analyze_project_files(files)
    direct_deps = [d for d in intel.discovered_dependencies if not d.inferred]
    assert len(direct_deps) >= 1
    assert direct_deps[0].confidence == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 18. INFERRED Evidence Classification
# ═══════════════════════════════════════════════════════════════════════════

def test_inferred_evidence_classification():
    manager = DependencyIntelligenceManager()
    files = {
        "frontend/page.tsx": '''fetch("http://127.0.0.1:8000/api/data");''',
        "backend/main.py": '''@app.get("/api/data")\ndef get_data(): return {}''',
    }
    intel = manager.analyze_project_files(files)
    inferred_deps = [d for d in intel.discovered_dependencies if d.inferred]
    assert len(inferred_deps) >= 1
    assert inferred_deps[0].relationship_type == "API_PROVIDER_DEPENDENCY"


# ═══════════════════════════════════════════════════════════════════════════
# 19. UNKNOWN Relationship Behavior (No Guessing)
# ═══════════════════════════════════════════════════════════════════════════

def test_unknown_relationship_behavior():
    manager = DependencyIntelligenceManager()
    files = {
        "app.py": "import some_unresolvable_private_pkg.foo.bar",
    }
    intel = manager.analyze_project_files(files)
    # Should NOT guess or fabricate an edge to an imaginary file
    assert len(intel.discovered_dependencies) == 0
    assert any("Unresolved" in u for u in intel.unknown_areas)


# ═══════════════════════════════════════════════════════════════════════════
# 20. No README Project Scanning
# ═══════════════════════════════════════════════════════════════════════════

def test_no_readme_project_scanning():
    manager = DependencyIntelligenceManager()
    files = {
        "index.js": "const utils = require('./utils');",
        "utils.js": "module.exports = {};",
    }
    intel = manager.analyze_project_files(files)
    assert intel.known_nodes >= 2
    assert len(intel.discovered_dependencies) == 1
    assert intel.project_intelligence_status in {"complete", "partial"}


# ═══════════════════════════════════════════════════════════════════════════
# 21. Tiny 2-File Project
# ═══════════════════════════════════════════════════════════════════════════

def test_tiny_two_file_project():
    project = {
        "files": {
            "backend.py": "import config\nprint(config.DB)",
            "config.py": "DB = 'sqlite:///test.db'",
        }
    }
    g = build_graph(project)
    assert g.has_node("file:backend.py")
    assert g.has_node("file:config.py")
    assert g.has_edge("file:backend.py", "file:config.py")


# ═══════════════════════════════════════════════════════════════════════════
# 22. Malformed Source File / Syntax Error Resilience
# ═══════════════════════════════════════════════════════════════════════════

def test_malformed_source_file_resilience():
    manager = DependencyIntelligenceManager()
    files = {
        "good.py": "import config",
        "config.py": "X = 1",
        "broken.py": "def broken_syntax( - invalid python {",
    }
    intel = manager.analyze_project_files(files)
    # Should successfully parse good.py and report error in unknown_areas for broken.py
    assert len(intel.discovered_dependencies) == 1
    assert any("Syntax error" in u for u in intel.unknown_areas)


# ═══════════════════════════════════════════════════════════════════════════
# 23. Unresolved Import Handling
# ═══════════════════════════════════════════════════════════════════════════

def test_unresolved_import_handling():
    analyzer = PythonDependencyAnalyzer()
    files = {"app.py"}
    content = "import custom_internal_lib.submodule"
    evidence, unknowns = analyzer.analyze_source("app.py", content, files)
    assert len(evidence) == 0
    assert len(unknowns) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 24. Circular Dependency Safety
# ═══════════════════════════════════════════════════════════════════════════

def test_circular_dependency_safety():
    manager = DependencyIntelligenceManager()
    files = {
        "a.py": "import b",
        "b.py": "import a",
    }
    intel = manager.analyze_project_files(files)
    assert len(intel.discovered_dependencies) == 2
    
    g = integrate_dependency_intelligence(build_graph({}), intel)
    assert validate_causal_path(g, ["file:a.py", "file:b.py", "file:a.py"]) is True


# ═══════════════════════════════════════════════════════════════════════════
# 25. Duplicate Import Deduplication
# ═══════════════════════════════════════════════════════════════════════════

def test_duplicate_import_deduplication():
    manager = DependencyIntelligenceManager()
    files = {
        "app.py": "from config import A\nfrom config import B\nimport config",
        "config.py": "A = 1; B = 2",
    }
    intel = manager.analyze_project_files(files)
    # Deduplicates to one logical IMPORTS edge between app.py and config.py
    app_to_config = [d for d in intel.discovered_dependencies if d.source_node == "file:app.py" and d.target_node == "file:config.py"]
    assert len(app_to_config) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 26. Unrelated Component Isolation
# ═══════════════════════════════════════════════════════════════════════════

def test_unrelated_component_isolation():
    manager = DependencyIntelligenceManager()
    files = {
        "auth.py": "import database",
        "database.py": "DB = 'active'",
        "payments.py": "PORT = 9000",
    }
    intel = manager.analyze_project_files(files)
    # payments.py has no imports, must have no edges to/from auth.py or database.py
    for dep in intel.discovered_dependencies:
        assert dep.source_node != "file:payments.py"
        assert dep.target_node != "file:payments.py"


# ═══════════════════════════════════════════════════════════════════════════
# 27. Progressive Partial Intelligence Metadata Reporting
# ═══════════════════════════════════════════════════════════════════════════

def test_progressive_partial_intelligence_reporting():
    manager = DependencyIntelligenceManager()
    files = {
        "module.py": "import external_service_unknown.api",
    }
    intel = manager.analyze_project_files(files)
    assert intel.project_intelligence_status == "partial"
    assert len(intel.unknown_areas) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 28. No Full-Project Propagation
# ═══════════════════════════════════════════════════════════════════════════

def test_no_full_project_propagation():
    project = {
        "files": {
            "a.py": "import b",
            "b.py": "X = 1",
            "isolated.py": "Y = 2",
        }
    }
    g = build_graph(project)
    res = simulate(project, SimulationRequest(node_id="file:a.py", delay_days=3))
    # isolated.py must not be in affected nodes
    assert "file:isolated.py" not in res.affected_nodes


# ═══════════════════════════════════════════════════════════════════════════
# 29. Benchmark Independence
# ═══════════════════════════════════════════════════════════════════════════

def test_benchmark_independence():
    for mod_name, mod in list(sys.modules.items()):
        if hasattr(mod, "__file__") and mod.__file__ and "app/dependency_intelligence" in mod.__file__.replace("\\\\", "/"):
            with open(mod.__file__, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            assert "expected_results.json" not in content


# ═══════════════════════════════════════════════════════════════════════════
# 30. Cross-Project Isolation & Determinism
# ═══════════════════════════════════════════════════════════════════════════

def test_cross_project_isolation_and_determinism():
    manager = DependencyIntelligenceManager()
    files_a = {"main.py": "import utils", "utils.py": "def f(): pass"}
    files_b = {"core.py": "import helper", "helper.py": "def h(): pass"}
    
    intel_a1 = manager.analyze_project_files(files_a)
    intel_b = manager.analyze_project_files(files_b)
    intel_a2 = manager.analyze_project_files(files_a)
    
    assert intel_a1.known_nodes == intel_a2.known_nodes
    assert len(intel_a1.discovered_dependencies) == len(intel_a2.discovered_dependencies)
    assert not any("helper" in d.source_node for d in intel_a1.discovered_dependencies)
