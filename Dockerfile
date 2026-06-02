###############################################################################
# Sovereign Trading System — Production Dockerfile
# Python 3.11-slim base, uv-managed dependencies, non-root user
###############################################################################
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# System packages required by native extensions (pandas, numpy, cryptography, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv and sync locked dependencies (layer-cached separately from app code)
COPY pyproject.toml uv.lock .python-version ./
RUN python -m pip install --no-cache-dir --upgrade pip uv \
    && uv sync --locked --no-install-project --no-dev

###############################################################################
# Runtime image
###############################################################################
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=base /app/.venv /app/.venv

# Non-root user for security
RUN groupadd --gid 1001 sovereign \
    && useradd --uid 1001 --gid sovereign --shell /bin/sh --create-home sovereign

COPY --chown=sovereign:sovereign src     ./src
COPY --chown=sovereign:sovereign migrations ./migrations
COPY --chown=sovereign:sovereign scripts ./scripts

# Persistent data directories (mounted at runtime via volume)
RUN mkdir -p /app/data /app/logs \
    && chown -R sovereign:sovereign /app/data /app/logs

USER sovereign

# Prometheus metrics     : 9090
# REST API               : 8000
EXPOSE 9090 8000

# Health check — verifies the API server is accepting connections
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["python", "-m", "src.main"]
