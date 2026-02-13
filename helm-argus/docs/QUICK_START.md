# Argus DevOps Agent - Quick Start Guide

## 🎯 **What This Does**

Deploys Argus DevOps Agent to monitor and automatically remediate incidents in your Kubernetes applications running on Minikube or any Kubernetes cluster.

## 📦 **What Gets Deployed**

```
dev-argus namespace:
├── Argus Agent (2 replicas) - FastAPI app with LangGraph
├── PostgreSQL (StatefulSet) - Stores incident state
└── Redis (Deployment) - Caching

Monitoring namespace (separate install):
├── Prometheus - Metrics collection
├── AlertManager - Alert routing
├── Grafana - Dashboards
└── Loki - Log aggregation
```

## ⚡ **Quick Setup (5 Steps)**

### **1. Start Minikube**
```bash
minikube start --cpus=4 --memory=8192
```

### **2. Install Monitoring Stack**
```bash
# Install Prometheus + Grafana + AlertManager
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace
```

### **3. Set Your Secrets**
```bash
export OPENAI_API_KEY="sk-..."
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_SIGNING_SECRET="..."
export DB_PASSWORD="your-db-password"
```

### **4. Install Argus**
```bash
cd helm-argus

helm install argus . \
  --namespace dev-argus \
  --create-namespace \
  --values values-argus.yaml \
  --set argus.secrets.openaiApiKey="$OPENAI_API_KEY" \
  --set argus.secrets.slackBotToken="$SLACK_BOT_TOKEN" \
  --set argus.secrets.slackSigningSecret="$SLACK_SIGNING_SECRET" \
  --set argus.secrets.databasePassword="$DB_PASSWORD"
```

### **5. Verify Installation**
```bash
# Check pods are running
kubectl get pods -n dev-argus

# Expected:
# argus-agent-xxx        1/1  Running
# argus-postgresql-0     1/1  Running
# argus-redis-xxx        1/1  Running

# Check RBAC
kubectl get clusterrole | grep argus
# Should see: argus-cluster-role

# Check logs
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent -f
```

## 🎯 **Deploy Sample App to Monitor**

```bash
# Create test namespace
kubectl create namespace test-app

# Deploy nginx
kubectl create deployment nginx --image=nginx:latest --replicas=3 -n test-app
kubectl expose deployment nginx --port=80 --type=ClusterIP -n test-app

# Verify
kubectl get pods -n test-app
```

## 📊 **Configure AlertManager to Send Alerts to Argus**

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
      receiver: 'argus-webhook'

    receivers:
    - name: 'argus-webhook'
      webhook_configs:
      - url: 'http://argus-agent-service.dev-argus.svc.cluster.local:8000/api/v1/incidents/alertmanager'
        send_resolved: true
```

```bash
kubectl apply -f alertmanager-config.yaml
kubectl rollout restart statefulset alertmanager-prometheus-kube-prometheus-alertmanager -n monitoring
```

## ✅ **Test the Workflow**

### **Test 1: Create Manual Incident**
```bash
# Port-forward Argus service
kubectl port-forward -n dev-argus svc/argus-agent-service 8000:8000

# In another terminal, send test alert
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "TestHighErrorRate",
    "severity": "critical",
    "namespace": "test-app",
    "service": "nginx",
    "description": "Test incident"
  }'

# Check Slack for approval message
# Click "Approve" button
# Watch Argus execute actions
```

### **Test 2: Verify RBAC Works**
```bash
# Test if Argus can read pods in other namespaces
kubectl auth can-i get pods --all-namespaces \
  --as=system:serviceaccount:dev-argus:argus-agent-sa

# Should return: yes

# Test if Argus can restart deployments
kubectl auth can-i patch deployments -n test-app \
  --as=system:serviceaccount:dev-argus:argus-agent-sa

# Should return: yes
```

## 🔧 **How Argus Monitors Your App**

```
Your App (test-app)
  ├─► Metrics → Prometheus
  │              ├─► Alert fires
  │              └─► AlertManager
  │                     └─► Webhook → Argus
  │
  └─► Argus Workflow:
      1. Receive Alert
      2. Monitor: Fetch metrics, logs, pod status, events
      3. Analyze: Identify root cause (GPT-4o)
      4. Approval: Send Slack message with buttons
      5. Execute: Restart/scale/rollback based on approval
      6. Summary: Post to Slack + create Jira ticket
