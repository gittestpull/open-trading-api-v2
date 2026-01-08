# Trading Bot Container with uv
FROM python:3.13-slim

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libxcb1 \
    libxcb-xinerama0 \
    libgl1 \
    libxkbcommon0 \
    libegl1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY requirements.txt ./

# Install dependencies using uv sync
RUN uv sync --no-dev

# Copy all source code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs
RUN mkdir -p /app/scalp_data
RUN mkdir -p /root/KIS/config

# Default entrypoint with uv
ENTRYPOINT ["uv", "run", "python", "monitor_scalp_universal.py"]
