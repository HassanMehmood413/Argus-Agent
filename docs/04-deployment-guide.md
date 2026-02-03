# Deployment Guide

Step-by-step guide to deploy Argus Agent on Kubernetes.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Docker Desktop Setup](#docker-desktop-setup)
3. [Build Docker Image](#build-docker-image)
4. [Deploy to Kubernetes](#deploy-to-kubernetes)
5. [Verify Deployment](#verify-deployment)
6. [Monitoring Setup](#monitoring-setup)
7. [Testing the Agent](#testing-the-agent)

---

## Prerequisites

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Docker Desktop | Latest | Container runtime + K8s |
| kubectl | v1.28+ | Kubernetes CLI |
| Helm | v3.x | Package manager (for Prometheus) |

### Verify Installation

```bash
# Docker
docker --version

# Kubernetes
kubectl version --client

# Helm
helm version
```

### Enable Kubernetes in Docker Desktop

1. Open Docker Desktop
2. Go to **Settings → Kubernetes**
3. Check **"Enable Kubernetes"**
4. Click **"Apply & Restart"**
5. Wait for Kubernetes to start (green indicator)

### Verify Kubernetes

```bash
kubectl cluster-info
kubectl get nodes
```

---

## Docker Desktop Setup

### Allocate Resources

Go to: **Docker Desktop → Settings → Resources**

Recommended settings:
- **CPUs:** 4+
- **Memory:** 8 GB+
- **Swap:** 2 GB
- **Disk:** 60 GB+

### Verify Context

```bash
# Check current context
kubectl config current-context
# Should show: docker-desktop

# If not, switch context
kubectl config use-context docker-desktop
```

---

## Build Docker Image

### Create Dockerfile (if not exists)

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build Image

```bash
cd backend

# Build the image
docker build -t argus-agent:latest .

# Verify image
docker images | grep argus-agent
```

### Test Image Locally

```bash
# Run container
docker run -d --name argus-test -p 8000:8000 argus-agent:latest

# Check logs
docker logs argus-test

# Test health endpoint
curl http://localhost:8000/health

# Stop and remove
docker stop argus-test && docker rm argus-test
```

---

## Deploy to Kubernetes

### Step 1: Create Namespace

```bash
kubectl apply -f k8s/namespace/agent_prod.yml
```

**Verify:**
```bash
kubectl get namespaces | grep argus
```

### Step 2: Deploy Database (PostgreSQL)

```bash
# Apply in order
kubectl apply -f k8s/backend/db/postgres-secret.yml
kubectl apply -f k8s/backend/db/postgres-pvc.yml
kubectl apply -f k8s/backend/db/postgres-statefulset.yml
kubectl apply -f k8s/backend/db/postgres-service.yml

# Wait for postgres to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n argus-agent-prod --timeout=120s
```

**Verify:**
```bash
kubectl get pods -n argus-agent-prod -l app=postgres
kubectl get pvc -n argus-agent-prod
```

### Step 3: Deploy RBAC

```bash
# ServiceAccount and Role
kubectl apply -f k8s/backend/agent/rbac-rolebinding.yml

# ClusterRole for cross-namespace access
kubectl apply -f k8s/rbac/cluster-role-threadlyai.yml
```

**Verify:**
```bash
kubectl get serviceaccount -n argus-agent-prod
kubectl get clusterrole argus-agent-cluster-role
```

### Step 4: Deploy Agent Configuration

```bash
# ConfigMap (non-sensitive config)
kubectl apply -f k8s/backend/agent/configMapRef.yml

# Secrets (sensitive config)
kubectl apply -f k8s/backend/agent/secrets.yml
```

**Verify:**
```bash
kubectl get configmap -n argus-agent-prod
kubectl get secret -n argus-agent-prod
```

### Step 5: Deploy Agent

```bash
# Deployment
kubectl apply -f k8s/backend/agent/deployment.yml

# Service
kubectl apply -f k8s/backend/agent/service.yml

# HPA (optional)
kubectl apply -f k8s/backend/agent/hpa.yml
```

**Wait for deployment:**
```bash
kubectl rollout status deployment/argus-agent-deployment -n argus-agent-prod --timeout=120s
```

### One-Command Deploy (All at Once)

```bash
# Deploy everything
kubectl apply -f k8s/namespace/ && \
kubectl apply -f k8s/backend/db/ && \
kubectl apply -f k8s/rbac/ && \
kubectl apply -f k8s/backend/agent/
```

---

## Verify Deployment

### Check All Resources

```bash
# All pods
kubectl get pods -n argus-agent-prod

# Expected output:
# NAME                                      READY   STATUS    RESTARTS   AGE
# argus-agent-deployment-xxx-xxx            1/1     Running   0          1m
# postgres-0                                1/1     Running   0          2m
```

### Check Pod Details

```bash
# Describe pod
kubectl describe pod -l app=argus-agent -n argus-agent-prod

# Check logs
kubectl logs -l app=argus-agent -n argus-agent-prod --tail=100
```

### Check Services

```bash
kubectl get svc -n argus-agent-prod

# Expected:
# NAME                   TYPE        CLUSTER-IP      PORT(S)
# argus-agent-service    ClusterIP   10.96.xxx.xxx   8000/TCP
# postgres-service       ClusterIP   10.96.xxx.xxx   5432/TCP
```

### Test Health Endpoint

```bash
# Port forward to test locally
kubectl port-forward svc/argus-agent-service 8000:8000 -n argus-agent-prod

# In another terminal
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/agent/health
```

### Check HPA

```bash
kubectl get hpa -n argus-agent-prod
```

---

## Monitoring Setup

### Option 1: Helm (Recommended)

```bash
# Add Prometheus repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install with custom values
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  -f k8s/monitoring/values.yaml

# Apply custom alert rules
kubectl apply -f k8s/monitoring/alert-rules.yaml
```

### Option 2: Without Helm

```bash
kubectl apply -f k8s/monitoring/
```

### Verify Monitoring

```bash
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

### Access Prometheus UI (Optional)

```bash
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n monitoring

# Open: http://localhost:9090
```

---

## Testing the Agent

### Test 1: Health Check

```bash
kubectl port-forward svc/argus-agent-service 8000:8000 -n argus-agent-prod

curl http://localhost:8000/health
curl http://localhost:8000/api/v1/agent/health
```

### Test 2: Create Test Incident

```bash
curl -X POST http://localhost:8000/api/v1/agent/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "alert": {
      "alertname": "TestAlert",
      "service": "test-service",
      "namespace": "default",
      "severity": "high"
    },
    "severity": "high",
    "async_processing": true
  }'
```

### Test 3: Check Incident Status

```bash
curl http://localhost:8000/api/v1/agent/incidents/{incident_id}
```

### Test 4: Test AlertManager Webhook

```bash
curl -X POST http://localhost:8000/api/v1/agent/incidents/alertmanager \
  -H "Content-Type: application/json" \
  -d '{
    "version": "4",
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "HighMemory",
        "service": "backend",
        "namespace": "ThreadlyAI",
        "severity": "critical"
      },
      "annotations": {
        "description": "Memory usage above 90%"
      }
    }]
  }'
