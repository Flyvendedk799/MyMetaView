# Railway CLI Debugging Guide

This guide shows how to use Railway CLI to access logs and debug issues directly from the deployment platform.

## Prerequisites

Railway CLI is already installed and authenticated:
- ✅ Version: `railway 4.16.1`
- ✅ Logged in as: `tobiasflyvende@gmail.com`
- ✅ Project: `practical-renewal`
- ✅ Environment: `production`
- ✅ Service: `web`

## Quick Commands

### View Recent Logs
```bash
# Last 50 lines (default)
railway logs

# Last 100 lines
railway logs --tail 100

# Follow logs in real-time
railway logs --follow
```

### View Logs from Specific Service
```bash
# If you have multiple services
railway logs --service web
railway logs --service worker
```

### Check Service Status
```bash
# Current service status
railway status

# List all services (if multiple)
railway service
```

### View Environment Variables
```bash
# List all variables
railway variables

# Get specific variable
railway variables get DATABASE_URL
```

### Run Commands in Railway Environment
```bash
# Run migrations
railway run alembic upgrade head

# Run Python commands
railway run python -c "print('Hello from Railway')"

# Run with specific service
railway run --service web python manage.py migrate
```

## Common Debugging Scenarios

### 1. Check if Preview Generation is Working
```bash
railway logs --tail 200 | grep -i "preview\|error\|exception"
```

### 2. Monitor Cache Operations
```bash
railway logs --follow | grep -i "cache\|redis"
```

### 3. Check for Rendering Issues
```bash
railway logs --tail 500 | grep -i "gradient\|dither\|banding\|render"
```

### 4. Monitor API Requests
```bash
railway logs --follow | grep -i "POST\|GET\|HTTP"
```

### 5. Check Worker Jobs
```bash
railway logs --tail 200 | grep -i "job\|worker\|queue"
```

## Filtering Logs

### By Log Level
```bash
# Errors only
railway logs --tail 500 | grep -i "error\|exception\|failed"

# Warnings
railway logs --tail 500 | grep -i "warn"

# Info messages
railway logs --tail 500 | grep -i "info"
```

### By Component
```bash
# Preview generation
railway logs --tail 500 | grep -i "preview_generation\|generate_preview"

# Brand extraction
railway logs --tail 500 | grep -i "brand\|extract"

# Image generation
railway logs --tail 500 | grep -i "image\|gradient\|template"
```

## Real-time Monitoring

### Watch Logs Live
```bash
railway logs --follow
```

### Watch Specific Component
```bash
railway logs --follow | grep -i "preview\|error"
```

## Troubleshooting

### If logs are empty
```bash
# Check service status
railway status

# Verify you're in the right project
railway whoami
```

### If service not found
```bash
# List all services in project
railway service

# Switch to correct service
railway service web
```

## Example: Debugging Rendering Issues

```bash
# 1. Get recent logs
railway logs --tail 200 > recent_logs.txt

# 2. Search for rendering-related messages
railway logs --tail 500 | grep -i "gradient\|dither\|banding"

# 3. Monitor in real-time while testing
railway logs --follow | grep -i "preview\|render\|error"
```

## Integration with Development

You can pipe Railway logs into your local tools:

```bash
# Save logs to file
railway logs --tail 1000 > railway_logs_$(date +%Y%m%d_%H%M%S).txt

# Search logs locally
railway logs --tail 500 | grep "error" | tee errors.txt
```

## Next Steps

When debugging issues:
1. ✅ Use `railway logs --tail 200` to see recent activity
2. ✅ Use `railway logs --follow` to monitor in real-time
3. ✅ Filter by component/error type using grep
4. ✅ Check service status with `railway status`
5. ✅ Verify environment variables with `railway variables`

This gives you direct access to production logs without needing the Railway dashboard!

