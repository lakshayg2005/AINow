from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import NewsletterIssue, NewsletterSection
from app.schemas.newsletter import (
    NewsletterCreateRequest,
    NewsletterCreateResponse,
    NewsletterDetailResponse,
    NewsletterSectionCreateRequest,
    NewsletterSectionResponse,
    NewsletterSummaryResponse,
)
from app.services.email.sender import (
    send_newsletter_to_subscribers,
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
def publish_newsletter(
    newsletter_id: int,
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

    if newsletter.status == "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Newsletter is already published",
        )

    if not newsletter.html_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Final HTML has not been generated yet",
        )

    sections = (
        db.query(NewsletterSection)
        .filter(NewsletterSection.newsletter_issue_id == newsletter_id)
        .count()
    )

    if sections == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Newsletter must contain at least one section",
        )

    newsletter.status = "published"
    newsletter.published_at = datetime.utcnow()

    db.commit()
    db.refresh(newsletter)

    delivery_results = (
    send_newsletter_to_subscribers(
        db=db,
        newsletter=newsletter,
    )
    )

    return {
        "message": "Newsletter published successfully",
        "newsletter_id": newsletter.id,
        "published_at": newsletter.published_at,
        "delivery_summary": {
            "total": len(delivery_results),
            "sent": sum(
                1
                for item in delivery_results
                if item["status"] == "sent"
            ),
            "failed": sum(
                1
                for item in delivery_results
                if item["status"] == "failed"
            ),
        },
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

    return newsletters


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

    return newsletter