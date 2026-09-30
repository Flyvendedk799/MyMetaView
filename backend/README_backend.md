# Preview SaaS Backend API

FastAPI backend for the Preview SaaS Dashboard application.

## Production Deployment

For production deployment instructions, see [DEPLOYMENT.md](../DEPLOYMENT.md) in the project root.

## Overview

This backend provides REST API endpoints for managing domains, brand settings, previews, and analytics. Uses SQLAlchemy ORM with SQLite for local development (can be easily switched to PostgreSQL/MySQL for production).

## Tech Stack

- **Python 3.10+**
- **FastAPI** - Modern, fast web framework
- **Uvicorn** - ASGI server for running FastAPI
- **Pydantic** - Data validation using Python type annotations
- **SQLAlchemy 2.x** - ORM for database operations
- **SQLite** - Database for local development (default)

## Project Structure

```
backend/
├── main.py                 # FastAPI app entry point
├── api/
│   ├── v1/
│   │   ├── routes_domains.py      # Domain management endpoints
│   │   ├── routes_brand.py         # Brand settings endpoints
│   │   ├── routes_previews.py      # Preview gallery endpoints
│   │   └── routes_analytics.py     # Analytics endpoints
├── db/
│   ├── __init__.py         # Base declarative class
│   └── session.py         # Database engine and session management
├── models/                 # SQLAlchemy ORM models
│   ├── domain.py           # Domain ORM model
│   ├── brand.py            # BrandSettings ORM model
│   └── preview.py          # Preview ORM model
├── schemas/                # Pydantic schemas for request/response validation
├── core/
│   └── config.py           # Application configuration (includes DATABASE_URL)
└── storage/
    └── in_memory.py        # Deprecated - no longer used
```

## Setup Instructions

### 1. Create a Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

**Note:** The project uses BeautifulSoup4 and lxml for HTML parsing. If you encounter issues, install them separately:

```bash
python3 -m pip install beautifulsoup4 lxml
```

Or install from `requirements.txt`:

```bash
pip install -r backend/requirements.txt
```

### 4. Configure Database (Optional)

The backend uses SQLite by default for local development. The database file (`app.db`) will be created automatically in the project root on first run.

To use a different database, set the `DATABASE_URL` environment variable:

**Windows:**
```bash
set DATABASE_URL=sqlite:///./app.db
```

**macOS/Linux:**
```bash
export DATABASE_URL=sqlite:///./app.db
```

**For PostgreSQL (production):**
```bash
export DATABASE_URL=postgresql://user:password@localhost/dbname
```

**For MySQL (production):**
```bash
export DATABASE_URL=mysql+pymysql://user:password@localhost/dbname
```

If not set, defaults to `sqlite:///./app.db` (SQLite file in project root).

### 5. Run the Backend Server

From the project root directory:

```bash
uvicorn backend.main:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

**Note:** On first run, the database tables will be created automatically.

## API Endpoints

All endpoints are prefixed with `/api/v1`.

### Domains

- `GET /api/v1/domains` - List all domains
- `POST /api/v1/domains` - Create a new domain
- `GET /api/v1/domains/{domain_id}` - Get a domain by ID
- `DELETE /api/v1/domains/{domain_id}` - Delete a domain

### Brand Settings

- `GET /api/v1/brand` - Get current brand settings
- `PUT /api/v1/brand` - Update brand settings

### Previews

- `GET /api/v1/previews` - List all previews
- `GET /api/v1/previews?type=product` - Filter previews by type (product/blog/landing)

### Analytics

- `GET /api/v1/analytics/summary?period=7d` - Get analytics summary (period: 7d or 30d)

## Development

### Running Frontend and Backend Together

1. **Terminal 1 - Redis (if not running as service):**
   ```bash
   redis-server
   ```

2. **Terminal 2 - RQ Worker:**
   ```bash
   cd backend
   python -m backend.queue.worker
   ```

3. **Terminal 3 - Backend API:**
   ```bash
   cd backend
   uvicorn backend.main:app --reload
   ```

4. **Terminal 4 - Frontend:**
   ```bash
   npm run dev
   ```

The backend runs on port 8000, and the frontend runs on port 5173 (Vite default). CORS is configured to allow requests from the frontend dev server.

**Note:** The RQ worker must be running for background job processing. Without it, preview generation jobs will remain in "queued" status.

## Database

The application uses SQLAlchemy ORM with SQLite for local development. The database schema is automatically created on application startup.

### Database Schema

- **domains** - Stores domain information
- **brand_settings** - Stores brand configuration (single row, id=1)
- **previews** - Stores preview data

### Migrations (Alembic)

The project now uses **Alembic** for database migrations. Schema changes should be managed through Alembic migrations going forward.

#### Running Migrations

From the **project root** directory:

**Install Alembic (if not already installed):**
```bash
pip install -r backend/requirements.txt
```

**Run migrations to apply all pending changes:**
```bash
alembic -c alembic.ini upgrade head
```

**Check current migration status:**
```bash
alembic -c alembic.ini current
```

**View migration history:**
```bash
alembic -c alembic.ini history
```

**Rollback to previous migration:**
```bash
alembic -c alembic.ini downgrade -1
```

#### Current Migrations

- **20241123_01_add_user_id_columns**: Adds `user_id` foreign key columns to `domains`, `brand_settings`, and `previews` tables (preparing for Phase 7 multi-tenancy).

#### Development vs Production

- **Development**: The FastAPI app still uses `Base.metadata.create_all()` on startup for convenience, but Alembic migrations are the source of truth for schema evolution.
- **Production**: Always apply Alembic migrations before starting the application. Never rely on `create_all()` in production.

#### Starting Fresh (Optional)

If you want to start with a clean database during development:

1. Delete the existing `app.db` file (if using SQLite)
2. Run migrations: `alembic -c alembic.ini upgrade head`
3. Start the FastAPI server: `uvicorn backend.main:app --reload`

The tables will be created by Alembic, and the FastAPI `create_all()` will be a no-op since tables already exist.

#### Legacy Data Handling

**Note for Development:** Pre-multi-tenancy data (rows with `user_id` NULL) are ignored by queries. All business endpoints now filter by `current_user.id`, so any existing data without a `user_id` will effectively be invisible. For a clean development experience, you can delete `app.db` and run migrations fresh, or accept that old data is isolated from new user accounts.

## Multi-tenancy

The application implements **full multi-tenancy** - all business data is scoped to the authenticated user:

- **Domains**: Each user only sees and manages their own domains
- **Brand Settings**: Each user has their own brand configuration (auto-created on first access)
- **Previews**: Each user only sees previews they created
- **Analytics**: All metrics are computed from the current user's data only

### Testing Multi-tenancy

To verify data isolation:

1. **Create Account A:**
   - Sign up with email `userA@example.com`
   - Create some domains and check analytics
   - Note the data you see

2. **Create Account B:**
   - Sign up with email `userB@example.com` (or logout and signup)
   - Verify you see an empty state (no domains, zero analytics)
   - Create different domains/previews

3. **Verify Isolation:**
   - Login as Account A again
   - Confirm you only see Account A's data
   - Account B's domains/previews should not be visible
   - Analytics should reflect only Account A's data

4. **Brand Settings:**
   - Each user gets their own brand settings automatically
   - Changing settings in Account A does not affect Account B
   - Each user starts with default brand settings on first access

## OpenAI Configuration

The backend uses OpenAI's GPT-4o and DALL-E 3 APIs for AI-powered preview generation.

### Setup

1. **Get an OpenAI API Key:**
   - Sign up at https://platform.openai.com/
   - Navigate to API Keys section
   - Create a new secret key

2. **Set Environment Variable:**
   
   **Windows:**
   ```bash
   set OPENAI_API_KEY=sk-your-api-key-here
   ```
   
   **macOS/Linux:**
   ```bash
   export OPENAI_API_KEY=sk-your-api-key-here
   ```
   
      **For production (PythonAnywhere, etc.):**
   - Add `OPENAI_API_KEY` to your environment variables in the hosting dashboard
   - Or add to `.env` file (if using python-dotenv)

3. **Redis Configuration:**
   
   **Local Development:**
   - Default: `redis://localhost:6379/0`
   - Ensure Redis server is running (see Setup Instructions above)
   
   **Production (PythonAnywhere, etc.):**
   - Use external Redis provider (Redis Cloud, AWS ElastiCache, etc.)
   - Set `REDIS_URL` environment variable:
     ```bash
     export REDIS_URL=redis://username:password@host:port/db
     ```
   - Example: `redis://default:password@redis-12345.c1.us-east-1.rds.amazonaws.com:6379/0`

