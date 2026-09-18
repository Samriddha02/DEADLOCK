from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.config.settings import settings


# ============================================================
# DATABASE PATH
# ============================================================

def database_path() -> Path:
    """
    Return the SQLite database path.

    Supports:
        sqlite:///relative/path.db   (resolved from backend dir)
        sqlite:////absolute/path.db  (used as-is)

    Falls back to <backend>/deadlock.db when no SQLite URL is set
    or a non-SQLite URL is encountered.

    The path is ALWAYS computed from __file__, never from the
    current working directory, so it is deterministic regardless
    of where the server is started from.
    """

    database_url = str(settings.database_url or "").strip()

    if database_url.startswith("sqlite:///"):
        raw_path = database_url[len("sqlite:///"):]
        path = Path(raw_path)

        # Resolve relative paths from the backend directory.
        if not path.is_absolute():
            backend_dir = Path(__file__).resolve().parents[2]
            path = backend_dir / path

        return path.resolve()

    # Fallback: always anchor to the backend directory.
    backend_dir = Path(__file__).resolve().parents[2]
    return (backend_dir / "deadlock.db").resolve()


# ============================================================
# CONNECTION
# ============================================================

def _connect() -> sqlite3.Connection:
    """
    Open a SQLite connection with safe, production-grade defaults:
    - WAL journal mode for concurrent readers
    - 30-second busy timeout
    - Foreign-key enforcement
    - Row factory for named-column access
    """

    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row

    # WAL mode: readers don't block writers and vice versa.
    conn.execute("PRAGMA journal_mode = WAL")

    # Wait up to 30 s before raising "database is locked".
    conn.execute("PRAGMA busy_timeout = 30000")

    # Enforce referential integrity.
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db() -> None:
    """
    Safely initialize / upgrade the SQLite database.

    This function is intentionally idempotent — calling it any
    number of times must not fail, and must never DROP or DELETE
    existing data.

    Schema additions are handled via ALTER TABLE … ADD COLUMN
    guarded by a PRAGMA table_info() check, so older databases
    are upgraded non-destructively.
    """

    with _connect() as conn:

        # --------------------------------------------------------
        # Base projects table
        # --------------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,

                owner       TEXT NOT NULL,
                repo        TEXT NOT NULL,

                data_json   TEXT NOT NULL,

                source      TEXT NOT NULL DEFAULT 'github',

                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_synced_at  DATETIME DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(owner, repo)
            )
            """
        )

        # --------------------------------------------------------
        # Non-destructive schema migrations
        # --------------------------------------------------------

        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(projects)").fetchall()
        }

        # SQLite ALTER TABLE only accepts constant literal defaults
        # (not function calls like CURRENT_TIMESTAMP).  Add the columns
        # with NULL defaults, then back-fill via UPDATE.
        _migrate_add_column(conn, columns, "created_at",     "DATETIME")
        _migrate_add_column(conn, columns, "updated_at",     "DATETIME")
        _migrate_add_column(conn, columns, "last_synced_at", "DATETIME")
        _migrate_add_column(conn, columns, "source",         "TEXT DEFAULT 'github'")

        # Back-fill NULL timestamps that pre-date the migration.
        conn.execute(
            """
            UPDATE projects
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )
        conn.execute(
            """
            UPDATE projects
            SET updated_at = CURRENT_TIMESTAMP
            WHERE updated_at IS NULL
            """
        )
        conn.execute(
            """
            UPDATE projects
            SET last_synced_at = CURRENT_TIMESTAMP
            WHERE last_synced_at IS NULL
            """
        )
        conn.execute(
            """
            UPDATE projects
            SET source = 'github'
            WHERE source IS NULL
            """
        )

        conn.commit()


def _migrate_add_column(
    conn: sqlite3.Connection,
    existing_columns: set[str],
    column_name: str,
    column_def: str,
) -> None:
    """Add a column only if it is absent — never raises on existing columns."""

    if column_name not in existing_columns:
        conn.execute(
            f"ALTER TABLE projects ADD COLUMN {column_name} {column_def}"
        )


