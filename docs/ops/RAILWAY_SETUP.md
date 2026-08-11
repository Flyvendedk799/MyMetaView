# Railway Deployment Setup Guide

## Quick Fix: Frontend Can't Connect to Backend

### Problem
Frontend is trying to connect to `localhost:8000` instead of your Railway backend URL.

### Solution

1. **Find Your Backend Service URL**
   - Go to Railway Dashboard
   - Click on your **backend service**
   - Look for the **Public Domain** (e.g., `your-backend.railway.app`)
   - Or check the **Settings** tab → **Networking** → **Public Domain**

2. **Set Frontend Environment Variable**
   - Go to Railway Dashboard
   - Click on your **frontend service**
   - Go to **Variables** tab
   - Click **+ New Variable**
   - Name: `VITE_API_BASE_URL`
   - Value: `https://your-backend-service.railway.app`
   - **Important**: Do NOT include `/api/v1` - just the base URL
   - Click **Add**

3. **Trigger Rebuild**
   - Railway will automatically rebuild when you add/modify environment variables
   - Or manually trigger: Go to **Deployments** tab → Click **Redeploy**

4. **Verify**
   - After rebuild completes, open your frontend URL in browser
   - Open DevTools Console (F12)
   - You should see: `[App Startup] API Base URL: https://your-backend-service.railway.app/api/v1`
   - The warning about `VITE_API_BASE_URL` should be gone

## Complete Environment Variables Checklist

### Frontend Service Variables

| Variable | Value Example | Required |
|----------|--------------|----------|
| `VITE_API_BASE_URL` | `https://your-backend.railway.app` | ✅ Yes |
| `VITE_STRIPE_PRICE_TIER_BASIC` | `price_xxxxx` (from Stripe Dashboard) | ⚠️ For billing |
| `VITE_STRIPE_PRICE_TIER_PRO` | `price_xxxxx` (from Stripe Dashboard) | ⚠️ For billing |
| `VITE_STRIPE_PRICE_TIER_AGENCY` | `price_xxxxx` (from Stripe Dashboard) | ⚠️ For billing |

### Backend Service Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ENV` | `production` | ✅ Yes |
| `DATABASE_URL` | PostgreSQL connection string (auto-set by Railway PostgreSQL service) | ✅ Yes |
| `SECRET_KEY` | Random secret key (generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`) | ✅ Yes |
| `REDIS_URL` | Redis connection string (auto-set by Railway Redis service) | ✅ Yes |
| `CORS_ALLOWED_ORIGINS` | Your frontend URL, e.g., `https://your-frontend.railway.app` | ✅ Yes |
| `FRONTEND_URL` | Your frontend URL, e.g., `https://your-frontend.railway.app` | ✅ Yes |
| `OPENAI_API_KEY` | Your OpenAI API key | ✅ Yes |
| `R2_ACCOUNT_ID` | Cloudflare R2 account ID | ✅ Yes |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key ID | ✅ Yes |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret access key | ✅ Yes |
| `R2_BUCKET_NAME` | Cloudflare R2 bucket name | ✅ Yes |
| `R2_PUBLIC_BASE_URL` | Cloudflare R2 public URL | ✅ Yes |
| `STRIPE_SECRET_KEY` | Stripe secret key | ✅ Yes |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret | ✅ Yes |
| `STRIPE_PRICE_TIER_BASIC` | Stripe Price ID for Basic plan (e.g., `price_xxxxx`) | ⚠️ For billing |
| `STRIPE_PRICE_TIER_PRO` | Stripe Price ID for Pro plan (e.g., `price_xxxxx`) | ⚠️ For billing |
| `STRIPE_PRICE_TIER_AGENCY` | Stripe Price ID for Agency plan (e.g., `price_xxxxx`) | ⚠️ For billing |

## Verifying Backend is Running

1. **Check Backend Logs**
   - Go to Railway Dashboard → Backend Service → **Logs**
   - Look for: `Starting Preview SaaS API`
   - Should see environment info and "Database tables initialized successfully"

2. **Test Health Endpoint**
   ```bash
   curl https://your-backend-service.railway.app/health
   ```
   Should return: `{"status": "ok", "version": "1.0.0"}`

3. **Check API Docs**
   - Visit: `https://your-backend-service.railway.app/docs`
   - Should show FastAPI Swagger UI

## Common Issues

### Issue: Frontend still shows localhost after rebuild
**Solution**: 
- Double-check the variable name is exactly `VITE_API_BASE_URL` (case-sensitive)
- Ensure the value includes `/api/v1` at the end
- Check build logs to see if variable was available during build

### Issue: CORS errors in browser console
**Solution**:
- Ensure `CORS_ALLOWED_ORIGINS` in backend includes your frontend URL
- Format: `https://your-frontend.railway.app` (no trailing slash)
- Rebuild backend after changing CORS settings

### Issue: Backend not starting
**Solution**:
- Check backend logs for missing environment variables
- Verify all required variables are set (see checklist above)
- Check database and Redis connections are working

### Issue: "Upgrade to Pro" button doesn't work / Stripe checkout fails
**Solution**:
- Ensure Stripe Price IDs are set in both frontend and backend services
- Frontend: `VITE_STRIPE_PRICE_TIER_BASIC`, `VITE_STRIPE_PRICE_TIER_PRO`, `VITE_STRIPE_PRICE_TIER_AGENCY`
- Backend: `STRIPE_PRICE_TIER_BASIC`, `STRIPE_PRICE_TIER_PRO`, `STRIPE_PRICE_TIER_AGENCY`
- Get Price IDs from Stripe Dashboard → Products → Select Product → Pricing → Copy Price ID
- Buttons will be disabled if price IDs are not configured

## Testing the Connection

After setting up environment variables:

1. **Frontend Console** (Browser DevTools):
   ```
   [App Startup] API Base URL: https://your-backend.railway.app/api/v1
   [App Startup] Environment: production
   ```
   (No warning about missing VITE_API_BASE_URL)

2. **Try Signup/Login**:
   - Should connect to backend successfully
   - No `ERR_CONNECTION_REFUSED` errors
   - Check Network tab to see API calls going to Railway backend

3. **Backend Logs**:
   - Should show incoming requests with request IDs
   - Should show successful responses

