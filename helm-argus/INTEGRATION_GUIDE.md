# Argus Integration Guide - Monitoring Other Applications

> **Goal:** Connect Argus to your existing applications so it can monitor and fix them automatically

---

## 📊 **The Big Picture - How It All Connects**

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: Your Application Exports Metrics                            │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ Your App (e.g., web-app namespace)                             │  │
│ │ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │  │
│ │ │   Pod 1      │  │   Pod 2      │  │   Pod 3      │          │  │
│ │ │   :9090/     │  │   :9090/     │  │   :9090/     │          │  │
│ │ │   metrics    │  │   metrics    │  │   metrics    │          │  │
│ │ └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │  │
│ │        │                  │                  │                   │  │
│ │        └──────────────────┴──────────────────┘                   │  │
│ │                           │                                       │  │
│ │                    Metrics endpoint                              │  │
│ │                    (CPU, memory, HTTP requests, errors)          │  │
│ └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 2: Prometheus Scrapes Metrics Every 30s                        │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ Prometheus (monitoring namespace)                              │  │
│ │ ┌──────────────────────────────────────────────────────────┐   │  │
│ │ │ ServiceMonitor (tells Prometheus what to scrape)         │   │  │
│ │ │ apiVersion: monitoring.coreos.com/v1                     │   │  │
│ │ │ kind: ServiceMonitor                                     │   │  │
│ │ │ spec:                                                    │   │  │
│ │ │   selector:                                              │   │  │
│ │ │     matchLabels:                                         │   │  │
│ │ │       app: web-app                                       │   │  │
│ │ │   endpoints:                                             │   │  │
│ │ │   - port: metrics                                        │   │  │
│ │ │     interval: 30s                                        │   │  │
│ │ └──────────────────────────────────────────────────────────┘   │  │
│ │                                                                  │  │
│ │ Prometheus stores: cpu_usage, memory_usage, error_rate, etc.   │  │
│ └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 3: PrometheusRule Defines Alert Conditions                     │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ PrometheusRule (monitoring namespace)                          │  │
│ │ apiVersion: monitoring.coreos.com/v1                           │  │
│ │ kind: PrometheusRule                                           │  │
│ │ spec:                                                          │  │
│ │   groups:                                                      │  │
│ │   - name: web-app-alerts                                       │  │
│ │     rules:                                                     │  │
│ │     - alert: HighErrorRate                                     │  │
│ │       expr: rate(http_errors[5m]) > 0.05   ← Alert condition  │  │
│ │       for: 2m                               ← Must last 2 min  │  │
│ │       labels:                                                  │  │
│ │         severity: critical                                     │  │
│ │         namespace: web-app                                     │  │
│ │       annotations:                                             │  │
│ │         summary: "High error rate detected"                    │  │
│ └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
                        Alert fires! 🚨
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 4: AlertManager Sends Webhook to Argus                         │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ AlertManager Configuration                                     │  │
│ │ route:                                                         │  │
│ │   receiver: argus-webhook                                      │  │
│ │ receivers:                                                     │  │
│ │ - name: argus-webhook                                          │  │
│ │   webhook_configs:                                             │  │
│ │   - url: http://argus-agent.dev-argus:8000/api/v1/incidents/  │  │
│ │           alertmanager                                         │  │
│ │     send_resolved: true                                        │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│ POST /api/v1/incidents/alertmanager                                 │
│ {                                                                    │
│   "alerts": [{                                                       │
│     "labels": {                                                      │
│       "alertname": "HighErrorRate",                                 │
│       "namespace": "web-app",                                        │
│       "severity": "critical"                                         │
│     },                                                               │
│     "annotations": {                                                 │
│       "summary": "High error rate detected"                          │
│     }                                                                │
│   }]                                                                 │
│ }                                                                    │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 5: Argus Processes the Alert                                   │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ Argus Agent (dev-argus namespace)                              │  │
│ │                                                                  │  │
│ │ 1. Receive alert                                                │  │
│ │ 2. Use RBAC permissions to:                                     │  │
│ │    - kubectl get pods -n web-app    ← Read pod status          │  │
│ │    - kubectl logs -n web-app pod-1  ← Read logs                │  │
│ │    - kubectl get events -n web-app  ← Read K8s events          │  │
│ │                                                                  │  │
│ │ 3. Query Prometheus for metrics history                         │  │
│ │ 4. Query Loki for application logs                              │  │
│ │                                                                  │  │
│ │ 5. Analyze with GPT-4o:                                         │  │
│ │    "High error rate because pod 2 is OOMKilled"                 │  │
│ │                                                                  │  │
│ │ 6. Recommend action:                                             │  │
│ │    "Restart deployment/web-app"                                 │  │
│ └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 6: Slack Approval                                               │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ Slack Message                                                   │  │
│ │ ┌────────────────────────────────────────────────────────────┐ │  │
│ │ │ 🚨 Incident: HighErrorRate in web-app                      │ │  │
│ │ │                                                              │ │  │
│ │ │ Root Cause: Pod OOMKilled                                   │ │  │
│ │ │ Recommended Action: Restart deployment                      │ │  │
│ │ │                                                              │ │  │
│ │ │ [ Approve ] [ Reject ] [ Modify ]                           │ │  │
│ │ └────────────────────────────────────────────────────────────┘ │  │
│ │                                                                  │  │
│ │ User clicks "Approve" ✅                                         │  │
│ └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 7: Argus Executes Action (Uses RBAC)                           │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ Argus executes:                                                 │  │
│ │ kubectl rollout restart deployment/web-app -n web-app          │  │
│ │                                                                  │  │
│ │ RBAC Check:                                                     │  │
│ │ Can system:serviceaccount:dev-argus:argus-agent-sa             │  │
│ │     patch deployments in namespace web-app?                     │  │
│ │                                                                  │  │
│ │ ClusterRole: argus-cluster-role                                 │  │
│ │ - apiGroups: ["apps"]                                           │  │
│ │   resources: ["deployments"]                                    │  │
│ │   verbs: ["patch", "update"]                                    │  │
│ │                                                                  │  │
│ │ ✅ ALLOWED - Execute action                                      │  │
│ └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 8: Your App Restarts & Recovers                                │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ Kubernetes restarts pods                                        │  │
│ │ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │  │
│ │ │  Pod 1       │  │  Pod 2 (new) │  │  Pod 3       │          │  │
│ │ │  Running ✅  │  │  Running ✅  │  │  Running ✅  │          │  │
│ │ └──────────────┘  └──────────────┘  └──────────────┘          │  │
│ │                                                                  │  │
│ │ Error rate drops to normal ✅                                   │  │
│ └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 9: Argus Creates Summary                                       │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ - Post summary to Slack                                         │  │
│ │ - Create Jira postmortem ticket                                 │  │
│ │ - Store incident in PostgreSQL                                  │  │
│ │ - Create vector embedding in Qdrant (for future similar cases) │  │
│ └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ **Step-by-Step Setup for Your Application**

