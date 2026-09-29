"""
Shared helpers for composing a newsletter issue: per-card
number verification, source renumbering, and the small text
helpers the LangGraph compose pipeline in `app.compose.graph`
builds its nodes from.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compose.context import SourceRegistry
from app.compose.selection import Candidate
from app.compose.verify import strip_unsupported
from app.db.models import CoveredStory
from app.schemas.issue import IssueContent


# ============================================================
# Verification
# ============================================================

def _verify_fields(
    card,
    fields: tuple[str, ...],
    context: str,
) -> int:
    removed = 0

    for name in fields:
        value = getattr(card, name, "")

        if value:
            cleaned, count = strip_unsupported(value, context)
            setattr(card, name, cleaned)
            removed += count

    return removed


# ============================================================
# Source renumbering
# ============================================================

def _renumber_sources(
    content: IssueContent,
    registry: SourceRegistry,
) -> None:
    """
    Keep only cited sources and number them 1..n in order of
    first citation, rewriting every card's refs.
    """

    cards = (
        list(content.quick_news)
        + list(content.research_spotlight)
        + ([content.paper_of_week] if content.paper_of_week else [])
        + ([content.deep_dive] if content.deep_dive else [])
        + list(content.trends)
        + list(content.resources)
    )

    order: list[int] = []

    for card in cards:
        for ref in card.refs:
            if ref not in order:
                order.append(ref)

    mapping = {old: new for new, old in enumerate(order, start=1)}
    by_id = {ref.id: ref for ref in registry.all()}

    for card in cards:
        card.refs = [mapping[ref] for ref in card.refs if ref in mapping]

    content.sources = [
        by_id[old].model_copy(update={"id": new})
        for old, new in mapping.items()
        if old in by_id
    ]


# ============================================================
# Text helpers
# ============================================================

def _pool_line(
    candidate: Candidate,
) -> str:
    story = candidate.story
    summary = f" — {story.summary}" if story.summary else ""
    return f"[{story.id}] ({story.category or 'other'}) {story.title}{summary}"


def _history_lines(
    db: Session,
    limit: int = 15,
) -> list[str]:
    rows = db.scalars(
        select(CoveredStory)
        .order_by(CoveredStory.covered_at.desc())
        .limit(limit)
    ).all()

    return [
        f"- {row.covered_at:%b %d}: {row.headline}"
        for row in rows
    ]
