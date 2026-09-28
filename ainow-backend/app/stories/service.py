from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import RawItem, Story
from app.ingest.utils import utcnow
from app.stories.cluster import CLUSTER_WINDOW_DAYS, assign_items
from app.stories.novelty import NoveltyResult, classify_novelty
from app.stories.scoring import aggregate_story, score_story
from app.stories.triage import triage_stories


# Only the highest pre-scored stories are sent to the LLM.
DEFAULT_TRIAGE_LIMIT = 150


def _load_items(
    db: Session,
    story_ids: list[int],
) -> dict[int, list[RawItem]]:
    items_by_story: dict[int, list[RawItem]] = defaultdict(list)

    if not story_ids:
        return items_by_story

    for item in db.scalars(
        select(RawItem).where(RawItem.story_id.in_(story_ids))
    ):
        items_by_story[item.story_id].append(item)

    return items_by_story


async def update_stories(
    db: Session,
    window_days: int = CLUSTER_WINDOW_DAYS,
    triage: bool = True,
    use_llm: bool = True,
    triage_limit: int = DEFAULT_TRIAGE_LIMIT,
) -> dict:
    """
    Cluster new items, refresh story signals, triage the
    promising stories, and rescore.
    """

    cluster_stats = assign_items(db, window_days)

    print(
        f"[Stories] Clustered {cluster_stats.assigned} items: "
        f"{cluster_stats.new_stories} new stories, "
        f"{cluster_stats.joined_by_entity} joined by name, "
        f"{cluster_stats.joined_by_similarity} by similarity"
    )

    # --------------------------------------------------------
    # Refresh every recent story: member signals keep growing
    # (points, stars) even when no new item joins.
    # --------------------------------------------------------

    since = utcnow() - timedelta(days=window_days)

    stories = db.scalars(
        select(Story).where(
            or_(
                Story.last_seen_at >= since,
                Story.id.in_(list(cluster_stats.touched_story_ids)),
            )
        )
    ).all()

    items_by_story = _load_items(
        db,
        [story.id for story in stories],
    )

    for story in stories:
        aggregate_story(story, items_by_story.get(story.id, []))
        story.score = score_story(story)

    db.commit()

    # --------------------------------------------------------
    # Triage new or grown stories, best first
    # --------------------------------------------------------

    triage_stats = None

    if triage:
        ranked = sorted(stories, key=lambda story: story.score, reverse=True)

        # Rule-based triage is provisional: redo it whenever
        # an LLM is allowed.
        pending = [
            story
            for story in ranked[:triage_limit]
            if story.triaged_at is None
            or story.item_count > story.triaged_item_count
            or (use_llm and story.triage_method == "heuristic")
        ]

        if pending:
            print(f"[Stories] Triaging {len(pending)} stories...")

            triage_stats = await triage_stories(
                pending,
                items_by_story,
                use_llm=use_llm,
            )

            for story in pending:
                story.score = score_story(story)

            db.commit()

    return {
        "clustered": cluster_stats.assigned,
        "new_stories": cluster_stats.new_stories,
        "joined_by_entity": cluster_stats.joined_by_entity,
        "joined_by_similarity": cluster_stats.joined_by_similarity,
        "stories_in_window": len(stories),
        "triaged_llm": triage_stats.llm if triage_stats else 0,
        "triaged_heuristic": triage_stats.heuristic if triage_stats else 0,
        "triage_models": sorted(triage_stats.models) if triage_stats else [],
    }


def top_stories(
    db: Session,
    limit: int = 25,
    window_days: int = 7,
    include_repeats: bool = False,
) -> list[tuple[Story, NoveltyResult]]:
    """
    Highest-scoring recent stories with their novelty status.
    This is the candidate pool the composer will draw from.
    """

    since = utcnow() - timedelta(days=window_days)

    stories = db.scalars(
        select(Story)
        .where(Story.last_seen_at >= since)
        .order_by(Story.score.desc())
    ).all()

    results: list[tuple[Story, NoveltyResult]] = []

    for story in stories:
        novelty = classify_novelty(db, story)

        if novelty.eligible or include_repeats:
            results.append((story, novelty))

        if len(results) >= limit:
            break

    return results