Let's say you have an app called **"web-app"** running in namespace **"production"**.

### **Step 1: Your App Must Export Metrics**

Your application needs to expose metrics in Prometheus format.

#### **Option A: Your App Already Has /metrics Endpoint**

If your app (FastAPI, Go, Node.js) already exports metrics:

```python
# FastAPI example
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

# Instrument your app
Instrumentator().instrument(app).expose(app)

# Now /metrics endpoint exists!
# Visit: http://your-app:8000/metrics
```

#### **Option B: Add Prometheus Client Library**

```python
# Python
pip install prometheus-client

# Node.js
npm install prom-client

# Go
go get github.com/prometheus/client_golang/prometheus
```

#### **Option C: Use Sidecar Exporter**

If you can't modify your app, use a sidecar container:

```yaml
# Add to your deployment
spec:
  template:
    spec:
      containers:
      - name: your-app
        image: your-app:latest

      - name: prometheus-exporter  # Sidecar
        image: prom/node-exporter:latest
        ports:
        - containerPort: 9100
```

---

### **Step 2: Create Service with Metrics Port**

```yaml
# web-app-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: web-app
  namespace: production
  labels:
    app: web-app
spec:
  selector:
    app: web-app
  ports:
  - name: http
    port: 80
    targetPort: 8080
  - name: metrics     # ← IMPORTANT: Metrics port
    port: 9090
    targetPort: 9090  # Your app's /metrics port
```

Apply:
```bash
kubectl apply -f web-app-service.yaml
```

---

### **Step 3: Create ServiceMonitor (Tell Prometheus to Scrape)**

```yaml
# web-app-servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: web-app-monitor
  namespace: production
  labels:
    app: web-app
    release: prometheus  # Must match your Prometheus release
spec:
  # Which service to scrape
  selector:
    matchLabels:
      app: web-app

  # Which endpoints to scrape
  endpoints:
  - port: metrics        # Port name from Service
    interval: 30s        # Scrape every 30 seconds
    path: /metrics       # Metrics endpoint path
```

