#!/bin/sh
set -e

echo "==> [Backend] Running Alembic database migrations..."
python -m alembic upgrade head

if [ "${AUTO_SEED_DEMO_USERS:-true}" = "true" ]; then
    echo "==> [Backend] Seeding initial demo authentication users..."
    python -m app.auth.seed || echo "==> [Backend] Demo user seed skipped or already present."
fi

echo "==> [Backend] Starting FastAPI application on 0.0.0.0:8000..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
