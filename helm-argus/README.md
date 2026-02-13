# Argus DevOps Agent - Complete Helm Guide for Beginners

> **📚 Learning Goal:** Understand Helm from scratch while deploying a production-ready application

---

## 📖 **Table of Contents**

1. [What is Helm? (ELI5)](#what-is-helm-eli5)
2. [Why Use Bitnami Charts?](#why-use-bitnami-charts)
3. [Helm Folder Structure Explained](#helm-folder-structure-explained)
4. [How Values Flow Through Templates](#how-values-flow-through-templates)
5. [Multiple Environments (Dev/Staging/Prod)](#multiple-environments)
6. [Step-by-Step Deployment](#step-by-step-deployment)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 **What is Helm? (ELI5)**

### **The Simple Explanation**

Imagine you want to build a LEGO house. You need:
- 🧱 Bricks (Kubernetes resources)
- 📋 Instructions (Templates)
- 🎨 Color choices (Values)
- 📦 A box to keep everything together (Chart)

**Helm is like a LEGO instruction booklet for Kubernetes.**

### **Without Helm (The Hard Way)**

```bash
# You have to create each file manually
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f secret.yaml
kubectl apply -f configmap.yaml
kubectl apply -f postgresql-deployment.yaml
kubectl apply -f redis-deployment.yaml
# ... 20 more files ...

# Want to change something? Edit each file manually!
# Want different environments? Copy all files and modify!
# Want to upgrade? Good luck remembering what to change!
```

### **With Helm (The Easy Way)**

```bash
# One command deploys everything
helm install argus .

# Change a setting? Just update values
helm upgrade argus . --set replicas=5

# Delete everything? One command
helm uninstall argus
```

---

## 🏗️ **Helm Architecture (How It Works)**

```
┌─────────────────────────────────────────────────────────────┐
│                     HELM CHART                               │
│  (Think of this as a recipe for your application)           │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  1. Chart.yaml                                       │   │
│  │     "This is Argus version 1.0.0"                    │   │
│  │     "I need PostgreSQL and Redis"                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  2. values.yaml (The Settings)                       │   │
│  │     replicas: 2          ← "I want 2 copies"        │   │
│  │     image: argus:latest  ← "Use this container"     │   │
│  │     memory: 2Gi          ← "Give me 2GB RAM"        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  3. templates/ (The Blueprints)                      │   │
│  │     deployment.yaml  ← "How to run the app"         │   │
│  │     service.yaml     ← "How to access the app"      │   │
│  │     secrets.yaml     ← "Where are passwords?"       │   │
│  └──────────────────────────────────────────────────────┘   │
│                         ↓                                     │
│              Helm combines them!                             │
│                         ↓                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Final Kubernetes YAML                               │   │
│  │  (Helm fills in the blanks from values.yaml)        │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
                         ↓
                   kubectl apply
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              KUBERNETES CLUSTER                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Argus    │  │PostgreSQL│  │  Redis   │                  │
│  │  Pod     │  │   Pod    │  │   Pod    │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 **Why Use Bitnami Charts?**

### **The Problem We're Solving**

**Scenario:** You need PostgreSQL for your application.

**Option 1: Build It Yourself (Hard)**
```yaml
# You have to create:
- StatefulSet (60 lines of YAML)
- Service (20 lines)
- ConfigMap (30 lines)
- PersistentVolumeClaim (15 lines)
- Init containers for setup (40 lines)
- Health checks (20 lines)
- Security contexts (15 lines)
- Backup scripts (100+ lines)
# Total: 300+ lines of complex YAML
# Plus: You have to maintain it, update it, fix bugs!
```

**Option 2: Use Bitnami Chart (Easy)**
```yaml
# In Chart.yaml:
dependencies:
  - name: postgresql
    version: 15.5.38
    repository: https://charts.bitnami.com/bitnami

# In values.yaml:
postgresql:
  enabled: true
  auth:
    username: myapp
    database: mydb
    password: secret

# That's it! 6 lines instead of 300+
```

### **What Bitnami Gives You**

```
┌────────────────────────────────────────────────────────────┐
│  Bitnami PostgreSQL Chart                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ✅ Production-Ready                                  │  │
│  │     - 10,000+ companies use it                       │  │
│  │     - Battle-tested in production                    │  │
│  │                                                       │  │
│  │  ✅ Security Hardened                                │  │
│  │     - Non-root user                                  │  │
│  │     - CVE patches applied                            │  │
│  │     - Security scanning done                         │  │
│  │                                                       │  │
│  │  ✅ High Availability                                │  │
│  │     - Replication built-in                           │  │
│  │     - Automatic failover                             │  │
│  │     - Backup/restore scripts                         │  │
│  │                                                       │  │
│  │  ✅ Monitoring                                       │  │
│  │     - Prometheus metrics exporter                    │  │
│  │     - Health checks configured                       │  │
│  │     - Grafana dashboards                             │  │
│  │                                                       │  │
│  │  ✅ Maintained                                       │  │
│  │     - Regular updates                                │  │
│  │     - Bug fixes                                      │  │
│  │     - Documentation                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### **How Bitnami Dependencies Work**

```
Your Argus Chart
│
├── Chart.yaml says: "I need PostgreSQL 15.5.38 from Bitnami"
│
└── When you run: helm dependency update
    │
    ├── Helm downloads postgresql-15.5.38.tgz
    │   └── Saves to: charts/ folder
    │
    └── When you run: helm install argus .
        │
        ├── Helm unpacks postgresql-15.5.38.tgz
        ├── Merges your values.yaml with PostgreSQL defaults
        ├── Creates PostgreSQL resources
        └── Creates your Argus resources

Result: PostgreSQL + Argus deployed together!
```

---

## 📁 **Helm Folder Structure Explained**

### **Our Argus Project Structure**

```
helm-argus/                          ← Root folder (the "chart")
│
├── 📄 Chart.yaml                    ← "Birth certificate" of your chart
│   └── What: Name, version, dependencies
│   └── Why: Tells Helm what this chart is
│
├── 📄 values.yaml                   ← "Settings file" (THE MOST IMPORTANT)
│   └── What: All configurable values
│   └── Why: Change behavior without editing templates
│
├── 📄 Chart.lock                    ← "Dependency lock file"
│   └── What: Exact versions of dependencies
│   └── Why: Ensures everyone uses same versions
│
├── 📄 README.md                     ← "Instruction manual"
│   └── What: This file you're reading!
│   └── Why: Explains how to use the chart
│
├── 📂 charts/                       ← "Downloaded dependencies"
│   ├── postgresql-15.5.38.tgz      ← Bitnami PostgreSQL chart
│   └── redis-20.5.0.tgz            ← Bitnami Redis chart
│   └── Why: Helm stores downloaded dependencies here
│
├── 📂 docs/                         ← "Documentation"
│   ├── QUICK_START.md              ← 5-minute setup
│   ├── ARCHITECTURE.md             ← How it all works
│   └── ...                         ← More guides
│   └── Why: Organized documentation
│
├── 📂 templates/                    ← "The Blueprints" (MOST IMPORTANT)
│   │                                   These are templates with placeholders
│   │                                   Helm fills in values from values.yaml
│   │
│   ├── 📄 _helpers.tpl             ← "Helper functions"
│   │   └── Reusable template functions
│   │
│   ├── 📄 deployment.yaml          ← "How to run Argus"
│   │   └── Defines pods, containers, resources
│   │
│   ├── 📄 service.yaml             ← "How to access Argus"
│   │   └── Exposes Argus on network
│   │
│   ├── 📄 hpa.yaml                 ← "Auto-scaling rules"
│   │   └── Scale up/down based on load
│   │
│   ├── 📂 rbac/                    ← "Permissions"
│   │   ├── serviceaccount.yaml    ← "Identity for Argus"
│   │   ├── clusterrole.yaml       ← "What Argus can do"
│   │   └── clusterrolebinding.yaml← "Grant permissions"
│   │
│   └── 📂 secrets/                 ← "Sensitive data"
│       └── agent-secrets.yaml     ← API keys, passwords
│
└── 📂 environments/                 ← "Environment-specific configs" (WE'LL CREATE THIS)
    ├── values-dev.yaml             ← Development settings
    ├── values-staging.yaml         ← Staging settings
    └── values-prod.yaml            ← Production settings
```

### **Comparison: Different Tier Architectures**

#### **3-Tier Application (Web + API + Database)**

```
helm-myapp/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── frontend/                ← Tier 1: Presentation
    │   ├── deployment.yaml
    │   └── service.yaml
    │
    ├── backend/                 ← Tier 2: Application
    │   ├── deployment.yaml
    │   └── service.yaml
    │
    └── database/                ← Tier 3: Data
        ├── statefulset.yaml
        └── service.yaml
```

#### **4-Tier Application (Add Cache Layer)**

```
helm-myapp/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── frontend/                ← Tier 1: Presentation
    ├── backend/                 ← Tier 2: Application
    ├── cache/                   ← Tier 3: Cache (Redis)
    │   ├── deployment.yaml
    │   └── service.yaml
    └── database/                ← Tier 4: Data
```

#### **Our Argus (3-Tier + Dependencies)**

```
helm-argus/
├── Chart.yaml                   ← Declares PostgreSQL & Redis dependencies
├── values.yaml
├── charts/                      ← Bitnami handles Tier 2 & 3
│   ├── postgresql-*.tgz        ← Tier 3: Database (managed by Bitnami)
│   └── redis-*.tgz             ← Tier 2: Cache (managed by Bitnami)
└── templates/
    ├── deployment.yaml          ← Tier 1: Argus Application
    ├── service.yaml
    └── rbac/                    ← Security layer
```

**Key Insight:** By using Bitnami, we don't need to create templates for PostgreSQL and Redis. Bitnami charts handle that!

---

## 🔄 **How Values Flow Through Templates**

### **The Magic of Helm Templates**

Helm templates use **Go templating** with special syntax `{{ }}` to insert values.

#### **Step 1: You Write values.yaml**

```yaml
# values.yaml
argus:
  replicaCount: 2
  image:
    repository: myregistry/argus
    tag: v1.0.0
  resources:
    memory: 2Gi
    cpu: 1000m
```

#### **Step 2: Template Uses {{ .Values.xxx }}**

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: argus-agent
spec:
  replicas: {{ .Values.argus.replicaCount }}      ← Helm fills this in
  template:
    spec:
      containers:
        - name: argus
          image: "{{ .Values.argus.image.repository }}:{{ .Values.argus.image.tag }}"
          resources:
            limits:
              memory: {{ .Values.argus.resources.memory }}
              cpu: {{ .Values.argus.resources.cpu }}
```

#### **Step 3: Helm Generates Final YAML**

```yaml
# Final output (what Kubernetes sees)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: argus-agent
spec:
  replicas: 2                              ← From values.yaml
  template:
    spec:
      containers:
        - name: argus
          image: "myregistry/argus:v1.0.0" ← From values.yaml
          resources:
            limits:
              memory: 2Gi                   ← From values.yaml
              cpu: 1000m                    ← From values.yaml
```

### **Common Template Syntax**

| Syntax | What It Does | Example |
|--------|--------------|---------|
| `{{ .Values.x }}` | Get value from values.yaml | `{{ .Values.argus.replicaCount }}` |
| `{{- if .Values.x }}` | Conditional (if) | `{{- if .Values.postgresql.enabled }}` |
| `{{ include "helper" . }}` | Call helper function | `{{ include "argus.fullname" . }}` |
| `{{- range .Values.list }}` | Loop | `{{- range .Values.envVars }}` |
| `{{ .Release.Name }}` | Get release name | `{{ .Release.Name }}-postgresql` |
| `{{ toYaml .Values.x \| nindent 4 }}` | Convert to YAML | For complex objects |

### **Values Hierarchy (Which Values Win?)**

Helm merges values from multiple sources. **Later sources override earlier ones:**

```
1. Chart's values.yaml (defaults)          ← Lowest priority
   ↓ (merged with)
2. Parent chart's values (if this is a subchart)
   ↓ (merged with)
3. values.yaml from --values flag
   ↓ (merged with)
4. Individual --set flags                  ← Highest priority
```

**Example:**

```bash
# values.yaml has:
replicas: 2

# You run:
helm install argus . --set argus.replicaCount=5

# Result: 5 replicas (--set wins over values.yaml)
```

---

## 🌍 **Multiple Environments (Dev/Staging/Prod)**

### **The Problem**

You want different settings for different environments:
- **Dev**: Small resources, no backups, quick to deploy
- **Staging**: Medium resources, test SSL, similar to prod
- **Prod**: Large resources, backups, high availability

### **Solution: Environment-Specific Values Files**

#### **Step 1: Create Environment Files**

Let's create a proper structure:

```bash
mkdir -p environments
```

Create three files:

**`environments/values-dev.yaml`** (Development)
```yaml
# Development environment
# Use this for local testing on Minikube

argus:
  namespace: dev-argus
  replicaCount: 1                    # Just 1 replica (save resources)

  image:
    repository: localhost:5000/argus  # Local registry
    tag: latest                       # Always use latest
    pullPolicy: Always

  resources:
    limits:
      cpu: 500m                       # Small CPU
      memory: 512Mi                   # Small memory
    requests:
      cpu: 250m
      memory: 256Mi

# Bitnami PostgreSQL - Development
postgresql:
  enabled: true
  auth:
    password: "dev-password"          # Simple password for dev
  primary:
    persistence:
      enabled: false                  # No persistence (faster)
    resources:
      limits:
        memory: 256Mi                 # Small DB
      requests:
        memory: 128Mi

# Bitnami Redis - Development
redis:
  enabled: true
  auth:
    enabled: false                    # No auth for dev
  master:
    persistence:
      enabled: false                  # No persistence
    resources:
      limits:
        memory: 128Mi
      requests:
        memory: 64Mi
```

**`environments/values-staging.yaml`** (Staging)
```yaml
# Staging environment
# Use this for QA testing before production

argus:
  namespace: staging-argus
  replicaCount: 2                     # 2 replicas for HA testing

  image:
    repository: myregistry/argus      # Shared registry
    tag: "1.0.0-rc1"                  # Release candidate
    pullPolicy: IfNotPresent

  resources:
    limits:
      cpu: 1000m                      # Medium CPU
      memory: 1Gi                     # Medium memory
    requests:
      cpu: 500m
      memory: 512Mi

# Bitnami PostgreSQL - Staging
postgresql:
  enabled: true
  auth:
    password: "staging-password"      # Different password
  primary:
    persistence:
      enabled: true                   # Enable persistence
      size: 5Gi                       # Smaller than prod
    resources:
      limits:
        memory: 512Mi
      requests:
        memory: 256Mi
  metrics:
    enabled: true                     # Enable monitoring

# Bitnami Redis - Staging
redis:
  enabled: true
  auth:
    enabled: true                     # Enable auth
    password: "staging-redis"
  master:
    persistence:
      enabled: true
      size: 2Gi
    resources:
      limits:
        memory: 256Mi
      requests:
        memory: 128Mi
  metrics:
    enabled: true
```

**`environments/values-prod.yaml`** (Production)
```yaml
# Production environment
# Use this for live production deployment

argus:
  namespace: argus
  replicaCount: 3                     # 3 replicas for HA

  image:
    repository: myregistry/argus
    tag: "1.0.0"                      # Stable release
    pullPolicy: IfNotPresent

  resources:
    limits:
      cpu: 2000m                      # Large CPU
      memory: 2Gi                     # Large memory
    requests:
      cpu: 1000m
      memory: 1Gi

# Bitnami PostgreSQL - Production
postgresql:
  enabled: true
  auth:
    existingSecret: "postgres-secret" # Use Kubernetes secret
  primary:
    persistence:
      enabled: true
      size: 20Gi                      # Large storage
      storageClass: "fast-ssd"        # Use fast storage
    resources:
      limits:
        memory: 2Gi
      requests:
        memory: 1Gi
  metrics:
    enabled: true
    serviceMonitor:
      enabled: true                   # Prometheus integration

  # High Availability
  replication:
    enabled: true
    replicaCount: 2                   # Standby replicas

# Bitnami Redis - Production
redis:
  enabled: true
  auth:
    enabled: true
    existingSecret: "redis-secret"    # Use Kubernetes secret

  architecture: replication           # Master-replica setup
  master:
    persistence:
      enabled: true
      size: 10Gi
      storageClass: "fast-ssd"
    resources:
      limits:
        memory: 1Gi
      requests:
        memory: 512Mi

  replica:
    replicaCount: 2                   # 2 read replicas
    persistence:
      enabled: true
      size: 10Gi

  metrics:
    enabled: true
    serviceMonitor:
      enabled: true

# Enable autoscaling in production
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

#### **Step 2: Deploy to Different Environments**

**Development:**
```bash
helm install argus . \
  --values environments/values-dev.yaml \
  --namespace dev-argus \
  --create-namespace
```

**Staging:**
```bash
helm install argus . \
  --values environments/values-staging.yaml \
  --namespace staging-argus \
  --create-namespace
```

**Production:**
```bash
# First create secrets
kubectl create secret generic postgres-secret \
  --from-literal=postgres-password=SUPER_SECRET_PASSWORD \
  --namespace argus

kubectl create secret generic redis-secret \
  --from-literal=redis-password=REDIS_SECRET_PASSWORD \
  --namespace argus

# Then deploy
helm install argus . \
  --values environments/values-prod.yaml \
  --namespace argus \
  --create-namespace
```

#### **Step 3: Override Specific Values**

You can combine environment files with --set:

```bash
# Use staging values but override image tag
helm install argus . \
  --values environments/values-staging.yaml \
  --set argus.image.tag=1.0.0-hotfix \
  --namespace staging-argus
```

---

## 🚀 **Step-by-Step Deployment (Complete Walkthrough)**

### **Prerequisites Checklist**

```bash
# 1. Check Kubernetes cluster
kubectl cluster-info
# Should show: Kubernetes control plane is running

# 2. Check Helm installation
helm version
# Should show: version.BuildInfo{Version:"v3.x.x"

# 3. Check namespace
kubectl get namespaces
# You should see: default, kube-system, etc.
```

### **Step 1: Understand What You're Deploying**

```
What we're installing:
1. Argus Agent (2 pods)          ← Our FastAPI application
2. PostgreSQL (1 pod)            ← Bitnami chart (state storage)
3. Redis (1 pod)                 ← Bitnami chart (caching)
4. RBAC resources                ← Permissions to manage other apps
5. Secrets                       ← API keys and passwords

Total: 4 pods + RBAC + secrets
```

### **Step 2: Prepare Your Environment**

```bash
# Navigate to helm chart directory
cd /path/to/helm-argus

# Check chart structure
ls -la
# You should see:
# - Chart.yaml
# - values.yaml
# - templates/
# - charts/
```

### **Step 3: Download Dependencies (Bitnami Charts)**

```bash
# This downloads PostgreSQL and Redis charts
helm dependency update

# What happens:
# 1. Helm reads Chart.yaml
# 2. Sees postgresql and redis dependencies
# 3. Downloads from https://charts.bitnami.com/bitnami
# 4. Saves to charts/ folder

# Verify
ls -lh charts/
# You should see:
# postgresql-15.5.38.tgz (75 KB)
# redis-20.5.0.tgz (103 KB)
```

**What just happened?**

```
Chart.yaml says:
  "I need postgresql version 15.5.38 from Bitnami"
  "I need redis version 20.5.0 from Bitnami"
       ↓
helm dependency update
       ↓
Downloads:
  charts/postgresql-15.5.38.tgz
  charts/redis-20.5.0.tgz
       ↓
Creates Chart.lock:
  "I locked postgresql to version 15.5.38"
  "I locked redis to version 20.5.0"
```

### **Step 4: Prepare Your Secrets**

```bash
# Set environment variables (NEVER commit these!)
export OPENAI_API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxx"
export SLACK_BOT_TOKEN="xoxb-xxxxxxxxxxxxxxxxxxxxx"
export SLACK_SIGNING_SECRET="xxxxxxxxxxxxxxxxxxxxxxxx"
export POSTGRES_PASSWORD="$(openssl rand -base64 32)"  # Generate secure password

# Verify they're set
echo $OPENAI_API_KEY
# Should print your key
```

### **Step 5: Preview What Will Be Deployed (Dry Run)**

```bash
# This shows you the final YAML without deploying
helm install argus . \
  --values environments/values-dev.yaml \
  --set argus.secrets.openaiApiKey="$OPENAI_API_KEY" \
  --set argus.secrets.slackBotToken="$SLACK_BOT_TOKEN" \
  --set argus.secrets.slackSigningSecret="$SLACK_SIGNING_SECRET" \
  --set postgresql.auth.password="$POSTGRES_PASSWORD" \
  --dry-run --debug \
  --namespace dev-argus

# This will print out:
# 1. All the templates
# 2. With values filled in
# 3. But NOT actually deploy anything

# Look for:
# - Are the secrets correct?
# - Are the image names correct?
# - Are the replicas correct?
```

### **Step 6: Deploy for Real**

```bash
# Remove --dry-run to actually deploy
helm install argus . \
  --values environments/values-dev.yaml \
  --set argus.secrets.openaiApiKey="$OPENAI_API_KEY" \
  --set argus.secrets.slackBotToken="$SLACK_BOT_TOKEN" \
  --set argus.secrets.slackSigningSecret="$SLACK_SIGNING_SECRET" \
  --set postgresql.auth.password="$POSTGRES_PASSWORD" \
  --namespace dev-argus \
  --create-namespace

# Output:
# NAME: argus
# LAST DEPLOYED: Sun Feb  9 12:00:00 2025
# NAMESPACE: dev-argus
# STATUS: deployed
# REVISION: 1
```

**What just happened?**

```
1. Helm created namespace: dev-argus
2. Helm created ServiceAccount: argus-agent-sa
3. Helm created ClusterRole: argus-cluster-role
4. Helm created ClusterRoleBinding (gives permissions)
5. Helm created Secret: argus-agent-secrets (with your API keys)
6. Helm unpacked postgresql-15.5.38.tgz
7. Helm deployed PostgreSQL (StatefulSet + Service)
8. Helm unpacked redis-20.5.0.tgz
9. Helm deployed Redis (Deployment + Service)
10. Helm deployed Argus Agent (Deployment + Service)
11. All pods started!
```

### **Step 7: Watch Pods Start**

```bash
# Watch pods starting up
kubectl get pods -n dev-argus --watch

# You'll see:
# NAME                           READY   STATUS              RESTARTS   AGE
# argus-agent-xxx                0/1     ContainerCreating   0          5s
# argus-postgresql-0             0/1     Init:0/1            0          5s
# argus-redis-master-0           0/1     ContainerCreating   0          5s

# After 30-60 seconds:
# argus-agent-xxx                1/1     Running             0          45s
# argus-postgresql-0             1/1     Running             0          45s
# argus-redis-master-0           1/1     Running             0          45s

# Press Ctrl+C to stop watching
```

### **Step 8: Verify Everything Works**

```bash
# 1. Check all pods are running
kubectl get pods -n dev-argus

# 2. Check services
kubectl get svc -n dev-argus
# You should see:
# - argus-agent
# - argus-postgresql
# - argus-redis-master

# 3. Check secrets were created
kubectl get secrets -n dev-argus
# You should see: argus-agent-secrets

# 4. Check RBAC
kubectl get clusterrole | grep argus
kubectl get clusterrolebinding | grep argus

# 5. Check logs (important!)
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent --tail=50

# Look for:
# ✅ "Connected to PostgreSQL"
# ✅ "Connected to Redis"
# ✅ "Server started on 0.0.0.0:8000"
# ❌ Any ERROR messages
```

### **Step 9: Access Your Application**

```bash
# Port forward to access locally
kubectl port-forward -n dev-argus svc/argus-agent 8000:8000

# In another terminal, test it:
curl http://localhost:8000/health

# Should return:
# {"status": "healthy"}
```

### **Step 10: Make Changes and Upgrade**

```bash
# Change a value (e.g., increase replicas to 3)
# Edit environments/values-dev.yaml:
# argus:
#   replicaCount: 3

# Upgrade the deployment
helm upgrade argus . \
  --values environments/values-dev.yaml \
  --namespace dev-argus

# Check that new pods are created
kubectl get pods -n dev-argus
# You should now see 3 argus-agent pods
```

### **Step 11: Clean Up**

```bash
# Uninstall everything
helm uninstall argus --namespace dev-argus

# Delete namespace (optional)
kubectl delete namespace dev-argus

# What gets deleted:
# ✅ All pods
# ✅ All services
# ✅ All secrets
# ✅ StatefulSets, Deployments
# ❌ ClusterRole, ClusterRoleBinding (cluster-wide resources remain)

# To delete cluster resources:
kubectl delete clusterrole argus-cluster-role
kubectl delete clusterrolebinding argus-cluster-role-binding
```

---

## 🔍 **How to Customize Values**

### **Method 1: Edit values.yaml Directly**

```bash
# Edit the file
nano values.yaml

# Change:
argus:
  replicaCount: 2   # ← Change this to 3

# Deploy
helm install argus . --namespace dev-argus
```

**Pros:** Simple, permanent changes
**Cons:** Have to edit file every time

### **Method 2: Use --set Flag**

```bash
# Override a single value
helm install argus . \
  --set argus.replicaCount=3 \
  --namespace dev-argus

# Override multiple values
helm install argus . \
  --set argus.replicaCount=3 \
  --set argus.image.tag=v2.0.0 \
  --set postgresql.auth.password=newsecret \
  --namespace dev-argus

# Override nested values
helm install argus . \
  --set argus.resources.memory=4Gi \
  --namespace dev-argus
```

**Pros:** Quick, command-line friendly
**Cons:** Hard to remember, not version controlled

### **Method 3: Use Separate Values File (BEST)**

```bash
# Create custom values file
cat > my-custom-values.yaml <<EOF
argus:
  replicaCount: 3
  image:
    tag: v2.0.0
postgresql:
  primary:
    persistence:
      size: 50Gi
EOF

# Deploy with custom values
helm install argus . \
  --values my-custom-values.yaml \
  --namespace dev-argus
```

**Pros:** Version controlled, reusable
**Cons:** Need to maintain separate file

### **Method 4: Combine Multiple Methods**

```bash
# Use environment file + override specific values
helm install argus . \
  --values environments/values-prod.yaml \
  --set argus.image.tag=v2.0.0-hotfix \
  --set postgresql.auth.password="$SECURE_PASSWORD" \
  --namespace argus
```

**Pros:** Flexible, secure (passwords not in files)
**Cons:** Command gets long

---

## 🐛 **Troubleshooting**

### **Issue 1: Helm dependency update fails**

```bash
# Error: Could not download chart
```

**Solution:**
```bash
# Add Bitnami repo
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Try again
helm dependency update
```

### **Issue 2: Pods stuck in Pending**

```bash
kubectl get pods -n dev-argus
# argus-postgresql-0   0/1   Pending   0   5m
```

**Solution:**
```bash
# Check why
kubectl describe pod argus-postgresql-0 -n dev-argus

# Common causes:
# 1. No storage class available
#    → Disable persistence for dev: postgresql.primary.persistence.enabled=false
# 2. Insufficient resources
#    → Reduce resource requests
```

### **Issue 3: Template rendering errors**

```bash
# Error: template: ... function "include" not defined
```

**Solution:**
```bash
# Check _helpers.tpl exists
ls templates/_helpers.tpl

# Verify Chart.yaml is valid
helm lint .
```

### **Issue 4: Values not being applied**

```bash
# You set replicas=5 but only 2 are running
```

**Solution:**
```bash
# Check which values are actually being used
helm get values argus --namespace dev-argus

# Debug: Render templates to see final YAML
helm template argus . --values environments/values-dev.yaml > debug.yaml
cat debug.yaml | grep -A 5 "replicas:"
```

---

## 📚 **Summary - Key Takeaways**

### **What You Learned:**

1. **Helm is like LEGO instructions** for Kubernetes
2. **Bitnami charts** = Pre-built, production-ready components (PostgreSQL, Redis)
3. **values.yaml** = Your settings (like a config file)
4. **Templates** = Blueprints with placeholders that Helm fills in
5. **helm install** = Deploy everything with one command
6. **Multiple environments** = Use different values-*.yaml files
7. **Chart structure** = Organized folders for different tiers/components

### **Helm Commands Cheat Sheet:**

| Command | What It Does |
|---------|--------------|
| `helm dependency update` | Download Bitnami charts |
| `helm install NAME .` | Deploy chart |
| `helm upgrade NAME .` | Update deployment |
| `helm uninstall NAME` | Delete everything |
| `helm list` | Show deployments |
| `helm get values NAME` | Show current values |
| `helm template .` | Preview YAML (don't deploy) |
| `helm lint .` | Check for errors |

### **Next Steps:**

1. ✅ Deploy to dev environment
2. ✅ Test functionality
3. ✅ Deploy to staging
4. ✅ Deploy to production
5. ✅ Set up monitoring
6. ✅ Configure AlertManager to send alerts to Argus

---

## 📖 **Further Reading**

- [Helm Official Docs](https://helm.sh/docs/)
- [Bitnami Chart Catalog](https://bitnami.com/stacks/helm)
- [Kubernetes Basics](https://kubernetes.io/docs/tutorials/kubernetes-basics/)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Deep dive into Argus architecture

---

**🎉 Congratulations!** You now understand Helm from basics to advanced usage!

**Questions?** Check [docs/QUICK_START.md](docs/QUICK_START.md) or the troubleshooting section above.