"""Stripe billing: checkout, customer portal, and the webhook that is the ONLY
writer of `user.plan`. The client never sets entitlements; it only redirects to
Stripe-hosted pages, so limits cannot be bypassed from the frontend."""

import logging

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models import User
from app.services import usage

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_stripe() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured on this deployment",
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY


@router.get("/config")
def billing_config() -> dict:
    """Public: lets the frontend know whether billing is live and the price."""
    return {
        "enabled": bool(settings.STRIPE_SECRET_KEY),
        "pro_price_cents": settings.PRO_PRICE_CENTS,
        "free_document_limit": settings.FREE_DOCUMENT_LIMIT,
        "free_questions_per_day": settings.FREE_QUESTIONS_PER_DAY,
    }


@router.get("/usage")
def my_usage(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    """Current plan + consumption, for the dashboard progress ring and paywall copy."""
    return usage.usage_summary(db, current_user)


@router.post("/checkout")
@limiter.limit("10/minute")
def create_checkout_session(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a Stripe Checkout session for the Pro subscription."""
    _require_stripe()
    if current_user.is_pro:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already on Pro")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            client_reference_id=str(current_user.id),
            customer=current_user.stripe_customer_id or None,
            customer_email=None if current_user.stripe_customer_id else current_user.email,
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": settings.PRO_PRICE_CENTS,
                        "recurring": {"interval": "month"},
                        "product_data": {
                            "name": "DocMaid Pro",
                            "description": "Unlimited questions, 50 documents, priority speed",
                        },
                    },
                }
            ],
            success_url=f"{settings.FRONTEND_URL}/dashboard?upgraded=1",
            cancel_url=f"{settings.FRONTEND_URL}/pricing",
        )
    except stripe.StripeError:
        logger.exception("Stripe checkout session creation failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not start checkout. Please try again.",
        ) from None
    return {"checkout_url": session.url}


@router.post("/portal")
def create_portal_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Stripe-hosted billing portal (cancel / update card)."""
    _require_stripe()
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No billing account")
    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/dashboard",
        )
    except stripe.StripeError:
        logger.exception("Stripe portal session failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not open the billing portal. Please try again.",
        ) from None
    return {"portal_url": session.url}


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict:
    """Receive subscription lifecycle events. Signature-verified; the only
    code path that changes a user's plan."""
    _require_stripe()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature or "", settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature"
        ) from None

    data = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        user = db.get(User, int(data["client_reference_id"]))
        if user is not None:
            user.plan = "pro"
            user.stripe_customer_id = data.get("customer")
            user.stripe_subscription_id = data.get("subscription")
            db.commit()
            logger.info("User %s upgraded to Pro", user.id)

    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.updated"):
        customer_id = data.get("customer")
        user = db.scalar(select(User).where(User.stripe_customer_id == customer_id))
        if user is not None:
            active = data.get("status") in ("active", "trialing") and event["type"] != (
                "customer.subscription.deleted"
            )
            user.plan = "pro" if active else "free"
            db.commit()
            logger.info("User %s plan set to %s via %s", user.id, user.plan, event["type"])

    return {"received": True}
