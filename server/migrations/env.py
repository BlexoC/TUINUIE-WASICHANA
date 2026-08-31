"""
server/migrations/env.py — Alembic migration environment

Wires Flask-Migrate into Alembic so that:
  - `flask db migrate` reads SQLALCHEMY_DATABASE_URI from the Flask app config
  - Autogenerate compares against all SQLAlchemy models registered with `db`
"""

import logging
from logging.config import fileConfig
import os

from flask import current_app
from alembic import context

# Alembic Config object — provides access to values in alembic.ini
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "alembic.ini"
        )
    )
logger = logging.getLogger("alembic.env")


def get_engine():
    """Support both Flask-SQLAlchemy < 3 and >= 3."""
    try:
        return current_app.extensions["migrate"].db.get_engine()
    except (TypeError, AttributeError):
        return current_app.extensions["migrate"].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")
    except AttributeError:
        return str(get_engine().url).replace("%", "%%")


# Override the sqlalchemy.url in alembic.ini with the Flask app's DB URL
config.set_main_option("sqlalchemy.url", get_engine_url())

target_db = current_app.extensions["migrate"].db


def get_metadata():
    """Return the correct MetaData object (handles multi-bind setups)."""
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Useful for generating SQL scripts to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations against a live DB connection.
    Skips auto-migration generation when the schema has no changes.
    """
    def process_revision_directives(context, revision, directives):
        """Suppress empty migration files (no schema diff detected)."""
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No schema changes detected — skipping migration file.")

    conf_args = current_app.extensions["migrate"].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
