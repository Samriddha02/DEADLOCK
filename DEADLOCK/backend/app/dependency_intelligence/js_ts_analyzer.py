from __future__ import annotations

import re
from pathlib import Path

from app.dependency_intelligence.models import EvidenceModel

JS_TS_IMPORT_PATTERN = re.compile(
    r'''(?:import\s+(?:[\w*\s{},$]+from\s+)?['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))'''
)


class JsTsDependencyAnalyzer:
    SUPPORTED_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx", ".json"]

    def analyze_source(
        self,
        filepath: str,
        content: str,
        all_filepaths: set[str],
    ) -> tuple[list[EvidenceModel], list[str]]:
        normalized_filepath = filepath.replace("\\", "/")
        source_node = f"file:{normalized_filepath}"
        source_dir = Path(normalized_filepath).parent

        evidence_list: list[EvidenceModel] = []
        unknown_imports: list[str] = []

        for match in JS_TS_IMPORT_PATTERN.finditer(content):
            import_path = match.group(1) or match.group(2)
            if not import_path:
                continue

            if import_path.startswith("."):
                resolved_target = self._resolve_relative_path(source_dir, import_path, all_filepaths)
                if resolved_target:
                    evidence_list.append(EvidenceModel(
                        source_node=source_node,
                        target_node=f"file:{resolved_target}",
                        relationship_type="IMPORTS",
                        evidence=f"{normalized_filepath} imports relative module '{import_path}' ({resolved_target})",
                        inferred=False,
                        inference_rule="js_ts_relative_import",
                        confidence=1.0,
                        source_type="js_ts_source",
                        source_id=normalized_filepath,
                    ))
                else:
                    unknown_imports.append(f"Unresolved JS/TS relative import '{import_path}' in {normalized_filepath}")

        seen = set()
        deduped = []
        for e in evidence_list:
            key = (e.source_node, e.target_node, e.relationship_type)
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        return deduped, unknown_imports

    def _resolve_relative_path(
        self,
        source_dir: Path,
        import_path: str,
        all_filepaths: set[str],
    ) -> str | None:
        raw_target = (source_dir / import_path).as_posix().replace("//", "/")

        if raw_target in all_filepaths:
            return raw_target

        for ext in self.SUPPORTED_EXTENSIONS:
            candidate = f"{raw_target}{ext}"
            if candidate in all_filepaths:
                return candidate

        for ext in self.SUPPORTED_EXTENSIONS:
            candidate = f"{raw_target}/index{ext}".replace("//", "/")
            if candidate in all_filepaths:
                return candidate

        target_name = Path(import_path).name
        for p in all_filepaths:
            if Path(p).stem == target_name and Path(p).suffix in self.SUPPORTED_EXTENSIONS:
                return p

        return None
