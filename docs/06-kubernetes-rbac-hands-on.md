# Kubernetes RBAC Hands-On Guide

A step-by-step guide for setting up Kubernetes RBAC with service accounts, roles, and contexts.

---

## Step 1: Check Current Contexts

Before starting, always check what contexts already exist in your kubeconfig.

```bash
kubectl config get-contexts
```

> **What is a context?**
> A context is a shortcut that bundles three things together:
> - **Cluster** — which Kubernetes cluster to connect to
> - **User** — which credentials to authenticate with
> - **Namespace** — the default namespace for commands
>
> The context name is just a label/alias for your convenience. You can name it anything you want.

---

## Step 2: Create a Namespace

```bash
kubectl create ns dev-team
```

Or using a YAML file:

```bash
kubectl apply -f namespace.yml
```

> **Why namespaces?**
> Namespaces provide isolation between environments (dev, staging, prod) or teams.
> Each developer/team can be restricted to their own namespace using RBAC.

---

## Step 3: Create a Service Account

```bash
kubectl create sa devuser -n dev-team
```

> **Key Learnings about Service Accounts:**
>
> - A ServiceAccount is an **identity** in the cluster — like a "username" for a developer or application.
> - Create **one service account per developer/identity**. If two developers have different permissions, they **must** have separate service accounts.
> - If multiple developers share the **same permissions**, they can share a service account — but separate ones are still recommended for audit/traceability.
> - To view the YAML of a created service account:
>   ```bash
>   kubectl get sa devuser -n dev-team -o yaml
>   ```

**Pro tip:** Save the service account YAML to a file for documentation:

```bash
kubectl get sa devuser -n dev-team -o yaml > serviceaccount.yml
```

---

## Step 4: Create a Role

```bash
kubectl create role devuser-role --resource=pods --verb=get,list,watch,delete,create -n dev-team --dry-run=client -o yaml > dev-role.yml
```

Then apply it:

```bash
kubectl apply -f dev-role.yml
```

> **Role vs ClusterRole — CRITICAL DIFFERENCE:**
>
> | | Role | ClusterRole |
> |---|---|---|
> | **Scope** | Single namespace only | Entire cluster |
> | **Use for** | Namespace-scoped resources (pods, services, deployments) | Cluster-scoped resources (namespaces, nodes, PVs) |
> | **Bound with** | RoleBinding | ClusterRoleBinding |
>
> **Common mistake:** If you put `namespaces` in a `Role`'s resources, it **won't work** because namespaces
> are a cluster-scoped resource. You'll get a "Forbidden" error like:
> ```
> Error from server (Forbidden): namespaces is forbidden: User "system:serviceaccount:..."
> cannot list resource "namespaces" in API group "" at the cluster scope
> ```
>
> **Fix:** Use `ClusterRole` + `ClusterRoleBinding` for cluster-scoped resources.
>
> **Quick rule:**
> - Pods, Services, Deployments, ConfigMaps → `Role` + `RoleBinding`
> - Namespaces, Nodes, PersistentVolumes → `ClusterRole` + `ClusterRoleBinding`

---

## Step 5: Create a RoleBinding

```bash
kubectl create rolebinding devuser-role --role=devuser-role --serviceaccount=dev-team:devuser -n dev-team --dry-run=client -o yaml > dev-rolebinding.yml
```

Then apply it:

```bash
kubectl apply -f dev-rolebinding.yml
```

> **Key Learnings about RoleBindings:**
>
> **1. Subjects must match the actual identity type:**
>
> If you authenticate with a **ServiceAccount token**, the subject must be:
> ```yaml
> subjects:
>   - kind: ServiceAccount     # NOT "User"
>     name: devuser            # must match actual SA name in cluster
>     namespace: dev-team      # required for ServiceAccount subjects
> ```
>
> If you authenticate with a **client certificate (x509)**, the subject must be:
> ```yaml
> subjects:
>   - kind: User
>     name: user@example.com   # CN from the certificate
>     apiGroup: rbac.authorization.k8s.io
> ```
>
> **Using the wrong kind (e.g., `User` when you have a SA token) will silently fail — no error, just "Forbidden" on every request.**
>
> **2. The roleRef name must exactly match the Role/ClusterRole name.**
> Double-check this — a typo here means the binding does nothing.
>
> **3. One RoleBinding can have multiple subjects** (for adding more developers with the same permissions):
> ```yaml
> subjects:
>   - kind: ServiceAccount
>     name: devuser-1
>     namespace: dev-team
>   - kind: ServiceAccount
>     name: devuser-2
>     namespace: dev-team
> ```
>
> **4. Adding a new developer with the same role:**
> You do NOT need to recreate the Role — just add a new ServiceAccount and add it as a subject to the existing RoleBinding.

---

