from __future__ import annotations

from pathlib import Path
from app.dependency_intelligence.models import EvidenceModel


class TestDependencyAnalyzer:
    def analyze_test_dependencies(
        self,
        filepath: str,
        content: str,
        all_filepaths: set[str],
    ) -> list[EvidenceModel]:
        normalized_file = filepath.replace("\\", "/")
        if not ("test" in normalized_file.lower() or normalized_file.endswith("_test.py") or normalized_file.startswith("test_")):
            return []

        evidence_list: list[EvidenceModel] = []
        source_node = f"file:{normalized_file}"

        for target_p in all_filepaths:
            norm_target = target_p.replace("\\", "/")
            if norm_target == normalized_file:
                continue
            if "test" in norm_target.lower():
                continue

            target_stem = Path(norm_target).stem
            if (
                f"import {target_stem}" in content
                or f".{target_stem}" in content
                or f"from {target_stem}" in content
                or (target_stem in content and ("import " in content or "from " in content))
            ):
                evidence_list.append(EvidenceModel(
                    source_node=source_node,
                    target_node=f"file:{norm_target}",
                    relationship_type="TEST_OF",
                    evidence=f"Test file '{normalized_file}' directly tests implementation module '{norm_target}'",
                    inferred=False,
                    inference_rule="test_import_implementation",
                    confidence=1.0,
                    source_type="test_suite",
                    source_id=normalized_file,
                ))

        return evidence_list