# ============================================================
# SAVE PROJECT  (atomic upsert)
# ============================================================

def save_project(
    owner: str,
    repo: str,
    data: dict,
    *,
    source: str = "github",
) -> None:
    """
    Atomically insert or update a project record.

    The owner/repo pair has a UNIQUE constraint, so repeated
    synchronisation updates the existing row instead of creating
    duplicates.

    Atomicity guarantee
    -------------------
    The INSERT … ON CONFLICT … DO UPDATE executes inside a
    single SQLite transaction.  If serialisation fails the
    existing record is left completely intact.

    Parameters
    ----------
    owner  : GitHub owner / organisation name  (must not be empty)
    repo   : GitHub repository name            (must not be empty)
    data   : Canonical project data dict       (must be a plain dict)
    source : Provenance tag, e.g. "github" or "seeded"
    """

    if not owner or not str(owner).strip():
        raise ValueError("Project owner cannot be empty.")

    if not repo or not str(repo).strip():
        raise ValueError("Project repository cannot be empty.")

    if not isinstance(data, dict):
        raise TypeError("Project data must be a plain Python dictionary.")

    owner = str(owner).strip()
    repo  = str(repo).strip()

    # Serialise first so we never write a half-finished record.
    try:
        serialized = json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Project data cannot be serialised to JSON: {exc}"
        ) from exc

    # Ensure schema exists before writing.
    init_db()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO projects (
                owner,
                repo,
                data_json,
                source,
                created_at,
                updated_at,
                last_synced_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)

            ON CONFLICT(owner, repo)
            DO UPDATE SET
                data_json      = excluded.data_json,
                source         = excluded.source,
                updated_at     = CURRENT_TIMESTAMP,
                last_synced_at = CURRENT_TIMESTAMP
            """,
            (owner, repo, serialized, source),
        )
        conn.commit()


# ============================================================
# CUSTOM EXCEPTIONS
# ============================================================

class ProjectNotFoundError(Exception):
    """Raised when a project row does not exist in the database."""


class ProjectCorruptError(Exception):
    """
    Raised when a project row exists but its stored JSON cannot
    be deserialised or is not a JSON object.

    The old record is intentionally preserved; it is never
    automatically deleted so that an administrator can inspect
    and repair it.
    """


# ============================================================
# GET PROJECT
# ============================================================

def get_project(
    owner: str,
    repo: str,
) -> dict:
    """
    Retrieve a project from SQLite.

    Returns
    -------
    dict
        The deserialised project data including cache-freshness
        metadata injected under the ``_meta`` key.

    Raises
    ------
    ProjectNotFoundError
        The (owner, repo) pair has never been persisted.
    ProjectCorruptError
        The row exists but the stored value is not valid JSON
        or is not a JSON object.  The row is NOT deleted.
    ValueError
        owner or repo is empty.
    """

    if not owner or not str(owner).strip():
        raise ValueError("Project owner cannot be empty.")

    if not repo or not str(repo).strip():
        raise ValueError("Project repository cannot be empty.")

    owner = str(owner).strip()
    repo  = str(repo).strip()

    # Ensure schema is current before reading.
    init_db()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                data_json,
                source,
                created_at,
                updated_at,
                last_synced_at
            FROM projects
            WHERE owner = ?
              AND repo  = ?
            """,
            (owner, repo),
        ).fetchone()

    if row is None:
        raise ProjectNotFoundError(
            f"Project '{owner}/{repo}' has not been synced yet."
        )

    # --- deserialise ---
    try:
        data = json.loads(row["data_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProjectCorruptError(
            f"Stored JSON for '{owner}/{repo}' is malformed.  "
            "The record has been preserved for manual inspection."
        ) from exc

    if not isinstance(data, dict):
        raise ProjectCorruptError(
            f"Stored data for '{owner}/{repo}' is not a JSON object.  "
            "The record has been preserved for manual inspection."
        )

    # --- inject cache-freshness metadata ---
    data["_meta"] = {
        "source":         row["source"],
        "created_at":     row["created_at"],
        "updated_at":     row["updated_at"],
        "last_synced_at": row["last_synced_at"],
    }

    return data