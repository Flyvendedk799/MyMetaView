# Nginx Docs Proxy Setup

This guide explains how to set up the `/docs` proxy so API documentation is accessible via `https://www.mymetaview.com/docs` instead of the Railway backend domain.

## How It Works

The frontend nginx server proxies requests to `/docs`, `/redoc`, and `/openapi.json` to the backend API. This allows users to access the API documentation through your custom domain with a valid SSL certificate.

## Required Railway Environment Variable

In your **Frontend** service on Railway, you need to set:

**Variable Name:** `BACKEND_API_URL`  
**Value:** Your backend Railway domain (e.g., `https://web-production-fc4e7.up.railway.app`)

**Important:** 
- Do NOT include `/api/v1` or any path - just the base URL
- Must use `https://` (not `http://`)
- This should be the same value as `VITE_API_BASE_URL` (but without the `/api/v1` suffix)

## Setup Steps

1. **Go to Railway Dashboard**
   - Select your **Frontend** service
   - Go to **Variables** tab

2. **Add Environment Variable**
   - Click **+ New Variable**
   - Name: `BACKEND_API_URL`
   - Value: `https://your-backend-service.railway.app` (your actual backend Railway domain)
   - Click **Add**

3. **Redeploy Frontend Service**
   - Railway will automatically redeploy when you add/modify variables
   - Or manually trigger: **Deployments** tab → **Redeploy**

4. **Verify**
   - After redeploy completes, visit `https://www.mymetaview.com/docs`
   - You should see the FastAPI interactive documentation
   - No SSL certificate errors should appear

## How Nginx Template Processing Works

The `nginx:alpine` Docker image automatically processes files in `/etc/nginx/templates/` with `.template` extension using `envsubst`. At container startup:

1. nginx entrypoint script finds `default.conf.template`
2. Runs `envsubst` to substitute `${BACKEND_API_URL}` with the actual environment variable value
3. Outputs the processed config to `/etc/nginx/conf.d/default.conf`
4. Starts nginx with the processed configuration

## Troubleshooting

### Docs Still Show Railway Domain

- Verify `BACKEND_API_URL` is set in Railway frontend service
- Check that the value matches your backend Railway domain exactly
- Ensure frontend service has been redeployed after adding the variable

### SSL Certificate Error

- Make sure you're accessing via `https://www.mymetaview.com/docs` (not `http://`)
- Verify your frontend custom domain has SSL certificate active in Railway
- Check Railway dashboard → Frontend service → Settings → Networking → Custom Domain status

### 502 Bad Gateway

- Verify `BACKEND_API_URL` points to the correct backend domain
- Check that backend service is running and accessible
- Verify backend service has valid SSL certificate

### Docs Page Shows 404

- Ensure backend service is running
- Check that FastAPI docs are enabled (they should be by default)
- Verify the backend URL in `BACKEND_API_URL` is correct

## Alternative: Use VITE_API_BASE_URL

If you prefer to reuse the existing `VITE_API_BASE_URL` variable, you can modify the nginx template to use that instead. However, note that `VITE_API_BASE_URL` is a build-time variable, so you'd need to ensure it's also available at runtime.

