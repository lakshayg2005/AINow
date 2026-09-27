"""
Incremental clustering of raw_items into stories.

Each unassigned item joins a recent story when

    - it shares a strong versioned name with the story
      ("claude opus 5.5") and is loosely similar
      (STRONG_ENTITY_JOIN_DISTANCE), or
    - it shares a weak one ("gpt 6") and is reasonably
      similar (ENTITY_JOIN_DISTANCE), or
    - it is a text item (article/paper/discussion), the story
      is textual too, and it is very similar
      (TEXT_JOIN_DISTANCE).

Otherwise it starts a new story. Thresholds are cosine
distances on all-MiniLM-L6-v2 title+summary embeddings,
calibrated on real ingested data: same-event pairs sat at
0.04-0.30, while different events from the same company
(Meta Muse vs Meta Tamagotchi) sat at 0.19. A title-only HN
post and a full article about the same launch can sit at
0.4-0.5, which only the strong-name rule catches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import Session

from app.db.models import CoveredStory, RawItem, Story
from app.ingest.utils import utcnow
from app.stories.entities import entity_keys, is_strong_key


CLUSTER_WINDOW_DAYS = 14

TEXT_JOIN_DISTANCE = 0.18
ENTITY_JOIN_DISTANCE = 0.35
STRONG_ENTITY_JOIN_DISTANCE = 0.60

CANDIDATE_STORIES = 5

TEXT_KINDS = {
    "article",
    "paper",
    "discussion",
}


@dataclass
class ClusterStats:
    assigned: int = 0
    new_stories: int = 0
    joined_by_entity: int = 0
    joined_by_similarity: int = 0
    touched_story_ids: set[int] = field(default_factory=set)


def _normalize(
    vector: np.ndarray,
) -> list[float]:
    norm = np.linalg.norm(vector)

    if norm == 0:
        return vector.tolist()

    return (vector / norm).tolist()


def _is_textual(
    story_kinds: set[str],
) -> bool:
    return bool(story_kinds & TEXT_KINDS)


def reset_stories(
    db: Session,
) -> int:
    """
    Drop all stories and unassign every item, so clustering
    can be re-run after tuning. Refuses once any story has
    been covered by an issue, since that would break the
    freshness memory's links.
    """

    if db.scalar(
        select(func.count()).select_from(CoveredStory).where(
            CoveredStory.story_id.is_not(None)
        )
    ):
        raise RuntimeError(
            "Stories are referenced by covered_stories; refusing to reset."
        )

    db.execute(update(RawItem).values(story_id=None))
    deleted = db.execute(delete(Story)).rowcount
    db.commit()

    return deleted


def assign_items(
    db: Session,
    window_days: int = CLUSTER_WINDOW_DAYS,
) -> ClusterStats:
    now = utcnow()
    since = now - timedelta(days=window_days)

    items = db.scalars(
        select(RawItem)
        .where(
            RawItem.story_id.is_(None),
            RawItem.embedding.is_not(None),
            or_(
                RawItem.published_at >= since,
                RawItem.published_at.is_(None),
            ),
        )
        .order_by(
            func.coalesce(
                RawItem.published_at,
                RawItem.fetched_at,
            )
        )
    ).all()

    stats = ClusterStats()

    # Kinds per story, including stories created this run.
    story_kinds: dict[int, set[str]] = {}

    for item in items:
        keys = entity_keys(item.title)

        distance_col = Story.centroid.cosine_distance(item.embedding).label("distance")

        base = select(Story, distance_col).where(
            Story.centroid.is_not(None),
            Story.last_seen_at >= since,
        )

        # Nearest stories, plus any story sharing a name key
        # (which may not be among the nearest few).
        candidates = db.execute(
            base.order_by("distance").limit(CANDIDATE_STORIES)
        ).all()

        if keys:
            candidates += db.execute(
                base.where(
                    Story.entities.has_any(array(sorted(keys)))
                ).order_by("distance")
            ).all()

        candidates = sorted(
            {story.id: (story, distance) for story, distance in candidates}.values(),
            key=lambda pair: pair[1],
        )

        chosen: Story | None = None

        for story, distance in candidates:
            kinds = story_kinds.setdefault(
                story.id,
                set((story.signals or {}).get("kinds") or []),
            )

            shared = keys & set(story.entities or [])

            join_distance = (
                STRONG_ENTITY_JOIN_DISTANCE
                if any(is_strong_key(key) for key in shared)
                else ENTITY_JOIN_DISTANCE
            )

            if shared and distance <= join_distance:
                chosen = story
                stats.joined_by_entity += 1
                break

            if (
                item.kind in TEXT_KINDS
                and _is_textual(kinds)
                and distance <= TEXT_JOIN_DISTANCE
            ):
                chosen = story
                stats.joined_by_similarity += 1
                break

        item_time = item.published_at or item.fetched_at

        if chosen is None:
            chosen = Story(
                title=item.title[:1000],
                status="open",
                item_count=1,
                source_count=1,
                signals={},
                entities=sorted(keys),
                centroid=np.asarray(item.embedding).tolist(),
                first_seen_at=item_time,
                last_seen_at=item_time,
                image_url=item.image_url,
            )
            db.add(chosen)
            db.flush()

            story_kinds[chosen.id] = {item.kind}
            stats.new_stories += 1

        else:
            count = max(1, chosen.item_count)

            centroid = (
                np.asarray(chosen.centroid) * count
                + np.asarray(item.embedding)
            ) / (count + 1)

            chosen.centroid = _normalize(centroid)
            chosen.item_count = count + 1
            chosen.entities = sorted(set(chosen.entities or []) | keys)
            chosen.last_seen_at = max(chosen.last_seen_at, item_time)

            story_kinds[chosen.id].add(item.kind)

        item.story_id = chosen.id
        stats.assigned += 1
        stats.touched_story_ids.add(chosen.id)

        # Session has autoflush off; make this assignment
        # visible to the next item's candidate query.
        db.flush()

    db.commit()

    return stats
