from __future__ import annotations

import json
import re
from app.dependency_intelligence.models import EvidenceModel


class ManifestDependencyAnalyzer:
    def parse_package_json(self, filepath: str, content: str) -> list[EvidenceModel]:
        evidence_list = []
        normalized_file = filepath.replace("\\", "/")
        source_node = f"file:{normalized_file}"

        try:
            data = json.loads(content)
        except Exception:
            return []

        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})

        for pkg, ver in {**deps, **dev_deps}.items():
            evidence_list.append(EvidenceModel(
                source_node=source_node,
                target_node=f"package:{pkg}",
                relationship_type="PACKAGE_DEPENDENCY",
                evidence=f"Manifest '{normalized_file}' declares npm dependency '{pkg}' (version: {ver})",
                inferred=False,
                inference_rule="manifest_package_json",
                confidence=1.0,
                source_type="package_manifest",
                source_id=normalized_file,
                metadata={"package": pkg, "version": str(ver), "ecosystem": "npm"},
            ))

        return evidence_list

    def parse_requirements_txt(self, filepath: str, content: str) -> list[EvidenceModel]:
        evidence_list = []
        normalized_file = filepath.replace("\\", "/")
        source_node = f"file:{normalized_file}"

        for line in content.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue
            match = re.match(r"^([a-zA-Z0-9_\-\.]+)", clean)
            if match:
                pkg = match.group(1).lower()
                evidence_list.append(EvidenceModel(
                    source_node=source_node,
                    target_node=f"package:{pkg}",
                    relationship_type="PACKAGE_DEPENDENCY",
                    evidence=f"Requirements manifest '{normalized_file}' declares pip dependency '{pkg}' ({clean})",
                    inferred=False,
                    inference_rule="manifest_requirements_txt",
                    confidence=1.0,
                    source_type="package_manifest",
                    source_id=normalized_file,
                    metadata={"package": pkg, "spec": clean, "ecosystem": "pypi"},
                ))

        return evidence_list
