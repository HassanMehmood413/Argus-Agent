# Argus Helm Chart - Clean File Structure

## ✅ **Cleaned Template Structure**

After cleanup, here's the final, production-ready structure:

```
helm-argus/
├── Chart.yaml                              # Helm chart metadata
├── values.yaml                             # Default values (original)
├── values-argus.yaml                       # Complete Argus configuration (USE THIS)
│
├── 📚 Documentation
├── QUICK_START.md                          # 5-step quick setup
├── IMPLEMENTATION_GUIDE.md                 # Detailed implementation guide
├── ARCHITECTURE.md                         # Architecture & RBAC deep dive
├── DEPLOYMENT_ARCHITECTURE.md              # Same cluster vs separate cluster
└── FILE_STRUCTURE.md                       # This file
│
└── templates/                              # Kubernetes manifests
    │
    ├── _helpers.tpl                        # Template helper functions
    ├── NOTES.txt                           # Post-install notes
    │
    ├── 🔐 RBAC (Cluster-wide permissions)
    ├── rbac/
    │   ├── serviceaccount.yaml             # ServiceAccount: argus-agent-sa
    │   ├── clusterrole.yaml                # ClusterRole: monitor + execute
    │   └── clusterrolebinding.yaml         # Binds SA to ClusterRole
    │
    ├── 🚀 Argus Agent (Main application)
    ├── deployment.yaml                     # Argus agent deployment
    └── service.yaml                        # Argus agent service
    │
    ├── 🗄️ PostgreSQL (State storage)
    ├── postgresql-statefulset.yaml         # PostgreSQL StatefulSet
    └── postgresql-service.yaml             # PostgreSQL service
    │
    ├── 💾 Redis (Caching)
    ├── redis-deployment.yaml               # Redis deployment
    ├── redis-service.yaml                  # Redis service
    └── redis-pvc.yaml                      # Redis persistent storage
    │
    ├── 🔒 Secrets
    └── secrets/
        └── agent-secrets.yaml              # All secrets template
    │
    └── 📊 Autoscaling (Optional)
        └── hpa.yaml                        # Horizontal Pod Autoscaler
```

---

## 🗑️ **Files Deleted (Cleanup)**

### **Removed:**
- ❌ `rbac/junior-role.yml` (empty test file)
- ❌ `rbac/senior-role.yml` (empty test file)
- ❌ `rbac/cluster-role-otherapp.yml` (empty, not needed)
- ❌ `rbac/rolebinding.yml` (using ClusterRoleBinding instead)
- ❌ `configmaps/db-ConfigMapRef.yml` (old approach)
- ❌ `secrets/db-Secrets.yml` (consolidated into agent-secrets.yaml)
- ❌ `secrets/redis-Secrets.yml` (consolidated into agent-secrets.yaml)
- ❌ `deployments/agent-deployment-new.yml` (temporary file)
- ❌ `services/agent-service.yml` (empty, recreated)
- ❌ `services/db-service.yml` (empty, recreated)
- ❌ `services/redis-service.yml` (empty, recreated)
- ❌ `statefulset/db-statefulset.yml` (empty, recreated)
- ❌ `hpa/agent-hpa.yml` (empty, recreated)
- ❌ `namespace/dev-namespace.yml` (not in templates)
- ❌ `namespace/prod-namespace.yml` (not in templates)

**Total removed: 15 unnecessary/empty files**

---

## 📋 **Essential Files (What You Need)**

### **1. Core Kubernetes Resources**

#### **deployment.yaml** (Argus Agent)
- FastAPI application with LangGraph
- 2 replicas for HA
- ServiceAccount: `argus-agent-sa`
- All environment variables configured
- Health probes configured
- Resource limits set

#### **service.yaml** (Argus Service)
- ClusterIP service
- Port 8000 (HTTP)
- Receives webhooks from AlertManager/Grafana/Slack

### **2. RBAC Configuration**

#### **rbac/serviceaccount.yaml**
- Creates ServiceAccount: `argus-agent-sa`
- Auto-mounts Kubernetes API token
- Used by Argus pods

#### **rbac/clusterrole.yaml**
- ClusterRole: `argus-cluster-role`
- **Read permissions** (monitoring):
  - pods, pods/log, pods/status
  - deployments, replicasets, events
  - services, configmaps, namespaces, nodes
- **Write permissions** (execution):
  - deployments (patch, update) - restart, image updates
  - deployments/scale (patch, update) - scaling
  - pods (delete) - remove stuck pods
  - deployments/rollback (create) - rollbacks

#### **rbac/clusterrolebinding.yaml**
- Binds `argus-agent-sa` to `argus-cluster-role`
- Grants cluster-wide permissions

### **3. Database & Caching**

#### **postgresql-statefulset.yaml**
- PostgreSQL 16 StatefulSet
- Stores incident state (LangGraph checkpoints)
- PersistentVolume for data (10Gi)
- Configurable via `values-argus.yaml`

#### **postgresql-service.yaml**
- ClusterIP service for PostgreSQL
- Port 5432
- DNS: `<release>-postgresql.<namespace>.svc.cluster.local`

