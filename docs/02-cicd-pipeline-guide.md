# CI/CD Pipeline Guide

Complete guide for the GitHub Actions CI/CD pipeline for Argus Agent.

---

## Table of Contents

1. [Pipeline Overview](#pipeline-overview)
2. [Branch Strategy](#branch-strategy)
3. [Workflow Files](#workflow-files)
4. [Environment Setup](#environment-setup)
5. [Deployment Flow](#deployment-flow)
6. [Rollback Procedures](#rollback-procedures)

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CI/CD Pipeline Flow                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Code Push                                                                  │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐              │
│  │  Lint   │────►│  Test   │────►│  Build  │────►│ Security│              │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘              │
│                                       │                                     │
│                                       ▼                                     │
│                              Push Docker Image                              │
│                                       │                                     │
│                    ┌──────────────────┼──────────────────┐                 │
│                    │                  │                  │                 │
│                    ▼                  ▼                  ▼                 │
│              ┌──────────┐      ┌──────────┐      ┌──────────┐             │
│              │   DEV    │      │ STAGING  │      │   PROD   │             │
│              │  (auto)  │      │  (auto)  │      │ (manual) │             │
│              └──────────┘      └──────────┘      └──────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Branch Strategy

### Branch Types

| Branch | Purpose | Deploys To | Auto-Deploy |
|--------|---------|------------|-------------|
| `feature/*` | New features/bugfixes | None | No |
| `develop` | Integration branch | Dev | Yes |
| `staging` | QA testing | Staging | Yes |
| `main` | Production releases | Production | Manual approval |

### Branch Flow

```
feature/fix-bug
       │
       │ PR (1 review)
       ▼
    develop ──────► argus-agent-dev
       │
       │ PR (1 senior review)
       ▼
    staging ──────► argus-agent-staging
       │
       │ PR (2 reviews: lead + devops)
       ▼
     main ────────► argus-agent-prod (manual approval)
```

### Creating Branches

```bash
# Create develop branch
git checkout main
git checkout -b develop
git push origin develop

# Create staging branch
git checkout main
git checkout -b staging
git push origin staging

# Create feature branch
git checkout develop
git checkout -b feature/my-new-feature
```

---

## Workflow Files

### 1. CI Workflow (`ci.yml`)

**Triggers:** All PRs and pushes to develop, staging, main

**Jobs:**
- `lint` - Runs Ruff linter and MyPy type checker
- `test` - Runs pytest with coverage
- `build` - Builds Docker image (no push)
- `security` - Runs Trivy security scan (staging/main only)

```yaml
# Trigger conditions
on:
  push:
    branches: [develop, staging, main]
  pull_request:
    branches: [develop, staging, main]
```

### 2. Deploy Dev (`deploy-dev.yml`)

**Triggers:** Push to develop branch

**Actions:**
1. Build Docker image with tag `dev-{sha}`
2. Push to GitHub Container Registry
3. Deploy to `argus-agent-dev` namespace
4. Send Slack notification

### 3. Deploy Staging (`deploy-staging.yml`)

**Triggers:** Push to staging branch

**Actions:**
1. Build Docker image with tag `staging-{sha}`
2. Push to GitHub Container Registry
3. Deploy to `argus-agent-staging` namespace
4. Run smoke tests
5. Send Slack notification

### 4. Deploy Production (`deploy-prod.yml`)

**Triggers:** Push to main branch

**Actions:**
1. Build Docker image with tag `prod-{sha}` and `latest`
2. Push to GitHub Container Registry
3. **Wait for manual approval**
4. Deploy to `argus-agent-prod` namespace
5. Verify deployment
6. Auto-rollback on failure
7. Send Slack notification

---

## Environment Setup

### Step 1: Create GitHub Environments

Go to: **Settings → Environments → New environment**

Create these environments:

| Environment | Protection Rules |
|-------------|-----------------|
| `development` | None |
| `staging` | Required reviewers: 1 |
| `production` | Required reviewers: 2, Wait timer: 5 min |

### Step 2: Configure Required Reviewers

1. Click on environment (e.g., `production`)
2. Check **"Required reviewers"**
3. Add reviewers (e.g., team leads, DevOps)
4. Click **"Save protection rules"**

### Step 3: Add Environment Secrets

Each environment can have its own secrets:

```
production:
  - KUBE_CONFIG_PROD

staging:
  - KUBE_CONFIG_STAGING

development:
  - KUBE_CONFIG_DEV
```

### Step 4: Configure Branch Protection

Go to: **Settings → Branches → Add rule**

**For `main` branch:**
- ✅ Require a pull request before merging
- ✅ Require approvals: 2
- ✅ Require status checks to pass
- ✅ Require branches to be up to date
- ✅ Include administrators

**For `staging` branch:**
- ✅ Require a pull request before merging
- ✅ Require approvals: 1
- ✅ Require status checks to pass

**For `develop` branch:**
- ✅ Require a pull request before merging
- ✅ Require approvals: 1

---

## Deployment Flow

### Scenario 1: Feature Development

```bash
# 1. Create feature branch
git checkout develop
git checkout -b feature/add-login

# 2. Make changes and commit
git add .
git commit -m "Add login feature"

# 3. Push and create PR
git push origin feature/add-login
# Create PR: feature/add-login → develop

# 4. After review and merge
# CI runs → Auto-deploys to DEV

# 5. Test in dev environment
kubectl get pods -n argus-agent-dev
```

### Scenario 2: Promote to Staging

```bash
# 1. Create PR: develop → staging
# In GitHub: New PR, base: staging, compare: develop

# 2. Senior developer reviews and approves

# 3. Merge PR
# CI runs → Auto-deploys to STAGING

# 4. QA tests in staging
kubectl get pods -n argus-agent-staging
```

### Scenario 3: Production Release

```bash
# 1. Create PR: staging → main
# In GitHub: New PR, base: main, compare: staging

# 2. Two reviewers must approve (lead + devops)

# 3. Merge PR
# CI runs → Builds image → Waits for approval

# 4. Go to Actions tab in GitHub
# Find "Deploy to Production" workflow
# Click "Review deployments"
# Select "production" environment
# Click "Approve and deploy"

# 5. Monitor deployment
kubectl get pods -n argus-agent-prod -w
```

---

## Rollback Procedures

### Automatic Rollback

The production workflow automatically rolls back if deployment fails:

```yaml
- name: Rollback on failure
  if: failure()
  run: |
    kubectl rollout undo deployment/argus-agent-deployment -n argus-agent-prod
```

### Manual Rollback

**Method 1: Undo last deployment**
```bash
kubectl rollout undo deployment/argus-agent-deployment -n argus-agent-prod
```

**Method 2: Rollback to specific revision**
```bash
# View history
kubectl rollout history deployment/argus-agent-deployment -n argus-agent-prod

# Rollback to specific revision
kubectl rollout undo deployment/argus-agent-deployment --to-revision=2 -n argus-agent-prod
```

**Method 3: Deploy specific image tag**
```bash
kubectl set image deployment/argus-agent-deployment \
  argus-agent=ghcr.io/your-org/argus-agent:prod-abc123 \
  -n argus-agent-prod
```

### Rollback Verification

```bash
# Check rollout status
kubectl rollout status deployment/argus-agent-deployment -n argus-agent-prod

# Check running pods
kubectl get pods -n argus-agent-prod

# Check which image is running
kubectl get deployment argus-agent-deployment -n argus-agent-prod -o jsonpath='{.spec.template.spec.containers[0].image}'
```

---

## Monitoring Deployments

### View Workflow Status

1. Go to GitHub repo → **Actions** tab
2. See all workflow runs
3. Click on specific run for details

### View Deployment Logs

```bash
# Pod logs
kubectl logs -f deployment/argus-agent-deployment -n argus-agent-prod

# Events
kubectl get events -n argus-agent-prod --sort-by='.lastTimestamp'
```

### Check Deployment Health

```bash
# Deployment status
kubectl get deployment -n argus-agent-prod

# Pod status
kubectl get pods -n argus-agent-prod

# Service status
kubectl get svc -n argus-agent-prod
```

---

## Troubleshooting

### Workflow Failed at "Configure kubectl"

**Cause:** Invalid kubeconfig secret

**Fix:**
1. Regenerate kubeconfig: `cat ~/.kube/config | base64 -w 0`
2. Update secret in GitHub
3. Re-run workflow

### Workflow Stuck at "Waiting for approval"

**Cause:** Production requires manual approval

**Fix:**
1. Go to Actions tab
2. Click on the workflow run
3. Click "Review deployments"
4. Approve the `production` environment

### Deployment Failed - ImagePullBackOff

**Cause:** Docker image not found or auth issue

**Fix:**
```bash
# Check image exists
docker pull ghcr.io/your-org/argus-agent:tag

# Check image pull secrets
kubectl get secrets -n argus-agent-prod
```

### Rollout Timeout

**Cause:** Pods not becoming ready

**Fix:**
```bash
# Check pod status
kubectl describe pod -l app=argus-agent -n argus-agent-prod

# Check events
kubectl get events -n argus-agent-prod

# Check logs
kubectl logs -l app=argus-agent -n argus-agent-prod
```

---

## Quick Reference Commands

```bash
# View workflow runs
gh run list

# Re-run failed workflow
gh run rerun <run-id>

# View deployment status
kubectl rollout status deployment/argus-agent-deployment -n argus-agent-prod

# Rollback
kubectl rollout undo deployment/argus-agent-deployment -n argus-agent-prod

# View deployment history
kubectl rollout history deployment/argus-agent-deployment -n argus-agent-prod
```
