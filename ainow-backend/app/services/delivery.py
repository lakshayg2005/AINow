"""
Newsletter delivery.

Each subscriber gets their own copy (their unsubscribe link),
with a plain-text part and RFC 8058 one-click unsubscribe
headers. One SMTP connection is reused for the whole batch,
and every send is recorded in newsletter_deliveries, so a
retry only touches recipients who haven't received the issue.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.compose.persist import load_issue_content, web_url_for
from app.core.config import settings
from app.core.security import create_unsubscribe_token
from app.db.models import NewsletterDelivery, NewsletterIssue, User
from app.services.email.provider import EmailProvider, get_email_provider
from app.services.email.sender import get_eligible_recipients
from app.services.issue_email import render_issue_email, render_issue_text


@dataclass
class OutgoingEmail:
    subject: str
    html: str
    text: str | None
    headers: dict[str, str]


def unsubscribe_urls(
    user: User,
) -> tuple[str, str]:
    """
    (page_url, one_click_url). The page asks for confirmation,
    so link scanners that open every URL can't unsubscribe
    people; mail clients POST to the one-click URL directly.
    """

    token = create_unsubscribe_token(user.id)

    return (
        f"{settings.frontend_url.rstrip('/')}/unsubscribe?token={token}",
        f"{settings.api_url.rstrip('/')}/subscriptions/unsubscribe?token={token}",
    )


def build_email(
    issue: NewsletterIssue,
    user: User,
) -> OutgoingEmail:
    page_url, one_click_url = unsubscribe_urls(user)
    web_url = web_url_for(issue.id)
    content = load_issue_content(issue)

    if content is not None:
        html = render_issue_email(
            content,
            web_url=web_url,
            manage_url=f"{settings.frontend_url.rstrip('/')}/dashboard",
            unsubscribe_url=page_url,
        )
        text = render_issue_text(content, web_url, page_url)
        subject = f"AINow — {content.headline or content.title}"

    else:
        # Legacy issues: stored HTML plus an unsubscribe footer.
        footer = (
            '<p style="font:12px Arial,sans-serif;color:#888;text-align:center;">'
            f'<a href="{page_url}" style="color:#888;">Unsubscribe</a></p>'
        )
        stored = issue.html_content or ""
        html = (
            stored.replace("</body>", f"{footer}</body>")
            if "</body>" in stored
            else stored + footer
        )
        text = None
        subject = f"AINow — {issue.title}"

    return OutgoingEmail(
        subject=subject,
        html=html,
        text=text,
        headers={
            "List-Unsubscribe": f"<{one_click_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )


def _delivery_row(
    db: Session,
    issue: NewsletterIssue,
    user: User,
) -> NewsletterDelivery:
    delivery = (
        db.query(NewsletterDelivery)
        .filter(
            NewsletterDelivery.newsletter_issue_id == issue.id,
            NewsletterDelivery.user_id == user.id,
        )
        .first()
    )

    if delivery is None:
        delivery = NewsletterDelivery(
            newsletter_issue_id=issue.id,
            user_id=user.id,
            recipient_email=user.email,
            status="pending",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

    return delivery


def deliver_issue(
    db: Session,
    issue_id: int,
    provider: EmailProvider | None = None,
    only_failed: bool = False,
    pause: Callable[[float], None] = time.sleep,
) -> dict:
    """
    Send a published issue to every active, verified
    subscriber who hasn't received it yet.

    Returns {"total", "sent", "failed", "skipped"}.
    """

    issue = db.get(NewsletterIssue, issue_id)

    if issue is None:
        raise ValueError(f"Newsletter {issue_id} not found")

    if issue.status != "published":
        raise ValueError("Only published issues can be delivered")

    provider = provider or get_email_provider()
    recipients = [user for user, _ in get_eligible_recipients(db)]

    summary = {"total": len(recipients), "sent": 0, "failed": 0, "skipped": 0}

    if not recipients:
        return summary

    with provider.batch():
        for index, user in enumerate(recipients):
            delivery = _delivery_row(db, issue, user)

            if delivery.status == "sent" or (
                only_failed and delivery.status != "failed"
            ):
                summary["skipped"] += 1
                continue

            email = build_email(issue, user)

            try:
                provider.send(
                    recipient_email=user.email,
                    subject=email.subject,
                    html_content=email.html,
                    text_content=email.text,
                    headers=email.headers,
                    idempotency_key=f"newsletter-{issue.id}-user-{user.id}",
                )

                delivery.status = "sent"
                delivery.sent_at = datetime.utcnow()
                delivery.error_message = None
                summary["sent"] += 1

            except Exception as error:
                delivery.status = "failed"
                delivery.failed_at = datetime.utcnow()
                delivery.error_message = str(error)[:2000]
                summary["failed"] += 1

            db.commit()

            if index < len(recipients) - 1:
                pause(settings.email_send_interval_seconds)

    return summary


def send_test_email(
    issue: NewsletterIssue,
    user: User,
    recipient_email: str | None = None,
    provider: EmailProvider | None = None,
) -> str:
    """
    Send one copy (drafts included) for review. Not recorded
    as a delivery.
    """

    email = build_email(issue, user)
    target = recipient_email or user.email

    (provider or get_email_provider()).send(
        recipient_email=target,
        subject=f"[TEST] {email.subject}",
        html_content=email.html,
        text_content=email.text,
        headers=email.headers,
        idempotency_key=f"test-{issue.id}-{datetime.utcnow().timestamp()}",
    )

    return target


def delivery_stats(
    db: Session,
    issue_id: int,
) -> dict:
    rows = (
        db.query(NewsletterDelivery)
        .filter(NewsletterDelivery.newsletter_issue_id == issue_id)
        .all()
    )

    stats = {"sent": 0, "failed": 0, "pending": 0}

    for row in rows:
        stats[row.status] = stats.get(row.status, 0) + 1

    stats["failures"] = [
        {"email": row.recipient_email, "error": row.error_message}
        for row in rows
        if row.status == "failed"
    ][:20]

    return stats