#### **redis-deployment.yaml**
- Redis 7 deployment
- Caching and session storage
- Optional persistence (5Gi PVC)

#### **redis-service.yaml**
- ClusterIP service for Redis
- Port 6379
- DNS: `<release>-redis.<namespace>.svc.cluster.local`

#### **redis-pvc.yaml**
- PersistentVolumeClaim for Redis (optional)
- Only created if `redis.persistence.enabled: true`

### **4. Secrets**

#### **secrets/agent-secrets.yaml**
- Consolidated secrets template
- Contains:
  - `database-url` - PostgreSQL connection string
  - `openai-api-key` - OpenAI API key
  - `slack-bot-token` - Slack bot token
  - `slack-signing-secret` - Slack webhook verification
  - `jira-api-token` - Jira API token (optional)
  - `qdrant-api-key` - Qdrant API key (optional)
  - `database-password` - PostgreSQL password

### **5. Autoscaling (Optional)**

#### **hpa.yaml**
- Horizontal Pod Autoscaler
- Scales Argus agent based on CPU/memory
- Only created if `autoscaling.enabled: true`
- Range: 2-10 replicas (configurable)

---

## 🎯 **File Count Summary**

| Category | Count | Files |
|----------|-------|-------|
| **RBAC** | 3 | serviceaccount, clusterrole, clusterrolebinding |
| **Argus Agent** | 2 | deployment, service |
| **PostgreSQL** | 2 | statefulset, service |
| **Redis** | 3 | deployment, service, pvc |
| **Secrets** | 1 | agent-secrets |
| **Autoscaling** | 1 | hpa |
| **Helpers** | 2 | _helpers.tpl, NOTES.txt |
| **Total** | **14** | Clean, production-ready |

---

## 📝 **Configuration Files**

### **values-argus.yaml** (PRIMARY CONFIG)
Complete configuration with:
- Argus agent settings
- RBAC settings
- PostgreSQL configuration
- Redis configuration
- Monitoring integration (Prometheus, Loki)
- Slack/Jira integration
- Execution settings
- Security settings

**Use this file for deployment:**
```bash
helm install argus . --values values-argus.yaml
```

### **values.yaml** (DEFAULT)
Original Helm default values
- Generic settings
- Not specific to Argus
- **Don't use this directly**

---

## 🚀 **Quick Deploy**

### **1. Set secrets**
```bash
export OPENAI_API_KEY="sk-..."
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_SIGNING_SECRET="..."
export DB_PASSWORD="secure-password"
```

### **2. Install**
```bash
helm install argus . \
  --namespace dev-argus \
  --create-namespace \
  --values values-argus.yaml \
  --set argus.secrets.openaiApiKey="$OPENAI_API_KEY" \
  --set argus.secrets.slackBotToken="$SLACK_BOT_TOKEN" \
  --set argus.secrets.slackSigningSecret="$SLACK_SIGNING_SECRET" \
  --set argus.secrets.databasePassword="$DB_PASSWORD"
```

### **3. Verify**
```bash
kubectl get pods -n dev-argus
kubectl get clusterrole | grep argus
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent -f
```

---

## 🔍 **Template Validation**

### **Check for syntax errors**
```bash
helm lint .
```

### **Dry run (see what will be created)**
```bash
helm install argus . \
  --namespace dev-argus \
  --values values-argus.yaml \
  --dry-run --debug
```

### **Render templates locally**
```bash
helm template argus . \
  --namespace dev-argus \
  --values values-argus.yaml \
  > rendered-manifests.yaml
```

---

## 📚 **Documentation Guide**

### **Start Here:**
1. **FILE_STRUCTURE.md** (this file) - Understand file organization
2. **DEPLOYMENT_ARCHITECTURE.md** - Same cluster vs separate cluster
3. **QUICK_START.md** - 5-step quick setup

### **Deep Dive:**
4. **IMPLEMENTATION_GUIDE.md** - Complete implementation details
5. **ARCHITECTURE.md** - Architecture & RBAC explanations

---

## ✅ **What's Next?**

### **Phase 1: Build Docker Image**
```bash
cd backend
docker build -t your-registry/argus-agent:latest .
docker push your-registry/argus-agent:latest
```

### **Phase 2: Update Configuration**
Edit `values-argus.yaml`:
```yaml
argus:
  image:
    repository: your-registry/argus-agent
    tag: latest
```

### **Phase 3: Deploy**
```bash
helm install argus . --values values-argus.yaml
```

### **Phase 4: Configure Monitoring**
- Install Prometheus/Grafana
- Configure AlertManager to send alerts to Argus
- Create PrometheusRules for your applications

### **Phase 5: Test**
- Create test incident
- Verify Slack approval workflow
- Check execution actions
- Review incident summaries

---

## 🎉 **Summary**

**Your Helm chart is now:**
- ✅ Clean and organized
- ✅ Production-ready
- ✅ Properly templated
- ✅ Fully documented
- ✅ Ready to deploy

**Total files: 14 essential manifests + 2 helpers + 5 documentation files**

**No unnecessary clutter. Everything has a purpose.**

---

For deployment instructions, see: **QUICK_START.md**
For cluster placement guidance, see: **DEPLOYMENT_ARCHITECTURE.md**
