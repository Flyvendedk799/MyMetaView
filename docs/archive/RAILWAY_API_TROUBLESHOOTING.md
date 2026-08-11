# Railway API Troubleshooting Guide

## "Not Authorized" Error

If you're getting "Not Authorized" even with a valid token, here are things to check:

### 1. Verify Token Format

Railway API tokens should be a long string. Make sure:
- No extra spaces before/after
- No newlines
- Copied completely (they're usually 100+ characters)

### 2. Check Token Permissions

Railway API tokens need specific permissions:
- Go to Railway Dashboard → Settings → API Tokens
- Check if your token has "Full Access" or the required scopes
- Some tokens might be project-specific

### 3. Railway GraphQL API May Not Be Public

**Important**: Railway's GraphQL API at `backboard.railway.app` might be:
- Internal only (not publicly accessible)
- Requiring different authentication
- Requiring Railway CLI authentication instead

### 4. Alternative: Use Railway CLI

If the GraphQL API doesn't work, Railway provides a CLI that might work better:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Add domain via CLI (if supported)
railway domain add <domain>
```

### 5. Manual Domain Addition (Recommended)

Since Railway's GraphQL API might not be publicly accessible, the **recommended approach** is:

1. **Create domain in your platform** (this works!)
2. **Add domain manually in Railway**:
   - Railway Dashboard → Backend Service → Settings → Networking
   - Click "Add Custom Domain"
   - Enter domain name
   - Railway provisions SSL automatically

### 6. Check Railway Documentation

Railway's public API documentation:
- https://docs.railway.com/reference/public-api
- Check if GraphQL API is documented
- Verify authentication method

### 7. Test Token Manually

You can test your token manually using curl:

```bash
curl -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ me { id email } }"}'
```

If this also fails with "Not Authorized", the API might not be publicly accessible.

## Current Status

The code supports automatic Railway domain addition **if** the API works, but **falls back gracefully** if it doesn't:

- ✅ Domain creation in your platform always works
- ✅ Manual Railway domain addition always works
- ⚠️ Automatic Railway API integration is optional

## Recommendation

For now, use **manual domain addition** in Railway:
1. User creates domain in your platform
2. You (or user) adds domain in Railway dashboard
3. Railway provisions SSL automatically
4. Domain works!

This is actually more reliable and gives you more control.

