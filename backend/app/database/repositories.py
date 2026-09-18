from app.database.database import (
    save_project,
    get_project,
)


def store_project(project) -> None:
    """
    Store a ProjectData object in SQLite.
    """

    save_project(
        owner=project.owner,
        repo=project.repo,
        data=project.model_dump()
    )


def load_project(
    owner: str,
    repo: str
):
    """
    Load a project from SQLite.
    """

    return get_project(
        owner=owner,
        repo=repo
    )