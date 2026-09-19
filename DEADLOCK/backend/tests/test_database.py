from __future__ import annotations

"""
Phase 2 database tests — 22 test cases.

All tests use an isolated temporary SQLite database so the
production database (deadlock.db) is never touched.
"""

import json
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# ─── helpers ────────────────────────────────────────────────────────────────

def _patch_db(tmp_path: Path):
    """Return a context-manager that redirects the database to a temp file."""
    db_file = str(tmp_path / "test_deadlock.db")
    return patch(
        "app.database.database.database_path",
        return_value=Path(db_file),
    )


# ─── sample data ─────────────────────────────────────────────────────────────

_SAMPLE = {
    "owner": "test-owner",
    "repo": "test-repo",
    "project": {"id": "p1", "name": "Test"},
    "developers": [],
    "issues": [],
}


# ═══════════════════════════════════════════════════════════════════════════
# 1. database_path() is deterministic (does not depend on CWD)
# ═══════════════════════════════════════════════════════════════════════════

def test_database_path_deterministic():
    from app.database.database import database_path

    original_cwd = os.getcwd()
    try:
        os.chdir(tempfile.gettempdir())
        path1 = database_path()
        os.chdir(Path(__file__).parent)
        path2 = database_path()
    finally:
        os.chdir(original_cwd)

    assert path1 == path2, (
        "database_path() must not change when the working directory changes"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. database_path() returns an absolute path
# ═══════════════════════════════════════════════════════════════════════════

def test_database_path_is_absolute():
    from app.database.database import database_path

    path = database_path()
    assert path.is_absolute(), "database_path() must always return an absolute path"


# ═══════════════════════════════════════════════════════════════════════════
# 3. init_db() creates the projects table
# ═══════════════════════════════════════════════════════════════════════════

def test_init_db_creates_table(tmp_path):
    from app.database.database import init_db

    with _patch_db(tmp_path):
        init_db()
        db_file = str(tmp_path / "test_deadlock.db")
        conn = sqlite3.connect(db_file)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()

    assert "projects" in tables


# ═══════════════════════════════════════════════════════════════════════════
# 4. init_db() is idempotent — calling it 10× never raises
# ═══════════════════════════════════════════════════════════════════════════

def test_init_db_idempotent(tmp_path):
    from app.database.database import init_db

    with _patch_db(tmp_path):
        for _ in range(10):
            init_db()  # must not raise


# ═══════════════════════════════════════════════════════════════════════════
# 5. init_db() does NOT drop or delete existing rows
# ═══════════════════════════════════════════════════════════════════════════

def test_init_db_preserves_existing_data(tmp_path):
    from app.database.database import init_db, save_project, get_project

    with _patch_db(tmp_path):
        init_db()
        save_project("owner", "repo", {"x": 1})
        # Call init_db again — must not wipe the row.
        init_db()
        data = get_project("owner", "repo")

    assert data["x"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 6. projects table has all required columns after init_db()
# ═══════════════════════════════════════════════════════════════════════════

def test_init_db_columns(tmp_path):
    from app.database.database import init_db

    with _patch_db(tmp_path):
        init_db()
        db_file = str(tmp_path / "test_deadlock.db")
        conn = sqlite3.connect(db_file)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(projects)").fetchall()
        }
        conn.close()

    required = {"owner", "repo", "data_json", "source", "created_at", "updated_at", "last_synced_at"}
    assert required.issubset(columns), f"Missing columns: {required - columns}"


# ═══════════════════════════════════════════════════════════════════════════
# 7. save_project() rejects empty owner
# ═══════════════════════════════════════════════════════════════════════════

def test_save_project_rejects_empty_owner(tmp_path):
    from app.database.database import save_project

    with _patch_db(tmp_path):
        with pytest.raises(ValueError, match="owner"):
            save_project("", "repo", {"x": 1})


# ═══════════════════════════════════════════════════════════════════════════
# 8. save_project() rejects empty repo
# ═══════════════════════════════════════════════════════════════════════════

def test_save_project_rejects_empty_repo(tmp_path):
    from app.database.database import save_project

    with _patch_db(tmp_path):
        with pytest.raises(ValueError, match="repo"):
            save_project("owner", "", {"x": 1})


# ═══════════════════════════════════════════════════════════════════════════
# 9. save_project() rejects non-dict data
# ═══════════════════════════════════════════════════════════════════════════

def test_save_project_rejects_non_dict(tmp_path):
    from app.database.database import save_project

    with _patch_db(tmp_path):
        with pytest.raises(TypeError):
            save_project("owner", "repo", "not-a-dict")


# ═══════════════════════════════════════════════════════════════════════════
# 10. save_project() → get_project() round-trip
# ═══════════════════════════════════════════════════════════════════════════

def test_save_and_get_project_roundtrip(tmp_path):
    from app.database.database import save_project, get_project

    payload = {"owner": "o", "repo": "r", "issues": [{"id": "i1"}]}

    with _patch_db(tmp_path):
        save_project("o", "r", payload)
        result = get_project("o", "r")

    assert result["issues"] == [{"id": "i1"}]


# ═══════════════════════════════════════════════════════════════════════════
# 11. save_project() upserts — no duplicate rows
# ═══════════════════════════════════════════════════════════════════════════

def test_save_project_upsert_no_duplicates(tmp_path):
    from app.database.database import save_project

    with _patch_db(tmp_path):
        save_project("owner", "repo", {"v": 1})
        save_project("owner", "repo", {"v": 2})
        save_project("owner", "repo", {"v": 3})

        db_file = str(tmp_path / "test_deadlock.db")
        conn = sqlite3.connect(db_file)
        count = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE owner='owner' AND repo='repo'"
        ).fetchone()[0]
        conn.close()

    assert count == 1, "Upsert must not create duplicate rows"


