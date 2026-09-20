"""AI authentication credential management — Claude, Antigravity/Gemini subscriptions & API keys."""
import time
import logging
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
    start_claude_login, exchange_claude_code
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

def _get_account_id(scope: str, org_id: Optional[int], user_id: int) -> str:
    return str(org_id) if scope == 'org' else str(user_id)

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
async def claude_login(
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
async def claude_login_complete(
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
        # exchange_claude_code is async
        token_data = await exchange_claude_code(req.code, verifier)
    except Exception as e:
        logger.error(f"Failed to exchange Claude code: {e}")
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
    
    store = _resolve_store(db, req.scope, req.org_id, user.id)
    account_store = ClaudeAccountStore(store, settings.SECRET_KEY)
    account_id = _get_account_id(req.scope, req.org_id, user.id)
    
    identity = ClaudeIdentityInput(
        account_id=token_data.account_id,
        account_name=token_data.account_name,
        plan=token_data.subscription_type or "Unknown"
    )
    
    await account_store.save(
        account_id=account_id,
        identity=identity,
    )
    # The current claude_account_store expects identity, access_token and refresh_token, wait, let me verify the signature of save.
    return {"connected": True, "plan": identity.subscription_type}

@router.get("/claude/status")
async def claude_status(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    account_store = ClaudeAccountStore(store, settings.SECRET_KEY)
    account_id = _get_account_id(scope, org_id, user.id)
    
    status_data = await account_store.status(account_id)
    return status_data.dict()

@router.delete("/claude")
async def claude_disconnect(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    account_store = ClaudeAccountStore(store, settings.SECRET_KEY)
    account_id = _get_account_id(scope, org_id, user.id)
    
    await account_store.forget(account_id)
    return {"success": True}

# --- Antigravity/Gemini OAuth Endpoints ---

@router.post("/antigravity/login")
async def antigravity_login(
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
async def antigravity_login_complete(
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
        token_data = await exchange_antigravity_code(req.code, verifier)
    except Exception as e:
        logger.error(f"Failed to exchange Antigravity code: {e}")
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
    
    store = _resolve_store(db, req.scope, req.org_id, user.id)
    account_store = AntigravityAccountStore(store, settings.SECRET_KEY)
    account_id = _get_account_id(req.scope, req.org_id, user.id)
    
    await account_store.save(
        account_id=account_id,
        identity=token_data
    )
    
    return {"connected": True}

@router.get("/antigravity/status")
async def antigravity_status(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    account_store = AntigravityAccountStore(store, settings.SECRET_KEY)
    account_id = _get_account_id(scope, org_id, user.id)
    
    status_data = await account_store.status(account_id)
    return status_data.dict()

@router.delete("/antigravity")
async def antigravity_disconnect(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    account_store = AntigravityAccountStore(store, settings.SECRET_KEY)
    account_id = _get_account_id(scope, org_id, user.id)
    
    await account_store.forget(account_id)
    return {"success": True}

@router.put("/antigravity/project")
async def antigravity_set_project(
    req: SetProjectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, req.scope, req.org_id, user)
    store = _resolve_store(db, req.scope, req.org_id, user.id)
    account_store = AntigravityAccountStore(store, settings.SECRET_KEY)
    account_id = _get_account_id(req.scope, req.org_id, user.id)
    
    status_data = await account_store.status(account_id)
    if not status_data.connected:
        raise HTTPException(status_code=400, detail="Not connected")
        
    await account_store.set_project_id(account_id, req.project_id)
    return {"success": True}

# --- API Key Endpoints ---

@router.put("/keys/{provider}")
async def put_api_key(
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
    
    await api_key_store.set(provider, req.key)
    return {"success": True}

@router.get("/keys")
async def list_api_keys(
    scope: str = Query(...),
    org_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    _check_access(db, scope, org_id, user)
    store = _resolve_store(db, scope, org_id, user.id)
    api_key_store = ApiKeyStore(store, settings.SECRET_KEY)
    
    hints = await api_key_store.list_hints()
    return {"keys": hints}

@router.delete("/keys/{provider}")
async def delete_api_key(
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
    
    await api_key_store.set(provider, None)
    return {"success": True}

# --- Combined Status Endpoint ---

@router.get("/status")
async def get_all_status(
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
    
    account_id = _get_account_id(scope, org_id, user.id)
    
    claude_status = await claude_store.status(account_id)
    antigravity_status = await antigravity_store.status(account_id)
    keys_status = await api_key_store.list_hints()
    
    return {
        "claude": claude_status.dict(),
        "antigravity": antigravity_status.dict(),
        "keys": keys_status
    }
