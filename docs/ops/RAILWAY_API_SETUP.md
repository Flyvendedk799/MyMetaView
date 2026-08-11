# Railway API Setup for Automatic Domain Management

## Overview

Railway provides a GraphQL API that allows you to programmatically add custom domains. This enables automatic domain configuration when users add domains to your platform.

## ✅ What's Implemented

1. **Railway Domain Service** (`backend/services/railway_domain_service.py`)
   - `add_domain_to_railway()` - Add domain via API
   - `list_railway_domains()` - List all domains
   - `check_domain_exists_in_railway()` - Check if domain exists

2. **Automatic Domain Addition**
   - When user creates domain in platform, it's automatically added to Railway
   - No manual Railway dashboard steps needed
   - Automatic SSL provisioning

## 🔧 Setup Instructions

### Step 1: Get Railway API Token

**IMPORTANT**: Railway API tokens must be created with proper permissions.

1. Go to Railway Dashboard: https://railway.app
2. Click on your profile (top right) → **Settings** → **API Tokens**
3. Click **"Create Token"**
4. **Give it a descriptive name** (e.g., "Domain Management Token")
5. **Make sure it has full access** to your project
6. Click **"Create"**
7. **Copy the token immediately** - you won't see it again!
8. Store it securely

**Troubleshooting "Not Authorized" errors:**
- Delete the old token and create a new one
- Make sure the token has access to your project
- Verify the token is copied correctly (no extra spaces)
- Check that the token hasn't expired

### Step 2: Get Service ID

**Method 1: From Railway Dashboard (Easiest)**

1. Go to Railway Dashboard: https://railway.app
2. Select your **Backend** service (the one running your FastAPI app)
3. Click on the service name to open it
4. Look at the URL in your browser - it will be something like:
   ```
   https://railway.app/project/[PROJECT_ID]/service/[SERVICE_ID]
   ```
   The **SERVICE_ID** is the UUID after `/service/`

**Method 2: From Service Settings**

1. Go to Railway Dashboard
2. Select your **Backend** service
3. Click **Settings** (gear icon) in the top right
4. Scroll down to **Service Details**
5. The **Service ID** is shown there (UUID format, e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)

**Method 3: From Railway CLI**

If you have Railway CLI installed:
```bash
railway service
```

This will show your service ID.

### Step 3: Get Environment ID (Optional)

1. In Railway Dashboard → Your service
2. Go to **Settings** → **Environments**
3. Copy the **Environment ID** (usually "production" or UUID)

### Step 4: Set Environment Variables

In Railway Dashboard → Backend Service → Variables:

```
RAILWAY_TOKEN=your_api_token_here
RAILWAY_SERVICE_ID=your_service_id_here
RAILWAY_ENVIRONMENT_ID=your_environment_id (optional)
```

**Note**: Railway uses `RAILWAY_TOKEN` as the standard environment variable name. The code also supports `RAILWAY_API_TOKEN` for compatibility.

### Step 5: Redeploy Backend

Railway will automatically redeploy when you add environment variables.

## 🚀 How It Works

### When User Adds Domain

1. User adds domain in your platform
2. Platform verifies ownership (TXT record)
3. Platform calls Railway API automatically
4. Railway adds domain and provisions SSL
5. User configures DNS (CNAME to Railway)
6. Site is accessible!

### Code Flow

```python
# User creates domain
POST /api/v1/domains
{
  "name": "example.com",
  "environment": "production"
}

# Backend automatically:
1. Creates domain in database
2. Calls Railway API to add domain
3. Railway provisions SSL (5-30 minutes)
4. Returns domain with status
```

## 📋 DNS Configuration

Users still need to configure DNS:

```
Type: CNAME
Name: @ (or www)
Value: your-railway-backend.railway.app
```

## 🔍 Testing

### Test Railway API Connection

```python
from backend.services.railway_domain_service import list_railway_domains

# This should list all domains in Railway
domains = list_railway_domains()
print(domains)
```

### Test Domain Addition

When you create a domain in your platform, check Railway logs:
```
[INFO] Adding domain example.com to Railway via API
[INFO] Successfully added example.com to Railway: {...}
```

## ⚠️ Important Notes

### Rate Limits

Railway API may have rate limits. If you hit limits:
- Add domains in batches
- Use background jobs for bulk operations
- Cache domain existence checks

### Error Handling

The code handles Railway API errors gracefully:
- If API fails, domain is still created in database
- User can add domain manually in Railway if needed
- Errors are logged but don't break domain creation

### SSL Provisioning

- SSL certificates are provisioned automatically
- Takes 5-30 minutes after domain is added
- Check Railway dashboard for SSL status

## 🎯 Alternative: Wildcard Domain

If you prefer subdomains instead of custom domains:

1. **Add wildcard domain in Railway:**
   ```
   Railway Dashboard → Backend Service → Settings → Networking
   Add Custom Domain: *.yourplatform.com
   ```

2. **Configure DNS:**
   ```
   Type: CNAME
   Name: *
   Value: your-railway-backend.railway.app
   ```

3. **Update backend** to extract subdomain:
   ```python
   host = request.headers.get("host", "")
   subdomain = host.split(".")[0]  # site1.yourplatform.com -> site1
   ```

## 📚 Railway API Documentation

- GraphQL API: https://backboard.railway.app/graphql/v2
- API Docs: https://docs.railway.app/reference/api
- Authentication: Bearer token in Authorization header

## 🔐 Security

- Keep `RAILWAY_API_TOKEN` secret
- Don't commit tokens to git
- Use Railway environment variables
- Rotate tokens periodically

## ✅ Checklist

- [ ] Railway API token created
- [ ] Service ID obtained
- [ ] Environment variables set in Railway
- [ ] Backend redeployed
- [ ] Test domain creation
- [ ] Verify domain appears in Railway dashboard
- [ ] Check SSL certificate provisioning

## 🐛 Troubleshooting

### "RAILWAY_TOKEN not set"
- Check environment variable is set in Railway
- Railway uses `RAILWAY_TOKEN` as the standard name (also supports `RAILWAY_API_TOKEN`)
- Verify variable name is exactly `RAILWAY_TOKEN` (or `RAILWAY_API_TOKEN`)
- Redeploy service after adding variable

### "RAILWAY_SERVICE_ID not set"
- Get Service ID from Railway dashboard
- Set as environment variable
- Redeploy service

### "Railway API error: Unauthorized"
- Check API token is valid
- Verify token hasn't expired
- Regenerate token if needed

### Domain not appearing in Railway
- Check Railway logs for API errors
- Verify API token has correct permissions
- Check service ID is correct

### SSL not provisioning
- Wait 30 minutes after domain addition
- Check Railway dashboard → Custom Domain status
- Verify DNS is correctly configured
- Ensure domain is accessible via DNS

