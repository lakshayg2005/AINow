from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    AIConcept,
    AIResource,
    NewsletterConcept,
    NewsletterIssue,
    NewsletterPaper,
    NewsletterResource,
    NewsletterSource,
    ResearchPaper,
    Source,
)
from app.schemas.content import (
    AIConceptCreateRequest,
    AIConceptResponse,
    AIResourceCreateRequest,
    AIResourceResponse,
    ResearchPaperCreateRequest,
    ResearchPaperResponse,
    SourceCreateRequest,
    SourceResponse,
)
from app.core.embeddings import generate_embedding


router = APIRouter(
    prefix="/content",
    tags=["Newsletter Content"],
)


# =========================================================
# AI CONCEPTS
# =========================================================

@router.post(
    "/concepts",
    response_model=AIConceptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_concept(
    concept_data: AIConceptCreateRequest,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(AIConcept)
        .filter(
            (AIConcept.name == concept_data.name)
            | (AIConcept.slug == concept_data.slug)
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An AI concept with this name or slug already exists",
        )

    concept = AIConcept(
        name=concept_data.name,
        slug=concept_data.slug,
        description=concept_data.description,
    )

    db.add(concept)
    db.commit()
    db.refresh(concept)

    return concept


@router.get(
    "/concepts",
    response_model=list[AIConceptResponse],
)
def get_concepts(
    db: Session = Depends(get_db),
):
    return db.query(AIConcept).order_by(AIConcept.name.asc()).all()


# =========================================================
# RESEARCH PAPERS
# =========================================================

@router.post(
    "/papers",
    response_model=ResearchPaperResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_paper(
    paper_data: ResearchPaperCreateRequest,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(ResearchPaper)
        .filter(ResearchPaper.url == paper_data.url)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A research paper with this URL already exists",
        )

    paper = ResearchPaper(
        title=paper_data.title,
        authors=paper_data.authors,
        url=paper_data.url,
        abstract=paper_data.abstract,
        published_at=paper_data.published_at,
    )

    db.add(paper)
    db.commit()
    db.refresh(paper)

    return paper


@router.get(
    "/papers",
    response_model=list[ResearchPaperResponse],
)
def get_papers(
    db: Session = Depends(get_db),
):
    return (
        db.query(ResearchPaper)
        .order_by(ResearchPaper.published_at.desc())
        .all()
    )


# =========================================================
# AI RESOURCES
# =========================================================

@router.post(
    "/resources",
    response_model=AIResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource(
    resource_data: AIResourceCreateRequest,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(AIResource)
        .filter(AIResource.url == resource_data.url)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An AI resource with this URL already exists",
        )

    resource = AIResource(
        name=resource_data.name,
        resource_type=resource_data.resource_type,
        url=resource_data.url,
        description=resource_data.description,
    )

    db.add(resource)
    db.commit()
    db.refresh(resource)

    return resource


@router.get(
    "/resources",
    response_model=list[AIResourceResponse],
)
def get_resources(
    db: Session = Depends(get_db),
):
    return (
        db.query(AIResource)
        .order_by(AIResource.created_at.desc())
        .all()
    )


# =========================================================
# SOURCES
# =========================================================

@router.post(
    "/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    source_data: SourceCreateRequest,
    db: Session = Depends(get_db),
):
    # --------------------------------------------------
    # 1. Exact duplicate check
    # --------------------------------------------------

    existing = (
        db.query(Source)
        .filter(Source.url == source_data.url)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A source with this URL already exists",
        )

    # --------------------------------------------------
    # 2. Generate embedding
    # --------------------------------------------------

    embedding = generate_embedding(source_data.raw_content)

    # --------------------------------------------------
    # 3. Semantic duplicate check
    # --------------------------------------------------

    similarity_limit = 0.20

    semantic_match = (
        db.query(
            Source,
            Source.embedding.cosine_distance(embedding).label("distance"),
        )
        .filter(Source.embedding.is_not(None))
        .order_by(
            Source.embedding.cosine_distance(embedding)
        )
        .first()
    )

    if semantic_match:
        existing_source, distance = semantic_match

        if distance <= similarity_limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "This source appears semantically similar to previously stored content",
                    "existing_source_id": existing_source.id,
                    "existing_source_title": existing_source.title,
                    "similarity_distance": float(distance),
                },
            )

    # --------------------------------------------------
    # 4. Save source
    # --------------------------------------------------

    source = Source(
        url=source_data.url,
        source_name=source_data.source_name,
        title=source_data.title,
        raw_content=source_data.raw_content,
        embedding=embedding,
        published_at=source_data.published_at,
    )

    db.add(source)
    db.commit()
    db.refresh(source)

    return source


@router.get(
    "/sources",
    response_model=list[SourceResponse],
)
def get_sources(
    db: Session = Depends(get_db),
):
    return (
        db.query(Source)
        .order_by(Source.retrieved_at.desc())
        .all()
    )


# =========================================================
# LINK CONCEPT TO NEWSLETTER
# =========================================================

@router.post(
    "/newsletters/{newsletter_id}/concepts/{concept_id}",
)
def attach_concept(
    newsletter_id: int,
    concept_id: int,
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

    concept = (
        db.query(AIConcept)
        .filter(AIConcept.id == concept_id)
        .first()
    )

    if not concept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI concept not found",
        )

    already_used = (
        db.query(NewsletterConcept)
        .join(NewsletterIssue)
        .filter(
            NewsletterConcept.concept_id == concept_id,
            NewsletterIssue.status == "published",
        )
        .first()
    )

    if already_used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This AI concept has already appeared in a published newsletter",
        )

    existing_link = (
        db.query(NewsletterConcept)
        .filter(
            NewsletterConcept.newsletter_issue_id == newsletter_id,
            NewsletterConcept.concept_id == concept_id,
        )
        .first()
    )

    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This concept is already attached to this newsletter",
        )

    link = NewsletterConcept(
        newsletter_issue_id=newsletter_id,
        concept_id=concept_id,
    )

    db.add(link)
    db.commit()

    return {
        "message": "Concept attached successfully",
        "newsletter_id": newsletter_id,
        "concept_id": concept_id,
    }


