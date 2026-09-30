"""Blog API routes with comprehensive CRUD and public endpoints."""
import re
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_, func
from pydantic import BaseModel, Field
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_admin
from backend.models.user import User
from backend.models.blog_post import BlogPost, BlogCategory


router = APIRouter(prefix="/blog", tags=["blog"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class CategoryBase(BaseModel):
    name: str = Field(..., max_length=100)
    slug: Optional[str] = Field(None, max_length=120)
    description: Optional[str] = None
    color: Optional[str] = Field("#f97316", max_length=20)
    icon: Optional[str] = Field(None, max_length=50)
    is_active: bool = True
    sort_order: int = 0
    meta_title: Optional[str] = Field(None, max_length=70)
    meta_description: Optional[str] = Field(None, max_length=160)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    slug: Optional[str] = Field(None, max_length=120)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=20)
    icon: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    meta_title: Optional[str] = Field(None, max_length=70)
    meta_description: Optional[str] = Field(None, max_length=160)


class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    post_count: Optional[int] = 0
    
    class Config:
        from_attributes = True


class BlogPostBase(BaseModel):
    title: str = Field(..., max_length=200)
    slug: Optional[str] = Field(None, max_length=250)
    excerpt: Optional[str] = None
    content: str
    featured_image: Optional[str] = Field(None, max_length=500)
    featured_image_alt: Optional[str] = Field(None, max_length=200)
    og_image: Optional[str] = Field(None, max_length=500)
    author_name: Optional[str] = Field(None, max_length=100)
    author_bio: Optional[str] = None
    author_avatar: Optional[str] = Field(None, max_length=500)
    category_id: Optional[int] = None
    tags: Optional[str] = None
    status: str = Field("draft", pattern="^(draft|published|scheduled|archived)$")
    is_featured: bool = False
    is_pinned: bool = False
    scheduled_at: Optional[datetime] = None
    meta_title: Optional[str] = Field(None, max_length=70)
    meta_description: Optional[str] = Field(None, max_length=160)
    meta_keywords: Optional[str] = Field(None, max_length=300)
    canonical_url: Optional[str] = Field(None, max_length=500)
    no_index: bool = False
    schema_type: str = Field("Article", max_length=50)
    twitter_title: Optional[str] = Field(None, max_length=70)
    twitter_description: Optional[str] = Field(None, max_length=200)
    twitter_image: Optional[str] = Field(None, max_length=500)
    related_post_ids: Optional[str] = Field(None, max_length=200)


class BlogPostCreate(BlogPostBase):
    pass


class BlogPostUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    slug: Optional[str] = Field(None, max_length=250)
    excerpt: Optional[str] = None
    content: Optional[str] = None
    featured_image: Optional[str] = Field(None, max_length=500)
    featured_image_alt: Optional[str] = Field(None, max_length=200)
    og_image: Optional[str] = Field(None, max_length=500)
    author_name: Optional[str] = Field(None, max_length=100)
    author_bio: Optional[str] = None
    author_avatar: Optional[str] = Field(None, max_length=500)
    category_id: Optional[int] = None
    tags: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|published|scheduled|archived)$")
    is_featured: Optional[bool] = None
    is_pinned: Optional[bool] = None
    scheduled_at: Optional[datetime] = None
    meta_title: Optional[str] = Field(None, max_length=70)
    meta_description: Optional[str] = Field(None, max_length=160)
    meta_keywords: Optional[str] = Field(None, max_length=300)
    canonical_url: Optional[str] = Field(None, max_length=500)
    no_index: Optional[bool] = None
    schema_type: Optional[str] = Field(None, max_length=50)
    twitter_title: Optional[str] = Field(None, max_length=70)
    twitter_description: Optional[str] = Field(None, max_length=200)
    twitter_image: Optional[str] = Field(None, max_length=500)
    related_post_ids: Optional[str] = Field(None, max_length=200)


class AuthorResponse(BaseModel):
    id: int
    name: Optional[str]
    bio: Optional[str]
    avatar: Optional[str]
    
    class Config:
        from_attributes = True


