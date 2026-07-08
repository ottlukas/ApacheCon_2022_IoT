# ApacheCon 2022 IoT Demo - Dockerfile
# Uses Python 3.11-slim as base image

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY panel_script.py .
COPY zenoh_producer.py .
COPY zenoh_retrieve.py .
COPY zenoh_subscriber.py .
COPY DEFAULT_CONFIG.json5 .
COPY asf-estd-1999-logo.jpg .

# Create necessary directories
RUN mkdir -p /app/iotdb/data /app/iotdb/logs /app/iotdb/conf

# Set default environment variables
ENV ZENOH_ROUTER_ENDPOINT="tcp://zenohd:7447" \
    IOTDB_HOST="iotdb" \
    IOTDB_PORT="6667" \
    IOTDB_USERNAME="root" \
    IOTDB_PASSWORD="root" \
    API_HOST="0.0.0.0" \
    API_PORT="8080"

# Expose API port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command: run the API
CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8080"]

# Alternative command to run panel script (uncomment if needed)
# CMD ["panel", "serve", "panel_script.py", "--host", "0.0.0.0", "--port", "5006", "--autoreload"]
