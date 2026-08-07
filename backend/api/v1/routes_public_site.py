"""Public site serving routes - domain-based routing."""
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from backend.db.session import get_db
from backend.models.published_site import (
    PublishedSite, SitePost, SitePage, SiteCategory, SiteSettings
)
from backend.models.domain import Domain
from backend.services.site_service import get_site_by_domain
from backend.services.template_renderer import render_template

router = APIRouter(tags=["public-site"])

# Template assets directory
TEMPLATE_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates', 'default', 'assets')


def get_site_from_host(request: Request, db: Session) -> Optional[PublishedSite]:
    """
    Get site from request host header.
    
    Supports both direct Railway connections and Cloudflare proxy.
    Cloudflare passes original domain in X-Forwarded-Host header.
    
    Args:
        request: FastAPI request
        db: Database session
        
    Returns:
        PublishedSite or None
    """
    # Check Cloudflare headers first (if using Cloudflare proxy)
    # X-Forwarded-Host contains the original domain when proxied through Cloudflare
    host = (
        request.headers.get("X-Forwarded-Host") or  # Cloudflare proxy
        request.headers.get("Host") or              # Direct connection
        ""
    )
    
    if not host:
        return None
    
    # Remove port if present
    domain_name = host.split(":")[0].lower().strip()
    
    # Skip Railway domains and localhost - these should be handled by API routes
    railway_domains = [".railway.app", ".up.railway.app", "localhost", "127.0.0.1", "0.0.0.0"]
    is_railway_domain = any(railway_domain in domain_name for railway_domain in railway_domains)
    
    if is_railway_domain:
        return None  # Let API routes handle Railway domains
    
    return get_site_by_domain(db, domain_name)