class BlogPostResponse(BaseModel):
    id: int
    title: str
    slug: str
    excerpt: Optional[str]
    content: str
    featured_image: Optional[str]
    featured_image_alt: Optional[str]
    og_image: Optional[str]
    author_id: int
    author_name: Optional[str]
    author_bio: Optional[str]
    author_avatar: Optional[str]
    category_id: Optional[int]
    category: Optional[CategoryResponse] = None
    tags: Optional[str]
    status: str
    is_featured: bool
    is_pinned: bool
    read_time_minutes: Optional[int]
    views_count: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]
    scheduled_at: Optional[datetime]
    meta_title: Optional[str]
    meta_description: Optional[str]
    meta_keywords: Optional[str]
    canonical_url: Optional[str]
    no_index: bool
    schema_type: str
    twitter_title: Optional[str]
    twitter_description: Optional[str]
    twitter_image: Optional[str]
    related_post_ids: Optional[str]
    
    class Config:
        from_attributes = True


class BlogPostListItem(BaseModel):
    """Lighter response for list views."""
    id: int
    title: str
    slug: str
    excerpt: Optional[str]
    featured_image: Optional[str]
    author_name: Optional[str]
    author_avatar: Optional[str]
    category: Optional[CategoryResponse] = None
    tags: Optional[str]
    status: str
    is_featured: bool
    is_pinned: bool
    read_time_minutes: Optional[int]
    views_count: int
    published_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class PaginatedBlogPosts(BaseModel):
    items: List[BlogPostListItem]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


# ============================================================================
# Helper Functions
# ============================================================================

def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    return slug[:250]


