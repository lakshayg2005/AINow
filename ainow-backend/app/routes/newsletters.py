from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import NewsletterIssue, NewsletterSection, User
from app.schemas.newsletter import (
    NewsletterCreateRequest,
    NewsletterCreateResponse,
    NewsletterDetailResponse,
    NewsletterSectionCreateRequest,
    NewsletterSectionResponse,
    NewsletterSummaryResponse,
)
from app.compose.persist import load_issue_content
from app.core.dependencies import get_current_admin
from app.jobs import JobConflict, start_job
from app.services.publishing import PublishError, publish_issue


def _summary(
    issue: NewsletterIssue,
) -> NewsletterSummaryResponse:
    content = load_issue_content(issue)

    cover = None

    if content:
        cards = (
            ([content.deep_dive] if content.deep_dive else [])
            + list(content.quick_news)
            + ([content.paper_of_week] if content.paper_of_week else [])
        )
        cover = next((card.image_url for card in cards if card.image_url), None)

    return NewsletterSummaryResponse(
        id=issue.id,
        title=issue.title,
        status=issue.status,
        created_at=issue.created_at,
        published_at=issue.published_at,
        headline=content.headline if content else None,
        intro=content.intro if content else None,
        cover_image=cover,
    )


def _detail(
    issue: NewsletterIssue,
) -> NewsletterDetailResponse:
    content = load_issue_content(issue)

    return NewsletterDetailResponse(
        id=issue.id,
        title=issue.title,
        status=issue.status,
        created_at=issue.created_at,
        published_at=issue.published_at,
        html_content=issue.html_content,
        content=content.model_dump(mode="json") if content else None,
    )


router = APIRouter(
    prefix="/newsletters",
    tags=["Newsletters"],
)


# ---------------------------------------------------------
# CREATE DRAFT
# ---------------------------------------------------------
@router.post(
    "",
    response_model=NewsletterCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_newsletter(
    newsletter_data: NewsletterCreateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    newsletter = NewsletterIssue(
        title=newsletter_data.title,
        status="draft",
    )

    db.add(newsletter)
    db.commit()
    db.refresh(newsletter)

    return newsletter


# ---------------------------------------------------------
# ADD SECTION TO DRAFT
# ---------------------------------------------------------

@router.post(
    "/{newsletter_id}/sections",
    response_model=NewsletterSectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_newsletter_section(
    newsletter_id: int,
    section_data: NewsletterSectionCreateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    newsletter = (
        db.query(NewsletterIssue)
        .filter(NewsletterIssue.id == newsletter_id)
        .first()
    )

    if not newsletter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Newsletter not found",
        )

    if newsletter.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sections can only be added to a draft newsletter",
        )

    section = NewsletterSection(
        newsletter_issue_id=newsletter_id,
        section_type=section_data.section_type,
        title=section_data.title,
        content=section_data.content,
        display_order=section_data.display_order,
    )

    db.add(section)
    db.commit()
    db.refresh(section)

    return section


# ---------------------------------------------------------
# SAVE FINAL HTML
# ---------------------------------------------------------

@router.put(
    "/{newsletter_id}/html",
    status_code=status.HTTP_200_OK,
)
def save_newsletter_html(
    newsletter_id: int,
    html_content: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    newsletter = (
        db.query(NewsletterIssue)
        .filter(NewsletterIssue.id == newsletter_id)
        .first()
    )

    if not newsletter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Newsletter not found",
        )

    if newsletter.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HTML can only be updated for a draft newsletter",
        )

    newsletter.html_content = html_content

    db.commit()
    db.refresh(newsletter)

    return {
        "message": "Newsletter HTML saved successfully",
        "newsletter_id": newsletter.id,
    }


# ---------------------------------------------------------
# PUBLISH
# ---------------------------------------------------------

@router.post(
    "/{newsletter_id}/publish",
    status_code=status.HTTP_200_OK,
)
async def publish_newsletter(
    newsletter_id: int,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    newsletter = (
        db.query(NewsletterIssue)
        .filter(NewsletterIssue.id == newsletter_id)
        .first()
    )

    if not newsletter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Newsletter not found",
        )

    try:
        stories_recorded = publish_issue(db, newsletter)
    except PublishError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    # Sending to every subscriber takes a while; do it in the
    # background and let the caller poll /admin/jobs/{id}.
    try:
        job = start_job("deliver", params={"issue_id": newsletter.id})
        job_id = job.id
    except JobConflict:
        job_id = None

    return {
        "message": "Newsletter published; delivery started",
        "newsletter_id": newsletter.id,
        "published_at": newsletter.published_at,
        "stories_recorded": stories_recorded,
        "delivery_job_id": job_id,
    }


# ---------------------------------------------------------
# PUBLIC ARCHIVE
# ---------------------------------------------------------

@router.get(
    "",
    response_model=list[NewsletterSummaryResponse],
)
def get_newsletters(
    db: Session = Depends(get_db),
):
    newsletters = (
        db.query(NewsletterIssue)
        .filter(NewsletterIssue.status == "published")
        .order_by(NewsletterIssue.published_at.desc())
        .all()
    )

    return [_summary(issue) for issue in newsletters]


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

    return _detail(newsletter)


# ---------------------------------------------------------
# PUBLIC DETAIL / FINAL HTML
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