# Railway Domain Configuration for www.mymetaview.com

This guide explains what needs to be updated in Railway after switching to the custom domain `www.mymetaview.com`.

## ✅ What You've Already Done

- Added `www.mymetaview.com` as a custom domain in Railway (Frontend service)
- Confirmed DNS configuration

## 🔧 Required Railway Environment Variable Updates

You need to update environment variables in **both** your Frontend and Backend services:

### Frontend Service Environment Variables

Update these variables in your **Frontend** service:

1. **`VITE_API_BASE_URL`**
   - **Current**: `https://web-production-fc4e7.up.railway.app` (or similar Railway domain)
   - **Update to**: `https://[YOUR_BACKEND_RAILWAY_DOMAIN]` 
   - **Note**: This should be your backend service's Railway domain (not the custom domain). Keep the Railway domain here since the backend doesn't have a custom domain yet.

2. **`VITE_FRONTEND_BASE_URL`** (if set)
   - **Update to**: `https://www.mymetaview.com`
   - **Purpose**: Used for generating absolute URLs in the frontend

### Backend Service Environment Variables

Update these variables in your **Backend** service:

1. **`CORS_ALLOWED_ORIGINS`** ⚠️ **CRITICAL**
   - **Current**: `https://preview-production-002a.up.railway.app` (or similar)
   - **Update to**: `https://www.mymetaview.com`
   - **Important**: This must match your frontend domain exactly. Without this, API calls will fail with CORS errors.

2. **`FRONTEND_URL`**
   - **Current**: `https://preview-production-002a.up.railway.app` (or similar)
   - **Update to**: `https://www.mymetaview.com`
   - **Purpose**: Used for generating invite links, email links, etc.

3. **`RAILWAY_PUBLIC_DOMAIN`** (if set)
   - **Update to**: Your backend's Railway domain (e.g., `web-production-xxxxx.up.railway.app`)
   - **Purpose**: Used for internal Railway routing

4. **`API_DOMAIN`** (if set)
   - **Update to**: Your backend's Railway domain (e.g., `web-production-xxxxx.up.railway.app`)
   - **Purpose**: Used for API endpoint references

## 📋 Step-by-Step Railway Configuration

### Step 1: Update Frontend Service Variables

1. Go to your Railway dashboard
2. Select your **Frontend** service
3. Go to the **Variables** tab
4. Update:
   - `VITE_API_BASE_URL` → Keep as your backend Railway domain (e.g., `https://web-production-xxxxx.up.railway.app`)
   - `VITE_FRONTEND_BASE_URL` → Set to `https://www.mymetaview.com` (if it exists)

### Step 2: Update Backend Service Variables

1. Go to your Railway dashboard
2. Select your **Backend** service
3. Go to the **Variables** tab
4. Update:
   - `CORS_ALLOWED_ORIGINS` → `https://www.mymetaview.com` ⚠️ **MUST UPDATE**
   - `FRONTEND_URL` → `https://www.mymetaview.com` ⚠️ **MUST UPDATE**

### Step 3: Verify DNS Configuration

Ensure your DNS records are correctly configured:

- **Type**: CNAME (or A record if using IP)
- **Name**: `www` (or `@` for root domain)
- **Value**: Your Railway frontend service's Railway domain (Railway will provide this)

### Step 4: Redeploy Services

After updating environment variables:

1. **Frontend**: Railway will auto-redeploy when you update variables (or trigger a manual redeploy)
2. **Backend**: Railway will auto-redeploy when you update variables (or trigger a manual redeploy)

### Step 5: Test

1. Visit `https://www.mymetaview.com` - should load the frontend
2. Try logging in - should connect to backend API
3. Check browser console for any CORS errors
4. Check Railway logs for any connection issues

## 🔍 Troubleshooting

### CORS Errors

If you see CORS errors in the browser console:
- Verify `CORS_ALLOWED_ORIGINS` in backend includes `https://www.mymetaview.com` exactly
- Ensure no trailing slashes
- Check that backend service has been redeployed after variable change

### API Connection Errors

If frontend can't connect to backend:
- Verify `VITE_API_BASE_URL` in frontend points to your backend Railway domain
- Ensure backend service is running
- Check Railway logs for backend errors

### DNS Issues

If domain doesn't resolve:
- Verify DNS records are correct
- Wait for DNS propagation (can take up to 48 hours, usually much faster)
- Check Railway's custom domain status in the dashboard

## 📝 Summary Checklist

- [ ] Updated `CORS_ALLOWED_ORIGINS` in Backend service → `https://www.mymetaview.com`
- [ ] Updated `FRONTEND_URL` in Backend service → `https://www.mymetaview.com`
- [ ] Verified `VITE_API_BASE_URL` in Frontend service points to backend Railway domain
- [ ] Verified DNS configuration is correct
- [ ] Both services redeployed successfully
- [ ] Tested frontend loads at `https://www.mymetaview.com`
- [ ] Tested login/signup works
- [ ] No CORS errors in browser console

## 🎯 Quick Reference

**Frontend Domain**: `https://www.mymetaview.com`  
**Backend Domain**: `https://[your-backend-railway-domain].up.railway.app`

**Critical Variables**:
- Backend: `CORS_ALLOWED_ORIGINS=https://www.mymetaview.com`
- Backend: `FRONTEND_URL=https://www.mymetaview.com`
- Frontend: `VITE_API_BASE_URL=https://[backend-railway-domain]`