Apply:
```bash
kubectl apply -f web-app-servicemonitor.yaml
```

**Verify Prometheus is scraping:**
```bash
# Port-forward Prometheus
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Open browser: http://localhost:9090
# Go to Status → Targets
# You should see: production/web-app-monitor
```

---

### **Step 4: Create PrometheusRule (Define Alerts)**

```yaml
# web-app-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: web-app-alerts
  namespace: monitoring  # PrometheusRules go in monitoring namespace
  labels:
    prometheus: kube-prometheus  # Must match your Prometheus
spec:
  groups:
  - name: web-app
    interval: 30s
    rules:

    # Alert 1: High Error Rate
    - alert: WebAppHighErrorRate
      expr: |
        rate(http_requests_total{status=~"5..", namespace="production"}[5m]) > 0.05
      for: 2m
      labels:
        severity: critical
        namespace: production
        service: web-app
      annotations:
        summary: "High 5xx error rate in web-app"
        description: "Error rate is {{ $value }} errors/sec"

    # Alert 2: High Memory Usage
    - alert: WebAppHighMemory
      expr: |
        container_memory_usage_bytes{namespace="production", pod=~"web-app.*"}
        /
        container_spec_memory_limit_bytes{namespace="production", pod=~"web-app.*"}
        > 0.9
      for: 5m
      labels:
        severity: warning
        namespace: production
        service: web-app
      annotations:
        summary: "High memory usage in web-app"
        description: "Memory usage is {{ $value | humanizePercentage }}"

    # Alert 3: Pod Restart Loop
    - alert: WebAppRestartLoop
      expr: |
        rate(kube_pod_container_status_restarts_total{namespace="production", pod=~"web-app.*"}[15m]) > 0
      for: 5m
      labels:
        severity: critical
        namespace: production
        service: web-app
      annotations:
        summary: "Web-app pod is restarting frequently"
        description: "Pod {{ $labels.pod }} has restarted {{ $value }} times"

    # Alert 4: Pod Not Ready
    - alert: WebAppPodNotReady
      expr: |
        kube_pod_status_ready{namespace="production", pod=~"web-app.*", condition="false"} == 1
      for: 10m
      labels:
        severity: warning
        namespace: production
        service: web-app
      annotations:
        summary: "Web-app pod not ready"
        description: "Pod {{ $labels.pod }} not ready for 10 minutes"
```

Apply:
```bash
kubectl apply -f web-app-alerts.yaml
```

**Verify alerts are loaded:**
```bash
# Open Prometheus UI: http://localhost:9090
# Go to Alerts
# You should see: WebAppHighErrorRate, WebAppHighMemory, etc.
```

---

### **Step 5: Configure AlertManager to Send Alerts to Argus**

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

    # Route alerts to Argus
    route:
      group_by: ['alertname', 'namespace', 'service']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
      receiver: 'argus-webhook'

      # Optional: Route critical alerts differently
      routes:
      - match:
          severity: critical
        receiver: 'argus-webhook'
        continue: false

      - match:
          severity: warning
        receiver: 'argus-webhook'
        continue: false

    # Receivers
    receivers:
    - name: 'argus-webhook'
      webhook_configs:
      - url: 'http://argus-agent.dev-argus.svc.cluster.local:8000/api/v1/incidents/alertmanager'
        send_resolved: true
        http_config:
          follow_redirects: true
```

Apply:
```bash
kubectl apply -f alertmanager-config.yaml

# Restart AlertManager to pick up config
kubectl rollout restart statefulset alertmanager-prometheus-kube-prometheus-alertmanager -n monitoring
```

---

### **Step 6: Verify RBAC Permissions**

Argus needs permissions to manage your app. Check:

```bash
# Can Argus read pods in your namespace?
kubectl auth can-i get pods -n production \
  --as=system:serviceaccount:dev-argus:argus-agent-sa
# Should return: yes

# Can Argus read logs?
kubectl auth can-i get pods/log -n production \
  --as=system:serviceaccount:dev-argus:argus-agent-sa
# Should return: yes

# Can Argus restart deployments?
kubectl auth can-i patch deployments -n production \
  --as=system:serviceaccount:dev-argus:argus-agent-sa
# Should return: yes

# Can Argus scale deployments?
kubectl auth can-i patch deployments/scale -n production \
  --as=system:serviceaccount:dev-argus:argus-agent-sa
# Should return: yes
```

If any return "no", your ClusterRole is not set up correctly.

---

### **Step 7: Test the Integration**

#### **Test 1: Manual Alert (Easiest)**

```bash
# Port-forward Argus
kubectl port-forward -n dev-argus svc/argus-agent 8000:8000

