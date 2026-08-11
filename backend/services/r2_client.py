"""Public asset storage: Cloudflare R2 primary, local disk fallback.

Every image the pipeline produces (screenshots, composited cards, crops)
flows through `upload_file_to_r2`. Historically this hard-required R2:
with the credentials missing or the API down, a fully rendered preview was
thrown away and the whole generation reported failure. Now the function
degrades to writing the bytes under `settings.MEDIA_ROOT` (inside
`backend/static`, already mounted at `/static`) and returning an absolute
URL on `settings.ASSET_BASE_URL`, so generation always succeeds and local
development works with zero cloud configuration.
"""
import logging
import os
import re

import boto3
from botocore.exceptions import ClientError

from backend.core.config import settings
from backend.services.retry_utils import sync_retry

logger = logging.getLogger(__name__)

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._-]")


def r2_configured() -> bool:
    """True when every setting needed to reach R2 is present."""
    return bool(
        settings.R2_ACCOUNT_ID
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_BUCKET_NAME
    )


def get_r2_client():
    """
    Get boto3 S3 client configured for Cloudflare R2.

    Returns:
        boto3 S3 client instance
    """
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",  # R2 uses "auto" region
    )


def store_file_locally(file_bytes: bytes, filename: str) -> str:
    """Write bytes under MEDIA_ROOT and return the public URL for them.

    `filename` may contain folder segments (e.g. "previews/saas/uuid.png");
    each segment is sanitized so a hostile key can't escape MEDIA_ROOT.
    """
    segments = [
        _SAFE_SEGMENT.sub("_", seg)
        for seg in filename.split("/")
        if seg not in ("", ".", "..")
    ]
    if not segments:
        raise ValueError(f"Unusable storage filename: {filename!r}")

    media_root = os.path.abspath(settings.MEDIA_ROOT)
    path = os.path.join(media_root, *segments)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(file_bytes)

    base = (settings.ASSET_BASE_URL or "http://localhost:8000").rstrip("/")
    url = f"{base}/static/media/{'/'.join(segments)}"
    logger.info(f"Stored asset locally: {path} -> {url}")
    return url


@sync_retry(max_attempts=3, base_delay=1.0, retry_on=(ClientError,))
def _upload_to_r2(file_bytes: bytes, filename: str, content_type: str) -> str:
    client = get_r2_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=filename,
        Body=file_bytes,
        ContentType=content_type,
        CacheControl="public, max-age=31536000",  # 1 year cache
    )

    # R2 public URLs can be:
    # 1. Custom domain (if R2_PUBLIC_BASE_URL is set to a custom domain)
    # 2. Public dev URL (if R2_PUBLIC_BASE_URL is set to pub-*.r2.dev)
    # 3. Fallback to bucket.account.r2.cloudflarestorage.com (requires public bucket)
    if settings.R2_PUBLIC_BASE_URL:
        base_url = settings.R2_PUBLIC_BASE_URL.rstrip('/')
        return f"{base_url}/{filename}"
    return (
        f"https://{settings.R2_BUCKET_NAME}.{settings.R2_ACCOUNT_ID}"
        f".r2.cloudflarestorage.com/{filename}"
    )


def upload_file_to_r2(file_bytes: bytes, filename: str, content_type: str) -> str:
    """
    Store a public asset and return its URL.

    Tries Cloudflare R2 when configured; any failure (or missing config)
    falls back to local disk under MEDIA_ROOT so the pipeline never loses
    a rendered image to a storage hiccup.
    """
    if r2_configured():
        try:
            return _upload_to_r2(file_bytes, filename, content_type)
        except Exception as e:
            logger.error(
                f"R2 upload failed ({type(e).__name__}); falling back to local storage"
            )
    return store_file_locally(file_bytes, filename)
