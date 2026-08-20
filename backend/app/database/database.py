from pathlib import Path
import json
import sqlite3

from app.config.settings import settings


def database_path() -> Path:
    """
    Get the SQLite database file path.
    """

    if settings.database_url.startswith("sqlite:///"):
        return Path(
            settings.database_url.replace(
                "sqlite:///",
                ""
            )
        )

    return Path("deadlock.db")


def init_db() -> None:
    """
    Create the database and projects table.
    """

    path = database_path()

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with sqlite3.connect(path) as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                owner TEXT NOT NULL,

                repo TEXT NOT NULL,

                data_json TEXT NOT NULL,

                created_at DATETIME
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(owner, repo)
            )
            """
        )

        conn.commit()


def save_project(
    owner: str,
    repo: str,
    data: dict
) -> None:
    """
    Save a project.

    If the project already exists,
    update its stored data.
    """

    with sqlite3.connect(
        database_path()
    ) as conn:

        conn.execute(
            """
            INSERT INTO projects (
                owner,
                repo,
                data_json
            )
            VALUES (?, ?, ?)

            ON CONFLICT(owner, repo)
            DO UPDATE SET
                data_json = excluded.data_json,
                created_at = CURRENT_TIMESTAMP
            """,
            (
                owner,
                repo,
                json.dumps(data)
            )
        )

        conn.commit()


def get_project(
    owner: str,
    repo: str
) -> dict | None:
    """
    Retrieve a project from the database.
    """

    with sqlite3.connect(
        database_path()
    ) as conn:

        row = conn.execute(
            """
            SELECT data_json
            FROM projects
            WHERE owner = ?
            AND repo = ?
            """,
            (
                owner,
                repo
            )
        ).fetchone()

    if row is None:
        return None

    return json.loads(row[0])