# Send test alert
curl -X POST http://localhost:8000/api/v1/incidents/alertmanager \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "TestAlert",
        "namespace": "production",
        "service": "web-app",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Test alert for integration testing",
        "description": "This is a test alert"
      },
      "startsAt": "2025-02-09T10:00:00Z"
    }]
  }'

# Check Argus logs
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent --tail=100

# Check Slack for approval message
```

#### **Test 2: Trigger Real Alert**

```bash
# Create a pod that will crash (OOMKilled)
kubectl run memory-bomb --image=polinux/stress -n production \
  --command -- stress --vm 1 --vm-bytes 2G

# Wait 2-5 minutes
# Alert should fire → Argus receives it → Slack message appears
```

#### **Test 3: Check Alert Flow**

```bash
# Check Prometheus has your app's metrics
# Open: http://localhost:9090
# Query: http_requests_total{namespace="production"}
# Should show data

# Check AlertManager
# Open: http://localhost:9093
# Should show active alerts if any fired

# Check Argus received alert
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent | grep "Received alert"
```

---

## 🔧 **Troubleshooting**

### **Problem: Prometheus not scraping my app**

**Check:**
```bash
# 1. Does ServiceMonitor exist?
kubectl get servicemonitor -n production

# 2. Does it match your service labels?
kubectl get svc web-app -n production -o yaml | grep -A 5 "labels:"

# 3. Is Prometheus configured to watch your namespace?
kubectl get prometheus -n monitoring -o yaml | grep -A 10 "serviceMonitorSelector"

# 4. Check Prometheus targets
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Visit: http://localhost:9090/targets
```

**Fix:**
```yaml
# If ServiceMonitor not discovered, update Prometheus config
kubectl edit prometheus prometheus-kube-prometheus-prometheus -n monitoring

# Change:
serviceMonitorSelector: {}  # ← This means "select all"

# Or add label selector:
serviceMonitorSelector:
  matchLabels:
    release: prometheus
```

---

### **Problem: Alerts not firing**

**Check:**
```bash
# 1. Is PrometheusRule loaded?
kubectl get prometheusrule -n monitoring

# 2. Check alert syntax
kubectl describe prometheusrule web-app-alerts -n monitoring

# 3. Check Prometheus UI
# Visit: http://localhost:9090/alerts
# Look for your alert, check if it's "Pending" or "Firing"
```

---

### **Problem: AlertManager not sending to Argus**

**Check:**
```bash
# 1. Is AlertManager config correct?
kubectl get secret alertmanager-prometheus-kube-prometheus-alertmanager -n monitoring -o yaml

# 2. Can AlertManager reach Argus?
kubectl run test-curl --image=curlimages/curl -it --rm -n monitoring -- \
  curl -v http://argus-agent.dev-argus.svc.cluster.local:8000/health

# 3. Check AlertManager logs
kubectl logs -n monitoring alertmanager-prometheus-kube-prometheus-alertmanager-0
```

---

## 📋 **Quick Setup Checklist**

For each application you want Argus to monitor:

- [ ] 1. App exports `/metrics` endpoint
- [ ] 2. Service has `metrics` port defined
- [ ] 3. ServiceMonitor created
- [ ] 4. Prometheus scraping (check targets)
- [ ] 5. PrometheusRule created with alerts
- [ ] 6. Alerts visible in Prometheus UI
- [ ] 7. AlertManager configured with Argus webhook
- [ ] 8. RBAC permissions verified
- [ ] 9. Test alert sent successfully
- [ ] 10. Slack approval received

---

## 🎓 **Summary**

**To connect an app to Argus:**

1. **Metrics**: App exports `/metrics`
2. **ServiceMonitor**: Tells Prometheus to scrape
3. **PrometheusRule**: Defines when to alert
4. **AlertManager**: Sends alerts to Argus webhook
5. **RBAC**: Argus has permissions to manage app
6. **Slack**: Receive approval requests
7. **Jira**: Get postmortem tickets

**Argus does NOT need:**
- Code changes in your app (just metrics endpoint)
- Direct connection to your app (goes through Prometheus)
- To be in the same namespace as your app
- Special network configuration (uses Kubernetes DNS)

---

## 📚 **Example Files Repository**

All example YAMLs are in: `helm-argus/examples/`

```
helm-argus/examples/
├── sample-app/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── servicemonitor.yaml
│   └── prometheusrule.yaml
└── README.md
```

Would you like me to create these example files? 🎯