# Environment Management Guide

Managing Dev, Staging, and Production environments for Argus Agent.

---

## Table of Contents

1. [Environment Overview](#environment-overview)
2. [Namespace Configuration](#namespace-configuration)
3. [Environment-Specific Settings](#environment-specific-settings)
4. [Promoting Changes](#promoting-changes)
5. [Environment Isolation](#environment-isolation)

---

## Environment Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Environment Architecture                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│   │      DEV        │  │    STAGING      │  │   PRODUCTION    │           │
│   ├─────────────────┤  ├─────────────────┤  ├─────────────────┤           │
│   │                 │  │                 │  │                 │           │
│   │ Namespace:      │  │ Namespace:      │  │ Namespace:      │           │
│   │ argus-agent-dev │  │ argus-agent-    │  │ argus-agent-    │           │
│   │                 │  │ staging         │  │ prod            │           │
│   │                 │  │                 │  │                 │           │
│   │ Branch:         │  │ Branch:         │  │ Branch:         │           │
│   │ develop         │  │ staging         │  │ main            │           │
│   │                 │  │                 │  │                 │           │
│   │ Access:         │  │ Access:         │  │ Access:         │           │
│   │ All developers  │  │ Senior devs     │  │ DevOps only     │           │
│   │                 │  │                 │  │                 │           │
│   │ Deploy:         │  │ Deploy:         │  │ Deploy:         │           │
│   │ Auto            │  │ Auto            │  │ Manual approval │           │
│   │                 │  │                 │  │                 │           │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Environment Purpose

| Environment | Purpose | Data | Users |
|-------------|---------|------|-------|
| **Dev** | Feature development, debugging | Fake/test data | Developers |
| **Staging** | QA testing, integration testing | Copy of prod data | QA team, Seniors |
| **Production** | Live users | Real data | End users |

---

## Namespace Configuration

### Creating Namespaces

```yaml
# k8s/namespace/agent_dev.yml
apiVersion: v1
kind: Namespace
metadata:
  name: argus-agent-dev
  labels:
    environment: development
    team: argus

---
# k8s/namespace/agent_staging.yml
apiVersion: v1
kind: Namespace
metadata:
  name: argus-agent-staging
  labels:
    environment: staging
    team: argus

---
# k8s/namespace/agent_prod.yml
apiVersion: v1
kind: Namespace
metadata:
  name: argus-agent-prod
  labels:
    environment: production
    team: argus
```

### Apply Namespaces

```bash
kubectl apply -f k8s/namespace/
```

### Resource Quotas (Optional)

Limit resources per environment:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: env-quota
  namespace: argus-agent-dev
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "20"
```

---

## Environment-Specific Settings

### ConfigMap Per Environment

**Dev ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argus-agent-config
  namespace: argus-agent-dev
data:
  EXECUTION_DRY_RUN: "true"          # Don't execute real actions
  LOG_LEVEL: "DEBUG"                  # Verbose logging
  SLACK_DEFAULT_CHANNEL: "#dev-alerts"
  AUTO_APPROVE_RISK_LEVELS: '["none", "low", "medium"]'  # More lenient
```

**Staging ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argus-agent-config
  namespace: argus-agent-staging
data:
  EXECUTION_DRY_RUN: "false"         # Execute real actions
  LOG_LEVEL: "INFO"
  SLACK_DEFAULT_CHANNEL: "#staging-alerts"
  AUTO_APPROVE_RISK_LEVELS: '["none", "low"]'
```

**Production ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argus-agent-config
  namespace: argus-agent-prod
data:
  EXECUTION_DRY_RUN: "false"
  LOG_LEVEL: "WARNING"               # Less verbose
  SLACK_DEFAULT_CHANNEL: "#prod-incidents"
  AUTO_APPROVE_RISK_LEVELS: '["none"]'  # Most restrictive
```

### Secrets Per Environment

**Dev Secrets:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: argus-agent-secrets
  namespace: argus-agent-dev
stringData:
  DATABASE_URL: "postgresql+asyncpg://dev:dev@postgres:5432/argus_dev"
  OPENAI_API_KEY: "sk-dev-key-xxx"  # Dev API key with lower limits
  SLACK_BOT_TOKEN: "xoxb-dev-token"
```

**Production Secrets:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: argus-agent-secrets
  namespace: argus-agent-prod
stringData:
  DATABASE_URL: "postgresql+asyncpg://prod:secure@prod-db:5432/argus_prod"
  OPENAI_API_KEY: "sk-prod-key-xxx"  # Production API key
  SLACK_BOT_TOKEN: "xoxb-prod-token"
```

### Deployment Differences

| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| Replicas | 1 | 2 | 3 |
| Resources (CPU) | 0.25 | 0.5 | 1 |
| Resources (Memory) | 256Mi | 512Mi | 1Gi |
| HPA Enabled | No | Yes | Yes |
| Dry Run | Yes | No | No |

---

## Promoting Changes

### Dev → Staging

```bash
# 1. Ensure develop branch is stable
git checkout develop
git pull origin develop

# 2. Create PR to staging
# GitHub: New PR, base: staging, compare: develop

# 3. After approval and merge
# CI automatically deploys to staging

# 4. Verify staging
kubectl get pods -n argus-agent-staging
kubectl logs -l app=argus-agent -n argus-agent-staging
```

### Staging → Production

```bash
# 1. Ensure staging is tested and stable
git checkout staging
git pull origin staging

# 2. Create PR to main
# GitHub: New PR, base: main, compare: staging

# 3. Get required approvals (2 reviewers)

# 4. Merge PR

# 5. Go to GitHub Actions
# Click "Review deployments" → Approve "production"

# 6. Monitor deployment
kubectl get pods -n argus-agent-prod -w
kubectl logs -l app=argus-agent -n argus-agent-prod -f
```

### Hotfix to Production

```bash
# 1. Create hotfix branch from main
git checkout main
git checkout -b hotfix/critical-fix

# 2. Make fix and commit

# 3. Create PR directly to main (bypass staging for critical fixes)
# Requires extra approval

# 4. After deployment, backport to staging and develop
git checkout staging
git merge hotfix/critical-fix

git checkout develop
git merge hotfix/critical-fix
```

---

## Environment Isolation

### Network Policies (Optional)

Prevent cross-namespace communication:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-cross-namespace
  namespace: argus-agent-prod
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: argus-agent-prod
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: argus-agent-prod
    - to:  # Allow external traffic (APIs, etc.)
        - ipBlock:
            cidr: 0.0.0.0/0
```

### RBAC Isolation

**Dev-only access for juniors:**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: junior-dev-access
  namespace: argus-agent-dev
subjects:
  - kind: Group
    name: junior-developers
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: developer-role
  apiGroup: rbac.authorization.k8s.io
```

### Separate Databases

```
Dev:     postgres-dev.argus-agent-dev.svc.cluster.local
Staging: postgres-staging.argus-agent-staging.svc.cluster.local
Prod:    postgres-prod.argus-agent-prod.svc.cluster.local
```

---

## Environment Commands Cheat Sheet

```bash
# ═══════════════════════════════════════════════════════════════
# SWITCH BETWEEN ENVIRONMENTS
# ═══════════════════════════════════════════════════════════════

# Set default namespace for kubectl
kubectl config set-context --current --namespace=argus-agent-dev
kubectl config set-context --current --namespace=argus-agent-staging
kubectl config set-context --current --namespace=argus-agent-prod

# ═══════════════════════════════════════════════════════════════
# VIEW RESOURCES IN SPECIFIC ENVIRONMENT
# ═══════════════════════════════════════════════════════════════

# Dev
kubectl get pods -n argus-agent-dev
kubectl get svc -n argus-agent-dev
kubectl logs -l app=argus-agent -n argus-agent-dev

# Staging
kubectl get pods -n argus-agent-staging
kubectl get svc -n argus-agent-staging
kubectl logs -l app=argus-agent -n argus-agent-staging

# Prod
kubectl get pods -n argus-agent-prod
kubectl get svc -n argus-agent-prod
kubectl logs -l app=argus-agent -n argus-agent-prod

# ═══════════════════════════════════════════════════════════════
# COMPARE ENVIRONMENTS
# ═══════════════════════════════════════════════════════════════

# Compare deployments across environments
kubectl get deployment argus-agent-deployment -n argus-agent-dev -o yaml > dev.yaml
kubectl get deployment argus-agent-deployment -n argus-agent-prod -o yaml > prod.yaml
diff dev.yaml prod.yaml

# Compare images
echo "Dev: $(kubectl get deployment argus-agent-deployment -n argus-agent-dev -o jsonpath='{.spec.template.spec.containers[0].image}')"
echo "Staging: $(kubectl get deployment argus-agent-deployment -n argus-agent-staging -o jsonpath='{.spec.template.spec.containers[0].image}')"
echo "Prod: $(kubectl get deployment argus-agent-deployment -n argus-agent-prod -o jsonpath='{.spec.template.spec.containers[0].image}')"

# ═══════════════════════════════════════════════════════════════
# PORT FORWARD FOR TESTING
# ═══════════════════════════════════════════════════════════════

# Dev
kubectl port-forward svc/argus-agent-service 8001:8000 -n argus-agent-dev

# Staging
kubectl port-forward svc/argus-agent-service 8002:8000 -n argus-agent-staging

# Prod
kubectl port-forward svc/argus-agent-service 8003:8000 -n argus-agent-prod
```

---

## Summary Table

| Aspect | Dev | Staging | Prod |
|--------|-----|---------|------|
| **Namespace** | argus-agent-dev | argus-agent-staging | argus-agent-prod |
| **Branch** | develop | staging | main |
| **Deploy Trigger** | Auto on merge | Auto on merge | Manual approval |
| **Approvers** | 1 | 1 senior | 2 (lead + devops) |
| **Replicas** | 1 | 2 | 3+ |
| **Dry Run** | Yes | No | No |
| **Log Level** | DEBUG | INFO | WARNING |
| **Access** | All devs | Senior devs | DevOps only |
