# Book Finder Agent — Docker Image
# Multi-stage build optimized for production deployment

FROM python:3.10-slim

WORKDIR /app

# Set build arguments for GCP credentials (secret mount)
ARG GOOGLE_APPLICATION_CREDENTIALS

# Install system dependencies required for PostgreSQL and other libraries
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first for better layer caching
COPY requirements.txt .

# Install Python dependencies with GCP artifact registry support
# Using secret mount to avoid exposing credentials in image layers
RUN --mount=type=secret,id=gcp_creds,target=/tmp/gcp_key.json,mode=0444 \
    pip install --upgrade pip setuptools wheel && \
    pip install keyring && \
    pip install keyrings.google-artifactregistry-auth && \
    export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp_key.json && \
    pip install --index-url https://us-central1-python.pkg.dev/alan-suite/llm-studio-pypi/simple \
    --extra-index-url https://pypi.org/simple/ \
    -r requirements.txt

# Copy application code
COPY . .

# Copy agent-specific files
COPY agents/book_finder_agent /app/agents/book_finder_agent
COPY book_finder_helpers.py book_finder_helpers.py
COPY run.py run.py
COPY config.py config.py

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Health check to verify agent is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)"

# Expose Flask port
EXPOSE 5000

# Set the entry point
ENTRYPOINT ["python", "run.py"]
