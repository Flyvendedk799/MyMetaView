# Multi-stage build for production backend
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY backend/ ./backend/
COPY alembic.ini ./

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Install fonts for preview image generation + Playwright + Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v
RUN pip install playwright
RUN playwright install --with-deps chromium

# Expose port (Railway will set PORT env var)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Kept below the Playwright/Chromium layers on purpose: this file changes far
# more rarely than they take to rebuild, so copying it last keeps them cached.
COPY backend-entrypoint.sh ./
RUN chmod +x /app/backend-entrypoint.sh

# Run migrations once, then hand off to the command below
ENTRYPOINT ["/app/backend-entrypoint.sh"]

# Default command (can be overridden by Railway)
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "backend.main:app"]

