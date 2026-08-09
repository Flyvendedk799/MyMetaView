"""Authentication routes."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.schemas.user import User, UserCreate, Token
from backend.core.security import create_access_token
from backend.core.config import settings
from backend.core.deps import get_current_user
from backend.db.session import get_db
from backend.storage.users import create_user, authenticate_user
from backend.models.user import User as UserModel
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationMember, OrganizationRole
from backend.services.activity_logger import log_activity, get_client_ip
from backend.services.rate_limiter import check_rate_limit, get_rate_limit_key_for_ip
from backend.services.email_service import send_welcome_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=User, status_code=status.HTTP_201_CREATED)
def signup(user_in: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Create a new user account."""
    # Rate limiting: 20 signups per 15 minutes per IP
    client_ip = get_client_ip(request)
    rate_limit_key = get_rate_limit_key_for_ip(client_ip, "signup")
    if not check_rate_limit(rate_limit_key, limit=20, window_seconds=900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    # Check if user already exists
    existing_user = db.query(UserModel).filter(UserModel.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = create_user(db, user_in)
    
    # Create default organization for the user, on a 14-day (no-card) trial
    from datetime import datetime, timedelta
    from backend.core.plans import TRIAL_PLAN, TRIAL_DAYS
    default_org = Organization(
        name=f"{user.email}'s Organization",
        owner_user_id=user.id,
        subscription_status="trialing",
        subscription_plan=TRIAL_PLAN,
        trial_ends_at=datetime.utcnow() + timedelta(days=TRIAL_DAYS),
    )
    db.add(default_org)
    db.commit()
    db.refresh(default_org)
    
    # Create owner membership
    membership = OrganizationMember(
        organization_id=default_org.id,
        user_id=user.id,
        role=OrganizationRole.OWNER
    )
    db.add(membership)
    db.commit()
    
    # Log signup activity
    log_activity(
        db,
        user_id=user.id,
        action="user.signup",
        metadata={"email": user.email, "organization_id": default_org.id},
        request=request
    )

    # Send welcome email (fire-and-forget; must never fail signup)
    try:
        send_welcome_email(user.email)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to enqueue welcome email")

    return user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and get access token."""
    # Rate limiting: 20 login attempts per 15 minutes per IP (brute force protection)
    client_ip = get_client_ip(request)
    rate_limit_key = get_rate_limit_key_for_ip(client_ip, "login")
    if not check_rate_limit(rate_limit_key, limit=20, window_seconds=900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # OAuth2PasswordRequestForm uses 'username' field, but we use email
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    # Log login activity
    log_activity(
        db,
        user_id=user.id,
        action="user.login",
        metadata={"email": user.email},
        request=request
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=User)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current authenticated user information with organization subscription status."""
    # Get user's primary organization (first owned or first membership)
    from backend.models.organization import Organization
    from backend.models.organization_member import OrganizationMember
    
    # Try to get owned organization first
    org = db.query(Organization).filter(
        Organization.owner_user_id == current_user.id
    ).first()
    
    # If no owned org, get first membership
    if not org:
        membership = db.query(OrganizationMember).join(Organization).filter(
            OrganizationMember.user_id == current_user.id
        ).first()
        if membership:
            org = db.query(Organization).filter(Organization.id == membership.organization_id).first()
    
    # If organization found, sync subscription status to user object
    if org:
        current_user.subscription_status = org.subscription_status
        current_user.subscription_plan = org.subscription_plan
        current_user.trial_ends_at = org.trial_ends_at
        current_user.stripe_customer_id = org.stripe_customer_id
        current_user.stripe_subscription_id = org.stripe_subscription_id
    
    return current_user

