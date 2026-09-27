"""
Story aggregation and scoring.

A story's score blends four things:

    importance  - LLM triage (1-10): how much it matters to AI
    buzz        - community engagement (HN points, HF upvotes,
                  GitHub stars, HF likes)
    coverage    - how many independent sources reported it
    recency     - how recently it was last reported

Promotional items (customer case studies, ads) are halved.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from app.db.models import RawItem, Story
from app.ingest.utils import utcnow


IMPORTANCE_WEIGHT = 0.40
BUZZ_WEIGHT = 0.30
COVERAGE_WEIGHT = 0.20
RECENCY_WEIGHT = 0.10

# Signal values that count as "maximum buzz".
BUZZ_SATURATION = {
    "hn_points": 800.0,
    "hn_comments": 500.0,
    "hf_upvotes": 150.0,
    "stars": 3000.0,
    "likes": 1500.0,
}

# Untriaged stories get a neutral importance.
DEFAULT_IMPORTANCE = 4

RECENCY_HALF_LIFE_DAYS = 4.0

MAX_SIGNALS = (
    "hn_points",
    "hn_comments",
    "hf_upvotes",
    "hf_comments",
    "stars",
    "forks",
    "likes",
    "downloads",
    "trending_score",
)


# ============================================================
# Aggregation
# ============================================================

_IMAGE_PRIORITY = {
    "article": 0,
    "paper": 1,
    "model": 2,
    "space": 2,
    "repo": 3,
    "discussion": 4,
}


def _item_time(
    item: RawItem,
) -> datetime:
    return item.published_at or item.fetched_at


def _effective_likes(
    item: RawItem,
) -> float:
    signals = item.signals or {}
    likes = float(signals.get("likes") or 0)

    # A model with thousands of likes and no downloads is
    # almost always like-farming.
    if item.kind == "model" and not signals.get("downloads"):
        return likes * 0.1

    return likes


def aggregate_story(
    story: Story,
    items: list[RawItem],
) -> None:
    """
    Recompute a story's display fields and signals from its
    member items.
    """

    if not items:
        return

    now = utcnow()

    sources: set[str] = set()

    for item in items:
        sources.update(
            (item.signals or {}).get("seen_in") or [item.source_key]
        )

    signals: dict = {}

    for key in MAX_SIGNALS:
        values = [
            float((item.signals or {}).get(key) or 0)
            for item in items
        ]

        if key == "likes":
            values = [_effective_likes(item) for item in items]

        if any(values):
            signals[key] = max(values)

    signals["sources"] = sorted(sources)
    signals["kinds"] = sorted({item.kind for item in items})
    signals["tier1_count"] = sum(1 for item in items if item.trust_tier == 1)
    signals["velocity_48h"] = sum(
        1
        for item in items
        if _item_time(item) >= now - timedelta(hours=48)
    )

    # The lab's own announcement names a story best; otherwise
    # the most-discussed item, which is usually the headline
    # people recognise ("Claude Opus 5.5", not "... now
    # available on AWS").
    title_item = min(
        items,
        key=lambda item: (
            0 if (item.kind, item.category) == ("article", "company") else 1,
            -float((item.signals or {}).get("hn_points") or 0),
            -float((item.signals or {}).get("hf_upvotes") or 0),
            item.trust_tier,
            _item_time(item),
        ),
    )

    image_items = sorted(
        (item for item in items if item.image_url),
        key=lambda item: (
            _IMAGE_PRIORITY.get(item.kind, 5),
            item.trust_tier,
        ),
    )

    story.title = title_item.title[:1000]
    story.image_url = image_items[0].image_url if image_items else None
    story.item_count = len(items)
    story.source_count = len(sources)
    story.signals = signals
    story.first_seen_at = min(_item_time(item) for item in items)
    story.last_seen_at = max(_item_time(item) for item in items)


# ============================================================
# Scoring
# ============================================================

def buzz_score(
    signals: dict,
) -> float:
    parts = sorted(
        (
            math.log1p(float(signals.get(key) or 0))
            / math.log1p(saturation)
            for key, saturation in BUZZ_SATURATION.items()
        ),
        reverse=True,
    )

    # Strongest signal, plus a little for corroborating ones.
    return min(
        1.0,
        parts[0] + 0.15 * sum(parts[1:3]),
    )


def coverage_score(
    source_count: int,
    tier1_count: int,
) -> float:
    score = min(1.0, max(0, source_count - 1) / 3)

    if tier1_count:
        score += 0.2

    return min(1.0, score)


def recency_score(
    last_seen_at: datetime,
    now: datetime | None = None,
) -> float:
    now = now or utcnow()

    age_days = max(
        0.0,
        (now - last_seen_at).total_seconds() / 86400,
    )

    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


def score_story(
    story: Story,
    now: datetime | None = None,
) -> float:
    signals = story.signals or {}

    importance = (
        story.importance
        if story.importance is not None
        else DEFAULT_IMPORTANCE
    )

    score = 100 * (
        IMPORTANCE_WEIGHT * (importance - 1) / 9
        + BUZZ_WEIGHT * buzz_score(signals)
        + COVERAGE_WEIGHT * coverage_score(
            story.source_count,
            int(signals.get("tier1_count") or 0),
        )
        + RECENCY_WEIGHT * recency_score(story.last_seen_at, now)
    )

    if story.is_promotional:
        score *= 0.5

    return round(score, 2)