3. **Required Models:**
   - **GPT-4o**: Used for generating preview titles and descriptions
   - **DALL-E 3**: Used for generating preview images
   
   Ensure your OpenAI account has access to these models and sufficient credits.

4. **Testing:**
   - Queue a preview with `POST /api/v1/jobs/preview`. `POST /api/v1/previews/generate` returns 410.
   - Generation fails the job if `OPENAI_API_KEY` is missing, invalid, or out of credits.

### Cost Considerations

- **GPT-4o**: ~$0.01-0.03 per preview generation (depending on prompt length)
- **DALL-E 3**: ~$0.04 per image generation
- **Total**: ~$0.05-0.07 per preview generation

Consider implementing rate limiting and caching for production use.

## Current Limitations

- **Screenshot API Dependency**: Currently uses external screenshot API (can be swapped for Playwright)
- **No File Upload**: Logos cannot be uploaded yet
- **No Real-time Updates**: No WebSockets for real-time data
- **No Rate Limiting/Caching**: Not yet implemented
- **Client-side Snippet Limitations**: Social crawlers may not execute JS for meta tags.
- **R2 Bucket Configuration**: Requires manual R2 bucket setup and public access configuration
- **No Migrations**: Tables are created automatically; use Alembic for production migrations

## Next Steps (Future Phases)

- Implement authentication and authorization
- Add AI engine for automatic preview generation
- Add database migrations with Alembic
- Add real-time updates via WebSockets
- Add file upload for logos
- Add rate limiting and caching
- Add multi-tenancy support

## Environment Variables Summary

All required environment variables:

```bash
# Database
DATABASE_URL=sqlite:///./app.db

# Security
SECRET_KEY=your-secret-key

# OpenAI
OPENAI_API_KEY=sk-your-key

# Redis
REDIS_URL=redis://localhost:6379/0

# Cloudflare R2
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_BASE_URL=https://your-custom-domain.com  # Optional

# Screenshot system uses Playwright (no API key needed)

# Placeholder Image (Optional)
PLACEHOLDER_IMAGE_URL=https://your-cdn.com/placeholder.png
```

## Domain Verification

The system supports three methods for verifying domain ownership:

1. **DNS TXT Record**: Add a TXT record to your domain's DNS settings
2. **HTML File Upload**: Upload a verification file to your website's root directory
3. **Meta Tag**: Add a meta tag to your homepage HTML

### Testing Domain Verification

1. **Create a domain** via the frontend or API
2. **Start verification** by choosing a method (DNS, HTML, or Meta)
3. **For DNS method**:
   - Add the TXT record to your DNS provider (e.g., Cloudflare)
   - Wait 30-60 seconds for DNS propagation
   - Click "Check Verification"
4. **For Meta tag method** (easiest for local testing):
   - Add the meta tag to your homepage HTML
   - Click "Check Verification"
5. **Verify restrictions**: Try generating a preview for an unverified domain - it should fail with a 400 error
6. **Confirm snippet.js**: The public preview endpoint only returns data for verified domains

### Screenshot System (Playwright)

The preview engine uses Playwright Chromium to capture full-page screenshots.
Works automatically inside Railway using our Dockerfile.

Dependencies:
- playwright
- chromium browser bundle

## Testing the API

You can test the API using:

1. **Interactive Docs**: Visit http://localhost:8000/docs
2. **curl**:
   ```bash
   curl http://localhost:8000/api/v1/domains
   ```
3. **Python requests**:
   ```python
   import requests
   response = requests.get("http://localhost:8000/api/v1/domains")
   print(response.json())
   ```

