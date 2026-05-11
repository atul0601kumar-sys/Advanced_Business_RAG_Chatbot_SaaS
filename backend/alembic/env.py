from __future__ import annotations

import re
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.models import *  # noqa: F403

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.resolved_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
DESTRUCTIVE_PATTERNS = [
    re.compile(r"\bop\.drop_table\(", re.MULTILINE),
    re.compile(r"\bop\.drop_column\(", re.MULTILINE),
    re.compile(r"\bop\.drop_constraint\(", re.MULTILINE),
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE),
]


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _assert_safe_pending_migrations(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()
def _assert_safe_pending_migrations(connection) -> None:  # noqa: ANN001
    if settings.app_env != "production" or settings.allow_destructive_migrations:
        return
    script_directory = ScriptDirectory.from_config(config)
    current_revision = MigrationContext.configure(connection).get_current_revision()
    pending_revisions = list(script_directory.iterate_revisions("heads", current_revision))
    for revision in pending_revisions:
        revision_path = Path(revision.path)
        if not revision_path.exists():
            continue
        contents = revision_path.read_text(encoding="utf-8")
        if any(pattern.search(contents) for pattern in DESTRUCTIVE_PATTERNS):
            raise RuntimeError(
                f"Destructive migration blocked in production: {revision.revision} ({revision_path.name}). "
                "Set ALLOW_DESTRUCTIVE_MIGRATIONS=true only after backup and manual approval."
            )


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
