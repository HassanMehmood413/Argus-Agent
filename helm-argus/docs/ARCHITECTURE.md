# Argus DevOps Agent - Architecture & RBAC Design

## 🏗️ **System Architecture**

### **High-Level Overview**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Kubernetes Cluster                                 │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Namespace: dev-argus (Argus Control Plane)                          │    │
│  │                                                                       │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │  Argus Agent (Deployment)                                    │   │    │
│  │  │  ┌────────────────────────────────────────────────────────┐  │   │    │
│  │  │  │  ServiceAccount: argus-agent-sa                        │  │   │    │
│  │  │  │  ├─► ClusterRoleBinding                                │  │   │    │
│  │  │  │  │   └─► ClusterRole: argus-cluster-role              │  │   │    │
│  │  │  │  │       ├─► Read: pods, deployments, logs, events    │  │   │    │
│  │  │  │  │       └─► Write: restart, scale, rollback          │  │   │    │
│  │  │  └────────────────────────────────────────────────────────┘  │   │    │
│  │  │                                                                │   │    │
│  │  │  Container: argus-agent                                       │   │    │
│  │  │  ├─► FastAPI REST API                                         │   │    │
│  │  │  ├─► LangGraph Orchestrator                                   │   │    │
│  │  │  ├─► GPT-4o for Analysis                                      │   │    │
│  │  │  └─► Kubernetes Client (uses ServiceAccount token)           │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  │                                                                       │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │    │
│  │  │  PostgreSQL      │  │     Redis        │  │   Qdrant (opt)   │  │    │
│  │  │  (StatefulSet)   │  │  (Deployment)    │  │  (vector DB)     │  │    │
│  │  │  - Checkpoints   │  │  - Cache         │  │  - Embeddings    │  │    │
│  │  │  - Incidents     │  │  - Sessions      │  │  - Similarity    │  │    │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │ Namespace: monitoring            │                                    │   │
│  │  ┌──────────────────┐  ┌─────────▼─────────┐  ┌──────────────────┐  │   │
│  │  │   Prometheus     │  │   AlertManager    │  │      Loki        │  │   │
│  │  │  - Scrapes       │  │  - Routes alerts  │  │  - Log storage   │  │   │
│  │  │    metrics       │  │  - Webhooks to    │  │  - Log queries   │  │   │
│  │  │  - Evaluates     │  │    Argus          │  │                  │  │   │
│  │  │    rules         │  │                   │  │                  │  │   │
│  │  └──────────────────┘  └───────────────────┘  └──────────────────┘  │   │
│  │                                                                       │   │
│  │  ┌──────────────────┐                                                │   │
│  │  │     Grafana      │                                                │   │
│  │  │  - Dashboards    │  Can also send alerts to Argus               │   │
│  │  │  - Visualize     │                                                │   │
│  │  └──────────────────┘                                                │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │ Namespace: your-app (Target Applications)                            │   │
│  │  ┌──────────────────┐  ┌─────────▼─────────┐  ┌──────────────────┐  │   │
│  │  │   Deployment     │  │   Deployment      │  │   StatefulSet    │  │   │
│  │  │   - app-1        │  │   - app-2         │  │   - database     │  │   │
│  │  │   - Pod 1        │  │   - Pod 1         │  │   - Pod 1        │  │   │
│  │  │   - Pod 2        │  │   - Pod 2         │  │                  │  │   │
│  │  └──────────────────┘  └───────────────────┘  └──────────────────┘  │   │
│  │         ▲                       ▲                       ▲             │   │
│  │         │                       │                       │             │   │
│  │         └───────────────────────┴───────────────────────┘             │   │
│  │                  Monitored & Managed by Argus                         │   │
│  │                  (via ClusterRole permissions)                        │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │ External Integrations                                                 │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │    Slack     │  │     Jira     │  │    OpenAI    │               │   │
│  │  │  - Approvals │  │  - Postmortem│  │  - GPT-4o    │               │   │
│  │  │  - Notify    │  │    tickets   │  │  - Analysis  │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔑 **RBAC Permission Model**

### **Components**

```
1. ServiceAccount: argus-agent-sa (namespace: dev-argus)
   │
   ├─► Used by: Argus Agent pods
   │
   └─► Bound to: ClusterRole via ClusterRoleBinding
            │
            └─► ClusterRole: argus-cluster-role
                ├─► Scope: Cluster-wide (all namespaces)
                │
                ├─► Read Permissions (Monitoring)
                │   ├─► pods, pods/status (get, list, watch)
                │   ├─► pods/log (get, list)
                │   ├─► deployments, deployments/status (get, list, watch)
                │   ├─► replicasets (get, list, watch)
                │   ├─► events (get, list, watch)
                │   ├─► services, configmaps (get, list, watch)
                │   ├─► namespaces (get, list, watch)
                │   └─► nodes, nodes/status (get, list, watch)
                │
                └─► Write Permissions (Execution)
                    ├─► deployments (patch, update) - for restarts, image updates
                    ├─► deployments/scale (get, patch, update) - for scaling
                    ├─► pods (delete, deletecollection) - for pod deletion
                    └─► deployments/rollback (create) - for rollbacks
```

