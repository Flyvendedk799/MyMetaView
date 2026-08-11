# Database Migration Fix Guide

## Problem
The application is experiencing errors because two database columns are missing:
1. `domains.site_id` - Foreign key to published_sites table
2. `previews.composited_image_url` - URL for composited preview images

## Solution Options

### Option 1: Run Alembic Migrations (Recommended)

Run the migrations using Alembic:

```bash
# From project root directory
alembic -c alembic.ini upgrade head
```

Or use the provided script:

```bash
python run_migrations.py
```

### Option 2: Run SQL Script Directly (Quick Fix)

If migrations fail or you need an immediate fix, run the SQL script directly against your PostgreSQL database:

```bash
# Connect to your database and run:
psql $DATABASE_URL -f fix_missing_columns.sql
```

Or copy the contents of `fix_missing_columns.sql` and run it in your database client.

### Option 3: Manual SQL Commands

Run these SQL commands directly in your database:

```sql
-- Add composited_image_url to previews table
ALTER TABLE previews ADD COLUMN IF NOT EXISTS composited_image_url VARCHAR;

-- Add site_id to domains table
ALTER TABLE domains ADD COLUMN IF NOT EXISTS site_id INTEGER;

-- Add foreign key constraint (if published_sites table exists)
ALTER TABLE domains 
ADD CONSTRAINT fk_domains_site 
FOREIGN KEY (site_id) REFERENCES published_sites(id);

-- Add index
CREATE INDEX IF NOT EXISTS ix_domains_site_id ON domains(site_id);
```

## Verification

After running migrations or SQL, verify the columns exist:

```sql
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name IN ('previews', 'domains') 
AND column_name IN ('composited_image_url', 'site_id')
ORDER BY table_name, column_name;
```

## Notes

- The migrations are idempotent (safe to run multiple times)
- They check for column existence before adding them
- The application should automatically run migrations on startup in production mode
- If migrations fail on startup, check the logs and run them manually

