# Trading Bot Container
FROM python:3.13-slim

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libxcb1 \
    libxcb-xinerama0 \
    libgl1 \
    libxkbcommon0 \
    libegl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY requirements.txt ./

# Install dependencies using pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs
RUN mkdir -p /app/scalp_data
RUN mkdir -p /root/KIS/config

# Default entrypoint
ENTRYPOINT ["python", "run_web.py"]
