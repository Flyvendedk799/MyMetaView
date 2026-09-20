"""AI authentication credential management — Claude, Antigravity/Gemini subscriptions & API keys."""
import time
import logging
import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.deps import get_current_user, get_db
from backend.models.user import User
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationMember
from backend.services.ai_auth.credential_store import SqlAlchemyCredentialStore
from backend.services.ai_auth.claude_account_store import ClaudeAccountStore, ClaudeIdentityInput
from backend.services.ai_auth.claude_oauth import (
    start_claude_login, exchange_claude_code, parse_pasted_code, same_state
)
from backend.services.ai_auth.antigravity_account_store import AntigravityAccountStore
from backend.services.ai_auth.antigravity_oauth import (
    start_antigravity_login, exchange_antigravity_code
)
from backend.services.ai_auth.api_key_store import ApiKeyStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-auth", tags=["ai-auth"])

# In-memory verifier storage (state -> { verifier, created_at })
# Each entry expires after 10 minutes
_pending_logins: Dict[str, Dict[str, Any]] = {}
PENDING_TTL = 600  # 10 minutes

def _cleanup_pending():
    now = time.time()
    expired = [k for k, v in _pending_logins.items() if now - v['created_at'] > PENDING_TTL]
    for k in expired:
        del _pending_logins[k]

def _resolve_store(db: Session, scope: str, org_id: Optional[int], user_id: int):
    if scope == 'org':
        if not org_id:
            raise HTTPException(status_code=400, detail="org_id is required for org scope")
        return SqlAlchemyCredentialStore(db, organization_id=org_id)
    return SqlAlchemyCredentialStore(db, user_id=user_id)

def _check_org_access(db: Session, org_id: int, user: User):
    """Verify user is admin/owner of the org."""
    if user.is_admin:
        return
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org and org.owner_user_id == user.id:
        return
    
    member = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user.id,
    ).first()
    if not member or member.role not in ('owner', 'admin'):
        raise HTTPException(status_code=403, detail='Admin or owner access required')

def _check_access(db: Session, scope: str, org_id: Optional[int], user: User):
    if scope == 'org':
        if not org_id:
            raise HTTPException(status_code=400, detail="org_id is required for org scope")
        _check_org_access(db, org_id, user)


class LoginStartRequest(BaseModel):
    scope: str
    org_id: Optional[int] = None

class LoginCompleteRequest(BaseModel):
    code: str
    state: str
    scope: str
    org_id: Optional[int] = None

class ApiKeyPutRequest(BaseModel):
    key: str
    scope: str
    org_id: Optional[int] = None

class SetProjectRequest(BaseModel):
    project_id: str
    scope: str
    org_id: Optional[int] = None

# --- Claude OAuth Endpoints ---

@router.post("/claude/login")
def claude_login(
    req: LoginStartRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, req.scope, req.org_id, user)
    _cleanup_pending()
    
    auth_url, state, verifier = start_claude_login()
    _pending_logins[state] = {
        'verifier': verifier,
        'created_at': time.time()
    }
    return {"url": auth_url, "state": state}

@router.post("/claude/login/complete")
def claude_login_complete(
    req: LoginCompleteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, req.scope, req.org_id, user)
    _cleanup_pending()
    
    if req.state not in _pending_logins:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    verifier = _pending_logins[req.state]['verifier']
    del _pending_logins[req.state]
    
    try:
        token_data = exchange_claude_code(req.code, verifier)
    except Exception as e:
        logger.error(f"Failed to exchange Claude code: {e}")
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
    
    store = _resolve_store(db, req.scope, req.org_id, user.id)
    account_store = ClaudeAccountStore(store, settings.SECRET_KEY)
    
    identity = ClaudeIdentityInput(
        account_id=token_data.get("account_id", ""),
        account_name=token_data.get("account_name", "Claude Account"),
        plan=token_data.get("plan", "Unknown")
    )
    
    account_store.save(
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        identity=identity
    )
    
    return {"connected": True, "plan": identity.plan}