```

---

## Useful Commands

### View Logs

```bash
# Agent logs
kubectl logs -f deployment/argus-agent-deployment -n argus-agent-prod

# Postgres logs
kubectl logs -f statefulset/postgres -n argus-agent-prod
```

### Restart Deployment

```bash
kubectl rollout restart deployment/argus-agent-deployment -n argus-agent-prod
```

### Scale Deployment

```bash
kubectl scale deployment/argus-agent-deployment --replicas=3 -n argus-agent-prod
```

### Delete Everything

```bash
# Delete agent
kubectl delete -f k8s/backend/agent/

# Delete database
kubectl delete -f k8s/backend/db/

# Delete namespace (removes everything in it)
kubectl delete namespace argus-agent-prod
```

---

## Troubleshooting

### Pod Stuck in Pending

```bash
kubectl describe pod <pod-name> -n argus-agent-prod
# Check Events section for errors
```

**Common causes:**
- Not enough resources (increase Docker Desktop resources)
- PVC not bound (check storage class)

### Pod CrashLoopBackOff

```bash
kubectl logs <pod-name> -n argus-agent-prod --previous
```

**Common causes:**
- Missing environment variables
- Database connection failed
- Syntax error in code

### ImagePullBackOff

```bash
kubectl describe pod <pod-name> -n argus-agent-prod
```

**Fix:**
- Ensure image is built: `docker images | grep argus-agent`
- Check image name in deployment matches

### Cannot Connect to Database

```bash
# Check postgres is running
kubectl get pods -n argus-agent-prod -l app=postgres

# Check postgres logs
kubectl logs statefulset/postgres -n argus-agent-prod

# Test connection from agent pod
kubectl exec -it deployment/argus-agent-deployment -n argus-agent-prod -- \
  python -c "import asyncpg; print('OK')"
```
