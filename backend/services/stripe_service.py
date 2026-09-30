"""Stripe service for billing and subscription management."""
import stripe
from typing import Optional, Dict
from datetime import datetime
from backend.core.config import settings
from backend.models.user import User
from backend.models.organization import Organization
from sqlalchemy.orm import Session

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_customer(email: str, organization_id: int) -> str:
    """
    Create a Stripe customer for an organization.
    
    Args:
        email: Organization owner's email address
        organization_id: Organization's database ID
        
    Returns:
        Stripe customer ID
    """
    try:
        customer = stripe.Customer.create(
            email=email,
            metadata={
                "organization_id": str(organization_id),
            }
        )
        return customer.id
    except Exception as e:
        raise Exception(f"Failed to create Stripe customer: {str(e)}")


def create_checkout_session(org: Organization, price_id: str) -> Dict[str, str]:
    """
    Create a Stripe Checkout session for subscription.
    
    Args:
        org: Organization model instance
        price_id: Stripe Price ID
        
    Returns:
        Dictionary with checkout_url
    """
    # Validate price_id is not empty
    if not price_id or not price_id.strip():
        raise ValueError("Price ID is required and cannot be empty")
    
    try:
        # Get owner email for customer creation
        from backend.db.session import SessionLocal
        db = SessionLocal()
        try:
            owner = db.query(User).filter(User.id == org.owner_user_id).first()
            owner_email = owner.email if owner else "unknown@example.com"
        finally:
            db.close()
        
        # Ensure organization has a Stripe customer ID
        if not org.stripe_customer_id:
            customer_id = create_stripe_customer(owner_email, org.id)
            org.stripe_customer_id = customer_id
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=org.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{settings.APP_PUBLIC_URL.rstrip('/')}/app/billing?success=true",
            cancel_url=f"{settings.APP_PUBLIC_URL.rstrip('/')}/app/billing?canceled=true",
            metadata={
                "organization_id": str(org.id),
            }
        )
        
        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
        }
    except Exception as e:
        raise Exception(f"Failed to create checkout session: {str(e)}")


def create_billing_portal(org: Organization) -> Dict[str, str]:
    """
    Create a Stripe Billing Portal session.
    
    Args:
        org: Organization model instance
        
    Returns:
        Dictionary with portal_url
    """
    try:
        if not org.stripe_customer_id:
            raise Exception("Organization does not have a Stripe customer ID")
        
        # Create billing portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=org.stripe_customer_id,
            return_url=f"{settings.APP_PUBLIC_URL.rstrip('/')}/app/billing",
        )
        
        return {
            "portal_url": portal_session.url,
        }
    except Exception as e:
        raise Exception(f"Failed to create billing portal session: {str(e)}")


def update_subscription_status(
    db: Session,
    organization_id: int,
    status: str,
    plan: Optional[str] = None,
    subscription_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    trial_ends_at: Optional[datetime] = None
) -> Organization:
    """
    Update organization's subscription status in database.
    
    Args:
        db: Database session
        organization_id: Organization ID
        status: Subscription status (active, past_due, canceled, unpaid, trialing, inactive)
        plan: Subscription plan name (optional)
        subscription_id: Stripe subscription ID (optional)
        customer_id: Stripe customer ID (optional)
        trial_ends_at: Trial end date (optional)
        
    Returns:
        Updated Organization model instance
    """
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise ValueError(f"Organization with ID {organization_id} not found")
    
    org.subscription_status = status
    if plan is not None:
        org.subscription_plan = plan
    if subscription_id is not None:
        org.stripe_subscription_id = subscription_id
    if customer_id is not None:
        org.stripe_customer_id = customer_id
    if trial_ends_at is not None:
        org.trial_ends_at = trial_ends_at
    
    db.commit()
    db.refresh(org)
    return org

