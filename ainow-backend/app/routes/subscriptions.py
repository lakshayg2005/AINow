from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import decode_unsubscribe_token
from app.db.database import get_db
from app.db.models import Subscription, User
from app.schemas.subscription import SubscriptionResponse


router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"],
)


@router.get(
    "/me",
    response_model=SubscriptionResponse,
)
def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .first()
    )

    if not subscription:
        return {
            "id": None,
            "user_id": current_user.id,
            "status": "not_subscribed",
            "created_at": None,
            "updated_at": None,
            "message": "You are not subscribed to AINow.",
        }

    return {
        "id": subscription.id,
        "user_id": subscription.user_id,
        "status": subscription.status,
        "created_at": subscription.created_at,
        "updated_at": subscription.updated_at,
        "message": (
            "Your AINow subscription is active."
            if subscription.status == "active"
            else "Your AINow subscription is canceled."
        ),
    }


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def subscribe(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before subscribing.",
        )

    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .first()
    )

    if subscription:
        if subscription.status == "active":
            return {
                "id": subscription.id,
                "user_id": subscription.user_id,
                "status": subscription.status,
                "created_at": subscription.created_at,
                "updated_at": subscription.updated_at,
                "message": "You are already subscribed to AINow.",
            }

        subscription.status = "active"
        subscription.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(subscription)

        return {
            "id": subscription.id,
            "user_id": subscription.user_id,
            "status": subscription.status,
            "created_at": subscription.created_at,
            "updated_at": subscription.updated_at,
            "message": "Your AINow subscription has been reactivated.",
        }

    subscription = Subscription(
        user_id=current_user.id,
        status="active",
    )

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return {
        "id": subscription.id,
        "user_id": subscription.user_id,
        "status": subscription.status,
        "created_at": subscription.created_at,
        "updated_at": subscription.updated_at,
        "message": "You are now subscribed to AINow.",
    }


@router.delete(
    "",
    response_model=SubscriptionResponse,
)
def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found.",
        )

    if subscription.status == "canceled":
        return {
            "id": subscription.id,
            "user_id": subscription.user_id,
            "status": subscription.status,
            "created_at": subscription.created_at,
            "updated_at": subscription.updated_at,
            "message": "Your subscription is already canceled.",
        }

    subscription.status = "canceled"
    subscription.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(subscription)

    return {
        "id": subscription.id,
        "user_id": subscription.user_id,
        "status": subscription.status,
        "created_at": subscription.created_at,
        "updated_at": subscription.updated_at,
        "message": "Your AINow subscription has been canceled.",
    }

# ---------------------------------------------------------
# UNSUBSCRIBE (no login)
# ---------------------------------------------------------

class UnsubscribeRequest(BaseModel):
    token: str | None = None


@router.post(
    "/unsubscribe",
)
def unsubscribe(
    token: str | None = None,
    request: UnsubscribeRequest | None = None,
    db: Session = Depends(get_db),
):
    """
    Unsubscribe via the signed link in every newsletter.

    Mail clients' one-click button (RFC 8058) POSTs here with
    the token in the query string; the /unsubscribe page sends
    it in the JSON body after the reader confirms.
    """

    raw_token = token or (request.token if request else None)

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing unsubscribe token.",
        )

    try:
        user_id = decode_unsubscribe_token(raw_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This unsubscribe link is invalid.",
        )

    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .first()
    )

    if subscription and subscription.status == "active":
        subscription.status = "canceled"
        subscription.updated_at = datetime.utcnow()
        db.commit()

    # Same answer whether or not they were subscribed.
    return {
        "message": "You have been unsubscribed from AINow.",
    }
