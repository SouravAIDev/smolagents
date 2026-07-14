# Book Finder Agent — Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Book Finder Agent to production environments using Docker containers and Kubernetes (or similar orchestration platforms).

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Docker Image Build](#docker-image-build)
3. [Container Registry Push](#container-registry-push)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Health Checks and Monitoring](#health-checks-and-monitoring)
6. [Logging and Observability](#logging-and-observability)
7. [Scaling and Load Balancing](#scaling-and-load-balancing)
8. [Rolling Updates and Rollbacks](#rolling-updates-and-rollbacks)
9. [Security Best Practices](#security-best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

Before deploying to production, verify the following:

### Code and Configuration
- [ ] All source code is committed and tagged in Git
- [ ] `.env.production` file is prepared with production credentials
- [ ] `INTEGRATION_CHECKLIST.md` has been completed and verified
- [ ] Configuration validation passes: `python -c "import Config; Config.validate_configuration()"`
- [ ] All unit tests pass: `python -m pytest tests/`
- [ ] Code is linted and formatted: `black . && pylint book_finder_agent/`

### Infrastructure
- [ ] PostgreSQL/AlloyDB is running and accessible
- [ ] Database tables are created and indexed
- [ ] Google Cloud credentials (service account key) are generated
- [ ] PubSub topic exists (if using streaming)
- [ ] VPC/networking is configured for inter-service communication

### Documentation
- [ ] DEVELOPER_GUIDE.md reviewed and confirmed accurate
- [ ] DEPLOYMENT_GUIDE.md reviewed and all steps understood
- [ ] Runbooks created for common operational tasks
- [ ] Incident response procedures documented

---

## Docker Image Build

### Step 1: Review Dockerfile

Ensure the Dockerfile uses the following structure:

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/utility/book-content-rag-agent/health || exit 1

EXPOSE 5000

CMD ["gunicorn", "--workers", "4", "--worker-class", "gthread", \
     "--threads", "2", "--bind", "0.0.0.0:5000", \
     "--timeout", "120", "--keep-alive", "120", \
     "--max-requests", "1000", "--max-requests-jitter", "50", \
     "--graceful-timeout", "30", "--limit-request-line", "8190", \
     "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", \
     "run:app"]
```

### Step 2: Build the Image Locally

```bash
# Build with a descriptive tag
VERSION=1.0.0
REGISTRY=gcr.io/your-project-id
IMAGE_NAME=book-finder-agent

docker build -t ${REGISTRY}/${IMAGE_NAME}:${VERSION} \
             -t ${REGISTRY}/${IMAGE_NAME}:latest \
             .
```

### Step 3: Test the Image Locally

```bash
# Run the image with test configuration
docker run -it \
  -e POSTGRES_HOST=host.docker.internal \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB=book_finder_db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=test_password \
  -e GCLOUD_PROJECT_ID=test-project \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -v /path/to/service-account-key.json:/app/credentials.json \
  -p 5000:5000 \
  ${REGISTRY}/${IMAGE_NAME}:latest

# Test from another terminal
curl http://localhost:5000/utility/book-content-rag-agent/health
```

### Step 4: Verify Image Size and Security

```bash
# Check image size
docker images | grep ${IMAGE_NAME}

# Scan for vulnerabilities (if using Snyk or Trivy)
trivy image ${REGISTRY}/${IMAGE_NAME}:${VERSION}

# Verify no secrets are embedded
docker history ${REGISTRY}/${IMAGE_NAME}:${VERSION}
```

Expected size: 300-400 MB for the final runtime image.

---

## Container Registry Push

### Step 1: Authenticate with Registry

#### Google Container Registry (GCR)

```bash
# Configure Docker authentication
gcloud auth configure-docker

# Or for Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev
```

#### Docker Hub

```bash
docker login
```

### Step 2: Push the Image

```bash
VERSION=1.0.0
REGISTRY=gcr.io/your-project-id
IMAGE_NAME=book-finder-agent

docker push ${REGISTRY}/${IMAGE_NAME}:${VERSION}
docker push ${REGISTRY}/${IMAGE_NAME}:latest
```

### Step 3: Verify Push

```bash
# GCR
gcloud container images list --repository=${REGISTRY}

# List tags
gcloud container images list-tags ${REGISTRY}/${IMAGE_NAME}
```

---

## Kubernetes Deployment

### Step 1: Create Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: book-finder-prod
```

Apply:

```bash
kubectl apply -f namespace.yaml
```

### Step 2: Create Secrets for Credentials

```bash
# Store database credentials
kubectl create secret generic book-finder-db \
  --from-literal=POSTGRES_HOST=alloydb.example.com \
  --from-literal=POSTGRES_PORT=5432 \
  --from-literal=POSTGRES_DB=book_finder_db \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_PASSWORD=your_secure_password \
  -n book-finder-prod

# Store Google Cloud credentials
kubectl create secret generic book-finder-gcp \
  --from-file=GOOGLE_APPLICATION_CREDENTIALS=service-account-key.json \
  -n book-finder-prod
```

### Step 3: Create ConfigMap for Non-Sensitive Configuration

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: book-finder-config
  namespace: book-finder-prod
data:
  GCLOUD_PROJECT_ID: "your-gcp-project-id"
  GCLOUD_LOCATION: "us-central1"
  LLM_MODEL_NAME: "gemini-2.0-flash-001"
  LLM_TEMPERATURE: "0.7"
  LLM_MAX_TOKENS: "1024"
  FLASK_ENV: "production"
  LOG_LEVEL: "info"
```

Apply:

```bash
kubectl apply -f configmap.yaml
```

### Step 4: Create Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-finder-agent
  namespace: book-finder-prod
  labels:
    app: book-finder-agent
    version: v1
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: book-finder-agent
  template:
    metadata:
      labels:
        app: book-finder-agent
        version: v1
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "5000"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: book-finder-agent
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: book-finder-agent
        image: gcr.io/your-project-id/book-finder-agent:1.0.0
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 5000
          protocol: TCP
        
        env:
        # From Secrets
        - name: POSTGRES_HOST
          valueFrom:
            secretKeyRef:
              name: book-finder-db
              key: POSTGRES_HOST
        - name: POSTGRES_PORT
          valueFrom:
            secretKeyRef:
              name: book-finder-db
              key: POSTGRES_PORT
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: book-finder-db
              key: POSTGRES_DB
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: book-finder-db
              key: POSTGRES_USER
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: book-finder-db
              key: POSTGRES_PASSWORD
        - name: GOOGLE_APPLICATION_CREDENTIALS
          value: /var/secrets/google/service-account-key.json
        
        # From ConfigMap
        - name: GCLOUD_PROJECT_ID
          valueFrom:
            configMapKeyRef:
              name: book-finder-config
              key: GCLOUD_PROJECT_ID
        - name: GCLOUD_LOCATION
          valueFrom:
            configMapKeyRef:
              name: book-finder-config
              key: GCLOUD_LOCATION
        - name: LLM_MODEL_NAME
          valueFrom:
            configMapKeyRef:
              name: book-finder-config
              key: LLM_MODEL_NAME
        - name: LLM_TEMPERATURE
          valueFrom:
            configMapKeyRef:
              name: book-finder-config
              key: LLM_TEMPERATURE
        - name: LLM_MAX_TOKENS
          valueFrom:
            configMapKeyRef:
              name: book-finder-config
              key: LLM_MAX_TOKENS
        - name: FLASK_ENV
          valueFrom:
            configMapKeyRef:
              name: book-finder-config
              key: FLASK_ENV
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: book-finder-config
              key: LOG_LEVEL
        
        volumeMounts:
        - name: google-credentials
          mountPath: /var/secrets/google
          readOnly: true
        
        # Health Checks
        livenessProbe:
          httpGet:
            path: /utility/book-content-rag-agent/health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /utility/book-content-rag-agent/health
            port: http
          initialDelaySeconds: 15
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        
        # Resource Limits
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        
        # Security Context
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
      
      volumes:
      - name: google-credentials
        secret:
          secretName: book-finder-gcp
      
      # Pod Disruption Budget (for availability)
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - book-finder-agent
              topologyKey: kubernetes.io/hostname
```

Apply:

```bash
kubectl apply -f deployment.yaml
```

### Step 5: Create Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: book-finder-agent
  namespace: book-finder-prod
  labels:
    app: book-finder-agent
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 5000
    protocol: TCP
    name: http
  selector:
    app: book-finder-agent
```

Apply:

```bash
kubectl apply -f service.yaml
```

### Step 6: Create Ingress (for external access)

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: book-finder-agent
  namespace: book-finder-prod
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.bookfinder.example.com
    secretName: book-finder-tls
  rules:
  - host: api.bookfinder.example.com
    http:
      paths:
      - path: /utility/book-content-rag-agent
        pathType: Prefix
        backend:
          service:
            name: book-finder-agent
            port:
              number: 80
```

Apply:

```bash
kubectl apply -f ingress.yaml
```

### Step 7: Verify Deployment

```bash
# Check deployment status
kubectl get deployment -n book-finder-prod
kubectl describe deployment book-finder-agent -n book-finder-prod

# Check pods
kubectl get pods -n book-finder-prod -o wide
kubectl logs -n book-finder-prod -l app=book-finder-agent --tail=100

# Port forward for testing
kubectl port-forward -n book-finder-prod svc/book-finder-agent 5000:80

# Test
curl http://localhost:5000/utility/book-content-rag-agent/health
```

---

## Health Checks and Monitoring

### Health Check Endpoint

The agent exposes a health check at:

```
GET /utility/book-content-rag-agent/health
```

Expected response:

```json
{"status": "healthy"}
```

The health check verifies:
- Database connectivity
- Google Cloud API accessibility
- Required tables exist

### Kubernetes Health Probes

The deployment includes two probes:

#### Liveness Probe

- **Purpose**: Restart container if unhealthy
- **Interval**: 10 seconds
- **Timeout**: 5 seconds
- **Failure threshold**: 3 consecutive failures
- **Initial delay**: 30 seconds

#### Readiness Probe

- **Purpose**: Remove from load balancer if not ready
- **Interval**: 5 seconds
- **Timeout**: 3 seconds
- **Failure threshold**: 3 consecutive failures
- **Initial delay**: 15 seconds

### Monitoring Metrics

The agent exposes Prometheus metrics at (if enabled):

```
GET /metrics
```

Key metrics to monitor:

- `book_finder_agent_requests_total`: Total requests by endpoint
- `book_finder_agent_request_duration_seconds`: Request latency
- `book_finder_agent_database_query_duration_seconds`: Database query time
- `book_finder_agent_llm_generation_duration_seconds`: LLM generation time
- `book_finder_agent_citations_verified_total`: Verified citations count
- `book_finder_agent_errors_total`: Total errors by type

---

## Logging and Observability

### Structured Logging

Logs are output to stdout/stderr in JSON format for easy parsing by log aggregators:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "BookFinderAgent",
  "message": "Processing request",
  "session_id": "sess-12345",
  "user_query": "Find books about AI"
}
```

### Google Cloud Logging Integration

Enable automatic integration:

```python
# In run.py
import google.cloud.logging
client = google.cloud.logging.Client()
client.setup_logging()
```

### Log Levels

Configure via `LOG_LEVEL` environment variable:

- `DEBUG`: Detailed information for debugging
- `INFO`: General information (default)
- `WARNING`: Warning messages
- `ERROR`: Error messages only

### Centralized Logging Stack

Recommended setup:

1. **ELK Stack** (Elasticsearch, Logstash, Kibana):
   ```bash
   # Logstash configuration
   input {
     kubernetes {
       kubernetes_url => "https://kubernetes.default"
       ca_file => "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
     }
   }
   
   filter {
     json { source => "message" }
   }
   
   output {
     elasticsearch {
       hosts => ["elasticsearch.logging:9200"]
       index => "book-finder-%{+YYYY.MM.dd}"
     }
   }
   ```

2. **Google Cloud Logging**:
   - Logs automatically appear in Cloud Logging console
   - Create log-based metrics for monitoring
   - Set up alerts based on log content

3. **Datadog** or **New Relic**:
   - Automatic pod log collection via agents
   - APM integration for distributed tracing

---

## Scaling and Load Balancing

### Horizontal Pod Autoscaling

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: book-finder-agent
  namespace: book-finder-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: book-finder-agent
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 15
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 2
        periodSeconds: 15
      selectPolicy: Max
```

Apply:

```bash
kubectl apply -f hpa.yaml

# Monitor
kubectl get hpa -n book-finder-prod -w
```

### Load Balancer Configuration

#### Session Affinity (if needed)

For stateful requests, enable session affinity:

```yaml
service:
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 3600
```

#### Distributed Session Storage

If scaling beyond 1 replica, ensure session data is persisted:

1. Use Redis for session caching
2. Or store session data in the database (already implemented via `book_retrieved_document_details` table)

---

## Rolling Updates and Rollbacks

### Rolling Update (0 Downtime)

```bash
# Update image
kubectl set image deployment/book-finder-agent \
  book-finder-agent=gcr.io/your-project-id/book-finder-agent:1.1.0 \
  -n book-finder-prod

# Watch rollout
kubectl rollout status deployment/book-finder-agent -n book-finder-prod

# Monitor pods
kubectl get pods -n book-finder-prod -w
```

### Rollback to Previous Version

```bash
# Check rollout history
kubectl rollout history deployment/book-finder-agent -n book-finder-prod

# Rollback to previous revision
kubectl rollout undo deployment/book-finder-agent -n book-finder-prod

# Rollback to specific revision
kubectl rollout undo deployment/book-finder-agent --to-revision=2 -n book-finder-prod

# Verify rollback
kubectl rollout status deployment/book-finder-agent -n book-finder-prod
```

### Blue-Green Deployment (Alternative)

```bash
# Deploy new version alongside old
kubectl apply -f deployment-v1.1.0.yaml

# Test new deployment
kubectl port-forward -n book-finder-prod deploy/book-finder-agent-v1.1.0 5000:5000

# Switch traffic
kubectl patch service book-finder-agent -p '{"spec":{"selector":{"version":"v1.1.0"}}}'

# Remove old deployment
kubectl delete deployment book-finder-agent-v1.0.0 -n book-finder-prod
```

---

## Security Best Practices

### Image Security

1. **Use minimal base images**:
   ```dockerfile
   FROM python:3.11-slim  # 170 MB vs 900 MB for full image
   ```

2. **Run as non-root user**:
   ```dockerfile
   RUN useradd -m -u 1000 appuser
   USER appuser
   ```

3. **Scan for vulnerabilities**:
   ```bash
   trivy image gcr.io/your-project-id/book-finder-agent:1.0.0
   ```

4. **Sign images** (if using Cloud Binary Authorization):
   ```bash
   gcloud container binauthz policy import policy.yaml
   ```

### Secrets Management

1. **Use Kubernetes Secrets** (or external secret managers):
   ```bash
   kubectl create secret generic book-finder-db --from-literal=PASSWORD=...
   ```

2. **Rotate credentials regularly**:
   - Update service account key quarterly
   - Cycle database passwords every 90 days

3. **Audit secret access**:
   ```bash
   kubectl logs -n book-finder-prod -l app=book-finder-agent | grep SECRET
   ```

### Network Security

1. **Network Policies**:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: book-finder-agent
     namespace: book-finder-prod
   spec:
     podSelector:
       matchLabels:
         app: book-finder-agent
     policyTypes:
     - Ingress
     - Egress
     ingress:
     - from:
       - namespaceSelector:
           matchLabels:
             name: book-finder-prod
       ports:
       - protocol: TCP
         port: 5000
     egress:
     - to:
       - namespaceSelector: {}
       ports:
       - protocol: TCP
         port: 443
   ```

2. **TLS/SSL**:
   - Use cert-manager to auto-renew certificates
   - Enforce HTTPS via Ingress

3. **RBAC** (Role-Based Access Control):
   ```yaml
   apiVersion: v1
   kind: ServiceAccount
   metadata:
     name: book-finder-agent
     namespace: book-finder-prod
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: Role
   metadata:
     name: book-finder-agent
     namespace: book-finder-prod
   rules:
   - apiGroups: [""]
     resources: ["configmaps", "secrets"]
     verbs: ["get", "list"]
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: RoleBinding
   metadata:
     name: book-finder-agent
     namespace: book-finder-prod
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: Role
     name: book-finder-agent
   subjects:
   - kind: ServiceAccount
     name: book-finder-agent
     namespace: book-finder-prod
   ```

---

## Troubleshooting

### Issue: Pod fails to start

**Debug**:

```bash
# Check pod status
kubectl describe pod <pod-name> -n book-finder-prod

# View logs
kubectl logs <pod-name> -n book-finder-prod

# Check events
kubectl get events -n book-finder-prod --sort-by='.lastTimestamp'
```

**Common causes**:

1. Image not found: Verify image exists in registry
2. Secrets missing: Ensure ConfigMap and Secrets are created
3. Database unreachable: Check VPC peering and firewall rules
4. Port conflict: Change containerPort if 5000 is unavailable

### Issue: Pod crashes with OOMKilled

**Solution**:

```bash
# Increase memory limit
kubectl set resources deployment book-finder-agent \
  --limits=memory=2Gi -n book-finder-prod

# Monitor memory usage
kubectl top pods -n book-finder-prod
```

### Issue: High latency on requests

**Debug**:

```bash
# Check database query time
kubectl logs -n book-finder-prod -l app=book-finder-agent | grep "query_time"

# Monitor database connections
psql -U postgres -h <db-host> -c "SELECT count(*) FROM pg_stat_activity;"

# Check pod CPU/memory
kubectl top pod <pod-name> -n book-finder-prod
```

**Solutions**:

1. Increase pod resource limits
2. Add database indices
3. Scale up replicas (HPA)
4. Reduce `max_chunks_to_use` configuration

### Issue: Database connection pool exhaustion

**Debug**:

```bash
psql -U postgres -h <db-host> -c "SELECT * FROM pg_stat_activity WHERE datname = 'book_finder_db';"
```

**Solution**:

```yaml
# Update deployment with connection pool settings
env:
- name: DATABASE_POOL_SIZE
  value: "10"
- name: DATABASE_POOL_RECYCLE
  value: "3600"
```

---

## Support and Monitoring

For production support:

1. Set up alerts in Prometheus/Grafana for:
   - High error rate (> 1%)
   - High latency (p95 > 5s)
   - Pod crashes
   - Database unavailability

2. Create runbooks for:
   - Emergency rollback
   - Database failover
   - Certificate renewal
   - Pod eviction recovery

3. Schedule regular:
   - Disaster recovery drills
   - Load testing
   - Security audits

For urgent issues, escalate to the infrastructure team and reference this guide.

