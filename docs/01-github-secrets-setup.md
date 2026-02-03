# GitHub Secrets Setup Guide

This document explains how to add and generate secrets for GitHub Actions CI/CD pipelines.

---

## Table of Contents

1. [Required Secrets](#required-secrets)
2. [How to Add Secrets in GitHub](#how-to-add-secrets-in-github)
3. [Generating Kubeconfig](#generating-kubeconfig)
4. [Generating Slack Webhook](#generating-slack-webhook)
5. [Environment-Specific Secrets](#environment-specific-secrets)

---

## Required Secrets

| Secret Name | Purpose | Required For |
|-------------|---------|--------------|
| `KUBE_CONFIG_DEV` | Kubernetes access for dev cluster | deploy-dev.yml |
| `KUBE_CONFIG_STAGING` | Kubernetes access for staging cluster | deploy-staging.yml |
| `KUBE_CONFIG_PROD` | Kubernetes access for prod cluster | deploy-prod.yml |
| `SLACK_WEBHOOK_URL` | Deployment notifications | All deploy workflows |

---

## How to Add Secrets in GitHub

### Step 1: Navigate to Settings

```
GitHub Repo → Settings → Secrets and variables → Actions
```

### Step 2: Add Repository Secret

1. Click **"New repository secret"**
2. Enter the **Name** (e.g., `KUBE_CONFIG_DEV`)
3. Enter the **Value** (the actual secret)
4. Click **"Add secret"**

### Step 3: Verify

After adding, you should see:
```
KUBE_CONFIG_DEV      Updated 2 minutes ago
KUBE_CONFIG_STAGING  Updated 2 minutes ago
KUBE_CONFIG_PROD     Updated 2 minutes ago
SLACK_WEBHOOK_URL    Updated 2 minutes ago
```

---

## Generating Kubeconfig

### For Docker Desktop (Local Testing)

**Linux/Mac/Git Bash:**
```bash
cat ~/.kube/config | base64 -w 0
```

**Windows PowerShell:**
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("$env:USERPROFILE\.kube\config"))
```

**Windows CMD:**
```cmd
certutil -encode %USERPROFILE%\.kube\config encoded.txt
type encoded.txt
```

> **Important:** The output must be ONE LINE with no line breaks.

### For Cloud Providers

**AWS EKS:**
```bash
aws eks update-kubeconfig --name my-cluster --region us-east-1
cat ~/.kube/config | base64 -w 0
```

**Google GKE:**
```bash
gcloud container clusters get-credentials my-cluster --zone us-central1-a
cat ~/.kube/config | base64 -w 0
```

**Azure AKS:**
```bash
az aks get-credentials --resource-group myResourceGroup --name myAKSCluster
cat ~/.kube/config | base64 -w 0
```

### Creating Separate Kubeconfigs (Production Best Practice)

Instead of using your personal kubeconfig, create a service account:

```bash
# 1. Create service account for CI/CD
kubectl create serviceaccount github-actions -n argus-agent-prod

# 2. Create cluster role binding
kubectl create clusterrolebinding github-actions-binding \
  --clusterrole=cluster-admin \
  --serviceaccount=argus-agent-prod:github-actions

# 3. Get the token
kubectl create token github-actions -n argus-agent-prod --duration=8760h

# 4. Create kubeconfig manually (see below)
```

**Minimal Kubeconfig Template:**
```yaml
apiVersion: v1
kind: Config
clusters:
  - name: my-cluster
    cluster:
      server: https://kubernetes-api-server:6443
      certificate-authority-data: <BASE64_CA_CERT>
contexts:
  - name: my-context
    context:
      cluster: my-cluster
      user: github-actions
current-context: my-context
users:
  - name: github-actions
    user:
      token: <SERVICE_ACCOUNT_TOKEN>
```

---

## Generating Slack Webhook

### Step 1: Create Slack App

1. Go to: https://api.slack.com/apps
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter App Name: `Argus Deployments`
5. Select your workspace

### Step 2: Enable Incoming Webhooks

1. In the app settings, click **"Incoming Webhooks"**
2. Toggle **"Activate Incoming Webhooks"** to ON
3. Click **"Add New Webhook to Workspace"**
4. Select the channel (e.g., `#deployments`)
5. Click **"Allow"**

### Step 3: Copy Webhook URL

You'll get a URL like:
```
https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
```

### Step 4: Test the Webhook

```bash
curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  -H 'Content-type: application/json' \
  -d '{"text":"Hello from GitHub Actions!"}'
```

---

## Environment-Specific Secrets

### GitHub Environments Setup

For additional security, use GitHub Environments:

```
GitHub Repo → Settings → Environments
```

| Environment | Secrets | Required Reviewers |
|-------------|---------|-------------------|
| `development` | `KUBE_CONFIG_DEV` | None |
| `staging` | `KUBE_CONFIG_STAGING` | 1 person |
| `production` | `KUBE_CONFIG_PROD` | 2 people |

### Adding Environment Secrets

1. Go to **Settings → Environments**
2. Click on environment (e.g., `production`)
3. Under **"Environment secrets"**, click **"Add secret"**
4. Add the kubeconfig for that specific environment

### Benefits of Environment Secrets

- Secrets are only available to workflows targeting that environment
- Required reviewers must approve before workflow runs
- Provides audit trail of who approved production deployments

---

## Security Best Practices

### DO:
- ✅ Use separate kubeconfigs for each environment
- ✅ Create dedicated service accounts for CI/CD
- ✅ Rotate secrets regularly
- ✅ Use environment protection rules for production
- ✅ Limit service account permissions (principle of least privilege)

### DON'T:
- ❌ Use personal kubeconfig in CI/CD
- ❌ Share production secrets with dev environment
- ❌ Commit secrets to the repository
- ❌ Use cluster-admin for CI/CD service accounts

---

## Troubleshooting

### "Permission denied" in workflow

Check that:
1. Secret name matches exactly (case-sensitive)
2. Kubeconfig is properly base64 encoded
3. Service account has required permissions

### "Invalid kubeconfig" error

Ensure:
1. No line breaks in the base64 string
2. Kubeconfig is valid: `kubectl cluster-info`
3. Certificate data is included

### "Slack notification failed"

Verify:
1. Webhook URL is correct
2. App is installed in the workspace
3. Channel still exists

---

## Quick Reference

```bash
# Encode kubeconfig (Linux/Mac)
cat ~/.kube/config | base64 -w 0

# Encode kubeconfig (Windows PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("$env:USERPROFILE\.kube\config"))

# Test Slack webhook
curl -X POST $SLACK_WEBHOOK_URL -H 'Content-type: application/json' -d '{"text":"Test"}'

# Verify kubectl access
kubectl cluster-info
kubectl get namespaces
```
