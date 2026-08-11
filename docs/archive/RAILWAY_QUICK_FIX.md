# Quick Fix for Railway - Run This Command

## Easiest Way: Railway CLI

Just run this one command in your terminal:

```bash
railway run python fix_database_columns_sqlalchemy.py
```

This script uses SQLAlchemy (which you already have) instead of psycopg2 directly.

## If You Don't Have Railway CLI

1. **Install Railway CLI**:
   ```bash
   npm i -g @railway/cli
   ```

2. **Login**:
   ```bash
   railway login
   ```

3. **Link to your project**:
   ```bash
   railway link
   ```

4. **Run the fix**:
   ```bash
   railway run python fix_database_columns_sqlalchemy.py
   ```

## Alternative: Railway Dashboard

1. Go to https://railway.app
2. Open your project
3. Click on your backend service
4. Look for "Run Command" or "Shell" option
5. Run: `python fix_database_columns_sqlalchemy.py`

## What Happens

The script will:
- ✅ Connect to your database
- ✅ Add `previews.composited_image_url` if missing
- ✅ Add `domains.site_id` if missing  
- ✅ Add foreign key and index if needed
- ✅ Show you what was fixed

**Safe to run multiple times** - it checks before adding anything.

## After Running

Your application should work! The errors about missing columns will be gone.

