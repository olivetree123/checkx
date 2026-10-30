import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def test_upgrade_existing_database_preserves_design_and_review(tmp_path):
    database = tmp_path / "upgrade.sqlite3"
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "DATABASE_URL": f"sqlite://{database}"}

    def migrate(*args):
        result = subprocess.run(
            [sys.executable, "-m", "tortoise", "migrate", *args],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    migrate("models", "0001_initial")
    ids = [uuid4().hex for _ in range(5)]
    with sqlite3.connect(database) as db:
        timestamp = "2026-09-29 00:00:00+00:00"
        db.execute(
            "INSERT INTO user VALUES (?, ?, ?, ?, ?)",
            (ids[0], "migration@example.com", "tester", "unused", timestamp),
        )
        db.execute(
            "INSERT INTO project (id, owner_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (ids[1], ids[0], "project", "", timestamp, timestamp),
        )
        db.execute(
            "INSERT INTO page (id, project_id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (ids[2], ids[1], "page", "", timestamp, timestamp),
        )
        db.execute(
            "INSERT INTO design (id, page_id, name, notes, stored_name, original_name, mime_type, size, width, height, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ids[3],
                ids[2],
                "design",
                "keep notes",
                "keep.png",
                "original.png",
                "image/png",
                10,
                2,
                2,
                "approved",
                timestamp,
                timestamp,
            ),
        )
        db.execute(
            "INSERT INTO review (id, design_id, author_label, content, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (ids[4], ids[3], "tester", "keep review", "approved", timestamp),
        )
    migrate()
    migrate()  # Re-running deployment is safe.
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT version, stored_name, notes, status FROM design").fetchone() == (
            1,
            "keep.png",
            "keep notes",
            "approved",
        )
        assert db.execute("SELECT version, content FROM review").fetchone() == (1, "keep review")
        assert db.execute("SELECT COUNT(*) FROM designimageversion").fetchone()[0] == 0
