# Complete Domain Routing Setup Guide

## The Problem

TXT record verification only proves domain ownership - it doesn't route traffic. For your sites to be accessible at their domains, you need:

1. ✅ **DNS A/CNAME records** pointing to Railway
2. ✅ **Railway custom domain configuration** for backend service
3. ✅ **Application routing** (already working)

## How Domain Routing Works

```
User visits: https://yourdomain.com
    ↓
DNS resolves to Railway IP
    ↓
Railway routes to your backend service
    ↓
Backend checks Host header
    ↓
Backend finds site by domain name
    ↓
Site is served
```

## Step-by-Step Setup

### Step 1: Configure DNS Records

For each domain you want to use for a site, add DNS records:

#### Option A: CNAME Record (Recommended)

**Type:** CNAME  
**Name:** `@` (for root domain) or `www` (for www subdomain)  
**Value:** Your Railway backend service domain (e.g., `web-production-xxxxx.up.railway.app`)

**Example:**
```
Type: CNAME
Name: @
Value: web-production-fc4e7.up.railway.app
TTL: 3600
```

#### Option B: A Record (If CNAME not supported)

**Type:** A  
**Name:** `@` or `www`  
**Value:** Railway's IP address (check Railway dashboard for current IP)

**Note:** Railway IPs can change, so CNAME is preferred.

### Step 2: Add Custom Domain in Railway

1. **Go to Railway Dashboard**
   - Select your **Backend** service (not frontend)
   - Go to **Settings** → **Networking**

2. **Add Custom Domain**
   - Click **"Add Custom Domain"**
   - Enter your domain (e.g., `yourdomain.com` or `www.yourdomain.com`)
   - Railway will automatically provision SSL certificate

3. **Wait for SSL Certificate**
   - Railway provisions SSL automatically via Let's Encrypt
   - Takes 5-30 minutes (usually faster)
   - Check status in Railway dashboard

### Step 3: Verify Domain in Your Platform

1. **In your platform dashboard:**
   - Go to Domains page
   - Verify domain shows as "verified" (TXT record check)
   - This proves ownership

2. **Create/Connect Site:**
   - Create a site and select the verified domain
   - Site will be linked to the domain

### Step 4: Test Domain Routing

1. **Wait for DNS propagation** (can take up to 48 hours, usually much faster)
2. **Visit your domain:** `https://yourdomain.com`
3. **Check browser console** for any errors
4. **Verify site loads correctly**

## Important Notes

### Backend vs Frontend Domains

- **Frontend domain** (`www.mymetaview.com`): Your main app dashboard
- **Backend custom domains** (`yourdomain.com`): Individual sites created by users

These are **separate**:
- Frontend = Your SaaS platform
- Backend custom domains = User sites

### Multiple Domains

You can add multiple custom domains to your Railway backend service:
- Each domain will route to the backend
- Backend checks Host header to find the correct site
- Each site can have its own domain

### DNS Propagation

After adding DNS records:
- **TTL (Time To Live)** determines how long DNS changes take
- Usually 1-4 hours, can be up to 48 hours
- Use `dig yourdomain.com` or `nslookup yourdomain.com` to check

## Troubleshooting

### Domain Not Resolving

**Check DNS:**
```bash
# Check if DNS is configured
dig yourdomain.com
nslookup yourdomain.com

# Should show Railway IP or CNAME
```

**Common Issues:**
- DNS records not added yet
- Wrong DNS record type (need A or CNAME, not TXT)
- DNS propagation still in progress
- Wrong Railway domain in CNAME

### Site Shows 404

**Check:**
1. Domain is verified in your platform (TXT record)
2. Site is created and linked to domain
3. Site status is "published"
4. Site is "active"

**Debug:**
- Check Railway backend logs for Host header
- Verify domain name matches exactly (case-sensitive)
- Check database: `SELECT * FROM domains WHERE name = 'yourdomain.com'`
- Check site: `SELECT * FROM published_sites WHERE domain_id = [domain_id]`

### SSL Certificate Issues

**If SSL not working:**
1. Wait 30 minutes for certificate provisioning
2. Check Railway dashboard → Custom Domain status
3. Ensure DNS is correctly configured
4. Try accessing via `https://` (not `http://`)

### CORS Errors

**If you see CORS errors:**
- This shouldn't happen for direct domain access
- CORS is only for API calls from frontend
- Check if you're accidentally making API calls from the site domain

## Railway Backend Custom Domain Setup

### Current Setup

Your backend service needs to accept custom domains. Railway handles this automatically when you:

1. Add custom domain in Railway dashboard
2. Configure DNS to point to Railway
3. Railway provisions SSL certificate

### Environment Variables

No special environment variables needed for domain routing. The backend automatically:
- Reads Host header from requests
- Looks up site by domain name
- Serves the correct site

## Testing Checklist

- [ ] DNS A/CNAME record added pointing to Railway
- [ ] Custom domain added in Railway backend service
- [ ] SSL certificate active in Railway dashboard
- [ ] Domain verified in your platform (TXT record)
- [ ] Site created and linked to domain
- [ ] Site status is "published"
- [ ] Site is "active"
- [ ] DNS propagated (check with `dig` or `nslookup`)
- [ ] Can access site at `https://yourdomain.com`
- [ ] Site content loads correctly

## Quick Reference

**DNS Setup:**
```
Type: CNAME
Name: @ (or www)
Value: web-production-xxxxx.up.railway.app
```

**Railway Setup:**
1. Backend service → Settings → Networking
2. Add Custom Domain
3. Wait for SSL certificate

**Platform Setup:**
1. Verify domain (TXT record)
2. Create site
3. Link domain to site
4. Publish site

## Need Help?

If domain routing isn't working:

1. **Check Railway logs:** `railway logs --service web`
2. **Check DNS:** `dig yourdomain.com`
3. **Check database:** Verify domain and site records
4. **Check Host header:** Backend logs show incoming Host header

The application code already handles domain routing correctly - the issue is usually DNS or Railway configuration.

