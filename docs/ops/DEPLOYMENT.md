# Production Deployment Guide

This document outlines the deployment process for the Preview SaaS platform on Railway.

## Prerequisites

- Railway account
- PostgreSQL database (Railway PostgreSQL service)
- Redis instance (Railway Redis service)
- Cloudflare R2 bucket configured
- Stripe account with API keys
- Screenshot API account

## Environment Variables

### Required Environment Variables

Set these in Railway's environment variables section:

#### Core Configuration
- `ENV=production` - Set to production mode
- `DATABASE_URL` - PostgreSQL connection string (provided by Railway PostgreSQL)
- `SECRET_KEY` - Strong random secret key (generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- `REDIS_URL` - Redis connection string (provided by Railway Redis)

#### CORS & Frontend
- `CORS_ALLOWED_ORIGINS` - Comma-separated list of allowed origins (e.g., `https://app.example.com,https://example.com`)
- `FRONTEND_URL` - Frontend application URL (e.g., `https://app.example.com`)

#### OpenAI
- `OPENAI_API_KEY` - OpenAI API key for AI preview generation

#### Cloudflare R2
- `R2_ACCOUNT_ID` - Cloudflare R2 account ID
- `R2_ACCESS_KEY_ID` - R2 access key ID
- `R2_SECRET_ACCESS_KEY` - R2 secret access key
- `R2_BUCKET_NAME` - R2 bucket name
- `R2_PUBLIC_BASE_URL` - Public base URL for R2 assets

#### Screenshot System
- Uses Playwright Chromium (installed automatically via Dockerfile, no API key needed)

#### Stripe
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing secret
- `STRIPE_PRICE_TIER_BASIC` - Stripe price ID for Basic tier
- `STRIPE_PRICE_TIER_PRO` - Stripe price ID for Pro tier
- `STRIPE_PRICE_TIER_AGENCY` - Stripe price ID for Agency tier

#### Optional
- `LOG_LEVEL` - Logging level (default: INFO)
- `MAX_REQUEST_SIZE` - Maximum request body size in bytes (default: 10485760 = 10MB)
- `PLACEHOLDER_IMAGE_URL` - Fallback placeholder image URL

### Frontend Environment Variables

Set these for the frontend build:

- `VITE_API_BASE_URL` - Backend API URL (e.g., `https://api.example.com`)

## Backend Deployment

### 1. Create Railway Service

1. Create a new Railway project
2. Add PostgreSQL service
3. Add Redis service
4. Add a new service from GitHub repository

### 2. Configure Backend Service

1. Set root directory to project root
2. Set build command: `pip install -r backend/requirements.txt`
3. Set start command: `gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 2 --timeout 120 backend.main:app`
4. Set all required environment variables

### 3. Configure Worker Service

1. Create a new service in the same project
2. Set start command: `python -m backend.queue.worker`
3. Link to same PostgreSQL and Redis services
4. Set all required environment variables (same as backend)

### 4. Run Database Migrations

After first deployment, run migrations:

```bash
railway run alembic upgrade head
```

Or via Railway CLI:
```bash
railway run --service backend alembic upgrade head
```

## Frontend Deployment

### Option 1: Railway Static Service

1. Create a new static service in Railway
2. Set build command: `npm ci && npm run build`
3. Set output directory: `dist`
4. Set environment variable: `VITE_API_BASE_URL`

### Option 2: Docker Deployment

1. Build Docker image:
   ```bash
   docker build -f Dockerfile.frontend -t preview-frontend .
   ```

2. Deploy to Railway or other container platform

## Health Checks

- Backend health endpoint: `GET /health`
- Frontend health endpoint: `GET /health` (via nginx)

## Playwright Requirements on Railway

- Dockerfile installs Chromium automatically
- No special Railway config required
- Worker container must have >= 512MB RAM

## Monitoring

### Logs

- Backend logs: Available in Railway dashboard
- Worker logs: Available in Railway dashboard
- All logs use structured JSON format

### Metrics

- Request IDs: All requests include `X-Request-ID` header
- Request logging: Includes path, method, status code, latency
- Worker logging: Includes job ID, duration, success/failure

## Backup Strategy

### PostgreSQL Backups

Railway provides automatic daily backups for PostgreSQL. To restore:

1. Go to Railway PostgreSQL service
2. Click "Backups" tab
3. Select backup to restore

### R2 Backups

R2 data is automatically replicated. For manual backups:

1. Use R2 API or Cloudflare dashboard
2. Export bucket contents periodically

### Redis Persistence

Redis on Railway uses persistent storage. For manual backups:

1. Use Redis `SAVE` command
2. Export RDB file

## Data Retention

Run cleanup script periodically (via cron or scheduled job):

```bash
python backend/scripts/cleanup_old_data.py
```

Retention periods (configurable via env vars):
- Preview variants: 365 days (default)
- Analytics events: 90 days (default)
- Job failures: 30 days (default)

## Security Checklist

- [ ] CORS is restricted to production domains
- [ ] All secrets are in environment variables
- [ ] HTTPS is enforced (Railway default)
- [ ] Rate limiting is active
- [ ] Security headers are enabled
- [ ] Admin routes require admin role
- [ ] Sensitive data is not logged

## Troubleshooting

### Common Issues

1. **Database connection errors**: Check `DATABASE_URL` is correct
2. **Redis connection errors**: Check `REDIS_URL` is correct
3. **CORS errors**: Verify `CORS_ALLOWED_ORIGINS` includes frontend URL
4. **Worker not processing jobs**: Check worker service is running and connected to Redis

### Debug Mode

To enable debug logging, set:
- `LOG_LEVEL=DEBUG`

Note: Never set `ENV=development` in production.

