"""Agency API keys. The secret is returned once; only a hash is stored."""
from datetime import datetime
import hashlib
from secrets import token_urlsafe
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.deps import get_current_org, get_current_user, role_required
from backend.core.plans import F_API, has_feature
from backend.db.session import get_db
from backend.models.api_key import ApiKey
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationRole
from backend.models.user import User

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class ApiKeyPublic(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: datetime
    revoked_at: datetime | None = None

    class Config:
        from_attributes = True


class ApiKeyCreated(ApiKeyPublic):
    token: str


def hash_api_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _require_api(org: Organization) -> None:
    if not has_feature(org, F_API):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="API access is not included in this plan.",
        )


@router.get("", response_model=List[ApiKeyPublic])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    _require_api(current_org)
    return (
        db.query(ApiKey)
        .filter(ApiKey.organization_id == current_org.id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
        .all()
    )


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN])),
):
    _require_api(current_org)
    token = "mv_" + token_urlsafe(32)
    row = ApiKey(
        organization_id=current_org.id,
        name=body.name.strip(),
        prefix=token[:11],
        key_hash=hash_api_key(token),
        created_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiKeyCreated(
        id=row.id,
        name=row.name,
        prefix=row.prefix,
        created_at=row.created_at,
        revoked_at=None,
        token=token,
    )


@router.delete("/{key_id}")
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    current_role: OrganizationRole = Depends(role_required([OrganizationRole.OWNER, OrganizationRole.ADMIN])),
):
    _require_api(current_org)
    row = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.organization_id == current_org.id)
        .first()
    )
    if not row or row.revoked_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    row.revoked_at = datetime.utcnow()
    db.commit()
    return {"success": True}
