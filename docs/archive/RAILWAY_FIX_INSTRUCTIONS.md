# How to Run Database Fix Script in Railway

## Option 1: Railway CLI (Easiest)

1. **Install Railway CLI** (if you don't have it):
   ```bash
   npm i -g @railway/cli
   ```

2. **Login to Railway**:
   ```bash
   railway login
   ```

3. **Link to your project** (if not already linked):
   ```bash
   railway link
   ```

4. **Run the fix script**:
   ```bash
   railway run python fix_database_columns.py
   ```

This will run the script in your Railway environment with access to all environment variables including `DATABASE_URL`.

## Option 2: Railway Dashboard (One-off Command)

1. Go to your Railway project dashboard
2. Click on your **backend service**
3. Go to the **"Deployments"** tab
4. Click **"New Deployment"** or find the **"Run Command"** option
5. Run this command:
   ```bash
   python fix_database_columns.py
   ```

## Option 3: Add as a Script Command

You can also add this to your `package.json` or create a simple script that Railway can run.

## Option 4: Run via Railway Shell (if available)

If Railway provides shell access:
1. Open Railway dashboard
2. Go to your service
3. Click "Shell" or "Terminal"
4. Run:
   ```bash
   python fix_database_columns.py
   ```

## What the Script Does

The script will:
1. ✅ Connect to your PostgreSQL database using `DATABASE_URL`
2. ✅ Check if `previews.composited_image_url` exists, add it if missing
3. ✅ Check if `domains.site_id` exists, add it if missing
4. ✅ Add foreign key constraint and index if needed
5. ✅ Verify all columns were added successfully

The script is **idempotent** - safe to run multiple times.

## After Running

Once the script completes successfully:
1. Restart your Railway service (or it will restart automatically on next deployment)
2. The errors should be gone and you can:
   - Add sites in dashboard
   - View previews
   - View domains

## Troubleshooting

If you get an error about `psycopg2` not being found:
- Make sure your Railway environment has the dependencies installed
- The script uses `psycopg2-binary` which should be in your `requirements.txt`

If you get connection errors:
- Verify `DATABASE_URL` is set in Railway environment variables
- Check that your database service is running

