import json

from sqlalchemy.orm import Session

from app.db.models import NewsletterIssue
from app.schemas.newsletter import NewsletterContent
from app.services.newsletter_renderer import (
    render_newsletter_html,
)


def create_newsletter_issue(
    db: Session,
    newsletter: NewsletterContent,
    title: str,
) -> NewsletterIssue:

    raw_content = newsletter.model_dump_json(
        indent=2
    )

    html_content = render_newsletter_html(
        newsletter,
        title=title,
    )

    issue = NewsletterIssue(
        title=title,
        raw_content=raw_content,
        html_content=html_content,
        status="draft",
    )

    db.add(issue)
    db.commit()
    db.refresh(issue)

    return issue