## Step 6: Generate a Token for the Service Account

```bash
kubectl create token devuser -n dev-team
```

To create a **long-lived token**, add `--duration` at the end:

```bash
# 30 days
kubectl create token devuser -n dev-team --duration=720h

# 1 year
kubectl create token devuser -n dev-team --duration=8760h
```

> **Token Expiry Warning:**
> By default, tokens are **short-lived (1 hour)**. For real developer access, always set a duration.
> For production environments, consider using a proper identity provider (OIDC with Azure AD, Google, Okta) instead of static tokens.

---

## Step 7: Set Up Credentials in Kubeconfig

```bash
kubectl config set-credentials devuser --token="(generated token here)"
```

> **What this does:**
> Saves the token in your local `~/.kube/config` file under a user entry.
> The `--user` name here (e.g., `devuser`) is what you'll reference when creating a context.
> This name must match an existing entry in `users:` of kubeconfig when used in `set-context --user=`.

---

## Step 8: Create a Context for the User

```bash
kubectl config set-context devuser@docker-desktop --user=devuser --namespace=dev-team --cluster=docker-desktop
```

> **Context naming:**
> The context name (`devuser@docker-desktop`) can be **anything you want** — it's just a local label.
> But the three values it points to must match real things:
>
> | Flag | Must match |
> |---|---|
> | `--cluster` | An existing cluster entry in kubeconfig |
> | `--user` | An existing user/credentials entry in kubeconfig |
> | `--namespace` | A real namespace in the cluster |

---

## Step 9: Switch to the Context (or Give It to the Developer)

```bash
kubectl config use-context devuser@docker-desktop
```

> **For production — distributing access to developers:**
>
> Option A: Generate a **standalone kubeconfig file** for each developer:
> ```yaml
> apiVersion: v1
> kind: Config
> clusters:
>   - cluster:
>       server: https://kubernetes.docker.internal:6443
>       certificate-authority-data: <ca-data>
>     name: docker-desktop
> contexts:
>   - context:
>       cluster: docker-desktop
>       user: devuser
>       namespace: dev-team
>     name: devuser-context
> current-context: devuser-context
> users:
>   - name: devuser
>     user:
>       token: <their-token>
> ```
>
> The developer uses it with:
> ```bash
> export KUBECONFIG=devuser-config.yaml
> kubectl get pods
> ```
>
> Option B: Give them the token and cluster details — they set up their own kubeconfig.

---

## Step 10: Test the RBAC Permissions

**Always test after setting up RBAC!**

Check if a specific action is allowed:

```bash
kubectl auth can-i delete pods
kubectl auth can-i create deployments
kubectl auth can-i list namespaces
```

Check all permissions in a namespace:

```bash
kubectl auth can-i --list -n dev-team
```

> **Testing tip:** Switch to the developer's context first, then run these commands.
> This verifies the permissions from the developer's perspective.

---

## Bonus: Create a Pod

```bash
kubectl run nginx-pod --image=nginx:latest --restart=Never --dry-run=client -o yaml
```

> **Common mistakes when creating pods:**
> - Use `=` not `:` for flags: `--image=nginx:latest` (not `--image:nginx:latest`)
> - Don't put `pod` before the name: `kubectl run nginx-pod` (not `kubectl run pod nginx-pod`)
> - No underscores in resource names: `nginx-pod` (not `nginx_pod`)

---

## Common kubectl Syntax Reminders

```bash
# Deleting resources — always specify the resource type first
kubectl delete ns my-namespace        # correct
kubectl delete my-namespace           # WRONG — thinks "my-namespace" is a resource type

# Viewing API resources — it's a command, not a resource
kubectl api-resources                 # correct
kubectl get api-resources             # WRONG
```

---

## Important Reminders

1. **Always save to files first, then apply.** Don't just run `kubectl create` imperatively — save the YAML with `--dry-run=client -o yaml > file.yml`, review it, then `kubectl apply -f file.yml`. This way you have a record of everything.

2. **The RBAC chain must be complete:**
   ```
   ServiceAccount → RoleBinding → Role → Permissions
   ```
   If any link is broken (wrong name, wrong kind, wrong namespace), access is denied.

3. **How Kubernetes resolves identity:**
   ```
   Token-based auth → identity = system:serviceaccount:<namespace>:<sa-name>
   Certificate auth → identity = User:<CN-from-cert>
   ```
   Your RoleBinding subjects must match this identity exactly.

4. **The full authentication flow:**
   ```
   kubectl get pods
       ↓
   kubeconfig (context → user → token)
       ↓
   API Server: Authentication (who are you?)
       ↓
   API Server: Authorization/RBAC (what can you do?)
       ↓
   RoleBinding matches subject? → Role allows verb+resource? → ALLOW/DENY
   ```