### **Permission Matrix**

| Operation | API Group | Resource | Verbs | Use Case |
|-----------|-----------|----------|-------|----------|
| **MONITORING** |
| Check pod status | `` (core) | `pods`, `pods/status` | get, list, watch | Monitor pod health, restarts |
| Read pod logs | `` (core) | `pods/log` | get, list | Analyze application logs |
| Monitor deployments | `apps` | `deployments`, `deployments/status` | get, list, watch | Track deployment health |
| Monitor replicasets | `apps` | `replicasets`, `replicasets/status` | get, list, watch | Check replica counts |
| Read K8s events | `` (core) | `events` | get, list, watch | Detect OOMKilled, CrashLoop |
| Read services | `` (core) | `services` | get, list, watch | Service information |
| Read configs | `` (core) | `configmaps` | get, list, watch | Configuration data |
| List namespaces | `` (core) | `namespaces` | get, list, watch | Namespace info |
| Monitor nodes | `` (core) | `nodes`, `nodes/status` | get, list, watch | Node resource utilization |
| **EXECUTION** |
| Restart deployment | `apps` | `deployments` | patch, update | `kubectl rollout restart` |
| Update deployment | `apps` | `deployments` | patch, update | Update image, resources |
| Scale deployment | `apps` | `deployments/scale` | get, patch, update | `kubectl scale` |
| Delete pods | `` (core) | `pods` | delete, deletecollection | Remove stuck pods |
| Rollback deployment | `apps` | `deployments/rollback` | create | `kubectl rollout undo` |

---

## 🔄 **Incident Processing Flow**

### **Complete Workflow with RBAC**

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 1. ALERT RECEIVED                                                        │
│    AlertManager → POST /api/v1/incidents/alertmanager → Argus Agent     │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 2. MONITORING PHASE                                                      │
│    Argus uses ServiceAccount token to call Kubernetes API:              │
│    ┌──────────────────────────────────────────────────────────────┐     │
│    │ RBAC Check: Can argus-agent-sa...                            │     │
│    │ ✅ GET /api/v1/namespaces/your-app/pods                      │     │
│    │ ✅ GET /api/v1/namespaces/your-app/pods/{name}/log           │     │
│    │ ✅ GET /api/v1/namespaces/your-app/events                    │     │
│    │ ✅ GET /apis/apps/v1/namespaces/your-app/deployments         │     │
│    └──────────────────────────────────────────────────────────────┘     │
│                                                                          │
│    Collects:                                                             │
│    ├─► Metrics from Prometheus (HTTP query, no RBAC needed)            │
│    ├─► Logs from Loki (HTTP query, no RBAC needed)                     │
│    ├─► Pod status (Kubernetes API, requires pods:get)                  │
│    ├─► Events (Kubernetes API, requires events:get)                    │
│    └─► Recent deployments (Kubernetes API, requires deployments:get)   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 3. ANALYSIS PHASE                                                        │
│    ├─► Pattern detection (local processing, no RBAC)                   │
│    ├─► Vector search in Qdrant (HTTP query, no RBAC)                   │
│    ├─► LLM analysis via OpenAI (HTTP query, no RBAC)                   │
│    └─► Generate recommended actions                                     │
│         └─► Actions: restart_deployment, scale_deployment, etc.         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 4. APPROVAL PHASE                                                        │
│    ├─► Send Slack message with buttons (HTTP, no RBAC)                 │
│    ├─► LangGraph interrupt() - pause execution                          │
│    ├─► User clicks "Approve" in Slack                                   │
│    ├─► Slack webhook → POST /api/v1/slack/interactions → Argus         │
│    └─► LangGraph resume() - continue execution                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 5. EXECUTION PHASE                                                       │
│    Argus uses ServiceAccount token to execute actions:                  │
│    ┌──────────────────────────────────────────────────────────────┐     │
│    │ Action: restart_deployment                                   │     │
│    │ RBAC Check: Can argus-agent-sa...                            │     │
│    │ ✅ PATCH /apis/apps/v1/namespaces/your-app/deployments/app-1 │     │
│    │    (requires deployments:patch)                              │     │
│    │ Execute: kubectl rollout restart deployment/app-1            │     │
│    └──────────────────────────────────────────────────────────────┘     │
│                                                                          │
│    ┌──────────────────────────────────────────────────────────────┐     │
│    │ Action: scale_deployment                                     │     │
│    │ RBAC Check: Can argus-agent-sa...                            │     │
│    │ ✅ PATCH /apis/apps/v1/namespaces/your-app/deployments/      │     │
│    │          app-1/scale                                          │     │
│    │    (requires deployments/scale:patch)                        │     │
│    │ Execute: kubectl scale deployment/app-1 --replicas=5         │     │
│    └──────────────────────────────────────────────────────────────┘     │
│                                                                          │
│    ┌──────────────────────────────────────────────────────────────┐     │
│    │ Action: delete_pod                                           │     │
│    │ RBAC Check: Can argus-agent-sa...                            │     │
│    │ ✅ DELETE /api/v1/namespaces/your-app/pods/app-1-xxx         │     │
│    │    (requires pods:delete)                                    │     │
│    │ Execute: kubectl delete pod app-1-xxx                        │     │
│    └──────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 6. SUMMARY PHASE                                                         │
│    ├─► Generate incident summary (local processing, no RBAC)           │
│    ├─► Post to Slack (HTTP query, no RBAC)                             │
│    └─► Create Jira ticket (HTTP query, no RBAC)                        │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ **Security Model**

