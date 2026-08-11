# Domain Routing Implementation Guide

## ✅ What Has Been Implemented

### 1. Domain-Based Routing Logic
- **Location**: `backend/services/site_service.py`
- **Function**: `get_site_by_domain()`
- **Features**:
  - Handles exact domain matches
  - Handles `www` prefix variations (www.domain.com ↔ domain.com)
  - Only returns published and active sites
  - Eager loads domain relationship

### 2. Public Site Routes
- **Location**: `backend/api/v1/routes_public_site.py`
- **Routes**:
  - `GET /` - Homepage (blog listing or custom homepage page)
  - `GET /posts/{slug}` - Individual blog posts
  - `GET /category/{slug}` - Category pages
  - `GET /page/{slug}` - Static pages
  - `GET /feed.xml` - RSS feed
  - `GET /sitemap.xml` - Sitemap
  - `GET /templates/default/assets/{file_path}` - Static assets

### 3. Domain Routing Middleware
- **Location**: `backend/middleware/domain_routing.py`
- **Purpose**: Logs and monitors domain routing for debugging
- **Behavior**: Checks if request is for custom domain, logs for debugging

### 4. Root Endpoint Handling
- **Location**: `backend/main.py`
- **Behavior**: 
  - Returns API info for Railway domains
  - Custom domains are handled by public site router (mounted first)

## 🔧 How It Works

### Request Flow

```
1. User visits: https://yourdomain.com
   ↓
2. DNS resolves to Railway IP
   ↓
3. Railway routes to backend service
   ↓
4. DomainRoutingMiddleware checks Host header
   ↓
5. FastAPI matches route:
   - If custom domain → routes_public_site router handles it
   - If Railway domain → root endpoint returns API info
   ↓
6. get_site_by_domain() looks up site by domain name
   ↓
7. Site content is served
```

### Route Matching Order

Routes are matched in registration order:

1. **Public Site Router** (mounted first) - handles custom domains
2. **API Routes** - handle `/api/v1/*` requests
3. **Root Endpoint** - handles Railway domain root requests

## 📋 Setup Requirements

### 1. DNS Configuration

For each domain, add DNS records:

**CNAME Record:**
```
Type: CNAME
Name: @ (or www)
Value: web-production-xxxxx.up.railway.app
TTL: 3600
```

### 2. Railway Custom Domain Setup

**For each user domain:**

1. Go to Railway Dashboard
2. Select **Backend** service
3. Go to **Settings** → **Networking**
4. Click **"Add Custom Domain"**
5. Enter domain name (e.g., `yourdomain.com`)
6. Wait 5-30 minutes for SSL certificate provisioning

**Important**: You need to add each domain manually in Railway. Railway doesn't support wildcard domains automatically.

### 3. Domain Verification in Platform

1. User adds domain in your platform
2. Platform verifies ownership via TXT record
3. Domain status becomes "verified"
4. User creates site and links domain
5. Site must be published and active

## 🚀 Testing Domain Routing

### Test Custom Domain

```bash
# Test domain resolution
dig yourdomain.com
nslookup yourdomain.com

# Test site access
curl -H "Host: yourdomain.com" https://your-backend.railway.app/
```

### Test Railway Domain

```bash
# Should return API info
curl https://your-backend.railway.app/
```

## 🔍 Troubleshooting

### Site Not Found (404)

**Check:**
1. Domain is verified in platform (TXT record)
2. Site is created and linked to domain
3. Site status is "published"
4. Site is "active"
5. DNS is pointing to Railway
6. Custom domain added in Railway

**Debug:**
```python
# Check database
SELECT d.name, d.site_id, ps.id, ps.status, ps.is_active 
FROM domains d 
LEFT JOIN published_sites ps ON d.site_id = ps.id 
WHERE d.name = 'yourdomain.com';
```

### Domain Not Resolving

**Check:**
1. DNS records are correct
2. DNS propagation (can take 48 hours)
3. Railway custom domain status

**Debug:**
```bash
# Check DNS
dig yourdomain.com
nslookup yourdomain.com

# Check Railway logs
railway logs --service web | grep "yourdomain.com"
```

### SSL Certificate Issues

**Check:**
1. Custom domain added in Railway
2. DNS is correctly configured
3. Wait 30 minutes for certificate provisioning
4. Check Railway dashboard → Custom Domain status

## 📝 Important Notes

### Railway Domain Limitations

- **No Wildcard Support**: Each domain must be added manually in Railway
- **SSL Auto-Provisioning**: Railway automatically provisions SSL certificates
- **DNS Required**: DNS must point to Railway for SSL to work

### Domain Matching

The system handles:
- Exact matches: `yourdomain.com`
- www variations: `www.yourdomain.com` ↔ `yourdomain.com`
- Case insensitive matching

### Performance

- Domain lookups are cached in middleware
- Database queries use indexes on `domain.name` and `site_id`
- Eager loading prevents N+1 queries

## 🎯 Next Steps

1. **Add domains to Railway**: For each user domain, add it as a custom domain in Railway backend service
2. **Configure DNS**: Users need to point their DNS to Railway
3. **Test**: Verify sites are accessible at their domains
4. **Monitor**: Check Railway logs for domain routing issues

## 🔐 Security Considerations

- Only published and active sites are served
- Domain verification ensures ownership
- SSL certificates are automatically provisioned
- CORS is configured for API endpoints only

## 📚 Related Files

- `backend/services/site_service.py` - Domain lookup logic
- `backend/api/v1/routes_public_site.py` - Public site routes
- `backend/middleware/domain_routing.py` - Domain routing middleware
- `backend/main.py` - Application setup and routing
- `DOMAIN_ROUTING_SETUP.md` - Setup instructions