```

## 🔑 **RBAC Explained**

### **What Argus Can Do**

**Read (Monitoring):**
- ✅ List/watch pods, deployments, events across ALL namespaces
- ✅ Read pod logs
- ✅ Read ConfigMaps, Services
- ✅ Read node status

**Write (Execution):**
- ✅ Restart deployments (`kubectl rollout restart`)
- ✅ Scale deployments (`kubectl scale`)
- ✅ Delete pods (`kubectl delete pod`)
- ✅ Rollback deployments (`kubectl rollout undo`)
- ❌ Delete namespaces (NO permission)
- ❌ Create/delete cluster resources (NO permission)

### **Why ClusterRole?**

Argus uses **ClusterRole** (not Role) because:
- Must monitor applications in **multiple namespaces**
- Must access cluster-wide resources (nodes, events)
- Role is limited to single namespace, ClusterRole works everywhere

## 📁 **File Structure**

```
helm-argus/
├── Chart.yaml                              # Helm chart metadata
├── values-argus.yaml                       # Configuration values
├── IMPLEMENTATION_GUIDE.md                 # Detailed guide (YOU ARE HERE)
├── QUICK_START.md                          # Quick setup (THIS FILE)
│
├── templates/
│   ├── _helpers.tpl                        # Template helpers
│   │
│   ├── rbac/
│   │   ├── serviceaccount.yaml             # ServiceAccount for Argus
│   │   ├── clusterrole.yaml                # ClusterRole with permissions
│   │   └── clusterrolebinding.yaml         # Binds SA to ClusterRole
│   │
│   ├── deployments/
│   │   └── agent-deployment.yml            # Argus agent deployment
│   │
│   ├── secrets/
│   │   └── agent-secrets.yaml              # Secrets template
│   │
│   ├── services/
│   │   └── agent-service.yml               # Argus service
│   │
│   └── statefulset/
│       └── db-statefulset.yml              # PostgreSQL StatefulSet
```

## 🐛 **Troubleshooting**

### **Pods not starting?**
```bash
kubectl describe pod -n dev-argus -l app.kubernetes.io/component=agent
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent
```

### **RBAC errors?**
```bash
# Verify ClusterRoleBinding exists
kubectl get clusterrolebinding | grep argus

# Check permissions
kubectl auth can-i get pods --all-namespaces --as=system:serviceaccount:dev-argus:argus-agent-sa
```

### **Alerts not reaching Argus?**
```bash
# Check AlertManager config
kubectl get secret alertmanager-prometheus-kube-prometheus-alertmanager -n monitoring -o yaml

# Check Argus service
kubectl get svc -n dev-argus

# Check logs
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent -f
```

## 📚 **Next Steps**

1. **Read IMPLEMENTATION_GUIDE.md** for detailed explanations
2. **Configure AlertManager** to send real alerts
3. **Create PrometheusRules** for your applications
4. **Test approval workflow** in Slack
5. **Review incident summaries** in Jira

## 🔒 **Security Notes**

- **Secrets**: Never commit secrets to git
- **RBAC**: Only necessary permissions granted
- **Slack Verification**: HMAC signature verification enabled
- **Dry Run Mode**: Test actions safely with `execution.dryRun: true`

## 📞 **Support**

Check logs for issues:
```bash
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent -f
```

Verify RBAC:
```bash
kubectl auth can-i --list --as=system:serviceaccount:dev-argus:argus-agent-sa
```

---

## 🎉 **You're All Set!**

Argus is now monitoring your applications and ready to respond to incidents automatically.

**What happens next:**
1. AlertManager sends alert to Argus
2. Argus analyzes the incident
3. You receive Slack approval request
4. Click "Approve" to let Argus fix it
5. Argus executes remediation actions
6. Summary posted to Slack + Jira ticket created

**Happy Monitoring! 🚀**
