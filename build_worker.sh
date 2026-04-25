#!/bin/bash
# Lightweight build script for Celery worker + beat services.
#
# Workers don't serve HTTP, don't serve static files, and migrations are
# already handled by the web service's build (./build_production.sh) — so we
# skip `check --deploy`, `collectstatic`, `migrate_schemas`, and
# `migrate_asterisk` entirely. Saves ~60-90s per worker deploy on DO.
#
# DO App Platform builds each component in its own container, so this
# script runs twice per deploy (worker + beat); both only need the deps.

set -e

echo "Installing worker dependencies..."
pip install -r requirements.txt

echo "Worker build complete."
