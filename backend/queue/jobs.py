"""Background job functions executed by RQ workers."""
from typing import Dict, Optional
from uuid import uuid4
from backend.db.session import SessionLocal
from backend.models.preview import Preview as PreviewModel
from backend.models.domain import Domain as DomainModel
from backend.models.brand import BrandSettings as BrandSettingsModel
from backend.services.preview_generator import generate_ai_preview
from backend.services.playwright_screenshot import capture_screenshot
from backend.services.r2_client import upload_file_to_r2
from backend.schemas.brand import BrandSettings as BrandSettingsSchema
from datetime import datetime


def generate_preview_job(user_id: int, url: str, domain: str) -> Dict:
    """
    Background job to generate AI preview for a URL.
    
    Args:
        user_id: ID of the user requesting the preview
        url: URL to generate preview for
        domain: Domain name
        
    Returns:
        Dictionary with preview_id and preview data
    """
    db = SessionLocal()
    try:
        # Step 1: Validate domain ownership
        domain_obj = db.query(DomainModel).filter(
            DomainModel.name == domain,
            DomainModel.user_id == user_id
        ).first()
        
        if not domain_obj:
            raise ValueError("Domain not found or not owned by the user")
        
        # Step 2: Load brand settings. Brands are per domain now, so pin this to
        # the account-wide default row rather than whichever domain sorts first.
        brand_settings = db.query(BrandSettingsModel).filter(
            BrandSettingsModel.user_id == user_id,
            BrandSettingsModel.domain_id.is_(None),
        ).first()
        
        # If no brand settings exist, create default ones
        if not brand_settings:
            brand_settings = BrandSettingsModel(
                primary_color="#2979FF",
                secondary_color="#0A1A3C",
                accent_color="#3FFFD3",
                font_family="Inter",
                logo_url=None,
                user_id=user_id,
            )
            db.add(brand_settings)
            db.commit()
            db.refresh(brand_settings)
        
        # Step 3: Convert to schema for AI generator
        brand_schema = BrandSettingsSchema.model_validate(brand_settings)
        
        # Step 4: Call AI preview generator (for title and description)
        ai_result = generate_ai_preview(url, brand_schema)
        
        # Step 5: Capture screenshot and upload to R2
        image_url = None
        try:
            screenshot_bytes = capture_screenshot(url)
            filename = f"screenshots/{uuid4()}.png"
            image_url = upload_file_to_r2(screenshot_bytes, filename, "image/png")
        except Exception as screenshot_error:
            print(f"Error capturing/uploading screenshot: {screenshot_error}")
            # Fallback to AI-generated image URL if screenshot fails
            image_url = ai_result.get("image_url") or ""
        
        # Step 6: Determine preview type based on URL
        url_lower = url.lower()
        if "/product" in url_lower or "/shop" in url_lower:
            preview_type = "product"
        elif "/blog" in url_lower or "/post" in url_lower:
            preview_type = "blog"
        else:
            preview_type = "landing"
        
        # Step 7: Upsert Preview entry
        existing_preview = db.query(PreviewModel).filter(
            PreviewModel.url == url,
            PreviewModel.user_id == user_id
        ).first()
        
        if existing_preview:
            # Update existing preview
            existing_preview.title = ai_result["title"]
            existing_preview.description = ai_result.get("description")
            existing_preview.image_url = image_url or ""
            if not existing_preview.type:
                existing_preview.type = preview_type
            
            db.commit()
            db.refresh(existing_preview)
            
            return {
                "preview_id": existing_preview.id,
                "preview": {
                    "id": existing_preview.id,
                    "url": existing_preview.url,
                    "domain": existing_preview.domain,
                    "title": existing_preview.title,
                    "type": existing_preview.type,
                    "image_url": existing_preview.image_url,
                    "description": existing_preview.description,
                    "created_at": existing_preview.created_at.isoformat(),
                    "monthly_clicks": existing_preview.monthly_clicks,
                }
            }
        else:
            # Create new preview
            new_preview = PreviewModel(
                url=url,
                domain=domain,
                title=ai_result["title"],
                description=ai_result.get("description"),
                type=preview_type,
                image_url=image_url or "",
                user_id=user_id,
                created_at=datetime.utcnow(),
                monthly_clicks=0,
            )
            db.add(new_preview)
            db.commit()
            db.refresh(new_preview)
            
            return {
                "preview_id": new_preview.id,
                "preview": {
                    "id": new_preview.id,
                    "url": new_preview.url,
                    "domain": new_preview.domain,
                    "title": new_preview.title,
                    "type": new_preview.type,
                    "image_url": new_preview.image_url,
                    "description": new_preview.description,
                    "created_at": new_preview.created_at.isoformat(),
                    "monthly_clicks": new_preview.monthly_clicks,
                }
            }
            
    except Exception as e:
        # Log error and re-raise for RQ to handle
        print(f"Error in generate_preview_job: {e}")
        raise
    finally:
        # Always close DB session
        db.close()

