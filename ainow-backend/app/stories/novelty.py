"""
Freshness memory: has this story already been told?

    new      - never covered; eligible
    update   - covered before, but new reporting has arrived
               since; eligible as an "Update:" item
    related  - a covered story is close; eligible, but the
               writer should be told what was already said
    repeat   - already covered with nothing new; skip
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.embeddings import generate_embeddings
from app.db.models import CoveredStory, NewsletterIssue, RawItem, Story
from app.ingest.utils import utcnow
from app.schemas.newsletter import NewsletterContent
from app.stories.entities import entity_keys


NOVELTY_MEMORY_DAYS = 120

REPEAT_DISTANCE = 0.15
ENTITY_MATCH_DISTANCE = 0.30
RELATED_DISTANCE = 0.30


NoveltyStatus = Literal["new", "update", "related", "repeat"]


@dataclass
class NoveltyResult:
    status: NoveltyStatus
    covered: CoveredStory | None = None
    distance: float | None = None
    new_item_count: int = 0

    @property
    def eligible(self) -> bool:
        return self.status != "repeat"


def _items_since(
    db: Session,
    story: Story,
    since,
) -> int:
    return len(
        db.scalars(
            select(RawItem.id).where(
                RawItem.story_id == story.id,
                RawItem.fetched_at > since,
            )
        ).all()
    )


def classify_novelty(
    db: Session,
    story: Story,
) -> NoveltyResult:
    # 1. This exact story was covered before.
    previous = db.scalar(
        select(CoveredStory)
        .where(CoveredStory.story_id == story.id)
        .order_by(CoveredStory.covered_at.desc())
    )

    if previous is not None:
        new_items = _items_since(db, story, previous.covered_at)

        return NoveltyResult(
            status="update" if new_items else "repeat",
            covered=previous,
            distance=0.0,
            new_item_count=new_items,
        )

    if story.centroid is None:
        return NoveltyResult(status="new")

    # 2. A semantically close story was covered before.
    since = utcnow() - timedelta(days=NOVELTY_MEMORY_DAYS)

    row = db.execute(
        select(
            CoveredStory,
            CoveredStory.embedding.cosine_distance(story.centroid).label("distance"),
        )
        .where(
            CoveredStory.embedding.is_not(None),
            CoveredStory.covered_at >= since,
        )
        .order_by("distance")
        .limit(1)
    ).first()

    if row is None:
        return NoveltyResult(status="new")

    covered, distance = row
    distance = float(distance)

    shared_entity = bool(
        set(story.entities or []) & set(covered.entities or [])
    )

    if distance <= REPEAT_DISTANCE or (
        shared_entity and distance <= ENTITY_MATCH_DISTANCE
    ):
        # Same event. Anything reported after we covered it?
        if story.last_seen_at > covered.covered_at:
            return NoveltyResult(
                status="update",
                covered=covered,
                distance=distance,
                new_item_count=_items_since(db, story, covered.covered_at),
            )

        return NoveltyResult(
            status="repeat",
            covered=covered,
            distance=distance,
        )

    if distance <= RELATED_DISTANCE:
        return NoveltyResult(
            status="related",
            covered=covered,
            distance=distance,
        )

    return NoveltyResult(status="new", distance=distance)


def mark_covered(
    db: Session,
    story: Story,
    section_type: str,
    headline: str,
    summary: str | None,
    newsletter_issue_id: int | None,
) -> CoveredStory:
    covered = CoveredStory(
        story_id=story.id,
        newsletter_issue_id=newsletter_issue_id,
        section_type=section_type,
        headline=headline[:1000],
        summary=summary,
        entities=sorted(set(story.entities or []) | entity_keys(headline)),
        embedding=story.centroid,
        covered_at=utcnow(),
    )

    story.status = "covered"
    db.add(covered)

    return covered


# ============================================================
# Seeding from issues written before this memory existed
# ============================================================

def _issue_entries(
    content: NewsletterContent,
) -> list[tuple[str, str, str]]:
    """(section_type, headline, summary) for every item."""

    entries = [
        ("quick_news", item.headline, item.summary)
        for item in content.quick_news
    ]

    entries += [
        ("research_spotlight", item.title, f"{item.core_idea} {item.key_result}")
        for item in content.research_spotlight
    ]

    if content.paper_of_week:
        paper = content.paper_of_week
        entries.append(
            ("paper_of_week", paper.title, f"{paper.core_idea} {paper.key_result}")
        )

    if content.deep_dive:
        entries.append(
            ("deep_dive", content.deep_dive.title, content.deep_dive.introduction)
        )

    entries += [
        ("ai_trends", item.title, item.explanation)
        for item in content.trends
    ]

    entries += [
        ("resources", item.name, item.description)
        for item in content.resources
    ]

    if content.concept:
        entries.append(
            ("ai_concept", content.concept.concept, content.concept.simple_explanation)
        )

    return entries


def seed_from_published_issues(
    db: Session,
) -> int:
    """
    Load headlines from already-published issues into
    covered_stories. Safe to re-run: issues that already have
    entries are skipped.
    """

    seeded_issue_ids = set(
        db.scalars(
            select(CoveredStory.newsletter_issue_id).where(
                CoveredStory.newsletter_issue_id.is_not(None)
            )
        ).all()
    )

    issues = db.scalars(
        select(NewsletterIssue).where(
            NewsletterIssue.status == "published",
            NewsletterIssue.raw_content.is_not(None),
        )
    ).all()

    created = 0

    for issue in issues:
        if issue.id in seeded_issue_ids:
            continue

        try:
            content = NewsletterContent.model_validate_json(issue.raw_content)
        except ValueError:
            continue

        entries = _issue_entries(content)

        if not entries:
            continue

        vectors = generate_embeddings(
            [f"{headline}\n\n{summary}" for _, headline, summary in entries]
        )

        for (section, headline, summary), vector in zip(entries, vectors):
            db.add(
                CoveredStory(
                    story_id=None,
                    newsletter_issue_id=issue.id,
                    section_type=section,
                    headline=headline[:1000],
                    summary=summary,
                    entities=sorted(entity_keys(headline)),
                    embedding=vector,
                    covered_at=issue.published_at or issue.created_at,
                )
            )
            created += 1

    db.commit()

    return created
