import json
from pathlib import Path
from typing import Any


def get_dataset_path() -> Path:
    """
    Return the path to Laptop 3's runtime dataset.
    """

    # backend/app/ingestion/dataset_loader.py
    # parents[0] = ingestion
    # parents[1] = app
    # parents[2] = backend

    backend_dir = Path(__file__).resolve().parents[2]

    return backend_dir / "data" / "seeded_project.json"


def load_seeded_project() -> dict[str, Any]:
    """
    Load the seeded NEXUS project dataset.

    This is the ONLY dataset used by the
    runtime Risk Engine.
    """

    dataset_path = get_dataset_path()

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}"
        )

    with dataset_path.open(
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            "seeded_project.json must contain a JSON object."
        )

    return data


def get_project_data() -> dict[str, Any]:
    """
    Convenience function for accessing the
    complete project dataset.
    """

    return load_seeded_project()


def get_entity(
    entity_type: str
) -> list[dict[str, Any]]:
    """
    Return one entity collection from the dataset.

    Example:
        get_entity("issues")
        get_entity("developers")
        get_entity("dependencies")
    """

    data = load_seeded_project()

    entities = data.get(entity_type, [])

    if not isinstance(entities, list):
        raise ValueError(
            f"'{entity_type}' must be a list."
        )

    return entities