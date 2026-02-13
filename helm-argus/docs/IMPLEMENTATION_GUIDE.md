# Argus DevOps Agent - Helm Deployment Implementation Guide

## 📋 **Table of Contents**
1. [Architecture Overview](#architecture-overview)
2. [RBAC Permissions Explained](#rbac-permissions-explained)
3. [Complete Setup Steps](#complete-setup-steps)
4. [values.yaml Configuration](#valuesyaml-configuration)
5. [Testing on Minikube](#testing-on-minikube)
6. [Monitoring Other Applications](#monitoring-other-applications)
7. [Troubleshooting](#troubleshooting)

---

## 🏗️ **Architecture Overview**

### **How Argus Monitors Other Applications**

```
┌──────────────────────────────────────────────────────────────┐
│                    Minikube Cluster                          │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Namespace: dev-argus (Argus Control Plane)            │  │
│  │                                                          │  │
│  │  ┌──────────────┐  Uses ServiceAccount: argus-agent-sa │  │
│  │  │ Argus Agent  │  ◄───────────────────────────────────┼──┤
│  │  │ (Deployment) │  With ClusterRole Permissions       │  │
│  │  └──────┬───────┘                                       │  │
│  │         │                                                │  │
│  └─────────┼────────────────────────────────────────────────┘  │
│            │                                                    │
│  ┌─────────▼──────────────────────────────────────────────┐   │
│  │  Namespace: your-app                                   │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐       │   │
│  │  │  Pod 1     │  │  Pod 2     │  │  Pod 3     │       │   │
│  │  └────────────┘  └────────────┘  └────────────┘       │   │
│  │      ▲ Monitored by Argus                             │   │
│  │      ▲ Argus can restart/scale/rollback these         │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Monitoring Stack (kube-prometheus-stack)              │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │   │
│  │  │Prometheus│  │ Grafana  │  │   Loki   │            │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘            │   │
│  │       │             │             │                    │   │
│  │       └─────────────┴─────────────┘                    │   │
│  │              ▲ Argus queries these                     │   │
│  │              ▲ AlertManager sends alerts to Argus      │   │
│  └────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### **Key Components**

1. **Argus Agent** - FastAPI application that:
   - Receives alerts from AlertManager/Grafana
   - Monitors Kubernetes resources (pods, deployments)
   - Analyzes root causes using GPT-4o
   - Requests human approval via Slack
   - Executes remediation actions
   - Creates postmortem tickets in Jira

2. **PostgreSQL** - Stores:
   - Incident state (LangGraph checkpoints)
   - Historical incident data

3. **Redis** - Caches:
   - Temporary data
   - Session information

4. **Prometheus/Grafana** - Provides:
   - Metrics for analysis
   - Alerting via AlertManager

5. **Loki** - Provides:
   - Application logs for analysis

---

## 🔐 **RBAC Permissions Explained**

### **Why ClusterRole and Not Role?**

- **Role**: Limited to a single namespace
- **ClusterRole**: Works across ALL namespaces

Argus needs **ClusterRole** because it must:
- Monitor applications in **multiple namespaces** (your-app, another-app, etc.)
- Access cluster-wide resources (nodes, events)

### **Permissions Breakdown**

#### **Read Permissions (Monitoring)**

| Resource | Verbs | Purpose |
|----------|-------|---------|
| `pods`, `pods/status` | get, list, watch | Check pod health, restart counts, status |
| `pods/log` | get, list | Fetch application logs for analysis |
| `deployments`, `deployments/status` | get, list, watch | Monitor deployment status, replica counts |
| `replicasets`, `replicasets/status` | get, list, watch | Check replicaset info |
| `events` | get, list, watch | Read K8s events (OOMKilled, CrashLoopBackOff) |
| `services` | get, list, watch | Service information |
| `configmaps` | get, list, watch | Configuration data |
| `namespaces` | get, list, watch | Namespace information |
| `nodes`, `nodes/status` | get, list, watch | Node resource utilization |

#### **Write Permissions (Execution)**

| Resource | Verbs | Purpose |
|----------|-------|---------|
| `deployments` | patch, update | Restart deployments, update images |
| `deployments/scale` | get, patch, update | Scale replicas up/down |
| `pods` | delete, deletecollection | Delete problematic pods |
| `deployments/rollback` | create | Rollback to previous version |

---

## 🚀 **Complete Setup Steps**

### **Phase 1: Prerequisites**

#### **1. Start Minikube with sufficient resources**
```bash
minikube start --cpus=4 --memory=8192 --disk-size=40g
```

#### **2. Install kube-prometheus-stack (Prometheus + Grafana + AlertManager)**
```bash
# Add Prometheus community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set grafana.adminPassword=admin
```

#### **3. (Optional) Install Loki for logs**
```bash
# Add Grafana Helm repo
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install Loki
helm install loki grafana/loki-stack \
  --namespace monitoring \
  --set grafana.enabled=false \
  --set loki.persistence.enabled=true \
  --set loki.persistence.size=10Gi
```

#### **4. (Optional) Install Qdrant for vector search**
```bash
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo update

helm install qdrant qdrant/qdrant \
  --namespace dev-argus \
  --create-namespace \
  --set service.type=ClusterIP
```

---

### **Phase 2: Configure Argus**

#### **1. Create namespace for Argus**
```bash
kubectl create namespace dev-argus
```

#### **2. Create secrets file**

Create `helm-argus/secrets.yaml` (DO NOT commit to git):
```yaml
# secrets.yaml - Store this securely, do NOT commit
openai_api_key: "sk-..." # Your OpenAI API key
slack_bot_token: "xoxb-..." # Your Slack bot token
slack_signing_secret: "..." # Your Slack signing secret
database_password: "your-db-password" # PostgreSQL password
qdrant_api_key: "" # Leave empty if Qdrant doesn't require auth

# Optional: Jira credentials
jira_api_token: "" # Your Jira API token
```

#### **3. Update values.yaml**

Key configurations to update in `helm-argus/values.yaml`:

```yaml
argus:
  namespace: dev-argus

  image:
    repository: your-registry/argus-agent
    tag: latest
    pullPolicy: IfNotPresent

  # Slack configuration
  slack:
    defaultChannel: "#incidents" # Your Slack channel
    approvalTimeoutHours: 24

  # Jira configuration (optional)
  jira:
    enabled: true
    url: "https://yourcompany.atlassian.net"
    email: "your-email@company.com"
    projectKey: "POST"
    issueType: "Task"

  # Qdrant configuration
  qdrant:
    url: "http://qdrant:6333"
    collection: "devops_incidents"

# Monitoring configuration
monitoring:
  prometheus:
    enabled: true
    url: "http://prometheus-kube-prometheus-prometheus.monitoring:9090"

  loki:
    enabled: true
    url: "http://loki.monitoring:3100"
```

---

### **Phase 3: Deploy Argus**

#### **1. Install Argus Helm chart**
```bash
cd helm-argus

# Dry run to check for errors
helm install argus . \
  --namespace dev-argus \
  --create-namespace \
  --dry-run --debug

# Install for real
helm install argus . \
  --namespace dev-argus \
  --create-namespace \
  --set-file argus.secrets.openaiApiKey=<(echo -n "$OPENAI_API_KEY") \
  --set-file argus.secrets.slackBotToken=<(echo -n "$SLACK_BOT_TOKEN") \
  --set-file argus.secrets.slackSigningSecret=<(echo -n "$SLACK_SIGNING_SECRET")
```

#### **2. Verify installation**
```bash
# Check pods
kubectl get pods -n dev-argus

# Expected output:
# NAME                           READY   STATUS    RESTARTS   AGE
# argus-agent-xxx                1/1     Running   0          2m
# argus-postgresql-0             1/1     Running   0          2m
# argus-redis-xxx                1/1     Running   0          2m

# Check RBAC
kubectl get clusterrole | grep argus
kubectl get clusterrolebinding | grep argus
kubectl get serviceaccount -n dev-argus

# Check logs
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent -f
```

#### **3. Verify RBAC permissions**
```bash
# Test if Argus can read pods in other namespaces
kubectl auth can-i get pods --all-namespaces \
  --as=system:serviceaccount:dev-argus:argus-sa

# Should return: yes

# Test if Argus can restart deployments
kubectl auth can-i patch deployments --all-namespaces \
  --as=system:serviceaccount:dev-argus:argus-sa

# Should return: yes
```

---

### **Phase 4: Deploy Sample Application to Monitor**

#### **1. Deploy a test application**
```bash
# Create test namespace
kubectl create namespace test-app

# Deploy nginx test app
kubectl create deployment nginx --image=nginx:latest --replicas=3 -n test-app
kubectl expose deployment nginx --port=80 --type=ClusterIP -n test-app

# Verify deployment
kubectl get pods -n test-app
```

#### **2. Create ServiceMonitor for Prometheus (so Prometheus scrapes your app)**
```yaml
# test-app-servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: test-app-monitor
  namespace: test-app
  labels:
    app: nginx
spec:
  selector:
    matchLabels:
      app: nginx
  endpoints:
  - port: http
    interval: 30s
```

```bash
kubectl apply -f test-app-servicemonitor.yaml
```

#### **3. Create PrometheusRule to generate alerts**
```yaml
# test-app-alert.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: test-app-alerts
  namespace: monitoring
  labels:
    prometheus: kube-prometheus
spec:
  groups:
  - name: test-app
    interval: 30s
    rules:
    - alert: TestAppHighErrorRate
      expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
      for: 1m
      labels:
        severity: critical
        namespace: test-app
        service: nginx
      annotations:
        summary: "High error rate detected in test-app"
        description: "Error rate is {{ $value }} errors/sec"
```

```bash
kubectl apply -f test-app-alert.yaml
```

---

### **Phase 5: Configure AlertManager to Send Alerts to Argus**

#### **1. Get Argus service URL**
```bash
kubectl get svc -n dev-argus

# Get the ClusterIP
ARGUS_URL="http://argus-agent-service.dev-argus.svc.cluster.local:8000"
```

#### **2. Update AlertManager configuration**
```yaml
# alertmanager-config.yaml
apiVersion: v1
kind: Secret
metadata:
  name: alertmanager-prometheus-kube-prometheus-alertmanager
  namespace: monitoring
type: Opaque
stringData:
  alertmanager.yaml: |
    global:
      resolve_timeout: 5m

    route:
      group_by: ['alertname', 'namespace']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
      receiver: 'argus-webhook'

    receivers:
    - name: 'argus-webhook'
      webhook_configs:
      - url: 'http://argus-agent-service.dev-argus.svc.cluster.local:8000/api/v1/incidents/alertmanager'
        send_resolved: true
```

```bash
kubectl apply -f alertmanager-config.yaml

# Restart AlertManager to pick up new config
kubectl rollout restart statefulset alertmanager-prometheus-kube-prometheus-alertmanager -n monitoring
```

---

## 📊 **Monitoring Flow**

### **How Argus Monitors Your Application**

```
1. Your Application (test-app namespace)
   └─► Metrics exported → Prometheus scrapes them
       └─► PrometheusRule evaluates metrics
           └─► Alert fires when condition met
               └─► AlertManager sends webhook → Argus (/api/v1/incidents/alertmanager)
                   └─► Argus Orchestrator starts:
                       ├─► Monitor: Fetch metrics, logs, pod status, events
                       ├─► Analyzer: Identify root cause (GPT-4o + vector search)
                       ├─► Approval: Send Slack message with buttons
                       │   └─► User clicks "Approve"
                       ├─► Executor: Execute actions (restart, scale, rollback)
                       └─► Summary: Post summary to Slack + create Jira ticket
```

### **What Argus Can Do to Your Application**

| Action | Command | Risk Level | Approval Required? |
|--------|---------|------------|-------------------|
| Restart deployment | `kubectl rollout restart` | Low | No (auto-approved) |
| Scale replicas up | `kubectl scale --replicas=N` | Low | No |
| Scale replicas down | `kubectl scale --replicas=N` | Medium | Yes |
| Delete pods | `kubectl delete pod` | Medium | Yes |
| Update image | `kubectl set image` | High | Yes |
| Rollback deployment | `kubectl rollout undo` | High | Yes |

---

## 🧪 **Testing on Minikube**

### **Test 1: Manual Incident Creation**

```bash
# Create a manual incident to test the full workflow
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "TestAppHighErrorRate",
    "severity": "critical",
    "namespace": "test-app",
    "service": "nginx",
    "description": "High error rate detected",
    "labels": {
      "alertname": "TestAppHighErrorRate",
      "namespace": "test-app",
      "service": "nginx"
    }
  }'
```

### **Test 2: Simulate Application Failure**

```bash
# Crash a pod to trigger OOMKilled
kubectl run memory-hog --image=polinux/stress --namespace=test-app -- stress --vm 1 --vm-bytes 512M

# Watch Argus detect and respond
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent -f
```

### **Test 3: Verify RBAC Permissions**

```bash
# Create a test pod using Argus service account
kubectl run test-rbac --image=bitnami/kubectl:latest \
  --namespace=dev-argus \
  --serviceaccount=argus-sa \
  --command -- sleep infinity

# Exec into the pod
kubectl exec -it test-rbac -n dev-argus -- /bin/bash

# Inside the pod, test permissions
kubectl get pods --all-namespaces  # Should work
kubectl get deployments -n test-app  # Should work
kubectl patch deployment nginx -n test-app -p '{"spec":{"replicas":5}}'  # Should work
kubectl delete namespace test-app  # Should FAIL (no permission)
```

---

## 🐛 **Troubleshooting**

### **Problem 1: Argus can't access other namespaces**

**Symptoms:**
```
Error: Forbidden: pods is forbidden: User "system:serviceaccount:dev-argus:argus-sa" cannot list resource "pods" in API group ""
```

**Solution:**
```bash
# Verify ClusterRoleBinding exists
kubectl get clusterrolebinding | grep argus

# If missing, check that RBAC is enabled in values.yaml
helm upgrade argus . --namespace dev-argus --set rbac.create=true

# Manually verify permissions
kubectl auth can-i get pods --all-namespaces --as=system:serviceaccount:dev-argus:argus-sa
```

---

### **Problem 2: Prometheus not reachable**

**Symptoms:**
```
Error: Connection refused when fetching metrics
```

**Solution:**
```bash
# Check Prometheus service
kubectl get svc -n monitoring

# Port-forward to test locally
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Verify URL in values.yaml matches
helm get values argus -n dev-argus | grep prometheus
```

---

### **Problem 3: Slack approval not working**

**Symptoms:**
- No Slack message sent
- Buttons don't work

**Solution:**
```bash
# Check Slack token is valid
kubectl get secret argus-agent-secrets -n dev-argus -o jsonpath='{.data.slack-bot-token}' | base64 -d

# Verify webhook URL is accessible FROM SLACK
# Expose Argus temporarily for testing
kubectl port-forward -n dev-argus svc/argus-agent-service 8000:8000

# Use ngrok to expose to internet
ngrok http 8000

# Update Slack app webhook URL to ngrok URL
```

---

## 📝 **Next Steps**

1. **Build Docker image** for your Argus agent:
   ```bash
   docker build -t your-registry/argus-agent:latest ./backend
   docker push your-registry/argus-agent:latest
   ```

2. **Update values.yaml** with your image repository

3. **Deploy Argus** using Helm

4. **Configure AlertManager** to send alerts to Argus

5. **Test with sample application**

6. **Monitor Slack** for approval requests

7. **Review incident summaries** in Slack and Jira

---

## 🔒 **Security Considerations**

1. **Secrets Management**: Store secrets in Kubernetes Secrets, not in values.yaml
2. **RBAC Least Privilege**: Only grant necessary permissions
3. **Network Policies**: Restrict network access to Argus
4. **Slack Webhook Verification**: Always verify HMAC signatures
5. **Dry Run Mode**: Test actions in dry-run mode first
6. **Audit Logs**: Enable Kubernetes audit logging

---

## 📚 **Additional Resources**

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Prometheus Alerting](https://prometheus.io/docs/alerting/latest/overview/)
- [Slack Block Kit](https://api.slack.com/block-kit)
- [Jira REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)

---

## 📧 **Support**

For issues and questions, check the logs:
```bash
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent -f
```