"""
Public newsletter archive: list, search and read published
issues, plus the admin-only draft preview.

Drafts are created, published and deleted from the admin
newsroom (app/routes/admin.py).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.compose.persist import load_issue_content
from app.core.dependencies import get_current_admin
from app.db.database import get_db
from app.db.models import CoveredStory, NewsletterIssue, User
from app.ingest.utils import truncate
from app.schemas.issue import IssueContent
from app.schemas.newsletter import (
    ArchiveMatch,
    ArchiveSearchResult,
    NewsletterDetailResponse,
    NewsletterSummaryResponse,
)
from app.services.archive_search import search_archive


def _cover_image(
    content: IssueContent | None,
) -> str | None:
    if content is None:
        return None

    cards = (
        ([content.deep_dive] if content.deep_dive else [])
        + list(content.quick_news)
        + ([content.paper_of_week] if content.paper_of_week else [])
    )

    return next((card.image_url for card in cards if card.image_url), None)


def _summary(
    issue: NewsletterIssue,
) -> NewsletterSummaryResponse:
    content = load_issue_content(issue)

    return NewsletterSummaryResponse(
        id=issue.id,
        title=issue.title,
        status=issue.status,
        created_at=issue.created_at,
        published_at=issue.published_at,
        headline=content.headline if content else None,
        intro=content.intro if content else None,
        cover_image=_cover_image(content),
    )


def _detail(
    issue: NewsletterIssue,
    include_review: bool = False,
) -> NewsletterDetailResponse:
    content = load_issue_content(issue)

    # The editor's review is for the admin preview only.
    exclude = None if include_review else {"review"}

    return NewsletterDetailResponse(
        id=issue.id,
        title=issue.title,
        status=issue.status,
        created_at=issue.created_at,
        published_at=issue.published_at,
        html_content=issue.html_content,
        content=content.model_dump(mode="json", exclude=exclude) if content else None,
    )


router = APIRouter(
    prefix="/newsletters",
    tags=["Newsletters"],
)


# ---------------------------------------------------------
# PUBLIC ARCHIVE
# ---------------------------------------------------------

@router.get(
    "",
    response_model=list[NewsletterSummaryResponse],
)
def get_newsletters(
    limit: int | None = Query(default=None, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # Some early issues were published without a timestamp.
    query = (
        db.query(NewsletterIssue)
        .filter(NewsletterIssue.status == "published")
        .order_by(
            func.coalesce(NewsletterIssue.published_at, NewsletterIssue.created_at).desc()
        )
    )

    if limit:
        query = query.limit(limit)

    return [_summary(issue) for issue in query.all()]


# ---------------------------------------------------------
# ARCHIVE SEARCH (declared before /{newsletter_id})
# ---------------------------------------------------------

@router.get(
    "/search",
    response_model=list[ArchiveSearchResult],
)
def search_newsletters(
    q: str = Query(min_length=2, max_length=200),
    db: Session = Depends(get_db),
):
    results = []

    for issue, stories in search_archive(db, q):
        content = load_issue_content(issue)

        # A story can be recorded once per section it appeared in.
        unique: dict[str, CoveredStory] = {}

        for story in stories:
            unique.setdefault(story.headline, story)

        results.append(
            ArchiveSearchResult(
                id=issue.id,
                title=issue.title,
                published_at=issue.published_at or issue.created_at,
                headline=content.headline if content else None,
                cover_image=_cover_image(content),
                matches=[
                    ArchiveMatch(
                        headline=story.headline,
                        section=story.section_type,
                        summary=truncate(story.summary, 220) if story.summary else None,
                    )
                    for story in unique.values()
                ],
            )
        )

    return results


# ---------------------------------------------------------
# DRAFT PREVIEW (any status)
# ---------------------------------------------------------

@router.get(
    "/{newsletter_id}/preview",
    response_model=NewsletterDetailResponse,
)
def preview_newsletter(
    newsletter_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    newsletter = db.get(NewsletterIssue, newsletter_id)

    if not newsletter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Newsletter not found",
        )

    return _detail(newsletter, include_review=True)


# ---------------------------------------------------------
# PUBLIC DETAIL
# ---------------------------------------------------------

@router.get(
    "/{newsletter_id}",
    response_model=NewsletterDetailResponse,
)
def get_newsletter(
    newsletter_id: int,
    db: Session = Depends(get_db),
):
    newsletter = (
        db.query(NewsletterIssue)
        .filter(
            NewsletterIssue.id == newsletter_id,
            NewsletterIssue.status == "published",
        )
        .first()
    )

    if not newsletter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Newsletter not found",
        )

    return _detail(newsletter)
