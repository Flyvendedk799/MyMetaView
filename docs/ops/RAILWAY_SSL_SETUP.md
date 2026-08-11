# Railway SSL/HTTPS Setup Guide

## Why You're Seeing "Not Secure"

If you see "Ikke sikker" (Not secure) or "Not secure" in your browser, it means:
1. **You're accessing the site via HTTP** (`http://www.mymetaview.com`) instead of HTTPS (`https://www.mymetaview.com`)
2. **SSL certificate is still propagating** (can take up to 30 minutes)
3. **HTTP to HTTPS redirect isn't working** (we've now fixed this)

## How Railway SSL Works

Railway **automatically provisions SSL certificates** for custom domains:
- ✅ SSL certificates are **free** and **automatic**
- ✅ Railway handles SSL termination at their edge/load balancer
- ✅ Certificates are issued by Let's Encrypt
- ⏱️ Certificate provisioning can take **5-30 minutes** after adding domain

## What We've Fixed

1. ✅ **Added HTTP to HTTPS redirect** in `nginx.conf`
   - All HTTP traffic now redirects to HTTPS
   - Checks Railway's `X-Forwarded-Proto` header

## What You Need to Do

### Step 1: Wait for SSL Certificate (5-30 minutes)

After adding your custom domain in Railway:
1. Railway automatically requests SSL certificate from Let's Encrypt
2. Certificate provisioning takes **5-30 minutes** (usually faster)
3. You'll see certificate status in Railway dashboard

### Step 2: Check Railway Dashboard

1. Go to Railway Dashboard
2. Select your **Frontend** service
3. Go to **Settings** → **Networking**
4. Check your custom domain status:
   - ✅ **Active** = SSL is ready
   - ⏳ **Pending** = Still provisioning (wait a bit longer)
   - ❌ **Error** = Check DNS configuration

### Step 3: Access via HTTPS

**Important**: Always use `https://` when accessing your site:

- ✅ **Correct**: `https://www.mymetaview.com`
- ❌ **Wrong**: `http://www.mymetaview.com` (will show "Not secure")

### Step 4: Verify SSL is Working

After certificate is active:

1. Visit `https://www.mymetaview.com`
2. Check browser address bar:
   - Should show **lock icon** 🔒
   - Should say **"Sikker"** (Secure) or **"Secure"**
   - Should **NOT** say "Ikke sikker" (Not secure)

3. Click the lock icon to see certificate details:
   - Issued by: Let's Encrypt
   - Valid for: www.mymetaview.com

## Troubleshooting

### Still Seeing "Not Secure" After 30 Minutes?

1. **Check you're using HTTPS**:
   - Make sure URL starts with `https://` not `http://`
   - Clear browser cache and try again

2. **Check Railway Domain Status**:
   - Railway Dashboard → Frontend Service → Settings → Networking
   - Domain should show "Active" status
   - If "Pending", wait a bit longer

3. **Check DNS Configuration**:
   - DNS records must be correct for SSL to work
   - Verify CNAME or A record points to Railway

4. **Force Redeploy**:
   - Railway Dashboard → Frontend Service → Deployments
   - Click "Redeploy" to ensure latest nginx config is deployed

5. **Check Browser Console**:
   - Open DevTools (F12)
   - Look for SSL/certificate errors
   - Check Network tab for mixed content warnings

### Mixed Content Warnings

If you see mixed content warnings:
- Ensure all API calls use `https://`
- Check `VITE_API_BASE_URL` uses `https://` (not `http://`)
- Check `CORS_ALLOWED_ORIGINS` uses `https://` (not `http://`)

### Certificate Not Provisioning

If certificate stays "Pending" for more than 30 minutes:

1. **Verify DNS**:
   ```bash
   # Check DNS resolution
   nslookup www.mymetaview.com
   # Should return Railway's IP
   ```

2. **Check Railway Logs**:
   - Railway Dashboard → Frontend Service → Logs
   - Look for SSL/certificate errors

3. **Remove and Re-add Domain**:
   - Railway Dashboard → Frontend Service → Settings → Networking
   - Remove custom domain
   - Wait 5 minutes
   - Add it back
   - Wait for certificate provisioning

## Summary Checklist

- [ ] Added custom domain in Railway (✅ Done)
- [ ] DNS configured correctly (✅ Done)
- [ ] HTTP to HTTPS redirect added (✅ Done in code)
- [ ] Wait 5-30 minutes for SSL certificate
- [ ] Check Railway dashboard for certificate status
- [ ] Access site via `https://www.mymetaview.com` (not `http://`)
- [ ] Verify lock icon appears in browser
- [ ] Test all functionality works over HTTPS

## Quick Test

After SSL is active, test these URLs:

1. **HTTPS (should work)**:
   ```
   https://www.mymetaview.com
   ```

2. **HTTP (should redirect to HTTPS)**:
   ```
   http://www.mymetaview.com
   ```
   Should automatically redirect to `https://www.mymetaview.com`

## Expected Timeline

- **0-5 minutes**: Railway detects domain and starts certificate request
- **5-15 minutes**: Certificate usually provisioned (most common)
- **15-30 minutes**: Certificate definitely should be active
- **30+ minutes**: If still pending, troubleshoot DNS/configuration

## Need Help?

If SSL still isn't working after 30 minutes:
1. Check Railway support/docs
2. Verify DNS is correct
3. Check Railway logs for errors
4. Try removing and re-adding domain

