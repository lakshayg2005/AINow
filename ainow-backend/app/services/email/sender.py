from sqlalchemy.orm import Session

from app.db.models import (
    NewsletterIssue,
    Subscription,
    User,
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
    """
    Kept for existing callers; delivery now lives in
    app.services.delivery (per-recipient unsubscribe links,
    plain-text part, one SMTP connection per batch).
    """

    from app.services.delivery import deliver_issue

    return deliver_issue(db, newsletter.id)
