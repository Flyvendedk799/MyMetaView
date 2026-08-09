"""Domain management routes."""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import List
from sqlalchemy.orm import Session
from datetime import datetime
from backend.schemas.domain import Domain, DomainCreate
from backend.models.domain import Domain as DomainModel
from backend.models.user import User
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_org, role_required
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationRole
from backend.services.activity_logger import log_activity
from backend.services.cache import invalidate_domain

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("", response_model=List[Domain])
def list_domains(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get all domains for the current organization."""
    domains = db.query(DomainModel).filter(
        DomainModel.organization_id == current_org.id
    ).order_by(DomainModel.created_at.desc()).all()
    return domains


@router.post("", response_model=Domain, status_code=status.HTTP_201_CREATED)
def create_domain(
    domain: DomainCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EDITOR]))
):
    """Create a new domain for the current organization (owner/admin/editor only)."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Check if domain with same name already exists for this organization
    existing_domain = db.query(DomainModel).filter(
        DomainModel.name == domain.name,
        DomainModel.organization_id == current_org.id
    ).first()
    
    if existing_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Domain '{domain.name}' already exists for your account"
        )
    
    db_domain = DomainModel(
        name=domain.name,
        environment=domain.environment,
        status=domain.status,
        created_at=datetime.utcnow(),
        monthly_clicks=0,
        user_id=current_user.id,
        organization_id=current_org.id
    )
    db.add(db_domain)
    db.commit()
    db.refresh(db_domain)

    # Invalidate cache (domain was just created, but invalidate to be safe)
    invalidate_domain(current_org.id, db_domain.name)
    
    # Log domain creation
    log_activity(
        db,
        user_id=current_user.id,
        action="domain.created",
        metadata={"domain_id": db_domain.id, "domain_name": db_domain.name, "environment": db_domain.environment},
        request=request
    )
    
    return db_domain


@router.get("/{domain_id}", response_model=Domain)
def get_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org)
):
    """Get a domain by ID for the current organization."""
    domain = db.query(DomainModel).filter(
        DomainModel.id == domain_id,
        DomainModel.organization_id == current_org.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain with ID {domain_id} not found"
        )
    return domain


@router.delete("/{domain_id}")
def delete_domain(
    domain_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN]))
):
    """Delete a domain by ID (owner/admin only)."""
    domain = db.query(DomainModel).filter(
        DomainModel.id == domain_id,
        DomainModel.organization_id == current_org.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain with ID {domain_id} not found"
        )
    
    domain_name = domain.name
    db.delete(domain)
    db.commit()
    
    # Invalidate cache
    invalidate_domain(current_org.id, domain_name)
    
    # Log domain deletion
    log_activity(
        db,
        user_id=current_user.id,
        action="domain.deleted",
        metadata={"domain_id": domain_id, "domain_name": domain_name},
        request=request
    )
    
    return {"success": True}