### **Principle of Least Privilege**

```
Argus ClusterRole permissions:
✅ GRANTED:
   ├─► Read pods, deployments, events (monitoring)
   ├─► Update deployments (restart, image updates)
   ├─► Scale deployments (up/down)
   ├─► Delete pods (stuck pods)
   └─► Create rollbacks (undo deployments)

❌ DENIED:
   ├─► Create/delete namespaces
   ├─► Create/delete cluster roles
   ├─► Create/delete persistent volumes
   ├─► Read secrets (except own namespace)
   ├─► Create/delete service accounts
   └─► Modify RBAC resources
```

### **ServiceAccount Token Usage**

```
1. Pod starts with ServiceAccount: argus-agent-sa

2. Kubernetes auto-mounts token at:
   /var/run/secrets/kubernetes.io/serviceaccount/token

3. Argus Kubernetes client reads token:
   kubernetes.config.load_incluster_config()

4. All Kubernetes API calls authenticated with this token:
   GET /api/v1/namespaces/your-app/pods
   Authorization: Bearer <argus-agent-sa-token>

5. Kubernetes API server checks RBAC:
   ├─► User: system:serviceaccount:dev-argus:argus-agent-sa
   ├─► ClusterRoleBinding: argus-cluster-role-binding
   ├─► ClusterRole: argus-cluster-role
   └─► Rule match: pods:get → ✅ ALLOWED

6. If no matching rule → ❌ FORBIDDEN
```

### **Namespace Isolation**

```
Argus can operate across namespaces:

dev-argus (Argus home namespace)
   └─► Has full access to own resources

your-app (Target namespace 1)
   └─► Can: read pods, restart deployments
   └─► Cannot: delete namespace, modify RBAC

another-app (Target namespace 2)
   └─► Can: read pods, restart deployments
   └─► Cannot: delete namespace, modify RBAC

kube-system (Protected namespace)
   └─► Can: read pods (monitoring only)
   └─► Cannot: modify resources (good practice)
```

---

## 📊 **Data Flow**

### **Monitoring Data Collection**

```
┌─────────────────┐
│  Target App Pod │
│  (your-app)     │
└────────┬────────┘
         │
         ├─► Metrics → Prometheus
         │              └─► Argus queries via HTTP
         │                   (no K8s RBAC needed)
         │
         ├─► Logs → Loki
         │           └─► Argus queries via HTTP
         │                (no K8s RBAC needed)
         │
         └─► Pod Status → Kubernetes API
                           └─► Argus queries via K8s client
                                (requires pods:get permission)
                                 │
                                 ▼
                        ┌────────────────────┐
                        │ Kubernetes API     │
                        │ RBAC Check:        │
                        │ ✅ pods:get        │
                        └────────────────────┘
```

### **Action Execution Flow**

```
User approves in Slack
         │
         ▼
┌─────────────────────────────────────────┐
│ Argus Executor determines action:       │
│ Action: restart_deployment              │
│ Target: deployment/app-1                │
│ Namespace: your-app                     │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│ Kubernetes Client API call:             │
│ PATCH /apis/apps/v1/namespaces/your-app │
│       /deployments/app-1                 │
│ Authorization: Bearer <SA token>         │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│ Kubernetes API Server                   │
│ 1. Authenticate: ServiceAccount token   │
│ 2. Authorize: Check ClusterRole         │
│    ├─► User: system:serviceaccount:     │
│    │         dev-argus:argus-agent-sa   │
│    ├─► Resource: deployments            │
│    ├─► Verb: patch                      │
│    └─► ClusterRole rule match: ✅       │
│ 3. Execute: Patch deployment            │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│ Deployment Controller                   │
│ ├─► Creates new ReplicaSet              │
│ ├─► Scales down old ReplicaSet          │
│ └─► Scales up new ReplicaSet            │
└─────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│ New Pods Created                        │
│ Application restarted successfully      │
└─────────────────────────────────────────┘
```