# =========================================================
# LINK PAPER TO NEWSLETTER
# =========================================================

@router.post(
    "/newsletters/{newsletter_id}/papers/{paper_id}",
)
def attach_paper(
    newsletter_id: int,
    paper_id: int,
    is_paper_of_week: bool = False,
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

    paper = (
        db.query(ResearchPaper)
        .filter(ResearchPaper.id == paper_id)
        .first()
    )

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research paper not found",
        )

    already_used = (
        db.query(NewsletterPaper)
        .join(NewsletterIssue)
        .filter(
            NewsletterPaper.paper_id == paper_id,
            NewsletterIssue.status == "published",
        )
        .first()
    )

    if already_used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This research paper has already appeared in a published newsletter",
        )

    existing_link = (
        db.query(NewsletterPaper)
        .filter(
            NewsletterPaper.newsletter_issue_id == newsletter_id,
            NewsletterPaper.paper_id == paper_id,
        )
        .first()
    )

    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This paper is already attached to this newsletter",
        )

    if is_paper_of_week:
        existing_paper_of_week = (
            db.query(NewsletterPaper)
            .filter(
                NewsletterPaper.newsletter_issue_id == newsletter_id,
                NewsletterPaper.is_paper_of_week.is_(True),
            )
            .first()
        )

        if existing_paper_of_week:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This newsletter already has a Paper of the Week",
            )

    link = NewsletterPaper(
        newsletter_issue_id=newsletter_id,
        paper_id=paper_id,
        is_paper_of_week=is_paper_of_week,
    )

    db.add(link)
    db.commit()

    return {
        "message": "Research paper attached successfully",
        "newsletter_id": newsletter_id,
        "paper_id": paper_id,
        "is_paper_of_week": is_paper_of_week,
    }


# =========================================================
# LINK RESOURCE TO NEWSLETTER
# =========================================================

@router.post(
    "/newsletters/{newsletter_id}/resources/{resource_id}",
)
def attach_resource(
    newsletter_id: int,
    resource_id: int,
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

    resource = (
        db.query(AIResource)
        .filter(AIResource.id == resource_id)
        .first()
    )

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI resource not found",
        )

    already_used = (
        db.query(NewsletterResource)
        .join(NewsletterIssue)
        .filter(
            NewsletterResource.resource_id == resource_id,
            NewsletterIssue.status == "published",
        )
        .first()
    )

    if already_used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This AI resource has already appeared in a published newsletter",
        )

    existing_link = (
        db.query(NewsletterResource)
        .filter(
            NewsletterResource.newsletter_issue_id == newsletter_id,
            NewsletterResource.resource_id == resource_id,
        )
        .first()
    )

    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This resource is already attached to this newsletter",
        )

    link = NewsletterResource(
        newsletter_issue_id=newsletter_id,
        resource_id=resource_id,
    )

    db.add(link)
    db.commit()

    return {
        "message": "AI resource attached successfully",
        "newsletter_id": newsletter_id,
        "resource_id": resource_id,
    }


# =========================================================
# LINK SOURCE TO NEWSLETTER
# =========================================================

@router.post(
    "/newsletters/{newsletter_id}/sources/{source_id}",
)
def attach_source(
    newsletter_id: int,
    source_id: int,
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

    source = (
        db.query(Source)
        .filter(Source.id == source_id)
        .first()
    )

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    existing_link = (
        db.query(NewsletterSource)
        .filter(
            NewsletterSource.newsletter_issue_id == newsletter_id,
            NewsletterSource.source_id == source_id,
        )
        .first()
    )

    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This source is already attached to this newsletter",
        )

    link = NewsletterSource(
        newsletter_issue_id=newsletter_id,
        source_id=source_id,
    )

    db.add(link)
    db.commit()

    return {
        "message": "Source attached successfully",
        "newsletter_id": newsletter_id,
        "source_id": source_id,
    }