@router.get("/claude/status")
def claude_status(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    account_store = ClaudeAccountStore(store, settings.SECRET_KEY)
    
    status_data = account_store.status()
    return status_data.dict()

@router.delete("/claude")
def claude_disconnect(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    account_store = ClaudeAccountStore(store, settings.SECRET_KEY)
    account_store.forget()
    return {"success": True}

# --- Antigravity/Gemini OAuth Endpoints ---

@router.post("/antigravity/login")
def antigravity_login(
    req: LoginStartRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, req.scope, req.org_id, user)
    _cleanup_pending()
    
    auth_url, state, verifier = start_antigravity_login()
    _pending_logins[state] = {
        'verifier': verifier,
        'created_at': time.time()
    }
    return {"url": auth_url, "state": state}

@router.post("/antigravity/login/complete")
def antigravity_login_complete(
    req: LoginCompleteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, req.scope, req.org_id, user)
    _cleanup_pending()
    
    if req.state not in _pending_logins:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    verifier = _pending_logins[req.state]['verifier']
    del _pending_logins[req.state]
    
    try:
        token_data = exchange_antigravity_code(req.code, verifier)
    except Exception as e:
        logger.error(f"Failed to exchange Antigravity code: {e}")
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
    
    store = _resolve_store(db, req.scope, req.org_id, user.id)
    account_store = AntigravityAccountStore(store, settings.SECRET_KEY)
    
    account_store.save(
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        identity=token_data.get("identity")
    )
    
    return {"connected": True}

@router.get("/antigravity/status")
def antigravity_status(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    account_store = AntigravityAccountStore(store, settings.SECRET_KEY)
    
    return account_store.status().dict()

@router.delete("/antigravity")
def antigravity_disconnect(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    account_store = AntigravityAccountStore(store, settings.SECRET_KEY)
    account_store.forget()
    return {"success": True}

@router.put("/antigravity/project")
def antigravity_set_project(
    req: SetProjectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, req.scope, req.org_id, user)
    store = _resolve_store(db, req.scope, req.org_id, user.id)
    account_store = AntigravityAccountStore(store, settings.SECRET_KEY)
    
    if not account_store.status().connected:
        raise HTTPException(status_code=400, detail="Not connected")
        
    account_store.set_project(req.project_id)
    return {"success": True}

# --- API Key Endpoints ---

@router.put("/keys/{provider}")
def put_api_key(
    provider: str,
    req: ApiKeyPutRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if provider not in ["anthropic", "openai", "gemini"]:
        raise HTTPException(status_code=400, detail="Unsupported provider")
        
    _check_access(db, req.scope, req.org_id, user)
    store = _resolve_store(db, req.scope, req.org_id, user.id)
    api_key_store = ApiKeyStore(store, settings.SECRET_KEY)
    
    api_key_store.save(provider, req.key)
    return {"success": True}

@router.get("/keys")
def list_api_keys(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    api_key_store = ApiKeyStore(store, settings.SECRET_KEY)
    
    return {"keys": api_key_store.list_keys()}

@router.delete("/keys/{provider}")
def delete_api_key(
    provider: str,
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if provider not in ["anthropic", "openai", "gemini"]:
        raise HTTPException(status_code=400, detail="Unsupported provider")
        
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    api_key_store = ApiKeyStore(store, settings.SECRET_KEY)
    
    api_key_store.forget(provider)
    return {"success": True}

# --- Combined Status Endpoint ---

@router.get("/status")
def get_all_status(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    
    claude_store = ClaudeAccountStore(store, settings.SECRET_KEY)
    antigravity_store = AntigravityAccountStore(store, settings.SECRET_KEY)
    api_key_store = ApiKeyStore(store, settings.SECRET_KEY)
    
    return {
        "claude": claude_store.status().dict(),
        "antigravity": antigravity_store.status().dict(),
        "keys": api_key_store.list_keys()
    }
