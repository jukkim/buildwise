#!/bin/bash
set -e

echo "=== BuildWise Backend Starting ==="

# Run Alembic migrations (skip for Celery workers)
if [[ "$1" != "celery" ]]; then
    echo "Running database migrations..."
    alembic upgrade head
    echo "Migrations complete."
fi

echo "Executing: $@"
exec "$@"
