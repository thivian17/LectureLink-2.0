# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy workspace root (lockfile + workspace definition)
COPY pyproject.toml uv.lock ./

# Copy package-level pyproject.toml (for dependency resolution)
COPY packages/api/pyproject.toml packages/api/

# Install dependencies only — excludes dev deps and the project itself
# so we get a clean layer cache that only busts when deps change.
RUN uv sync --frozen --no-dev --no-install-project --project packages/api

# ---- Stage 2: Runtime ----
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual-env with all dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY packages/api/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    ENVIRONMENT="production" \
    PYTHONUNBUFFERED="1"

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "lecturelink_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
