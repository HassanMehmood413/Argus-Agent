# Kubernetes RBAC Guide

Complete guide for Role-Based Access Control (RBAC) in Kubernetes for Argus Agent.

---

## Table of Contents

1. [RBAC Concepts](#rbac-concepts)
2. [ServiceAccount](#serviceaccount)
3. [Role vs ClusterRole](#role-vs-clusterrole)
4. [RoleBinding vs ClusterRoleBinding](#rolebinding-vs-clusterrolebinding)
5. [Argus Agent RBAC Setup](#argus-agent-rbac-setup)
6. [User Roles (Junior/Senior)](#user-roles)
7. [Best Practices](#best-practices)

---

## RBAC Concepts

### What is RBAC?

RBAC (Role-Based Access Control) controls WHO can do WHAT on WHICH resources.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RBAC Components                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Subject          Binding              Role              Resource          │
│   (WHO)      ────► (LINKS) ────►      (WHAT)      ────►   (WHICH)          │
│                                                                             │
│   • User           • RoleBinding       • Role             • pods            │
│   • Group          • ClusterRole       • ClusterRole      • deployments     │
│   • ServiceAccount   Binding                              • secrets         │
│                                                           • services        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Terms

| Term | Description |
|------|-------------|
| **Subject** | Who is making the request (User, Group, ServiceAccount) |
| **Role** | Set of permissions (what actions on what resources) |
| **Binding** | Links a subject to a role |
| **Namespace** | Logical isolation boundary |

---

## ServiceAccount

### What is a ServiceAccount?

A ServiceAccount is an identity for processes running in pods. Unlike user accounts (for humans), ServiceAccounts are for applications.

### When to Use ServiceAccount

- ✅ Applications running in pods that need K8s API access
- ✅ CI/CD pipelines deploying to clusters
- ✅ Monitoring agents collecting metrics
- ✅ Your Argus Agent (needs to read pods, logs, scale deployments)

### Creating a ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: argus-agent-service-account
  namespace: argus-agent-prod
```

**Apply:**
```bash
kubectl apply -f serviceaccount.yaml
```

**Verify:**
```bash
kubectl get serviceaccount -n argus-agent-prod
```

### Using ServiceAccount in Pod

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: argus-agent-deployment
spec:
  template:
    spec:
      serviceAccountName: argus-agent-service-account  # <-- Reference here
      containers:
        - name: argus-agent
          image: argus-agent:latest
```

### Getting ServiceAccount Token

```bash
# Create a token (Kubernetes 1.24+)
kubectl create token argus-agent-service-account -n argus-agent-prod

# For long-lived token (not recommended for production)
kubectl create token argus-agent-service-account -n argus-agent-prod --duration=8760h
```

---

## Role vs ClusterRole

### Role (Namespace-Scoped)

A **Role** defines permissions within a **single namespace**.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: argus-agent-prod  # <-- Only works in this namespace
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
```

**Use Role when:**
- Permissions needed only in one namespace
- Following principle of least privilege
- Isolating access between teams/environments

### ClusterRole (Cluster-Wide)

A **ClusterRole** defines permissions across **all namespaces** or for cluster-scoped resources.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: pod-reader-cluster  # <-- No namespace, applies cluster-wide
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
```

**Use ClusterRole when:**
- Need access across multiple namespaces
- Accessing cluster-scoped resources (nodes, namespaces, PVs)
- Your Argus Agent needs to access ThreadlyAI namespace

### Comparison

| Aspect | Role | ClusterRole |
|--------|------|-------------|
| Scope | Single namespace | All namespaces |
| Use case | Team-specific access | Cross-team, cluster admins |
| Bound with | RoleBinding | RoleBinding or ClusterRoleBinding |
| Resources | Namespace-scoped | Any resource |

---

## RoleBinding vs ClusterRoleBinding

### RoleBinding

Links a **Subject** to a **Role** (or ClusterRole) in a **specific namespace**.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods-binding
  namespace: argus-agent-prod  # <-- Binding is namespace-scoped
subjects:
  - kind: ServiceAccount
    name: argus-agent-service-account
    namespace: argus-agent-prod
roleRef:
  kind: Role  # or ClusterRole
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

### ClusterRoleBinding

Links a **Subject** to a **ClusterRole** across **all namespaces**.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: read-pods-cluster-binding  # <-- No namespace
subjects:
  - kind: ServiceAccount
    name: argus-agent-service-account
    namespace: argus-agent-prod
roleRef:
  kind: ClusterRole
  name: pod-reader-cluster
  apiGroup: rbac.authorization.k8s.io
```

### Binding Combinations

| Role Type | Binding Type | Result |
|-----------|--------------|--------|
| Role | RoleBinding | Access in one namespace |
| ClusterRole | RoleBinding | ClusterRole scoped to one namespace |
| ClusterRole | ClusterRoleBinding | Access across all namespaces |

---

## Argus Agent RBAC Setup

### Why Argus Agent Needs RBAC

The agent needs to:
1. **READ** - Pods, logs, events, deployments (monitoring)
2. **WRITE** - Restart pods, scale deployments (remediation)
3. **Cross-namespace** - Access ThreadlyAI namespace from argus-agent-prod

### Complete RBAC Configuration

#### 1. ServiceAccount

```yaml
# File: k8s/backend/agent/rbac-rolebinding.yml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: argus-agent-service-account
  namespace: argus-agent-prod
```

#### 2. ClusterRole (For Cross-Namespace Access)

```yaml
# File: k8s/rbac/cluster-role-threadlyai.yml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argus-agent-cluster-role
rules:
  # READ: For monitoring and analysis
  - apiGroups: [""]
    resources: ["pods", "pods/log", "events", "services", "endpoints", "configmaps"]
    verbs: ["get", "list", "watch"]

  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets"]
    verbs: ["get", "list", "watch"]

  # WRITE: For remediation
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["delete"]  # Restart pods

  - apiGroups: ["apps"]
    resources: ["deployments", "deployments/scale"]
    verbs: ["get", "patch", "update"]  # Scale and rollback
```

#### 3. ClusterRoleBinding

```yaml
# File: k8s/rbac/cluster-role-threadlyai.yml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: argus-agent-cluster-role-binding
subjects:
  - kind: ServiceAccount
    name: argus-agent-service-account
    namespace: argus-agent-prod
roleRef:
  kind: ClusterRole
  name: argus-agent-cluster-role
  apiGroup: rbac.authorization.k8s.io
```

### Apply RBAC

```bash
# Apply in order
kubectl apply -f k8s/backend/agent/rbac-rolebinding.yml
kubectl apply -f k8s/rbac/cluster-role-threadlyai.yml

# Verify
kubectl get serviceaccount -n argus-agent-prod
kubectl get clusterrole argus-agent-cluster-role
kubectl get clusterrolebinding argus-agent-cluster-role-binding
```

### Test RBAC Permissions

```bash
# Test if ServiceAccount can list pods in ThreadlyAI namespace
kubectl auth can-i list pods \
  --as=system:serviceaccount:argus-agent-prod:argus-agent-service-account \
  -n ThreadlyAI

# Test if can delete pods
kubectl auth can-i delete pods \
  --as=system:serviceaccount:argus-agent-prod:argus-agent-service-account \
  -n ThreadlyAI

# Test if can scale deployments
kubectl auth can-i patch deployments/scale \
  --as=system:serviceaccount:argus-agent-prod:argus-agent-service-account \
  -n ThreadlyAI
```

---

## User Roles

### Junior Developer Role

Junior developers can only **view** resources in **dev namespace**.

```yaml
# File: k8s/rbac/junior-role.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: argus-agent-junior-role
  namespace: argus-agent-dev
rules:
  - apiGroups: [""]
    resources: ["pods", "services"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
```

**Bind to junior user:**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: junior-binding
  namespace: argus-agent-dev
subjects:
  - kind: User
    name: junior@company.com
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: argus-agent-junior-role
  apiGroup: rbac.authorization.k8s.io
```

### Senior Developer Role

Senior developers can **view and modify** resources across **all namespaces**.

```yaml
# File: k8s/rbac/senior-role.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argus-agent-senior-cluster-role
rules:
  - apiGroups: [""]
    resources: ["pods", "services"]
    verbs: ["get", "list", "watch", "create", "update", "delete"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch", "create", "update", "delete"]
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list", "watch"]
```

**Bind to senior user:**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: senior-binding
subjects:
  - kind: User
    name: senior@company.com
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: argus-agent-senior-cluster-role
  apiGroup: rbac.authorization.k8s.io
```

### Permission Matrix

| Role | Namespace | Pods | Deployments | Secrets |
|------|-----------|------|-------------|---------|
| Junior | dev only | view | view | ❌ |
| Senior | all | view, edit | view, edit | view |
| DevOps | all | all | all | all |

---

## Best Practices

### 1. Principle of Least Privilege

Give only the minimum permissions needed.

```yaml
# BAD: Too broad
rules:
  - apiGroups: ["*"]
    resources: ["*"]
    verbs: ["*"]

# GOOD: Specific permissions
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list"]
```

### 2. Use Namespaces for Isolation

```
argus-agent-dev      → Junior devs can access
argus-agent-staging  → Senior devs can access
argus-agent-prod     → Only DevOps can access
```

### 3. Limit Secret Access

```yaml
# Only allow specific secrets
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get"]
  resourceNames:
    - "agent-secrets"
    - "db-credentials"
```

### 4. Audit RBAC Regularly

```bash
# List all role bindings
kubectl get rolebindings,clusterrolebindings --all-namespaces

# Check specific user's permissions
kubectl auth can-i --list --as=junior@company.com

# Check ServiceAccount permissions
kubectl auth can-i --list \
  --as=system:serviceaccount:argus-agent-prod:argus-agent-service-account
```

### 5. Use Groups Instead of Individual Users

```yaml
subjects:
  - kind: Group
    name: developers
    apiGroup: rbac.authorization.k8s.io
```

---

## Quick Reference Commands

```bash
# Create ServiceAccount
kubectl create serviceaccount my-sa -n my-namespace

# Create Role
kubectl create role pod-reader --verb=get,list --resource=pods -n my-namespace

# Create RoleBinding
kubectl create rolebinding my-binding --role=pod-reader --serviceaccount=my-namespace:my-sa -n my-namespace

# Create ClusterRole
kubectl create clusterrole pod-reader-cluster --verb=get,list --resource=pods

# Create ClusterRoleBinding
kubectl create clusterrolebinding my-cluster-binding --clusterrole=pod-reader-cluster --serviceaccount=my-namespace:my-sa

# Test permissions
kubectl auth can-i list pods --as=system:serviceaccount:my-namespace:my-sa

# Get token for ServiceAccount
kubectl create token my-sa -n my-namespace

# View RBAC resources
kubectl get roles,rolebindings -n my-namespace
kubectl get clusterroles,clusterrolebindings
```

---

## Troubleshooting

### "Forbidden" Error

```
Error: pods is forbidden: User "system:serviceaccount:..." cannot list resource "pods"
```

**Fix:**
1. Check if RoleBinding/ClusterRoleBinding exists
2. Verify ServiceAccount name matches
3. Verify namespace is correct

```bash
kubectl get rolebindings -n argus-agent-prod
kubectl describe rolebinding my-binding -n argus-agent-prod
```

### ServiceAccount Not Found

```bash
# Check if SA exists
kubectl get serviceaccount -n argus-agent-prod

# Create if missing
kubectl create serviceaccount argus-agent-service-account -n argus-agent-prod
```

### Permission Test Failing

```bash
# Debug: List all permissions for SA
kubectl auth can-i --list \
  --as=system:serviceaccount:argus-agent-prod:argus-agent-service-account \
  -n ThreadlyAI
```
