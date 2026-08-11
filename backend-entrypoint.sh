#!/bin/sh
# Docker entrypoint for the FastAPI backend.
#
# Brings the database schema up to date before the app server starts, so a
# deploy can never leave the running code ahead of the schema it expects.
#
# This runs in the container's init process, i.e. exactly once per container
# start -- NOT once per gunicorn worker. gunicorn forks its workers only after
# `exec "$@"` below, so the migration has already finished by then.
#
# alembic.ini sits at /app and points script_location at backend/migrations.
# backend/migrations/env.py ignores the placeholder URL in alembic.ini and uses
# settings.DATABASE_URL, so this migrates whichever database the app itself is
# configured against -- no separate migration credentials to keep in sync.

set -e

cd /app

echo "[Entrypoint] Running database migrations (alembic upgrade head)..."
alembic upgrade head
echo "[Entrypoint] Migrations up to date."

echo "[Entrypoint] Starting app: $*"
exec "$@"
