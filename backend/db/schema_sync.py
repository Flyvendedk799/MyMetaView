"""Bring an existing database up to date with the models at startup.

``Base.metadata.create_all()`` creates tables that do not exist yet, but it will
never touch a table that does. So every migration that adds a *column* is
invisible to it — and because nothing in the deploy path runs
``alembic upgrade``, those columns never appeared in production at all. The
result is a 500 on every endpoint that touches the model, with
"no such column" / "column ... does not exist" in the logs.

This module closes that gap: it compares each mapped table against the live
schema and adds any column the model declares but the database lacks.

Deliberately narrow. It only ever ADDs columns. It does not drop them, change
types, add constraints, create indexes, or backfill data — anything structural
still belongs in an Alembic migration.
"""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy import Column, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateColumn

from backend.db import Base

logger = logging.getLogger(__name__)


def _already_exists(error: Exception) -> bool:
    """Two workers can race to add the same column; losing that race is fine."""
    message = str(error).lower()
    return "duplicate column" in message or "already exists" in message


def _add_column_sql(engine: Engine, table_name: str, column: Column) -> str:
    """Render an ADD COLUMN statement for this dialect.

    The column definition is compiled by SQLAlchemy rather than assembled by
    hand, so literals and types are quoted the way each backend expects —
    ``DEFAULT 'auto'`` for a string, ``DEFAULT false`` rather than ``DEFAULT 0``
    for a Postgres boolean.
    """
    if not column.nullable and column.server_default is None:
        # Adding a NOT NULL column with no default fails outright on a table
        # that already has rows. Add it nullable instead: the point is to stop
        # the query erroring, and a migration can tighten it afterwards.
        logger.warning(
            "schema sync: adding %s.%s as nullable — the model marks it NOT NULL "
            "but it has no server default, and existing rows have no value for it",
            table_name,
            column.name,
        )
        column = Column(column.name, column.type, nullable=True)

    definition = CreateColumn(column).compile(dialect=engine.dialect)
    preparer = engine.dialect.identifier_preparer
    return f"ALTER TABLE {preparer.quote(table_name)} ADD COLUMN {definition}"


def sync_missing_columns(engine: Engine) -> List[str]:
    """Add columns the models declare but the database is missing.

    Returns the list of "table.column" entries that were added.
    """
    added: List[str] = []

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
    except SQLAlchemyError as exc:
        logger.error("schema sync: could not inspect the database: %s", exc)
        return added

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            # create_all() handles brand new tables.
            continue

        try:
            live_columns = {col["name"] for col in inspector.get_columns(table.name)}
        except SQLAlchemyError as exc:
            logger.error("schema sync: could not inspect %s: %s", table.name, exc)
            continue

        missing = [col for col in table.columns if col.name not in live_columns]
        if not missing:
            continue

        for column in missing:
            statement = _add_column_sql(engine, table.name, column)
            try:
                with engine.begin() as connection:
                    connection.execute(text(statement))
            except SQLAlchemyError as exc:
                if _already_exists(exc):
                    logger.debug("schema sync: %s.%s already added", table.name, column.name)
                    continue
                # Keep going: one column we cannot add should not block the rest.
                logger.error(
                    "schema sync: failed to add %s.%s (%s): %s",
                    table.name,
                    column.name,
                    statement,
                    exc,
                )
                continue

            added.append(f"{table.name}.{column.name}")
            logger.info("schema sync: added %s.%s", table.name, column.name)

    return added