def ensure_unique_slug(db: Session, slug: str, exclude_id: Optional[int] = None) -> str:
    """Ensure slug is unique, append number if necessary."""
    original_slug = slug
    counter = 1
    while True:
        query = db.query(BlogPost).filter(BlogPost.slug == slug)
        if exclude_id:
            query = query.filter(BlogPost.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{original_slug}-{counter}"
        counter += 1


def ensure_unique_category_slug(db: Session, slug: str, exclude_id: Optional[int] = None) -> str:
    """Ensure category slug is unique."""
    original_slug = slug
    counter = 1
    while True:
        query = db.query(BlogCategory).filter(BlogCategory.slug == slug)
        if exclude_id:
            query = query.filter(BlogCategory.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{original_slug}-{counter}"
        counter += 1


# ============================================================================
# Public Endpoints (No Auth Required)
# ============================================================================

@router.get("/posts", response_model=PaginatedBlogPosts)
def get_public_posts(
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=50),
    category: Optional[str] = Query(None, description="Category slug"),
    tag: Optional[str] = Query(None, description="Tag to filter by"),
    search: Optional[str] = Query(None, description="Search in title and content"),
    featured: Optional[bool] = Query(None, description="Filter featured posts only"),
    db: Session = Depends(get_db)
):
    """Get paginated list of published blog posts (public endpoint)."""
    query = db.query(BlogPost).filter(
        BlogPost.status == "published",
        BlogPost.published_at <= datetime.utcnow()
    )
    
    # Category filter
    if category:
        cat = db.query(BlogCategory).filter(BlogCategory.slug == category).first()
        if cat:
            query = query.filter(BlogPost.category_id == cat.id)
    
    # Tag filter
    if tag:
        query = query.filter(BlogPost.tags.ilike(f"%{tag}%"))
    
    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                BlogPost.title.ilike(search_term),
                BlogPost.excerpt.ilike(search_term),
                BlogPost.content.ilike(search_term)
            )
        )
    
    # Featured filter
    if featured is not None:
        query = query.filter(BlogPost.is_featured == featured)
    
    # Get total count
    total = query.count()
    total_pages = (total + per_page - 1) // per_page
    
    # Order: pinned first, then by published date
    query = query.order_by(desc(BlogPost.is_pinned), desc(BlogPost.published_at))
    
    # Paginate
    offset = (page - 1) * per_page
    posts = query.offset(offset).limit(per_page).all()
    
    # Convert to response with category info
    items = []
    for post in posts:
        item = BlogPostListItem.model_validate(post)
        if post.category:
            item.category = CategoryResponse.model_validate(post.category)
        items.append(item)
    
    return PaginatedBlogPosts(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


@router.get("/posts/featured", response_model=List[BlogPostListItem])
def get_featured_posts(
    limit: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """Get featured blog posts for homepage display."""
    posts = db.query(BlogPost).filter(
        BlogPost.status == "published",
        BlogPost.published_at <= datetime.utcnow(),
        BlogPost.is_featured == True
    ).order_by(desc(BlogPost.published_at)).limit(limit).all()
    
    items = []
    for post in posts:
        item = BlogPostListItem.model_validate(post)
        if post.category:
            item.category = CategoryResponse.model_validate(post.category)
        items.append(item)
    
    return items


@router.get("/posts/recent", response_model=List[BlogPostListItem])
def get_recent_posts(
    limit: int = Query(5, ge=1, le=20),
    exclude_id: Optional[int] = Query(None, description="Post ID to exclude"),
    db: Session = Depends(get_db)
):
    """Get recent blog posts."""
    query = db.query(BlogPost).filter(
        BlogPost.status == "published",
        BlogPost.published_at <= datetime.utcnow()
    )
    
    if exclude_id:
        query = query.filter(BlogPost.id != exclude_id)
    
    posts = query.order_by(desc(BlogPost.published_at)).limit(limit).all()
    
    items = []
    for post in posts:
        item = BlogPostListItem.model_validate(post)
        if post.category:
            item.category = CategoryResponse.model_validate(post.category)
        items.append(item)
    
    return items


@router.get("/posts/{slug}", response_model=BlogPostResponse)
def get_post_by_slug(
    slug: str,
    db: Session = Depends(get_db)
):
    """Get a single blog post by slug (public, published posts only)."""
    post = db.query(BlogPost).filter(
        BlogPost.slug == slug,
        BlogPost.status == "published",
        BlogPost.published_at <= datetime.utcnow()
    ).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Increment view count
    post.views_count += 1
    db.commit()
    
    response = BlogPostResponse.model_validate(post)
    if post.category:
        response.category = CategoryResponse.model_validate(post.category)
    
    return response


@router.get("/categories", response_model=List[CategoryResponse])
def get_public_categories(
    include_empty: bool = Query(False, description="Include categories with no posts"),
    db: Session = Depends(get_db)
):
    """Get all active blog categories with post counts."""
    query = db.query(BlogCategory).filter(BlogCategory.is_active == True)
    categories = query.order_by(asc(BlogCategory.sort_order), asc(BlogCategory.name)).all()
    
    result = []
    for cat in categories:
        # Count published posts in this category
        post_count = db.query(BlogPost).filter(
            BlogPost.category_id == cat.id,
            BlogPost.status == "published",
            BlogPost.published_at <= datetime.utcnow()
        ).count()
        
        if include_empty or post_count > 0:
            cat_response = CategoryResponse.model_validate(cat)
            cat_response.post_count = post_count
            result.append(cat_response)
    
    return result


@router.get("/categories/{slug}", response_model=CategoryResponse)
def get_category_by_slug(
    slug: str,
    db: Session = Depends(get_db)
):
    """Get a single category by slug."""
    category = db.query(BlogCategory).filter(
        BlogCategory.slug == slug,
        BlogCategory.is_active == True
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Count posts
    post_count = db.query(BlogPost).filter(
        BlogPost.category_id == category.id,
        BlogPost.status == "published",
        BlogPost.published_at <= datetime.utcnow()
    ).count()
    
    response = CategoryResponse.model_validate(category)
    response.post_count = post_count
    
    return response


@router.get("/feed.xml")
def get_rss_feed(
    db: Session = Depends(get_db)
):
    """Generate RSS 2.0 feed for blog posts."""
    # Get latest 20 published posts
    posts = db.query(BlogPost).filter(
        BlogPost.status == "published",
        BlogPost.published_at <= datetime.utcnow()
    ).order_by(desc(BlogPost.published_at)).limit(20).all()
    
    # Build RSS XML
    base_url = "https://metaview.io"  # Update with your actual domain
    rss_items = []
    
    for post in posts:
        # Format date for RSS (RFC 822)
        pub_date = post.published_at.strftime("%a, %d %b %Y %H:%M:%S +0000") if post.published_at else ""
        
        # Escape XML special characters
        def escape_xml(text: str) -> str:
            if not text:
                return ""
            return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))
        
        post_url = f"{base_url}/blog/{post.slug}"
        title = escape_xml(post.title)
        description = escape_xml(post.excerpt or post.meta_description or "")
        author = escape_xml(post.author_name or "MetaView Team")
        
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
    <title>MetaView Blog</title>
    <link>{base_url}/blog</link>
    <description>Tips, strategies, and best practices for optimizing your URL previews and boosting click-through rates.</description>
    <language>en-us</language>
    <lastBuildDate>{datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
    <atom:link href="{base_url}/api/v1/blog/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(rss_items)}
  </channel>
</rss>"""
    
    return Response(content=rss_xml, media_type="application/rss+xml")


# ============================================================================
# Admin Endpoints (Auth Required)
# ============================================================================

@router.post("/admin/images")
async def admin_upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin),
):
    """Store a blog image and return its public URL."""
    from uuid import uuid4
    from backend.services.r2_client import upload_file_to_r2

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be 8MB or smaller")
    ext = "png"
    name = (file.filename or "").lower()
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        ext = "jpg"
    elif name.endswith(".webp"):
        ext = "webp"
    elif name.endswith(".gif"):
        ext = "gif"
    url = upload_file_to_r2(raw, f"blog/{uuid4()}.{ext}", file.content_type or "image/png")
    return {"url": url}


@router.get("/admin/posts", response_model=PaginatedBlogPosts)
def admin_get_all_posts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Get all blog posts including drafts."""
    query = db.query(BlogPost)
    
    if status:
        query = query.filter(BlogPost.status == status)
    
    if category_id:
        query = query.filter(BlogPost.category_id == category_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                BlogPost.title.ilike(search_term),
                BlogPost.excerpt.ilike(search_term)
            )
        )
    
    total = query.count()
    total_pages = (total + per_page - 1) // per_page
    
    query = query.order_by(desc(BlogPost.updated_at))
    offset = (page - 1) * per_page
    posts = query.offset(offset).limit(per_page).all()
    
    items = []
    for post in posts:
        item = BlogPostListItem.model_validate(post)
        if post.category:
            item.category = CategoryResponse.model_validate(post.category)
        items.append(item)
    
    return PaginatedBlogPosts(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


@router.get("/admin/posts/{post_id}", response_model=BlogPostResponse)
def admin_get_post(
    post_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Get a single blog post by ID (includes drafts)."""
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    response = BlogPostResponse.model_validate(post)
    if post.category:
        response.category = CategoryResponse.model_validate(post.category)
    
    return response


@router.post("/admin/posts", response_model=BlogPostResponse, status_code=status.HTTP_201_CREATED)
def admin_create_post(
    post_in: BlogPostCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Create a new blog post."""
    # Generate slug if not provided
    slug = post_in.slug if post_in.slug else generate_slug(post_in.title)
    slug = ensure_unique_slug(db, slug)
    
    post = BlogPost(
        **post_in.model_dump(exclude={'slug'}),
        slug=slug,
        author_id=current_user.id
    )
    
    # Set author name if not provided
    if not post.author_name:
        post.author_name = current_user.email.split('@')[0].title()
    
    # Calculate reading time
    post.calculate_read_time()
    
    # Generate excerpt if not provided
    post.generate_excerpt()
    
    # Set published_at if publishing
    if post.status == "published" and not post.published_at:
        post.published_at = datetime.utcnow()
    
    db.add(post)
    db.commit()
    db.refresh(post)
    
    response = BlogPostResponse.model_validate(post)
    if post.category:
        response.category = CategoryResponse.model_validate(post.category)
    
    return response


@router.put("/admin/posts/{post_id}", response_model=BlogPostResponse)
def admin_update_post(
    post_id: int,
    post_in: BlogPostUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Update a blog post."""
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Update fields
    update_data = post_in.model_dump(exclude_unset=True)
    
    # Handle slug update
    if 'slug' in update_data and update_data['slug']:
        update_data['slug'] = ensure_unique_slug(db, update_data['slug'], exclude_id=post_id)
    elif 'title' in update_data and update_data['title'] != post.title:
        # Regenerate slug if title changed and no explicit slug provided
        new_slug = generate_slug(update_data['title'])
        update_data['slug'] = ensure_unique_slug(db, new_slug, exclude_id=post_id)
    
    for key, value in update_data.items():
        setattr(post, key, value)
    
    # Recalculate reading time if content changed
    if 'content' in update_data:
        post.calculate_read_time()
        if not post.excerpt:
            post.generate_excerpt()
    
    # Set published_at if status changed to published
    if post.status == "published" and not post.published_at:
        post.published_at = datetime.utcnow()
    
    post.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(post)
    
    response = BlogPostResponse.model_validate(post)
    if post.category:
        response.category = CategoryResponse.model_validate(post.category)
    
    return response


@router.delete("/admin/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_post(
    post_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Delete a blog post."""
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    db.delete(post)
    db.commit()


@router.post("/admin/posts/{post_id}/publish", response_model=BlogPostResponse)
def admin_publish_post(
    post_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Quick publish a draft post."""
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    post.status = "published"
    post.published_at = datetime.utcnow()
    post.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(post)
    
    response = BlogPostResponse.model_validate(post)
    if post.category:
        response.category = CategoryResponse.model_validate(post.category)
    
    return response


@router.post("/admin/posts/{post_id}/unpublish", response_model=BlogPostResponse)
def admin_unpublish_post(
    post_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Unpublish a post (set to draft)."""
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    post.status = "draft"
    post.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(post)
    
    response = BlogPostResponse.model_validate(post)
    if post.category:
        response.category = CategoryResponse.model_validate(post.category)
    
    return response


# ============================================================================
# Admin Category Endpoints
# ============================================================================

@router.get("/admin/categories", response_model=List[CategoryResponse])
def admin_get_categories(
    include_inactive: bool = Query(True),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Get all categories including inactive ones."""
    query = db.query(BlogCategory)
    if not include_inactive:
        query = query.filter(BlogCategory.is_active == True)
    
    categories = query.order_by(asc(BlogCategory.sort_order), asc(BlogCategory.name)).all()
    
    result = []
    for cat in categories:
        post_count = db.query(BlogPost).filter(BlogPost.category_id == cat.id).count()
        cat_response = CategoryResponse.model_validate(cat)
        cat_response.post_count = post_count
        result.append(cat_response)
    
    return result


@router.post("/admin/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def admin_create_category(
    category_in: CategoryCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Create a new category."""
    slug = category_in.slug if category_in.slug else generate_slug(category_in.name)
    slug = ensure_unique_category_slug(db, slug)
    
    category = BlogCategory(
        **category_in.model_dump(exclude={'slug'}),
        slug=slug
    )
    
    db.add(category)
    db.commit()
    db.refresh(category)
    
    response = CategoryResponse.model_validate(category)
    response.post_count = 0
    
    return response


@router.put("/admin/categories/{category_id}", response_model=CategoryResponse)
def admin_update_category(
    category_id: int,
    category_in: CategoryUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Update a category."""
    category = db.query(BlogCategory).filter(BlogCategory.id == category_id).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    update_data = category_in.model_dump(exclude_unset=True)
    
    if 'slug' in update_data and update_data['slug']:
        update_data['slug'] = ensure_unique_category_slug(db, update_data['slug'], exclude_id=category_id)
    elif 'name' in update_data and update_data['name'] != category.name:
        new_slug = generate_slug(update_data['name'])
        update_data['slug'] = ensure_unique_category_slug(db, new_slug, exclude_id=category_id)
    
    for key, value in update_data.items():
        setattr(category, key, value)
    
    category.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(category)
    
    post_count = db.query(BlogPost).filter(BlogPost.category_id == category.id).count()
    response = CategoryResponse.model_validate(category)
    response.post_count = post_count
    
    return response


@router.delete("/admin/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_category(
    category_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Delete a category (sets posts to uncategorized)."""
    category = db.query(BlogCategory).filter(BlogCategory.id == category_id).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Set posts in this category to uncategorized
    db.query(BlogPost).filter(BlogPost.category_id == category_id).update(
        {BlogPost.category_id: None}
    )
    
    db.delete(category)
    db.commit()


