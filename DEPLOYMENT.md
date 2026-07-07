# Book Finder Agent - Deployment Guide

This document provides comprehensive instructions for deploying the Book Finder Agent to various environments: local development, staging, and production.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Local Development Deployment](#local-development-deployment)
4. [Docker Container Deployment](#docker-container-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment-production)
6. [Cloud Platform Deployment](#cloud-platform-deployment)
7. [Database Setup](#database-setup)
8. [Configuration Management](#configuration-management)
9. [Monitoring & Observability](#monitoring--observability)
10. [Troubleshooting](#troubleshooting)
11. [Rollback Procedures](#rollback-procedures)

## Quick Start

### Local Development (5 minutes)

```bash
# Clone repository
git clone https://github.com/your-org/book-finder-agent.git
cd book-finder-agent

# Copy and configure environment
make env-setup
nan .env  # Edit with your API keys

# Start complete stack
make dev-docker

# Verify deployment
make health-check
```

### Production Kubernetes (30 minutes)

```bash
# Configure namespace and secrets
kubectl create namespace book-finder-agent
kubectl create secret generic book-finder-secrets -n book-finder-agent \
  --from-literal=DB_PASSWORD=your-secure-password \
  --from-literal=OPENAI_API_KEY=sk-your-key

# Deploy
kubectl apply -f k8s-deployment.yaml -n book-finder-agent

# Verify
kubectl get pods -n book-finder-agent
kubectl logs -f deployment/book-finder-agent -n book-finder-agent
```

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Load Balancer / Ingress                      │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/HTTPS
┌────────────────────────▼────────────────────────────────────────┐
│            Book Finder Agent Service (3 replicas)               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Flask Application (Gunicorn)                            │   │
│  │  - Request validation & normalization (A3)              │   │
│  │  - Core orchestration (A4)                              │   │
│  │  - Response assembly & citations (A5/B1/C1)            │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────┬──────────────────────────────────────┬─────┘
                     │                                      │
         ┌───────────▼──────────┐              ┌────────────▼─────┐
         │  PostgreSQL + pgvector               │    Redis Cache   │
         │  - book_metadata_v2                  │  - Session state │
         │  - book_author_v2                    │  - Result cache  │
         │  - book_genre_v2                     │                  │
         │  - book_excerpt_v2                   │                  │
         │  - book_retrieved_documents          │                  │
         └────────────────────┘                 └──────────────────┘

         ┌────────────────────────────────────────────┐
         │   External Services (via LLM Studio)      │
         │  - OpenAI API (embeddings, LLM)           │
         │  - Anthropic Claude                       │
         │  - Google Generative AI                   │
         │  - Google Cloud AI Platform               │
         └────────────────────────────────────────────┘
```

## Local Development Deployment

### Prerequisites

- Python 3.9+
- Docker and Docker Compose v2.0+
- Git
- curl (for health checks)

### Setup Steps

1. **Clone Repository**
   ```bash
   git clone https://github.com/your-org/book-finder-agent.git
   cd book-finder-agent
   ```

2. **Create Virtual Environment**
   ```bash
   make install-dev
   ```

3. **Configure Environment**
   ```bash
   make env-setup
   
   # Edit .env with your settings
   # Required: OPENAI_API_KEY, DB_PASSWORD, etc.
   ```

4. **Start Development Stack**
   ```bash
   # Option A: Docker Compose (recommended)
   make dev-docker
   
   # Option B: Local Flask with external services
   # (requires running PostgreSQL and Redis separately)
   docker-compose up -d postgres redis
   make dev
   ```

5. **Verify Deployment**
   ```bash
   # Health check
   curl http://localhost:5000/utility/book-finder-agent/
   
   # Get configuration schema
   curl http://localhost:5000/utility/book-finder-agent/get_config
   ```

### Expected Output

```bash
$ make health-check
Checking agent health...
BookFinderAgent_v2 is running!✓ Health check passed
```

## Docker Container Deployment

### Building the Image

```bash
# Build with Docker Compose
make docker-build

# Or build directly
docker build -t book-finder-agent:latest .

# Build with custom tag
docker build -t your-registry.azurecr.io/book-finder-agent:v1.0.0 .
```

### Running Containers

```bash
# Single container (requires external PostgreSQL/Redis)
docker run -d \
  -p 5000:5000 \
  -e DB_HOST=your-db-host \
  -e DB_PASSWORD=your-db-password \
  -e OPENAI_API_KEY=sk-your-key \
  -e REDIS_HOST=your-redis-host \
  book-finder-agent:latest

# Full stack with Docker Compose
make docker-up

# View logs
make docker-logs SERVICE=book_finder_agent FOLLOW=1
```

### Multi-Stage Build Optimization

The Dockerfile uses a multi-stage build:

- **Stage 1 (builder)**: Install all dependencies in virtual environment
- **Stage 2 (runtime)**: Copy venv, minimal app files, non-root user

Result: ~500MB final image (vs ~2GB if dependencies installed at runtime)

### Image Registry Push

```bash
# Docker Hub
docker tag book-finder-agent:latest your-username/book-finder-agent:latest
docker push your-username/book-finder-agent:latest

# Azure Container Registry
az acr login --name yourregistry
docker tag book-finder-agent:latest yourregistry.azurecr.io/book-finder-agent:v1.0.0
docker push yourregistry.azurecr.io/book-finder-agent:v1.0.0

# Google Container Registry
gcloud auth configure-docker
docker tag book-finder-agent:latest gcr.io/your-project/book-finder-agent:v1.0.0
docker push gcr.io/your-project/book-finder-agent:v1.0.0
```

## Kubernetes Deployment (Production)

### Prerequisites

- Kubernetes cluster 1.20+
- kubectl configured
- Helm (optional, for templating)
- Persistent Volume provisioner (for PostgreSQL/Redis)

### Step 1: Create Namespace

```bash
kubectl create namespace book-finder-agent
kubectl config set-context --current --namespace=book-finder-agent
```

### Step 2: Create Secrets

```bash
# Database credentials
kubectl create secret generic book-finder-db-secret \
  --from-literal=password='your-very-secure-password' \
  -n book-finder-agent

# LLM API keys
kubectl create secret generic book-finder-llm-secret \
  --from-literal=openai-key='sk-...' \
  --from-literal=anthropic-key='sk-ant-...' \
  --from-literal=google-key='...' \
  -n book-finder-agent

# GCP credentials (if using Google Cloud services)
kubectl create secret generic gcp-credentials \
  --from-file=credentials.json=/path/to/service-account-key.json \
  -n book-finder-agent
```

### Step 3: Deploy

```bash
# Deploy all resources
kubectl apply -f k8s-deployment.yaml -n book-finder-agent

# Verify deployment
kubectl get all -n book-finder-agent

# Watch rollout
kubectl rollout status deployment/book-finder-agent -n book-finder-agent
```

### Step 4: Expose Service

```bash
# Port forward (for testing)
kubectl port-forward svc/book-finder-agent 5000:80 -n book-finder-agent

# Or configure Ingress
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: book-finder-ingress
  namespace: book-finder-agent
spec:
  ingressClassName: nginx
  rules:
  - host: book-finder.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: book-finder-agent
            port:
              number: 80
EOF
```

### Step 5: Verify Deployment

```bash
# Check pod status
kubectl get pods -n book-finder-agent

# View logs
kubectl logs -f deployment/book-finder-agent -n book-finder-agent

# Test health endpoint
kubectl exec -it pod/book-finder-agent-xxxxx -n book-finder-agent -- \
  curl localhost:5000/utility/book-finder-agent/
```

## Cloud Platform Deployment

### Google Cloud Run

```bash
# Build and push to GCR
cloud builds submit --tag gcr.io/your-project/book-finder-agent

# Deploy to Cloud Run
gcloud run deploy book-finder-agent \
  --image gcr.io/your-project/book-finder-agent \
  --platform managed \
  --region us-central1 \
  --memory 512Mi \
  --set-env-vars OPENAI_API_KEY=sk-...,DB_HOST=cloudsql-proxy
```

### Azure Container Instances

```bash
# Push to ACR
az acr build --registry yourregistry --image book-finder-agent:v1.0.0 .

# Deploy
az container create \
  --resource-group your-rg \
  --name book-finder-agent \
  --image yourregistry.azurecr.io/book-finder-agent:v1.0.0 \
  --port 5000 \
  --environment-variables OPENAI_API_KEY=sk-...
```

### AWS ECS Fargate

```bash
# Create task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
  --cluster book-finder \
  --service-name book-finder-agent \
  --task-definition book-finder-agent:1 \
  --desired-count 3
```

## Database Setup

### PostgreSQL with pgvector

#### Docker Initialization

```bash
# Start PostgreSQL with initialization script
docker-compose up -d postgres

# Database is initialized automatically with:
# - pgvector extension
# - book_retrieved_document_details table for session state
```

#### Manual Setup

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d book_finder_db

# Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Create session context table
CREATE TABLE IF NOT EXISTS book_retrieved_document_details (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    book_data JSONB NOT NULL,
    is_displayed BOOLEAN DEFAULT FALSE,
    similarity_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ON book_retrieved_document_details(session_id);
CREATE INDEX ON book_retrieved_document_details(is_displayed);
```

#### Performance Tuning

```sql
-- Create indices for faster queries
CREATE INDEX idx_book_summary_embeddings ON book_metadata_v2 
  USING ivfflat (book_summary_embeddings vector_cosine_ops)
  WITH (lists = 100);

-- Analyze tables after initial data load
ANALYZE book_metadata_v2;
ANALYZE book_retrieved_document_details;

-- Monitor slow queries
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1s
SELECT pg_reload_conf();
```

### Redis Configuration

```bash
# Persistent Redis with AOF
redis-server --appendonly yes --appendfsync everysec

# Or with Docker
docker run -d \
  -v redis_data:/data \
  -p 6379:6379 \
  redis:7-alpine redis-server --appendonly yes
```

## Configuration Management

### Environment Variables

See `.env.example` for all available variables. Critical variables:

```bash
# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=book_finder_db
DB_USER=postgres
DB_PASSWORD=secure-password

# LLM APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_GENAI_API_KEY=...

# Search Configuration
SIMILARITY_THRESHOLD=0.3
FILTER_SIMILARITY_THRESHOLD=0.65
```

### ConfigMap (Kubernetes)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: book-finder-config
data:
  FLASK_ENV: production
  BOOKS_PER_RESULT: "5"
  MAX_BOOKS_PER_RESPONSE: "3"
  SIMILARITY_THRESHOLD: "0.3"
```

## Monitoring & Observability

### Health Checks

```bash
# Liveness probe
curl http://localhost:5000/utility/book-finder-agent/

# Kubernetes health check
kubectl exec -it pod/book-finder-agent -n book-finder-agent -- \
  curl localhost:5000/utility/book-finder-agent/
```

### Logging

```bash
# Docker logs
make docker-logs SERVICE=book_finder_agent FOLLOW=1

# Kubernetes logs
kubectl logs -f deployment/book-finder-agent -n book-finder-agent

# Tail last 100 lines
kubectl logs --tail=100 deployment/book-finder-agent -n book-finder-agent
```

### Metrics Collection

The agent logs structured JSON compatible with:
- Google Cloud Logging
- ELK Stack
- Datadog
- CloudWatch

```python
# Metrics are automatically logged in this format:
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Book retrieval completed",
  "trace_id": "xyz123",
  "duration_ms": 342,
  "books_retrieved": 15,
  "similarity_threshold": 0.3
}
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Timeout

```bash
# Check PostgreSQL is running
docker-compose logs postgres

# Reset database
make db-reset

# Verify connection parameters in .env
```

#### 2. API Key Errors

```bash
# Verify OPENAI_API_KEY is set
echo $OPENAI_API_KEY

# Check secret in Kubernetes
kubectl get secret book-finder-llm-secret -n book-finder-agent -o yaml

# Redact and test
kubectl set env deployment/book-finder-agent \
  OPENAI_API_KEY=sk-new-key -n book-finder-agent
```

#### 3. Out of Memory

```bash
# Increase resource limits
kubectl set resources deployment/book-finder-agent \
  --limits=cpu=2,memory=2Gi \
  --requests=cpu=500m,memory=512Mi \
  -n book-finder-agent

# Or edit k8s-deployment.yaml and reapply
```

#### 4. Slow Queries

```sql
-- Check query performance
EXPLAIN ANALYZE
SELECT * FROM book_metadata_v2 
WHERE book_summary_embeddings <=> '[0.1,0.2,...]'::vector 
LIMIT 10;

-- Build indexes if missing
VACUUM ANALYZE book_metadata_v2;
```

## Rollback Procedures

### Docker Rollback

```bash
# Keep previous images
docker tag book-finder-agent:latest book-finder-agent:v1.0.0

# Rollback to previous image
docker-compose down
docker run book-finder-agent:v0.9.9 ...
```

### Kubernetes Rollback

```bash
# View rollout history
kubectl rollout history deployment/book-finder-agent -n book-finder-agent

# Rollback to previous version
kubectl rollout undo deployment/book-finder-agent -n book-finder-agent

# Rollback to specific revision
kubectl rollout undo deployment/book-finder-agent --to-revision=5 -n book-finder-agent
```

### Database Rollback

```bash
# PostgreSQL WAL-based recovery
psql -h localhost -U postgres -d book_finder_db < backup.sql

# Or use point-in-time recovery (if configured)
psql -h localhost -U postgres -d book_finder_db -c "SELECT pg_wal_replay_pause();"
```

---

## Support & Documentation

- [README.md](README.md) - Project overview and quick start
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guidelines
- [k8s-deployment.yaml](k8s-deployment.yaml) - Kubernetes manifests
- [docker-compose.yml](docker-compose.yml) - Docker Compose configuration

