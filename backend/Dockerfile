FROM python:3.14-slim

WORKDIR /workspace/backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy backend package and migration files
COPY backend/pyproject.toml backend/alembic.ini backend/README.md ./
COPY backend/alembic/ alembic/
COPY backend/app/ app/
COPY backend/entrypoint.sh ./

# Copy simulator directory to maintain relative filesystem path expected by app/demo/router.py
COPY simulator/ /workspace/simulator/

# Install backend and dependencies
RUN pip install --no-cache-dir .

RUN chmod +x entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=5s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
