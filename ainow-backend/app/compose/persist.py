from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import NewsletterIssue, NewsletterSection, Story
from app.schemas.issue import IssueContent
from app.services.issue_email import render_issue_email
from app.stories.novelty import mark_covered


def web_url_for(
    issue_id: int,
) -> str:
    return f"{settings.frontend_url.rstrip('/')}/newsletters/{issue_id}"


def load_issue_content(
    issue: NewsletterIssue,
) -> IssueContent | None:
    """Parse v2 content; None for legacy issues."""

    if not issue.raw_content or '"version"' not in issue.raw_content[:200]:
        return None

    try:
        return IssueContent.model_validate_json(issue.raw_content)
    except ValueError:
        return None


_SECTIONS = (
    ("quick_news", "Quick News", "quick_news"),
    ("research_spotlight", "Research Spotlight", "research_spotlight"),
    ("paper_of_week", "Paper of the Week", "paper_of_week"),
    ("deep_dive", "AI Deep Dive", "deep_dive"),
    ("ai_trends", "AI Trends", "trends"),
    ("ai_concept", "AI Concept", "concept"),
    ("resources", "AI Resources", "resources"),
    ("our_take", "Our Take", "our_take"),
    ("sources", "Sources", "sources"),
)


def save_issue_draft(
    db: Session,
    content: IssueContent,
) -> NewsletterIssue:
    issue = NewsletterIssue(
        title=content.title,
        status="draft",
    )

    db.add(issue)
    db.flush()

    _write_content(db, issue, content)

    db.commit()
    db.refresh(issue)

    return issue


def update_issue_content(
    db: Session,
    issue: NewsletterIssue,
    content: IssueContent,
) -> None:
    """Replace a draft's content (e.g. after re-checking it)."""

    db.query(NewsletterSection).filter(
        NewsletterSection.newsletter_issue_id == issue.id
    ).delete()

    _write_content(db, issue, content)

    db.commit()


def _write_content(
    db: Session,
    issue: NewsletterIssue,
    content: IssueContent,
) -> None:
    issue.raw_content = content.model_dump_json(indent=2)

    order = 1

    for section_type, title, field in _SECTIONS:
        value = getattr(content, field)

        if not value:
            continue

        db.add(
            NewsletterSection(
                newsletter_issue_id=issue.id,
                section_type=section_type,
                title=title,
                content=(
                    value
                    if isinstance(value, str)
                    else content.model_dump_json(include={field})
                ),
                display_order=order,
            )
        )
        order += 1

    issue.html_content = render_issue_email(
        content,
        web_url=web_url_for(issue.id),
        manage_url=f"{settings.frontend_url.rstrip('/')}/dashboard",
    )


def mark_issue_covered(
    db: Session,
    issue: NewsletterIssue,
) -> int:
    """
    Record every story in a published issue in the freshness
    memory, so later issues don't repeat it.
    """

    content = load_issue_content(issue)

    if content is None:
        return 0

    marked = 0

    for story_id, section, headline, summary in content.story_ids():
        story = db.get(Story, story_id)

        if story is None:
            continue

        mark_covered(
            db,
            story,
            section_type=section,
            headline=headline,
            summary=summary,
            newsletter_issue_id=issue.id,
        )
        marked += 1

    db.commit()

    return marked
