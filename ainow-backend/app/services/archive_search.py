"""
Search the published archive by meaning and by name.

Every story a published issue covered is already stored in
covered_stories with its embedding (the freshness memory),
so the query is embedded and matched against those. A plain
text match runs alongside, so exact names ("GPT-6", "Qwen3")
always hit even when the embedding match is weak.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.embeddings import generate_embedding
from app.db.models import CoveredStory, NewsletterIssue


# Cosine distance above which a story is not a match.
MAX_DISTANCE = 0.6

MAX_MATCHES_PER_ISSUE = 4


def _like_pattern(
    query: str,
) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search_archive(
    db: Session,
    query: str,
    limit: int = 10,
) -> list[tuple[NewsletterIssue, list[CoveredStory]]]:
    """Published issues matching the query, best first, with their matching stories."""

    query = " ".join(query.split())[:200]

    if len(query) < 2:
        return []

    published = (
        select(CoveredStory, NewsletterIssue)
        .join(NewsletterIssue, NewsletterIssue.id == CoveredStory.newsletter_issue_id)
        .where(NewsletterIssue.status == "published")
    )

    # (score, covered, issue); text matches score 0, the best.
    best: dict[int, tuple[float, CoveredStory, NewsletterIssue]] = {}

    pattern = _like_pattern(query)

    for covered, issue in db.execute(
        published.where(
            or_(
                CoveredStory.headline.ilike(pattern, escape="\\"),
                CoveredStory.summary.ilike(pattern, escape="\\"),
            )
        ).limit(50)
    ):
        best[covered.id] = (0.0, covered, issue)

    distance = CoveredStory.embedding.cosine_distance(generate_embedding(query)).label("distance")

    for covered, issue, value in db.execute(
        published.add_columns(distance)
        .where(CoveredStory.embedding.is_not(None))
        .order_by(distance)
        .limit(40)
    ):
        if value > MAX_DISTANCE:
            break

        best.setdefault(covered.id, (float(value), covered, issue))

    grouped: dict[int, list[tuple[float, CoveredStory]]] = {}
    issues: dict[int, NewsletterIssue] = {}

    for score, covered, issue in best.values():
        grouped.setdefault(issue.id, []).append((score, covered))
        issues[issue.id] = issue

    def issue_date(issue: NewsletterIssue) -> float:
        return (issue.published_at or issue.created_at).timestamp()

    ranked = sorted(
        grouped,
        key=lambda issue_id: (
            min(score for score, _ in grouped[issue_id]),
            -issue_date(issues[issue_id]),
        ),
    )

    return [
        (
            issues[issue_id],
            [covered for _, covered in sorted(grouped[issue_id], key=lambda pair: pair[0])][
                :MAX_MATCHES_PER_ISSUE
            ],
        )
        for issue_id in ranked[:limit]
    ]
