# Railway API Investigation

## Findings

After checking Railway's official documentation and API:

### 1. API Endpoint
- **Correct endpoint**: `https://backboard.railway.com/graphql/v2` (`.com`, not `.app`)
- We were using: `https://backboard.railway.app/graphql/v2` ❌

### 2. Token Types
Railway has:
- **Personal API Token**: Full account access (required for mutations)
- **Project Token**: Scoped to one project (read-only, limited mutations)

### 3. Domain Management API

**IMPORTANT**: Railway's GraphQL API documentation does NOT show `customDomainCreate` mutation in their public API.

According to Railway's official API docs:
- The public API focuses on deployments, logs, and project management
- **Custom domain management is NOT exposed via the public GraphQL API**
- Domain management is only available through:
  1. Railway Dashboard (manual)
  2. Railway CLI (if supported)
  3. Internal/internal APIs (not public)

### 4. What Works

✅ **What Railway API supports:**
- Query projects, services, deployments
- View logs
- Manage deployments
- Project management

❌ **What Railway API does NOT support:**
- Custom domain creation (`customDomainCreate` mutation doesn't exist in public API)
- Domain management operations
- SSL certificate management

## Conclusion

**Railway's public GraphQL API does not support domain management.**

The `customDomainCreate` mutation we're trying to use doesn't exist in Railway's public API schema.

## Recommended Solution

Use **manual domain addition** in Railway Dashboard:
1. User creates domain in your platform ✅
2. Add domain manually: Railway Dashboard → Service → Settings → Networking → Add Custom Domain ✅
3. Railway provisions SSL automatically ✅

This is the only reliable way to add custom domains to Railway.

## Alternative: Railway CLI

Railway CLI might support domain management, but it requires:
- CLI installation
- Authentication via CLI
- Running commands manually or via scripts

Not suitable for automated SaaS platform integration.

