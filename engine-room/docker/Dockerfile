# =============================================================================
# Nexus — Multi-stage Docker Build
# =============================================================================
# Python 3.12 slim image with uv for fast dependency management
# =============================================================================

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

WORKDIR /app

# -----------------------------------------------------------------------------
# Dependencies stage — cached separately from source code
# -----------------------------------------------------------------------------
FROM base AS dependencies

# Copy only dependency specification first (Docker layer caching)
COPY pyproject.toml ./
COPY uv.lock* ./

# Install dependencies (without the project itself)
RUN uv sync --no-install-project

# -----------------------------------------------------------------------------
# Final stage — copy source and run
# -----------------------------------------------------------------------------
FROM dependencies AS runtime

# Copy the full project source
COPY . .

# Install the project itself
RUN uv sync

# Expose the default service port
EXPOSE 8000

# Run Nexus as a Python module
CMD ["python", "-m", "nexus"]
