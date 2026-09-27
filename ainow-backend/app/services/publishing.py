from datetime import datetime

from sqlalchemy.orm import Session

from app.compose.persist import mark_issue_covered
from app.db.models import NewsletterIssue, NewsletterSection


class PublishError(ValueError):
    pass


def publish_issue(
    db: Session,
    issue: NewsletterIssue,
) -> int:
    """
    Mark a draft published and record its stories in the
    freshness memory. Delivery is a separate background job.

    Returns the number of stories recorded as covered.
    """

    if issue.status == "published":
        raise PublishError("Newsletter is already published")

    if not issue.html_content:
        raise PublishError("Final HTML has not been generated yet")

    sections = (
        db.query(NewsletterSection)
        .filter(NewsletterSection.newsletter_issue_id == issue.id)
        .count()
    )

    if sections == 0:
        raise PublishError("Newsletter must contain at least one section")

    issue.status = "published"
    issue.published_at = datetime.utcnow()

    db.commit()
    db.refresh(issue)

    return mark_issue_covered(db, issue)