---

## 🔍 **RBAC Verification**

### **How to Test RBAC Permissions**

```bash
# Test 1: Can Argus read pods in all namespaces?
kubectl auth can-i get pods --all-namespaces \
  --as=system:serviceaccount:dev-argus:argus-agent-sa

# Expected: yes


# Test 2: Can Argus read pod logs?
kubectl auth can-i get pods/log -n your-app \
  --as=system:serviceaccount:dev-argus:argus-agent-sa

# Expected: yes


# Test 3: Can Argus restart deployments?
kubectl auth can-i patch deployments -n your-app \
  --as=system:serviceaccount:dev-argus:argus-agent-sa

# Expected: yes


# Test 4: Can Argus delete namespaces? (Should be NO)
kubectl auth can-i delete namespaces \
  --as=system:serviceaccount:dev-argus:argus-agent-sa

# Expected: no


# Test 5: List all permissions
kubectl auth can-i --list \
  --as=system:serviceaccount:dev-argus:argus-agent-sa
```

### **Inside Pod Testing**

```bash
# Create test pod with Argus ServiceAccount
kubectl run test-rbac --image=bitnami/kubectl:latest \
  --namespace=dev-argus \
  --serviceaccount=argus-agent-sa \
  --command -- sleep infinity

# Exec into pod
kubectl exec -it test-rbac -n dev-argus -- /bin/bash

# Inside pod - test permissions
kubectl get pods --all-namespaces        # Should work
kubectl get deployments -n your-app      # Should work
kubectl logs -n your-app app-1-xxx       # Should work
kubectl patch deployment app-1 -n your-app \
  -p '{"spec":{"replicas":3}}'           # Should work
kubectl delete namespace your-app        # Should FAIL
kubectl create clusterrole test          # Should FAIL
```

---

## 🎯 **Best Practices**

### **RBAC Security**

1. **Use ClusterRole for cross-namespace access**
   - Required when monitoring multiple namespaces
   - More powerful than Role, use with caution

2. **Grant minimum necessary permissions**
   - Only what's needed for monitoring and execution
   - No cluster-admin or namespace deletion

3. **Separate monitoring and execution permissions**
   - Read permissions for monitoring
   - Write permissions for execution only

4. **Regularly audit permissions**
   ```bash
   kubectl auth can-i --list \
     --as=system:serviceaccount:dev-argus:argus-agent-sa
   ```

5. **Enable Kubernetes audit logging**
   - Track what Argus is doing
   - Detect unauthorized access attempts

### **Deployment Security**

1. **Run as non-root user**
   ```yaml
   securityContext:
     runAsNonRoot: true
     runAsUser: 1000
   ```

2. **Drop unnecessary capabilities**
   ```yaml
   securityContext:
     capabilities:
       drop:
         - ALL
   ```

3. **Use secrets for sensitive data**
   - Never hardcode API keys in values.yaml
   - Use Kubernetes Secrets or external secret managers

4. **Enable network policies**
   - Restrict traffic to/from Argus pods
   - Only allow necessary connections

5. **Use dry-run mode for testing**
   ```yaml
   execution:
     dryRun: true
   ```

---

## 📈 **Monitoring Argus Itself**

### **Metrics to Track**

- Incident processing time
- Approval response time
- Action execution success rate
- RBAC permission denials
- API errors
- Slack notification failures

### **Logs to Monitor**

```bash
# Argus agent logs
kubectl logs -n dev-argus -l app.kubernetes.io/component=agent -f

# Look for:
# - "Forbidden" errors (RBAC issues)
# - "Connection refused" (service connectivity)
# - "Timeout" errors (long-running operations)
# - "Authentication failed" (token issues)
```

---

## 🎓 **Summary**

**Argus uses Kubernetes RBAC to securely monitor and manage applications across multiple namespaces:**

1. **ServiceAccount** (`argus-agent-sa`) provides identity
2. **ClusterRole** (`argus-cluster-role`) defines permissions
3. **ClusterRoleBinding** connects ServiceAccount to ClusterRole
4. **Token** auto-mounted in pods authenticates API calls
5. **RBAC rules** authorize each Kubernetes API request
6. **Least privilege** ensures Argus only has necessary permissions

**This design allows Argus to:**
- ✅ Monitor applications in any namespace
- ✅ Execute remediation actions safely
- ✅ Operate with minimal permissions
- ✅ Be auditable and secure
- ✅ Scale across multiple teams and applications

---

For deployment instructions, see [QUICK_START.md](QUICK_START.md)
For detailed setup, see [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)