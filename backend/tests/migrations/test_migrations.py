from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.migration
def test_alembic_offline_upgrade_sql_builds_cleanly():
    backend_dir = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head", "--sql"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE integration_connections" in result.stdout
    assert "CREATE TABLE notification_jobs" in result.stdout


@pytest.mark.migration
def test_upgrade_revisions_avoid_destructive_operations():
    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    for migration_file in versions_dir.glob("*.py"):
        if migration_file.name == "__init__.py":
            continue
        source = migration_file.read_text(encoding="utf-8")
        if "def upgrade" not in source:
            continue
        upgrade_block = source.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
        assert "drop_column(" not in upgrade_block
        assert "drop_table(" not in upgrade_block
