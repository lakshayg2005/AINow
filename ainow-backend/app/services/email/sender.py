from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import (
    NewsletterDelivery,
    NewsletterIssue,
    Subscription,
    User,
)

from app.services.email.smtp_provider import (
    SMTPEmailProvider,
)


def get_eligible_recipients(
    db: Session,
):
    return (
        db.query(User, Subscription)
        .join(
            Subscription,
            Subscription.user_id == User.id,
        )
        .filter(
            User.is_email_verified.is_(True),
            Subscription.status == "active",
        )
        .all()
    )


def send_newsletter_to_subscribers(
    db: Session,
    newsletter: NewsletterIssue,
):
    provider = SMTPEmailProvider()

    recipients = get_eligible_recipients(db)

    results = []

    for user, subscription in recipients:

        # -----------------------------------------
        # Avoid duplicate delivery rows
        # -----------------------------------------

        delivery = (
            db.query(NewsletterDelivery)
            .filter(
                NewsletterDelivery.newsletter_issue_id
                == newsletter.id,

                NewsletterDelivery.user_id
                == user.id,
            )
            .first()
        )

        if delivery:

            if delivery.status == "sent":
                results.append(
                    {
                        "user_id": user.id,
                        "status": "sent",
                    }
                )

                continue

        else:

            delivery = NewsletterDelivery(
                newsletter_issue_id=(
                    newsletter.id
                ),
                user_id=user.id,
                recipient_email=user.email,
                status="pending",
            )

            db.add(delivery)
            db.commit()
            db.refresh(delivery)

        # -----------------------------------------
        # Send
        # -----------------------------------------

        try:

            idempotency_key = (
                f"newsletter-{newsletter.id}"
                f"-user-{user.id}"
            )

            provider.send(
                recipient_email=(
                    delivery.recipient_email
                ),
                subject=(
                    f"AINow — {newsletter.title}"
                ),
                html_content=(
                    newsletter.html_content
                ),
                idempotency_key=idempotency_key,
            )

            delivery.status = "sent"
            delivery.sent_at = datetime.utcnow()
            delivery.error_message = None

            db.commit()

            results.append(
                {
                    "user_id": user.id,
                    "status": "sent",
                }
            )

        except Exception as error:

            delivery.status = "failed"
            delivery.failed_at = datetime.utcnow()
            delivery.error_message = str(error)

            db.commit()

            results.append(
                {
                    "user_id": user.id,
                    "status": "failed",
                    "error": str(error),
                }
            )

    return results