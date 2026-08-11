"""Domain verification routes."""
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.models.domain import Domain as DomainModel
from backend.models.user import User
from backend.db.session import get_db
from backend.core.deps import get_current_user, get_current_org, role_required
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationRole
from backend.schemas.domain import Domain
from backend.schemas.domain import Domain as DomainSchema
from backend.core.config import settings
import logging
logger = logging.getLogger(__name__)
from backend.utils.verification_tokens import (
    generate_verification_token,
    get_dns_instructions,
    get_html_file_instructions,
    get_meta_tag_instructions
)
from backend.services.domain_verification import verify_domain, get_fresh_dns_resolver
from backend.services.activity_logger import log_activity

router = APIRouter(prefix="/domains", tags=["verification"])


class VerificationStartRequest(BaseModel):
    """Schema for starting verification."""
    method: str = Field(..., description="Verification method: dns, html, or meta")


class VerificationStartResponse(BaseModel):
    """Schema for verification start response."""
    domain_id: int
    method: str
    token: str
    instructions: Dict[str, str]


@router.post("/{domain_id}/verification/start", response_model=VerificationStartResponse)
def start_verification(
    domain_id: int,
    request: VerificationStartRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN]))
):
    """
    Start domain verification process (owner/admin only).
    
    Generates a verification token and returns instructions based on the chosen method.
    """
    # Validate method
    if request.method not in ['dns', 'html', 'meta']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification method. Must be 'dns', 'html', or 'meta'"
        )
    
    # Get domain and verify ownership
    domain = db.query(DomainModel).filter(
        DomainModel.id == domain_id,
        DomainModel.organization_id == current_org.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found or not owned by this organization"
        )
    
    # Check if we should reuse existing token (same method, token already exists)
    if domain.verification_method == request.method and domain.verification_token:
        # Reuse existing token - don't regenerate
        token = domain.verification_token
    else:
        # Generate new token (new method or no existing token)
        token = generate_verification_token()
        
        # Save token and method to domain
        domain.verification_method = request.method
        domain.verification_token = token
        db.commit()
        db.refresh(domain)
    
    # Get instructions based on method
    if request.method == 'dns':
        instructions = get_dns_instructions(domain.name, token)
    elif request.method == 'html':
        instructions = get_html_file_instructions(domain.name, token)
    else:  # meta
        instructions = get_meta_tag_instructions(domain.name, token)
    
    # Log verification start
    log_activity(
        db,
        user_id=current_user.id,
        action="domain.verification.started",
        metadata={"domain_id": domain.id, "domain_name": domain.name, "method": request.method},
        request=http_request
    )
    
    return VerificationStartResponse(
        domain_id=domain.id,
        method=request.method,
        token=token,
        instructions=instructions
    )


class VerificationDebugResponse(BaseModel):
    """Debug response for DNS verification."""
    domain: str
    expected_value: str
    found_records: list
    is_verified: bool
    error: str | None


@router.get("/{domain_id}/verification/debug", response_model=VerificationDebugResponse)
def debug_verification(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN]))
):
    """
    Debug endpoint to see what DNS records are found for a domain.
    Uses fresh DNS resolver to bypass caching.
    """
    import dns.resolver
    
    domain = db.query(DomainModel).filter(
        DomainModel.id == domain_id,
        DomainModel.organization_id == current_org.id
    ).first()
    
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    if not domain.verification_token:
        raise HTTPException(status_code=400, detail="No verification in progress")
    
    expected_value = f"preview-verification={domain.verification_token}"
    found_records = []
    error = None
    is_verified = False
    
    try:
        # Use fresh resolver to bypass any caching
        resolver = get_fresh_dns_resolver()
        answers = resolver.resolve(domain.name, 'TXT')
        for answer in answers:
            for txt_string in answer.strings:
                txt_str = txt_string.decode('utf-8') if isinstance(txt_string, bytes) else str(txt_string)
                found_records.append(txt_str)
                if expected_value in txt_str or domain.verification_token in txt_str:
                    is_verified = True
    except dns.resolver.NXDOMAIN:
        error = "Domain does not exist in DNS"
    except dns.resolver.NoAnswer:
        error = "No TXT records found for this domain"
    except dns.resolver.Timeout:
        error = "DNS query timed out"
    except Exception as e:
        error = f"DNS error: {str(e)}"
    
    return VerificationDebugResponse(
        domain=domain.name,
        expected_value=expected_value,
        found_records=found_records,
        is_verified=is_verified,
        error=error
    )


@router.get("/{domain_id}/verification/check", response_model=Domain)
def check_verification(
    domain_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN]))
):
    """
    Check if domain verification is successful (owner/admin only).
    
    Performs the actual verification check based on the domain's verification method.
    """
    # Get domain and verify ownership
    domain = db.query(DomainModel).filter(
        DomainModel.id == domain_id,
        DomainModel.organization_id == current_org.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found or not owned by this organization"
        )
    
    # Check if verification is already in progress
    if not domain.verification_method or not domain.verification_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verification in progress. Start verification first."
        )
    
    # Perform verification check
    is_verified, error_message = verify_domain(
        domain.name,
        domain.verification_method,
        domain.verification_token
    )
    
    if is_verified:
        # Update domain status
        domain.status = "verified"
        domain.verified_at = datetime.utcnow()
        db.commit()
        db.refresh(domain)

        # Log verification success
        log_activity(
            db,
            user_id=current_user.id,
            action="domain.verification.succeeded",
            metadata={"domain_id": domain.id, "domain_name": domain.name, "method": domain.verification_method},
            request=request
        )

        # Celebrate + point at the next step (fire-and-forget)
        try:
            from backend.services.email_service import send_domain_verified_email
            send_domain_verified_email(
                current_user.email,
                domain.name,
                f"{settings.FRONTEND_URL.rstrip('/')}/app/previews",
            )
        except Exception:
            logger.exception("Failed to enqueue domain-verified email")

        return domain
    else:
        # Log verification failure
        log_activity(
            db,
            user_id=current_user.id,
            action="domain.verification.failed",
            metadata={"domain_id": domain.id, "domain_name": domain.name, "method": domain.verification_method, "error": error_message},
            request=request
        )

        # Return the domain plus WHY the check failed, so the dashboard can
        # tell "not propagated yet" apart from "wrong record".
        payload = DomainSchema.model_validate(domain, from_attributes=True)
        payload.verification_error = error_message or "Verification not confirmed yet."
        return payload

