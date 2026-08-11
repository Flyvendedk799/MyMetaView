# Environment Variables Reference

Complete list of all environment variables used in the Preview SaaS platform.

## Backend Environment Variables

### Core Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENV` | No | `development` | Environment mode (`production` or `development`) |
| `DATABASE_URL` | Yes (prod) | `sqlite:///./app.db` | Database connection string |
| `SECRET_KEY` | Yes (prod) | Auto-generated | Secret key for JWT tokens |
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### CORS & Frontend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CORS_ALLOWED_ORIGINS` | Yes (prod) | Empty | Comma-separated list of allowed origins |
| `FRONTEND_URL` | Yes (prod) | `http://localhost:5173` | Frontend application URL |

### OpenAI

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes (prod) | Empty | OpenAI API key for AI preview generation |

### Redis

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | Yes (prod) | `redis://localhost:6379/0` | Redis connection string for job queue |

### Cloudflare R2

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `R2_ACCOUNT_ID` | Yes (prod) | Empty | Cloudflare R2 account ID |
| `R2_ACCESS_KEY_ID` | Yes (prod) | Empty | R2 access key ID |
| `R2_SECRET_ACCESS_KEY` | Yes (prod) | Empty | R2 secret access key |
| `R2_BUCKET_NAME` | Yes (prod) | Empty | R2 bucket name |
| `R2_PUBLIC_BASE_URL` | Yes (prod) | Empty | Public base URL for R2 assets |

### Screenshot System

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| *(None)* | N/A | N/A | Uses Playwright Chromium (installed via Dockerfile, no API key needed) |

### Stripe

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STRIPE_SECRET_KEY` | Yes (prod) | Empty | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Yes (prod) | Empty | Stripe webhook signing secret |
| `STRIPE_PRICE_TIER_BASIC` | No | Empty | Stripe price ID for Basic tier |
| `STRIPE_PRICE_TIER_PRO` | No | Empty | Stripe price ID for Pro tier |
| `STRIPE_PRICE_TIER_AGENCY` | No | Empty | Stripe price ID for Agency tier |

### Optional

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PLACEHOLDER_IMAGE_URL` | No | Placeholder URL | Fallback placeholder image URL |
| `MAX_REQUEST_SIZE` | No | `10485760` | Maximum request body size in bytes (10MB) |
| `PREVIEW_VARIANT_RETENTION_DAYS` | No | `365` | Days to retain preview variants |
| `ANALYTICS_EVENT_RETENTION_DAYS` | No | `90` | Days to retain analytics events |
| `JOB_FAILURE_RETENTION_DAYS` | No | `30` | Days to retain job failure records |

### Railway-Specific

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORT` | Yes | `8000` | Port to bind to (set by Railway) |
| `RAILWAY_PUBLIC_DOMAIN` | No | Empty | Railway public domain |
| `API_DOMAIN` | No | Empty | Custom API domain |

## Frontend Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | Yes (prod) | `http://localhost:8000` | Backend API base URL |
| `VITE_STRIPE_PRICE_TIER_BASIC` | No | Empty | Stripe price ID for Basic tier |
| `VITE_STRIPE_PRICE_TIER_PRO` | No | Empty | Stripe price ID for Pro tier |
| `VITE_STRIPE_PRICE_TIER_AGENCY` | No | Empty | Stripe price ID for Agency tier |
| `VITE_FRONTEND_BASE_URL` | No | `http://localhost:5173` | Frontend base URL |

## Production Checklist

Before deploying to production, ensure all required variables are set:

### Backend (Required)
- [ ] `ENV=production`
- [ ] `DATABASE_URL` (PostgreSQL)
- [ ] `SECRET_KEY` (strong random key)
- [ ] `REDIS_URL`
- [ ] `CORS_ALLOWED_ORIGINS`
- [ ] `FRONTEND_URL`
- [ ] `OPENAI_API_KEY`
- [ ] `R2_ACCOUNT_ID`
- [ ] `R2_ACCESS_KEY_ID`
- [ ] `R2_SECRET_ACCESS_KEY`
- [ ] `R2_BUCKET_NAME`
- [ ] `R2_PUBLIC_BASE_URL`
- [ ] Playwright Chromium (installed via Dockerfile)
- [ ] `STRIPE_SECRET_KEY`
- [ ] `STRIPE_WEBHOOK_SECRET`

### Frontend (Required)
- [ ] `VITE_API_BASE_URL`

## Generating Secret Keys

Generate a secure `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Security Notes

- Never commit `.env` files to version control
- Use Railway's environment variable management
- Rotate secrets regularly
- Use different keys for development and production