@router.get("/templates/default/assets/{file_path:path}")
def serve_template_assets(file_path: str):
    """Serve template static assets (CSS, JS, images)."""
    full_path = os.path.join(TEMPLATE_ASSETS_DIR, file_path)
    
    # Security check - ensure path is within template directory
    if not os.path.abspath(full_path).startswith(os.path.abspath(TEMPLATE_ASSETS_DIR)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Determine media type
    media_type = "text/plain"
    if file_path.endswith('.css'):
        media_type = "text/css"
    elif file_path.endswith('.js'):
        media_type = "application/javascript"
    elif file_path.endswith('.png'):
        media_type = "image/png"
    elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
        media_type = "image/jpeg"
    elif file_path.endswith('.svg'):
        media_type = "image/svg+xml"
    
    return FileResponse(full_path, media_type=media_type)


@router.get("/", response_class=HTMLResponse)
def serve_homepage(
    request: Request,
    db: Session = Depends(get_db)
):
    """Serve site homepage."""
    site = get_site_from_host(request, db)
    
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Get homepage page or latest posts
    homepage_page = db.query(SitePage).filter(
        SitePage.site_id == site.id,
        SitePage.is_homepage == True,
        SitePage.status == 'published'
    ).first()
    
    if homepage_page:
        return HTMLResponse(render_template(site, "page", {"page": homepage_page, "request": request}))
    
    # Otherwise show blog listing
    posts = db.query(SitePost).filter(
        SitePost.site_id == site.id,
        SitePost.status == 'published'
    ).order_by(SitePost.published_at.desc()).limit(10).all()
    
    # Load categories for posts
    for post in posts:
        if post.category_id:
            post.category = db.query(SiteCategory).filter(SiteCategory.id == post.category_id).first()
    
    return HTMLResponse(render_template(site, "home", {"posts": posts, "request": request}))


@router.get("/posts/{slug}", response_class=HTMLResponse)
def serve_post(
    slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Serve a single post."""
    site = get_site_from_host(request, db)
    
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    post = db.query(SitePost).filter(
        SitePost.site_id == site.id,
        SitePost.slug == slug,
        SitePost.status == 'published'
    ).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Load category for post
    if post.category_id:
        post.category = db.query(SiteCategory).filter(SiteCategory.id == post.category_id).first()
    
    # Get related posts (same category, limit 3)
    related_posts = []
    if post.category_id:
        related_posts = db.query(SitePost).filter(
            SitePost.site_id == site.id,
            SitePost.category_id == post.category_id,
            SitePost.id != post.id,
            SitePost.status == 'published'
        ).order_by(SitePost.published_at.desc()).limit(3).all()
    
    # Increment view count
    post.views_count = (post.views_count or 0) + 1
    db.commit()
    
    return HTMLResponse(render_template(site, "post", {"post": post, "related_posts": related_posts, "request": request}))


@router.get("/category/{slug}", response_class=HTMLResponse)
def serve_category(
    slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Serve category page."""
    site = get_site_from_host(request, db)
    
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    category = db.query(SiteCategory).filter(
        SiteCategory.site_id == site.id,
        SiteCategory.slug == slug,
        SiteCategory.is_active == True
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    posts = db.query(SitePost).filter(
        SitePost.site_id == site.id,
        SitePost.category_id == category.id,
        SitePost.status == 'published'
    ).order_by(SitePost.published_at.desc()).all()
    
    return HTMLResponse(render_template(site, "category", {"category": category, "posts": posts, "request": request}))


@router.get("/page/{slug}", response_class=HTMLResponse)
def serve_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Serve a static page."""
    site = get_site_from_host(request, db)
    
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    page = db.query(SitePage).filter(
        SitePage.site_id == site.id,
        SitePage.slug == slug,
        SitePage.status == 'published'
    ).first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    return HTMLResponse(render_template(site, "page", {"page": page, "request": request}))


@router.get("/feed.xml", response_class=Response)
def serve_rss_feed(
    request: Request,
    db: Session = Depends(get_db)
):
    """Serve RSS feed."""
    site = get_site_from_host(request, db)
    
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    posts = db.query(SitePost).filter(
        SitePost.site_id == site.id,
        SitePost.status == 'published'
    ).order_by(SitePost.published_at.desc()).limit(20).all()
    
    # Generate RSS XML
    from datetime import datetime
    base_url = f"https://{site.domain.name}"
    
    rss_items = []
    for post in posts:
        pub_date = post.published_at.strftime("%a, %d %b %Y %H:%M:%S +0000") if post.published_at else ""
        
        def escape_xml(text: str) -> str:
            if not text:
                return ""
            return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))
        
        post_url = f"{base_url}/posts/{post.slug}"
        title = escape_xml(post.title)
        description = escape_xml(post.excerpt or post.meta_description or "")
        author = escape_xml(post.author_name or "Author")
        
        item = f"""    <item>
      <title>{title}</title>
      <link>{post_url}</link>
      <description>{description}</description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="true">{post_url}</guid>
      <author>{author}</author>
    </item>"""
        rss_items.append(item)
    
    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape_xml(site.name)}</title>
    <link>{base_url}</link>
    <description>{escape_xml(site.meta_description or '')}</description>
    <language>en-us</language>
    <lastBuildDate>{datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
    <atom:link href="{base_url}/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(rss_items)}
  </channel>
</rss>"""
    
    return Response(content=rss_xml, media_type="application/rss+xml")


@router.get("/sitemap.xml", response_class=Response)
def serve_sitemap(
    request: Request,
    db: Session = Depends(get_db)
):
    """Serve sitemap."""
    site = get_site_from_host(request, db)

    if not site:
        # Not a published customer site — this is the main product domain.
        # Serve the platform sitemap instead of 404ing the domain's SEO.
        from backend.api.v1.routes_sitemap import generate_sitemap
        return generate_sitemap(request, db)
    
    # Check if sitemap is enabled
    settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).first()
    if settings and not settings.sitemap_enabled:
        raise HTTPException(status_code=404, detail="Sitemap disabled")
    
    base_url = f"https://{site.domain.name}"
    
    urls = []
    
    # Homepage
    urls.append(f"  <url><loc>{base_url}/</loc><priority>1.0</priority></url>")
    
    # Published posts
    posts = db.query(SitePost).filter(
        SitePost.site_id == site.id,
        SitePost.status == 'published'
    ).all()
    
    for post in posts:
        urls.append(f"  <url><loc>{base_url}/posts/{post.slug}</loc><lastmod>{post.updated_at.strftime('%Y-%m-%d')}</lastmod><priority>0.8</priority></url>")
    
    # Published pages
    pages = db.query(SitePage).filter(
        SitePage.site_id == site.id,
        SitePage.status == 'published'
    ).all()
    
    for page in pages:
        urls.append(f"  <url><loc>{base_url}/page/{page.slug}</loc><lastmod>{page.updated_at.strftime('%Y-%m-%d')}</lastmod><priority>0.6</priority></url>")
    
    # Categories
    categories = db.query(SiteCategory).filter(
        SiteCategory.site_id == site.id,
        SiteCategory.is_active == True
    ).all()
    
    for category in categories:
        urls.append(f"  <url><loc>{base_url}/category/{category.slug}</loc><priority>0.5</priority></url>")
    
    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""
    
    return Response(content=sitemap_xml, media_type="application/xml")

