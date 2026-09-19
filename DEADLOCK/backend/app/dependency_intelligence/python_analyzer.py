from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from app.dependency_intelligence.models import EvidenceModel

MAX_FILE_SIZE = 1_000_000


class PythonDependencyAnalyzer:
    def analyze_source(
        self,
        filepath: str,
        content: str,
        all_filepaths: set[str],
    ) -> tuple[list[EvidenceModel], list[str]]:
        if len(content) > MAX_FILE_SIZE:
            return [], [f"File {filepath} exceeds size limit for AST analysis"]

        try:
            tree = ast.parse(content, filename=filepath)
        except SyntaxError as e:
            return [], [f"Syntax error parsing {filepath}: {e.msg} at line {e.lineno}"]
        except Exception as e:
            return [], [f"Error parsing {filepath}: {str(e)}"]

        evidence_list: list[EvidenceModel] = []
        unknown_imports: list[str] = []
        normalized_filepath = filepath.replace("\\", "/")
        source_node = f"file:{normalized_filepath}"

        module_map: dict[str, str] = {}
        for p in all_filepaths:
            norm_p = p.replace("\\", "/")
            if norm_p.endswith(".py"):
                base_name = Path(norm_p).stem
                module_map[base_name] = norm_p
                parts = norm_p.replace(".py", "").split("/")
                module_map[".".join(parts)] = norm_p

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_name = alias.name
                    target_file = self._resolve_module(mod_name, module_map)
                    if target_file:
                        evidence_list.append(EvidenceModel(
                            source_node=source_node,
                            target_node=f"file:{target_file}",
                            relationship_type="IMPORTS",
                            evidence=f"{normalized_filepath} imports local module '{mod_name}' ({target_file})",
                            inferred=False,
                            inference_rule="python_ast_direct_import",
                            confidence=1.0,
                            source_type="python_source",
                            source_id=normalized_filepath,
                        ))
                    elif "." in mod_name and not self._is_standard_or_popular_pkg(mod_name.split(".")[0]):
                        unknown_imports.append(f"Unresolved Python import '{mod_name}' in {normalized_filepath}")

            elif isinstance(node, ast.ImportFrom):
                mod_name = node.module or ""
                target_file = self._resolve_module(mod_name, module_map)
                if target_file:
                    imported_names = [a.name for a in node.names]
                    evidence_list.append(EvidenceModel(
                        source_node=source_node,
                        target_node=f"file:{target_file}",
                        relationship_type="IMPORTS",
                        evidence=f"{normalized_filepath} imports symbols [{', '.join(imported_names)}] from '{target_file}'",
                        inferred=False,
                        inference_rule="python_ast_from_import",
                        confidence=1.0,
                        source_type="python_source",
                        source_id=normalized_filepath,
                    ))
                elif mod_name and not self._is_standard_or_popular_pkg(mod_name.split(".")[0]):
                    unknown_imports.append(f"Unresolved Python from-import '{mod_name}' in {normalized_filepath}")

        deduped = self._deduplicate(evidence_list)
        return deduped, unknown_imports

    def _resolve_module(self, mod_name: str, module_map: dict[str, str]) -> str | None:
        if not mod_name:
            return None
        if mod_name in module_map:
            return module_map[mod_name]
        parts = mod_name.split(".")
        if parts[-1] in module_map:
            return module_map[parts[-1]]
        return None

    def _is_standard_or_popular_pkg(self, pkg: str) -> bool:
        stdlib = {
            "os", "sys", "math", "time", "datetime", "json", "typing", "pathlib",
            "collections", "itertools", "functools", "re", "ast", "copy", "logging",
            "unittest", "pytest", "hashlib", "enum", "dataclasses", "abc", "contextlib",
            "fastapi", "uvicorn", "pydantic", "networkx", "requests", "httpx", "sqlite3",
        }
        return pkg.lower() in stdlib

    def _deduplicate(self, evidence_list: list[EvidenceModel]) -> list[EvidenceModel]:
        seen = set()
        deduped = []
        for e in evidence_list:
            key = (e.source_node, e.target_node, e.relationship_type)
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        return deduped
