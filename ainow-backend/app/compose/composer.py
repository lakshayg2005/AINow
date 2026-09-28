"""
Compose one newsletter issue from the week's stories.

    select stories per section
        -> retrieve grounded context per story (RAG)
        -> write each section (free LLM, cited)
        -> verify numbers against the context
        -> editorial pass (headline, intro, trends, concept, take)
        -> renumber sources to the ones actually cited
        -> check images, then review the draft for the editor
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.compose.context import SourceRegistry, StoryContext, build_story_context
from app.compose.images import vet_images
from app.compose.review import review_issue
from app.compose.selection import Candidate, build_candidates, select_sections
from app.compose.verify import strip_unsupported
from app.compose.writer import (
    editor_prompt,
    write_deep_dive,
    write_editorial,
    write_quick_news,
    write_research,
    write_resources,
)
from app.db.models import CoveredStory, RawItem
from app.ingest.utils import utcnow
from app.schemas.issue import IssueContent, IssueStats


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
# Compose
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


async def compose_issue(
    db: Session,
    window_days: int = 7,
) -> IssueContent:
    now = utcnow()

    candidates = build_candidates(db, window_days=window_days)

    if not candidates:
        raise RuntimeError(
            "No eligible stories in the window. Run `python -m app.ingest` first."
        )

    selection = select_sections(candidates)
    registry = SourceRegistry()
    models: set[str] = set()

    print(
        f"[Compose] {len(candidates)} candidates -> "
        f"{len(selection.quick_news)} news, {len(selection.research)} research, "
        f"paper={'yes' if selection.paper_of_week else 'no'}, "
        f"deep dive={'yes' if selection.deep_dive else 'no'}, "
        f"{len(selection.resources)} resources"
    )

    # --------------------------------------------------------
    # Retrieve
    # --------------------------------------------------------

    def contexts(pool, need, max_chars=3500, max_sources=4) -> list[StoryContext]:
        return [
            build_story_context(db, c, registry, need, max_chars, max_sources)
            for c in pool
        ]

    news_ctx = contexts(
        selection.quick_news,
        "what was announced or happened, key facts, who is affected",
        max_chars=2800,
    )
    research_ctx = contexts(
        selection.research,
        "problem, method, main results and numbers",
        max_chars=2500,
        max_sources=2,
    )
    paper_ctx = contexts(
        [selection.paper_of_week] if selection.paper_of_week else [],
        "problem, method, main results and numbers",
        max_chars=3500,
        max_sources=3,
    )
    dive_ctx = contexts(
        [selection.deep_dive] if selection.deep_dive else [],
        "technical details, how it works, results, implications, open questions",
        max_chars=9000,
        max_sources=5,
    )
    resource_ctx = contexts(
        selection.resources,
        "what it does, key features, how to use it",
        max_chars=2000,
        max_sources=2,
    )

    # --------------------------------------------------------
    # Write (sequential: free tiers rate-limit bursts)
    # --------------------------------------------------------

    print("[Compose] Writing Quick News...")
    quick_news = await write_quick_news(news_ctx, models)

    print("[Compose] Writing Research...")
    research_cards = await write_research(research_ctx + paper_ctx, models)
    paper_of_week = research_cards.pop() if paper_ctx and research_cards else None

    print("[Compose] Writing Deep Dive...")
    deep_dive = await write_deep_dive(dive_ctx[0] if dive_ctx else None, models)

    print("[Compose] Writing Resources...")
    resources = await write_resources(resource_ctx, models)

    # --------------------------------------------------------
    # Verify numbers against each card's own context
    # --------------------------------------------------------

    context_text = {
        ctx.story.id: ctx.text
        for ctx in news_ctx + research_ctx + paper_ctx + dive_ctx + resource_ctx
    }

    removed = 0

    for card in quick_news:
        removed += _verify_fields(card, ("headline", "summary", "why_it_matters"), context_text[card.story_id])

    for card in research_cards + ([paper_of_week] if paper_of_week else []):
        removed += _verify_fields(
            card,
            ("problem", "core_idea", "key_result", "why_it_matters"),
            context_text[card.story_id],
        )

    if deep_dive:
        dive_context = context_text[deep_dive.story_id]
        removed += _verify_fields(deep_dive, ("introduction",), dive_context)

        for section in deep_dive.sections:
            removed += _verify_fields(section, ("body",), dive_context)

        deep_dive.sections = [s for s in deep_dive.sections if s.body]

    for card in resources:
        removed += _verify_fields(card, ("description", "why_useful"), context_text[card.story_id])

    # --------------------------------------------------------
    # Editorial pass
    # --------------------------------------------------------

    issue_lines = [
        f"[{card.story_id}] {card.headline} — {card.summary}" for card in quick_news
    ]
    issue_lines += [
        f"[{card.story_id}] (paper) {card.title} — {card.core_idea}"
        for card in research_cards + ([paper_of_week] if paper_of_week else [])
    ]

    if deep_dive:
        issue_lines.append(f"[{deep_dive.story_id}] (deep dive) {deep_dive.title} — {deep_dive.introduction}")

    issue_lines += [
        f"[{card.story_id}] (resource) {card.name} — {card.description}" for card in resources
    ]

    chosen_ids = {c.story.id for c in selection.chosen()}
    pool_lines = [
        _pool_line(c) for c in selection.pool if c.story.id not in chosen_ids
    ][:30]

    # Trends may cite pool stories; register their primary
    # source so the trend can link to it.
    story_refs: dict[int, list[int]] = {
        ctx.story.id: ctx.ref_ids
        for ctx in news_ctx + research_ctx + paper_ctx + dive_ctx + resource_ctx
    }

    for candidate in selection.pool[:40]:
        if candidate.story.id not in story_refs and candidate.items:
            story_refs[candidate.story.id] = [registry.ref(candidate.items[0]).id]

    editor_context = "\n".join(issue_lines + pool_lines)

    print("[Compose] Editorial pass...")
    editorial = await write_editorial(
        editor_prompt(issue_lines, pool_lines, _history_lines(db)),
        valid_story_ids=set(story_refs),
        story_refs=story_refs,
        models=models,
    )

    for trend in editorial["trends"]:
        removed += _verify_fields(trend, ("explanation", "evidence"), editor_context)

    intro, removed_intro = strip_unsupported(editorial["intro"], editor_context)

    # Editorial call failed: a plain but accurate intro beats none.
    if not intro and quick_news:
        highlights = [card.headline.rstrip(".") for card in quick_news[:3]]

        if deep_dive:
            highlights.insert(0, deep_dive.title.rstrip("."))

        intro = "This week: " + "; ".join(highlights[:3]) + "."
    our_take, removed_take = strip_unsupported(editorial["our_take"], editor_context)
    removed += removed_intro + removed_take

    # --------------------------------------------------------
    # Assemble
    # --------------------------------------------------------

    items_scanned = db.scalar(
        select(func.count()).select_from(RawItem).where(
            RawItem.fetched_at >= now - timedelta(days=window_days)
        )
    )

    content = IssueContent(
        title=f"AINow Weekly — {now:%B} {now.day}, {now.year}",
        headline=(
            editorial["headline"]
            or (deep_dive.title if deep_dive else "")
            or (quick_news[0].headline if quick_news else "")
        ),
        intro=intro,
        issue_date=now,
        quick_news=quick_news,
        research_spotlight=research_cards,
        paper_of_week=paper_of_week,
        deep_dive=deep_dive,
        trends=editorial["trends"],
        concept=editorial["concept"],
        resources=resources,
        our_take=our_take,
        stats=IssueStats(
            items_scanned=items_scanned or 0,
            stories_considered=len(candidates),
            window_days=window_days,
            models=sorted(models),
            numbers_removed=removed,
        ),
    )

    _renumber_sources(content, registry)
    content.stats.sources_used = len(content.sources)

    print("[Compose] Checking images...")
    content.stats.images_replaced = await vet_images(db, content)

    print("[Compose] Reviewing draft...")
    content.review = await review_issue(db, content)

    return content
