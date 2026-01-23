FROM python:3.13-slim

# Install system deps
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency files first
COPY pyproject.toml uv.lock ./

# Configuration for uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
# CRITICAL: Force uv to use the system python (3.13)
ENV UV_PYTHON=/usr/local/bin/python

# Sync dependencies
RUN uv sync --frozen --no-install-project --no-dev

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code
COPY . .

# Expose port
EXPOSE 8001

# Command
CMD ["uv", "run", "python", "run_web.py"]
