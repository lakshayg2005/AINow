from app.core.embeddings import generate_embedding
from app.db.models import (
    NewsletterIssue,
    NewsletterPaper,
    NewsletterResource,
    ResearchPaper,
    Source,
)
from app.schemas.research import (
    ResearchCandidate,
    ResearchResult,
)


SEMANTIC_DUPLICATE_DISTANCE = 0.20


def check_source_freshness(
    candidate: ResearchCandidate,
    db,
) -> ResearchResult:

    # --------------------------------------------------
    # 1. Exact URL duplicate
    # --------------------------------------------------

    existing_source = (
        db.query(Source)
        .filter(Source.url == candidate.url)
        .first()
    )

    if existing_source:
        return ResearchResult(
            candidate=candidate,
            is_fresh=False,
            duplicate_reason="exact_url",
            existing_source_id=existing_source.id,
        )

    # --------------------------------------------------
    # 2. Generate embedding
    # --------------------------------------------------

    embedding = generate_embedding(
        candidate.raw_content
    )

    # --------------------------------------------------
    # 3. Semantic duplicate search
    # --------------------------------------------------

    semantic_match = (
        db.query(
            Source,
            Source.embedding.cosine_distance(
                embedding
            ).label("distance"),
        )
        .filter(
            Source.embedding.is_not(None)
        )
        .order_by(
            Source.embedding.cosine_distance(
                embedding
            )
        )
        .first()
    )

    if semantic_match:

        existing_source, distance = semantic_match

        distance = float(distance)

        if distance <= SEMANTIC_DUPLICATE_DISTANCE:
            return ResearchResult(
                candidate=candidate,
                is_fresh=False,
                duplicate_reason="semantic_similarity",
                existing_source_id=existing_source.id,
                semantic_distance=distance,
            )

    # --------------------------------------------------
    # 4. Fresh candidate
    # --------------------------------------------------

    return ResearchResult(
        candidate=candidate,
        is_fresh=True,
    )


def check_paper_freshness(
    candidate: ResearchCandidate,
    db,
) -> ResearchResult:

    existing_paper = (
        db.query(ResearchPaper)
        .filter(
            ResearchPaper.url == candidate.url
        )
        .first()
    )

    if existing_paper:
        return ResearchResult(
            candidate=candidate,
            is_fresh=False,
            duplicate_reason="exact_url",
            existing_source_id=existing_paper.id,
        )

    embedding = generate_embedding(
        candidate.raw_content
    )

    semantic_match = (
        db.query(
            ResearchPaper,
            ResearchPaper.embedding.cosine_distance(
                embedding
            ).label("distance"),
        )
        .filter(
            ResearchPaper.embedding.is_not(None)
        )
        .order_by(
            ResearchPaper.embedding.cosine_distance(
                embedding
            )
        )
        .first()
    )

    if semantic_match:

        existing_paper, distance = semantic_match

        distance = float(distance)

        if distance <= SEMANTIC_DUPLICATE_DISTANCE:
            return ResearchResult(
                candidate=candidate,
                is_fresh=False,
                duplicate_reason="semantic_similarity",
                existing_source_id=existing_paper.id,
                semantic_distance=distance,
            )

    return ResearchResult(
        candidate=candidate,
        is_fresh=True,
    )


def check_resource_freshness(
    resource_id: int,
    db,
) -> bool:

    existing = (
        db.query(NewsletterResource)
        .join(NewsletterIssue)
        .filter(
            NewsletterResource.resource_id == resource_id,
            NewsletterIssue.status == "published",
        )
        .first()
    )

    return existing is None