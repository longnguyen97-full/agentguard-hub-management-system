FROM python:3.11-slim

# Install uv for fast, reliable dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Configure Python and uv environment
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app/backend \
    PYTHONUTF8=1

# Copy package manifests
COPY pyproject.toml uv.lock* ./

# Install dependencies using uv
RUN uv sync --no-dev || uv pip install --system -e .

# Copy backend code and runner
COPY backend/ /app/backend/
COPY run.py /app/
COPY agent_sdk.py /app/

# Ensure data directory exists for SQLite persistence
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uv", "run", "run.py"]
