from __future__ import annotations

from app.dependency_intelligence.models import EvidenceModel

CONFIG_NAMES = {"config", "settings", "env", "environment", "configuration"}


class SchemaConfigAnalyzer:
    def analyze_configuration_references(
        self,
        filepath: str,
        content: str,
        all_filepaths: set[str],
    ) -> list[EvidenceModel]:
        evidence_list: list[EvidenceModel] = []
        normalized_file = filepath.replace("\\", "/")
        source_node = f"file:{normalized_file}"

        for conf_candidate in all_filepaths:
            norm_conf = conf_candidate.replace("\\", "/")
            stem = norm_conf.split("/")[-1].split(".")[0].lower()
            if stem in CONFIG_NAMES and norm_conf != normalized_file:
                if f"import {stem}" in content or f"from {stem}" in content or f"from .{stem}" in content or f'require("./{stem}' in content or f'from "./{stem}' in content:
                    evidence_list.append(EvidenceModel(
                        source_node=source_node,
                        target_node=f"file:{norm_conf}",
                        relationship_type="CONFIG_DEPENDENCY",
                        evidence=f"File '{normalized_file}' references configuration module '{norm_conf}'",
                        inferred=False,
                        inference_rule="config_reference_detection",
                        confidence=1.0,
                        source_type="configuration",
                        source_id=normalized_file,
                    ))

        return evidence_list

    def analyze_schema_contracts(
        self,
        filepath: str,
        content: str,
        all_schemas: dict[str, str],
    ) -> list[EvidenceModel]:
        evidence_list: list[EvidenceModel] = []
        normalized_file = filepath.replace("\\", "/")
        source_node = f"file:{normalized_file}"

        for schema_name, defining_file in all_schemas.items():
            if defining_file == normalized_file:
                continue
            if f"import {schema_name}" in content or f"import {{ {schema_name} }}" in content or f"from " in content and schema_name in content:
                if f"class {schema_name}" not in content and f"interface {schema_name}" not in content:
                    evidence_list.append(EvidenceModel(
                        source_node=source_node,
                        target_node=f"file:{defining_file}",
                        relationship_type="SCHEMA_CONTRACT_DEPENDENCY",
                        evidence=f"File '{normalized_file}' consumes shared schema contract '{schema_name}' defined in '{defining_file}'",
                        inferred=False,
                        inference_rule="explicit_schema_import",
                        confidence=1.0,
                        source_type="schema_contract",
                        source_id=normalized_file,
                    ))

        return evidence_list
