# Book Finder Agent — Docker Deployment Guide

This guide covers building, running, and deploying the Book Finder Agent using Docker.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Building the Docker Image](#building-the-docker-image)
3. [Running with Docker Compose](#running-with-docker-compose)
4. [Running in Production](#running-in-production)
5. [Docker Configuration](#docker-configuration)
6. [Troubleshooting](#troubleshooting)
7. [Security Best Practices](#security-best-practices)

---

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 1.29+
- GCP credentials JSON file (for LLM and embeddings)
- PostgreSQL 13+ (if not using Docker Compose)
- 4GB RAM minimum, 8GB recommended

### 1. Using Docker Compose (Recommended for Development)

```bash
# Clone the repository
git clone <repo-url>
cd book_finder_agent

# Create .env file with configuration
cat > .env << EOF
DB_USER=bookfinder
DB_PASSWORD=bookfinder123
DB_NAME=book_finder_db
DB_PORT=5432
FLASK_PORT=5000
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=your-secret-key-change-in-production
GCP_PROJECT_ID=alan-suite
SEMANTIC_SIMILARITY_THRESHOLD=0.65
CITATION_CONFIDENCE_THRESHOLD=0.75
LOG_LEVEL=INFO
EOF

# Create GCP credentials directory
mkdir -p .gcp
cp /path/to/your/credentials.json .gcp/credentials.json

# Start all services
docker-compose up
```

The agent will be available at `http://localhost:5000`.

### 2. Using Only Docker (Production)

```bash
# Build the image
docker build -t book-finder-agent:latest .

# Run the container
docker run -d \
  --name book-finder-agent \
  -p 5000:5000 \
  -e DATABASE_URI="postgresql://user:password@postgres-host:5432/book_finder_db" \
  -e SECRET_KEY="your-secret-key" \
  -e GCP_PROJECT_ID="alan-suite" \
  -v /path/to/credentials.json:/app/.gcp/credentials.json:ro \
  book-finder-agent:latest
```

---

## Building the Docker Image

### Standard Build

```bash
# Build with default settings
docker build -t book-finder-agent:latest .

# Build with custom tag
docker build -t gcr.io/alan-suite/book-finder-agent:v1.0.0 .

# Build with build args
docker build \
  --build-arg PYTHON_VERSION=3.10 \
  -t book-finder-agent:latest .
```

### Build with Secret Mount (for GCP Credentials)

```bash
# Build with secret mount
docker build \
  --secret id=gcp_creds,src=/path/to/credentials.json \
  -t book-finder-agent:latest .
```

### Build Output

```
Building book-finder-agent:latest...
Step 1/20 : FROM python:3.10-slim
Step 2/20 : WORKDIR /app
Step 3/20 : ARG GOOGLE_APPLICATION_CREDENTIALS
...
Successfully built abc123def456
Successfully tagged book-finder-agent:latest
```

---

## Running with Docker Compose

### Start Services

```bash
# Start all services in background
docker-compose up -d

# Start with verbose logging
docker-compose up

# Start specific service
docker-compose up postgres
docker-compose up book_finder_agent
```

### Check Service Status

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f book_finder_agent

# View specific service logs
docker-compose logs postgres
```

### Test the Agent

```bash
# Test prediction endpoint
curl -X POST http://localhost:5000/utility/book-finder-agent/prediction \
  -H "Content-Type: application/json" \
  -d '{
    "search_query": "Find books about machine learning",
    "session_id": "test-session-123"
  }'

# Get configuration
curl http://localhost:5000/utility/book-finder-agent/get_config

# Get LLM configuration
curl http://localhost:5000/utility/book-finder-agent/get_llm_config
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Stop and remove all data
docker-compose down -v --remove-orphans
```

---

## Running in Production

### Docker Swarm Deployment

```bash
# Initialize swarm
docker swarm init

# Build and tag image
docker build -t book-finder-agent:v1.0.0 .

# Create production stack
docker stack deploy -c docker-compose.prod.yml book_finder

# View stack services
docker service ls

# View service logs
docker service logs book_finder_book_finder_agent
```

### Kubernetes Deployment (Optional)

```bash
# Build and push to registry
docker build -t gcr.io/alan-suite/book-finder-agent:v1.0.0 .
docker push gcr.io/alan-suite/book-finder-agent:v1.0.0

# Create Kubernetes deployment (example)
kubectl apply -f k8s-deployment.yaml
```

### Health Check Verification

```bash
# Check container health
docker-compose ps

# Expected output:
# NAME                          STATUS
# book_finder_postgres          Up 2 minutes (healthy)
# book_finder_redis             Up 2 minutes (healthy)
# book_finder_agent             Up 2 minutes (healthy)
```

---

## Docker Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database Configuration
DB_USER=bookfinder
DB_PASSWORD=bookfinder123
DB_NAME=book_finder_db
DB_PORT=5432

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=0
FLASK_PORT=5000
SECRET_KEY=your-secret-key-change-in-production

# GCP Configuration
GCP_PROJECT_ID=alan-suite
GCP_CREDENTIALS_FILE=./.gcp/credentials.json

# Book Finder Agent Configuration
SEMANTIC_SIMILARITY_THRESHOLD=0.65
CITATION_CONFIDENCE_THRESHOLD=0.75
MAX_RESULTS_PER_QUERY=25
PAGE_SIZE=10
SESSION_EXPIRY_HOURS=24

# LLM Configuration
LLM_MODEL=gemini-2.0-flash
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048

# Logging
LOG_LEVEL=INFO
```

### Volume Mounts

```bash
# Mount configuration files
docker run -v /path/to/.env:/app/.env:ro book-finder-agent

# Mount GCP credentials
docker run -v /path/to/credentials.json:/app/.gcp/credentials.json:ro book-finder-agent

# Mount data directory
docker run -v book_finder_data:/app/data book-finder-agent
```

### Network Configuration

```bash
# Create custom network
docker network create book-finder-net

# Run containers on custom network
docker run --network book-finder-net --name postgres postgres:15
docker run --network book-finder-net --name agent book-finder-agent

# Containers can communicate by hostname
# In agent: postgresql://postgres:5432/...
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Error

```
Error: could not connect to server: Connection refused
```

**Solution:**

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Verify DATABASE_URI
echo $DATABASE_URI

# Wait for database to be ready
docker-compose up postgres
# Wait 30 seconds, then start agent
```

#### 2. GCP Credentials Not Found

```
Error: Application Default Credentials not found
```

**Solution:**

```bash
# Verify credentials file exists
ls -la .gcp/credentials.json

# Check GOOGLE_APPLICATION_CREDENTIALS is set
docker exec book_finder_agent env | grep GOOGLE_APPLICATION_CREDENTIALS

# Mount credentials correctly
docker run -e GOOGLE_APPLICATION_CREDENTIALS=/app/.gcp/credentials.json \
  -v /path/to/credentials.json:/app/.gcp/credentials.json:ro \
  book-finder-agent
```

#### 3. Port Already in Use

```
Error: Address already in use
```

**Solution:**

```bash
# Find process using port 5000
lsof -i :5000

# Kill the process
kill -9 <PID>

# Or use different port
docker run -p 5001:5000 book-finder-agent

# Or update .env
echo "FLASK_PORT=5001" >> .env
```

#### 4. Out of Memory

```
Error: Cannot allocate memory
```

**Solution:**

```bash
# Increase Docker memory limit
# Mac/Windows: Docker Desktop → Preferences → Resources → Memory → 8GB
# Linux: docker run -m 8g book-finder-agent

# Or reduce page size
echo "PAGE_SIZE=5" >> .env
docker-compose restart
```

### Debug Mode

```bash
# Start with debug logging
echo "LOG_LEVEL=DEBUG" >> .env
docker-compose up

# Execute command in running container
docker-compose exec book_finder_agent bash

# View real-time logs
docker-compose logs -f --tail=100 book_finder_agent
```

---

## Security Best Practices

### 1. Secrets Management

```bash
# Use Docker secrets in production
docker secret create db_password secret.txt

# Use secret mounts for credentials (already in Dockerfile)
docker build --secret id=gcp_creds,src=credentials.json .
```

### 2. Environment Variables

```bash
# Never hardcode secrets in .env
# Use secure secret management:

# Option 1: Pass at runtime
docker run -e SECRET_KEY="$(openssl rand -hex 32)" book-finder-agent

# Option 2: Use .env.local (excluded from git)
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env.local
```

### 3. Image Security

```bash
# Use specific Python version (not latest)
FROM python:3.10-slim  # Good
FROM python:latest     # Bad

# Scan image for vulnerabilities
docker scan book-finder-agent:latest

# Use least privilege user
RUN useradd -m -u 1000 appuser
USER appuser
```

### 4. Network Security

```bash
# Use named networks (not host network)
docker run --network book-finder-net book-finder-agent  # Good
docker run --network host book-finder-agent             # Bad

# Restrict port access
docker run -p 127.0.0.1:5000:5000 book-finder-agent  # Only localhost
docker run -p 5000:5000 book-finder-agent             # All interfaces
```

### 5. Data Security

```bash
# Use read-only volumes for config
docker run -v /path/to/config:/app/config:ro book-finder-agent

# Use encrypted volumes for data
docker volume create --driver local \
  --opt type=tmpfs \
  --opt device=tmpfs \
  tmp_data

# Set proper file permissions
docker exec book_finder_agent chmod 600 .gcp/credentials.json
```

---

## Performance Optimization

### Resource Limits

```bash
# Set memory limit
docker run -m 2g --memory-swap 4g book-finder-agent

# Set CPU limit
docker run --cpus="2.0" book-finder-agent

# In docker-compose.yml
services:
  book_finder_agent:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G
```

### Caching Layers

```bash
# Docker automatically caches layers
# Order Dockerfile for efficient caching:
# 1. System packages (rarely change)
# 2. Requirements.txt (occasionally change)
# 3. Application code (frequently change)
```

### Multi-Stage Builds

```dockerfile
# Reduces final image size
FROM python:3.10-slim as builder
# ... build dependencies ...

FROM python:3.10-slim
# ... copy only necessary files ...
```

---

## Monitoring & Logging

### Docker Logs

```bash
# View container logs
docker logs book_finder_agent

# Follow logs
docker logs -f book_finder_agent

# View last 100 lines
docker logs --tail 100 book_finder_agent

# View logs with timestamps
docker logs -t book_finder_agent
```

### Health Checks

```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' book_finder_agent

# View health check details
docker inspect book_finder_agent | grep -A 5 Health
```

### Metrics

```bash
# View resource usage
docker stats book_finder_agent

# View detailed resource information
docker inspect book_finder_agent | grep -i memory
```

---

## Conclusion

The Book Finder Agent Docker configuration provides:

- ✅ Production-ready containerization
- ✅ Easy local development with docker-compose
- ✅ Security best practices (secret mounts, least privilege)
- ✅ Health checks for orchestration
- ✅ Performance optimization
- ✅ Comprehensive logging and monitoring

For questions or issues, refer to the main [SYSTEM_DEPLOYMENT_GUIDE.md](SYSTEM_DEPLOYMENT_GUIDE.md) or check [Troubleshooting](#troubleshooting).

