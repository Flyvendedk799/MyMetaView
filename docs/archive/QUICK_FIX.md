# Quick Fix for Database Column Errors

## The Problem
Your application is failing because two database columns are missing:
- `domains.site_id` - Referenced by the Domain model but doesn't exist in the database
- `previews.composited_image_url` - Referenced by the Preview model but doesn't exist in the database

## Immediate Solution

### Option 1: Run SQL Script (Fastest - Recommended for Production)

Connect to your PostgreSQL database and run:

```bash
psql $DATABASE_URL -f fix_missing_columns.sql
```

Or copy-paste the SQL commands from `fix_missing_columns.sql` into your database client.

### Option 2: Run Alembic Migrations

From your project root:

```bash
alembic -c alembic.ini upgrade head
```

This will apply all pending migrations including the ones that add these columns.

### Option 3: Manual SQL (If above don't work)

Run these commands in your database:

```sql
-- Add missing columns
ALTER TABLE previews ADD COLUMN IF NOT EXISTS composited_image_url VARCHAR;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS site_id INTEGER;

-- Add foreign key (if published_sites table exists)
ALTER TABLE domains 
ADD CONSTRAINT fk_domains_site 
FOREIGN KEY (site_id) REFERENCES published_sites(id);

-- Add index
CREATE INDEX IF NOT EXISTS ix_domains_site_id ON domains(site_id);
```

## What I Fixed

1. ✅ Cleaned up duplicate migration code in `backend/main.py`
2. ✅ Improved migration error handling
3. ✅ Created SQL script (`fix_missing_columns.sql`) for immediate fixes
4. ✅ Created migration guide (`MIGRATION_FIX.md`)

## After Running the Fix

Restart your application. The errors should be resolved and you should be able to:
- Add sites in the dashboard
- View previews
- View domains

## Prevention

The migrations should run automatically on startup in production mode. If they don't, check:
1. `ENV=production` is set
2. Check application logs for migration errors
3. Run migrations manually if needed