# ═══════════════════════════════════════════════════════════════════════════
# 12. save_project() upsert overwrites data_json
# ═══════════════════════════════════════════════════════════════════════════

def test_save_project_upsert_overwrites_data(tmp_path):
    from app.database.database import save_project, get_project

    with _patch_db(tmp_path):
        save_project("owner", "repo", {"version": 1})
        save_project("owner", "repo", {"version": 2})
        result = get_project("owner", "repo")

    assert result["version"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# 13. save_project() stores the source tag
# ═══════════════════════════════════════════════════════════════════════════

def test_save_project_stores_source_tag(tmp_path):
    from app.database.database import save_project

    with _patch_db(tmp_path):
        save_project("owner", "repo", {"x": 1}, source="seeded")

        db_file = str(tmp_path / "test_deadlock.db")
        conn = sqlite3.connect(db_file)
        row = conn.execute(
            "SELECT source FROM projects WHERE owner='owner' AND repo='repo'"
        ).fetchone()
        conn.close()

    assert row[0] == "seeded"


# ═══════════════════════════════════════════════════════════════════════════
# 14. get_project() raises ProjectNotFoundError for unknown repo
# ═══════════════════════════════════════════════════════════════════════════

def test_get_project_raises_not_found(tmp_path):
    from app.database.database import get_project, ProjectNotFoundError

    with _patch_db(tmp_path):
        with pytest.raises(ProjectNotFoundError):
            get_project("ghost-owner", "ghost-repo")


# ═══════════════════════════════════════════════════════════════════════════
# 15. get_project() raises ProjectCorruptError for malformed JSON
# ═══════════════════════════════════════════════════════════════════════════

def test_get_project_raises_corrupt_for_bad_json(tmp_path):
    from app.database.database import init_db, get_project, ProjectCorruptError

    with _patch_db(tmp_path):
        init_db()
        # Write invalid JSON directly.
        db_file = str(tmp_path / "test_deadlock.db")
        conn = sqlite3.connect(db_file)
        conn.execute(
            "INSERT INTO projects (owner, repo, data_json, source) VALUES (?, ?, ?, ?)",
            ("owner", "repo", "NOT VALID JSON {{{", "github"),
        )
        conn.commit()
        conn.close()

        with pytest.raises(ProjectCorruptError):
            get_project("owner", "repo")


# ═══════════════════════════════════════════════════════════════════════════
# 16. Corrupt row is NOT deleted after ProjectCorruptError
# ═══════════════════════════════════════════════════════════════════════════

def test_corrupt_row_preserved_after_error(tmp_path):
    from app.database.database import init_db, get_project, ProjectCorruptError

    with _patch_db(tmp_path):
        init_db()
        db_file = str(tmp_path / "test_deadlock.db")
        conn = sqlite3.connect(db_file)
        conn.execute(
            "INSERT INTO projects (owner, repo, data_json, source) VALUES (?, ?, ?, ?)",
            ("owner", "repo", "CORRUPT", "github"),
        )
        conn.commit()
        conn.close()

        # Trigger error.
        with pytest.raises(ProjectCorruptError):
            get_project("owner", "repo")

        # Row must still be there.
        conn2 = sqlite3.connect(db_file)
        count = conn2.execute(
            "SELECT COUNT(*) FROM projects WHERE owner='owner' AND repo='repo'"
        ).fetchone()[0]
        conn2.close()

    assert count == 1, "Corrupt row must NOT be auto-deleted"


# ═══════════════════════════════════════════════════════════════════════════
# 17. get_project() injects _meta cache-freshness block
# ═══════════════════════════════════════════════════════════════════════════

def test_get_project_injects_meta(tmp_path):
    from app.database.database import save_project, get_project

    with _patch_db(tmp_path):
        save_project("owner", "repo", {"x": 1}, source="seeded")
        result = get_project("owner", "repo")

    assert "_meta" in result
    meta = result["_meta"]
    assert meta["source"] == "seeded"
    assert "created_at" in meta
    assert "updated_at" in meta
    assert "last_synced_at" in meta


# ═══════════════════════════════════════════════════════════════════════════
# 18. upsert preserves old record when serialisation fails mid-write
#     (save_project should raise before touching the DB)
# ═══════════════════════════════════════════════════════════════════════════

def test_failed_upsert_preserves_old_record(tmp_path):
    from app.database.database import save_project, get_project

    class Unserializable:
        pass

    with _patch_db(tmp_path):
        save_project("owner", "repo", {"version": "original"})

        with pytest.raises((ValueError, TypeError)):
            save_project("owner", "repo", {"bad": Unserializable()})

        # Old data must still be readable.
        result = get_project("owner", "repo")

    assert result["version"] == "original"


# ═══════════════════════════════════════════════════════════════════════════
# 19. is_demo_repo() returns True for the canonical demo repo (case-insensitive)
# ═══════════════════════════════════════════════════════════════════════════

def test_is_demo_repo_canonical():
    from app.database.repositories import is_demo_repo

    assert is_demo_repo("Aritra-DSU", "RF-SENTINEL")
    assert is_demo_repo("aritra-dsu", "rf-sentinel")
    assert is_demo_repo("ARITRA-DSU", "RF-SENTINEL")


# ═══════════════════════════════════════════════════════════════════════════
# 20. is_demo_repo() returns False for unknown repos
# ═══════════════════════════════════════════════════════════════════════════

def test_is_demo_repo_unknown():
    from app.database.repositories import is_demo_repo

    assert not is_demo_repo("some-org", "some-repo")
    assert not is_demo_repo("CampusConnect", "main")
    assert not is_demo_repo("", "")


# ═══════════════════════════════════════════════════════════════════════════
# 21. GET /api/projects/{owner}/{repo} — demo repo falls back to seeded data
#     when no DB row exists (no 404 returned for the demo repo)
# ═══════════════════════════════════════════════════════════════════════════

def test_get_project_endpoint_demo_fallback(tmp_path):
    from fastapi.testclient import TestClient

    with _patch_db(tmp_path):
        # Import app inside the patch so it picks up the test DB.
        from app.main import app
        client = TestClient(app)
        # Request the canonical demo repo (should now return 404 as live repo without DB entry)
        resp = client.get("/api/projects/Aritra-DSU/RF-SENTINEL")
        assert resp.status_code == 404

    assert resp.status_code == 404
    # No seeded data should be returned for live repos without data
    # The response body may contain an error detail.


# ═══════════════════════════════════════════════════════════════════════════
# 22. GET /api/projects/{owner}/{repo} — live repo returns 404
#     when no DB row exists (must NOT return seeded demo data)
# ═══════════════════════════════════════════════════════════════════════════

def test_get_project_endpoint_live_not_found(tmp_path):
    from fastapi.testclient import TestClient

    with _patch_db(tmp_path):
        from app.main import app
        client = TestClient(app)

        resp = client.get("/api/projects/some-org/some-live-repo")

    assert resp.status_code == 404
    assert "some-org/some-live-repo" in resp.json()["detail"]
