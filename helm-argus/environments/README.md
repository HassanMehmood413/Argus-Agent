# Environment-Specific Configurations

This folder contains values files for different environments.

## 📁 Files

| File | Environment | Use Case |
|------|-------------|----------|
| `values-dev.yaml` | Development | Local Minikube/Docker Desktop testing |
| `values-staging.yaml` | Staging | QA testing before production |
| `values-prod.yaml` | Production | Live production deployment |

## 🎯 Quick Usage

### Development
```bash
helm install argus .. \
  --values values-dev.yaml \
  --namespace dev-argus \
  --create-namespace
```

### Staging
```bash
helm install argus .. \
  --values values-staging.yaml \
  --set postgresql.auth.password="$POSTGRES_PASSWORD" \
  --set redis.auth.password="$REDIS_PASSWORD" \
  --namespace staging-argus \
  --create-namespace
```

### Production
```bash
# First create secrets
kubectl create secret generic postgres-secret \
  --from-literal=postgres-password="$POSTGRES_PASSWORD" \
  --from-literal=password="$POSTGRES_PASSWORD" \
  --namespace argus

kubectl create secret generic redis-secret \
  --from-literal=redis-password="$REDIS_PASSWORD" \
  --namespace argus

# Then deploy
helm install argus .. \
  --values values-prod.yaml \
  --namespace argus \
  --create-namespace
```

## 🔑 Key Differences

| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| **Replicas** | 1 | 2 | 3 |
| **Persistence** | ❌ Disabled | ✅ 5Gi | ✅ 20Gi |
| **Resources** | Small (500m/512Mi) | Medium (1000m/1Gi) | Large (2000m/2Gi) |
| **Dry Run** | ✅ Yes | ❌ No | ❌ No |
| **Monitoring** | ❌ Disabled | ✅ Enabled | ✅ Enabled |
| **Jira** | ❌ Disabled | ✅ Enabled | ✅ Enabled |
| **Redis Auth** | ❌ Disabled | ✅ Enabled | ✅ Enabled |
| **HA** | ❌ No | ⚠️ Partial | ✅ Full |
| **Auto-scaling** | ❌ No | ✅ Yes (2-5) | ✅ Yes (3-10) |

## 📝 Customization

To customize for your needs:

1. Copy a template:
   ```bash
   cp values-dev.yaml values-my-env.yaml
   ```

2. Edit the values

3. Deploy with your custom values:
   ```bash
   helm install argus .. --values values-my-env.yaml
   ```